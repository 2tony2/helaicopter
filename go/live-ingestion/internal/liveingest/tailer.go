package liveingest

import (
	"bufio"
	"context"
	"fmt"
	"io"
	"log/slog"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"syscall"
	"time"
)

type FileProcessor struct {
	cfg         Config
	logger      *slog.Logger
	checkpoints *CheckpointStore
	queue       chan<- ProcessedLine
	pathLocks   sync.Map
}

func NewFileProcessor(cfg Config, logger *slog.Logger, checkpoints *CheckpointStore, queue chan<- ProcessedLine) *FileProcessor {
	return &FileProcessor{
		cfg:         cfg,
		logger:      logger,
		checkpoints: checkpoints,
		queue:       queue,
	}
}

func (p *FileProcessor) ProcessPath(ctx context.Context, path string) error {
	lockValue, _ := p.pathLocks.LoadOrStore(path, &sync.Mutex{})
	lock := lockValue.(*sync.Mutex)
	lock.Lock()
	defer lock.Unlock()

	source, ok := discoverSource(path, p.cfg.ClaudeRoot, p.cfg.CodexRoot)
	if !ok {
		return nil
	}

	file, err := os.Open(path)
	if err != nil {
		if os.IsNotExist(err) {
			return nil
		}
		return fmt.Errorf("open %s: %w", path, err)
	}
	defer file.Close()

	info, err := file.Stat()
	if err != nil {
		return fmt.Errorf("stat %s: %w", path, err)
	}
	if info.IsDir() {
		return nil
	}

	fileID := statFileID(info)
	checkpoint, found := p.checkpoints.Get(path)
	if !found {
		checkpoint = FileCheckpoint{
			Path:     path,
			Provider: source.Provider,
			FileID:   fileID,
		}
		if p.cfg.StartPosition == "end" {
			checkpoint.Offset = info.Size()
		}
	}
	if checkpoint.FileID != "" && checkpoint.FileID != fileID {
		checkpoint = FileCheckpoint{
			Path:     path,
			Provider: source.Provider,
			FileID:   fileID,
		}
		if p.cfg.StartPosition == "end" {
			checkpoint.Offset = info.Size()
		}
	}
	if checkpoint.Offset > info.Size() {
		checkpoint.Offset = 0
		checkpoint.LineNumber = 0
		checkpoint.State = ParserState{}
	}

	if _, err := file.Seek(checkpoint.Offset, io.SeekStart); err != nil {
		return fmt.Errorf("seek %s: %w", path, err)
	}

	reader := bufio.NewReader(file)
	offset := checkpoint.Offset
	lineNumber := checkpoint.LineNumber
	state := checkpoint.State
	source.ProjectPath = firstNonEmpty(state.Claude.ProjectPath, state.Codex.ProjectPath, source.ProjectPath)
	source.ProjectName = firstNonEmpty(state.Claude.ProjectName, state.Codex.ProjectName, source.ProjectName)
	source.ConversationID = conversationID(source.Provider, source.SessionID)

	for {
		bytes, err := reader.ReadBytes('\n')
		if err != nil && err != io.EOF {
			return fmt.Errorf("read %s: %w", path, err)
		}
		if len(bytes) == 0 {
			return nil
		}
		if err == io.EOF && bytes[len(bytes)-1] != '\n' {
			return nil
		}

		offset += int64(len(bytes))
		lineNumber++
		line := strings.TrimRight(string(bytes), "\r\n")
		nextState, envelope := normalizeLine(source, lineNumber, line, state)
		state = nextState

		item := ProcessedLine{
			Source: source,
			Checkpoint: FileCheckpoint{
				Path:       path,
				Provider:   source.Provider,
				FileID:     fileID,
				Offset:     offset,
				LineNumber: lineNumber,
				State:      state,
			},
			Envelope: envelope,
		}
		p.checkpoints.MarkCurrent(item.Checkpoint)

		select {
		case <-ctx.Done():
			return ctx.Err()
		case p.queue <- item:
		}

		if err == io.EOF {
			return nil
		}
	}
}

func statFileID(info os.FileInfo) string {
	stat, ok := info.Sys().(*syscall.Stat_t)
	if !ok {
		return fmt.Sprintf("%s:%d", filepath.Base(info.Name()), info.ModTime().UnixNano())
	}
	return fmt.Sprintf("%d:%d", stat.Dev, stat.Ino)
}

func isSessionFile(path string, claudeRoot, codexRoot string) bool {
	if !strings.HasSuffix(strings.ToLower(path), ".jsonl") {
		return false
	}
	if _, ok := discoverSource(path, claudeRoot, codexRoot); ok {
		return true
	}
	return false
}

func scanSessionFiles(root string, fn func(path string)) {
	_ = filepath.WalkDir(root, func(path string, entry os.DirEntry, err error) error {
		if err != nil {
			return nil
		}
		if entry.IsDir() {
			return nil
		}
		fn(path)
		return nil
	})
}

func sleepContext(ctx context.Context, delay time.Duration) error {
	timer := time.NewTimer(delay)
	defer timer.Stop()
	select {
	case <-ctx.Done():
		return ctx.Err()
	case <-timer.C:
		return nil
	}
}
