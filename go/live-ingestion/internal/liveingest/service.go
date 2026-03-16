package liveingest

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"path/filepath"
	"sync"
	"sync/atomic"
	"time"

	"github.com/fsnotify/fsnotify"
)

type Service struct {
	cfg         Config
	logger      *slog.Logger
	client      *ClickHouseClient
	checkpoints *CheckpointStore
	hub         *EventHub
	processor   *FileProcessor
	queue       chan ProcessedLine
	stats       RuntimeStats
}

func NewService(cfg Config, logger *slog.Logger) (*Service, error) {
	checkpoints, err := NewCheckpointStore(cfg.CheckpointPath)
	if err != nil {
		return nil, err
	}

	queue := make(chan ProcessedLine, cfg.QueueCapacity)
	service := &Service{
		cfg:         cfg,
		logger:      logger,
		client:      NewClickHouseClient(cfg.ClickHouse),
		checkpoints: checkpoints,
		hub:         NewEventHub(),
		queue:       queue,
		stats: RuntimeStats{
			StartedAt: time.Now().UTC(),
		},
	}
	service.processor = NewFileProcessor(cfg, logger, checkpoints, queue)
	return service, nil
}

func (s *Service) Run(ctx context.Context) error {
	httpServer := &http.Server{
		Addr:    s.cfg.HTTPAddr,
		Handler: s.routes(),
	}

	groupCtx, cancel := context.WithCancel(ctx)
	defer cancel()

	errCh := make(chan error, 1)
	var wg sync.WaitGroup

	wg.Add(1)
	go func() {
		defer wg.Done()
		if err := s.runWriter(groupCtx); err != nil && !errors.Is(err, context.Canceled) {
			select {
			case errCh <- err:
			default:
			}
			cancel()
		}
	}()

	wg.Add(1)
	go func() {
		defer wg.Done()
		if err := s.runWatcher(groupCtx); err != nil && !errors.Is(err, context.Canceled) {
			select {
			case errCh <- err:
			default:
			}
			cancel()
		}
	}()

	wg.Add(1)
	go func() {
		defer wg.Done()
		s.logger.Info("live ingestion HTTP server listening", "addr", s.cfg.HTTPAddr)
		if err := httpServer.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			select {
			case errCh <- err:
			default:
			}
			cancel()
		}
	}()

	select {
	case <-ctx.Done():
	case err := <-errCh:
		if err != nil {
			_ = httpServer.Shutdown(context.Background())
			wg.Wait()
			return err
		}
	}

	cancel()
	shutdownCtx, shutdownCancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer shutdownCancel()
	_ = httpServer.Shutdown(shutdownCtx)
	wg.Wait()

	select {
	case err := <-errCh:
		return err
	default:
		return nil
	}
}

func (s *Service) runWatcher(ctx context.Context) error {
	watcher, err := fsnotify.NewWatcher()
	if err != nil {
		return fmt.Errorf("create file watcher: %w", err)
	}
	defer watcher.Close()

	enqueue := make(chan string, s.cfg.QueueCapacity)
	var enqueueMu sync.Mutex
	pending := map[string]struct{}{}
	queuePath := func(path string) {
		enqueueMu.Lock()
		if _, ok := pending[path]; ok {
			enqueueMu.Unlock()
			return
		}
		pending[path] = struct{}{}
		enqueueMu.Unlock()

		select {
		case <-ctx.Done():
		case enqueue <- path:
		}
	}
	popPath := func(path string) {
		enqueueMu.Lock()
		delete(pending, path)
		enqueueMu.Unlock()
	}

	if err := addWatchTree(watcher, filepath.Join(s.cfg.ClaudeRoot, "projects")); err != nil {
		s.logger.Warn("failed to add Claude watch tree", "error", err)
	}
	if err := addWatchTree(watcher, filepath.Join(s.cfg.CodexRoot, "sessions")); err != nil {
		s.logger.Warn("failed to add Codex watch tree", "error", err)
	}

	scanSessionFiles(filepath.Join(s.cfg.ClaudeRoot, "projects"), func(path string) {
		if isSessionFile(path, s.cfg.ClaudeRoot, s.cfg.CodexRoot) {
			queuePath(path)
		}
	})
	scanSessionFiles(filepath.Join(s.cfg.CodexRoot, "sessions"), func(path string) {
		if isSessionFile(path, s.cfg.ClaudeRoot, s.cfg.CodexRoot) {
			queuePath(path)
		}
	})

	var workerWG sync.WaitGroup
	for worker := 0; worker < 4; worker++ {
		workerWG.Add(1)
		go func() {
			defer workerWG.Done()
			for {
				select {
				case <-ctx.Done():
					return
				case path, ok := <-enqueue:
					if !ok {
						return
					}
					if err := s.processor.ProcessPath(ctx, path); err != nil && !errors.Is(err, context.Canceled) {
						s.logger.Error("failed to process file", "path", path, "error", err)
					}
					popPath(path)
				}
			}
		}()
	}
	defer func() {
		close(enqueue)
		workerWG.Wait()
	}()

	rescanTicker := time.NewTicker(s.cfg.RescanInterval)
	defer rescanTicker.Stop()

	for {
		select {
		case <-ctx.Done():
			return ctx.Err()
		case event := <-watcher.Events:
			if event.Name == "" {
				continue
			}
			if event.Op&fsnotify.Create != 0 {
				if info, err := os.Stat(event.Name); err == nil && info.IsDir() {
					_ = addWatchTree(watcher, event.Name)
				}
			}
			if event.Op&(fsnotify.Create|fsnotify.Write|fsnotify.Rename) != 0 && isSessionFile(event.Name, s.cfg.ClaudeRoot, s.cfg.CodexRoot) {
				queuePath(event.Name)
			}
		case err := <-watcher.Errors:
			if err != nil {
				s.logger.Warn("file watcher error", "error", err)
			}
		case <-rescanTicker.C:
			scanSessionFiles(filepath.Join(s.cfg.ClaudeRoot, "projects"), func(path string) {
				if isSessionFile(path, s.cfg.ClaudeRoot, s.cfg.CodexRoot) {
					queuePath(path)
				}
			})
			scanSessionFiles(filepath.Join(s.cfg.CodexRoot, "sessions"), func(path string) {
				if isSessionFile(path, s.cfg.ClaudeRoot, s.cfg.CodexRoot) {
					queuePath(path)
				}
			})
		}
	}
}

func addWatchTree(watcher *fsnotify.Watcher, root string) error {
	return filepath.WalkDir(root, func(path string, entry os.DirEntry, err error) error {
		if err != nil {
			return nil
		}
		if entry.IsDir() {
			return watcher.Add(path)
		}
		return nil
	})
}

func (s *Service) runWriter(ctx context.Context) error {
	ticker := time.NewTicker(s.cfg.FlushInterval)
	defer ticker.Stop()

	batch := make([]ProcessedLine, 0, s.cfg.BatchSize)
	flush := func() error {
		if len(batch) == 0 {
			return nil
		}

		attempt := 0
		for {
			attempt++
			if err := s.flushBatch(ctx, batch); err != nil {
				atomic.StoreInt64(&s.stats.RetryCount, atomic.LoadInt64(&s.stats.RetryCount)+1)
				s.stats.LastError = err.Error()
				if ctx.Err() != nil {
					return ctx.Err()
				}
				delay := retryDelay(attempt, s.cfg.MaxRetryDelay)
				s.logger.Warn("clickhouse flush failed; retrying", "error", err, "attempt", attempt, "delay", delay)
				if err := sleepContext(ctx, delay); err != nil {
					return err
				}
				continue
			}
			s.stats.LastError = ""
			s.stats.LastFlushAt = time.Now().UTC().Format(time.RFC3339Nano)
			batch = batch[:0]
			return nil
		}
	}

	for {
		select {
		case <-ctx.Done():
			for {
				select {
				case item := <-s.queue:
					batch = append(batch, item)
				default:
					if len(batch) > 0 {
						return flush()
					}
					return ctx.Err()
				}
			}
		case item, ok := <-s.queue:
			if !ok {
				return flush()
			}
			atomic.AddInt64(&s.stats.QueuedLines, 1)
			batch = append(batch, item)
			if len(batch) >= s.cfg.BatchSize {
				if err := flush(); err != nil {
					return err
				}
			}
		case <-ticker.C:
			if err := flush(); err != nil {
				return err
			}
		}
	}
}

func (s *Service) flushBatch(ctx context.Context, batch []ProcessedLine) error {
	conversationRows := make([]any, 0, len(batch))
	messageRows := make([]any, 0)
	toolRows := make([]any, 0)
	usageRows := make([]any, 0)
	checkpoints := make([]FileCheckpoint, 0, len(batch))
	envelopes := make([]NormalizedEnvelope, 0, len(batch))

	for _, item := range batch {
		checkpoints = append(checkpoints, item.Checkpoint)
		if item.Envelope == nil {
			continue
		}
		conversationRows = append(conversationRows, item.Envelope.ConversationEvent)
		for _, row := range item.Envelope.MessageEvents {
			messageRows = append(messageRows, row)
		}
		for _, row := range item.Envelope.ToolEvents {
			toolRows = append(toolRows, row)
		}
		for _, row := range item.Envelope.UsageEvents {
			usageRows = append(usageRows, row)
		}
		envelopes = append(envelopes, *item.Envelope)
	}

	if err := s.client.InsertRows(ctx, "conversation_events", conversationRows); err != nil {
		return err
	}
	if err := s.client.InsertRows(ctx, "message_events", messageRows); err != nil {
		return err
	}
	if err := s.client.InsertRows(ctx, "tool_events", toolRows); err != nil {
		return err
	}
	if err := s.client.InsertRows(ctx, "usage_events", usageRows); err != nil {
		return err
	}
	if err := s.checkpoints.UpdateMany(checkpoints); err != nil {
		return err
	}

	atomic.AddInt64(&s.stats.PersistedLines, int64(len(batch)))
	atomic.AddInt64(&s.stats.InsertedConversation, int64(len(conversationRows)))
	atomic.AddInt64(&s.stats.InsertedMessages, int64(len(messageRows)))
	atomic.AddInt64(&s.stats.InsertedTools, int64(len(toolRows)))
	atomic.AddInt64(&s.stats.InsertedUsage, int64(len(usageRows)))

	for _, envelope := range envelopes {
		s.hub.Broadcast(envelope)
	}
	return nil
}

func (s *Service) routes() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("/healthz", func(writer http.ResponseWriter, _ *http.Request) {
		writer.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(writer).Encode(map[string]any{
			"status":    "ok",
			"startedAt": s.stats.StartedAt.Format(time.RFC3339Nano),
		})
	})
	mux.HandleFunc("/stats", func(writer http.ResponseWriter, _ *http.Request) {
		writer.Header().Set("Content-Type", "application/json")
		stats := RuntimeStats{
			StartedAt:            s.stats.StartedAt,
			QueuedLines:          atomic.LoadInt64(&s.stats.QueuedLines),
			PersistedLines:       atomic.LoadInt64(&s.stats.PersistedLines),
			InsertedConversation: atomic.LoadInt64(&s.stats.InsertedConversation),
			InsertedMessages:     atomic.LoadInt64(&s.stats.InsertedMessages),
			InsertedTools:        atomic.LoadInt64(&s.stats.InsertedTools),
			InsertedUsage:        atomic.LoadInt64(&s.stats.InsertedUsage),
			RetryCount:           atomic.LoadInt64(&s.stats.RetryCount),
			LastFlushAt:          s.stats.LastFlushAt,
			LastError:            s.stats.LastError,
		}
		_ = json.NewEncoder(writer).Encode(stats)
	})
	mux.HandleFunc("/events", func(writer http.ResponseWriter, request *http.Request) {
		writer.Header().Set("Content-Type", "text/event-stream")
		writer.Header().Set("Cache-Control", "no-cache")
		writer.Header().Set("Connection", "keep-alive")

		flusher, ok := writer.(http.Flusher)
		if !ok {
			http.Error(writer, "streaming unsupported", http.StatusInternalServerError)
			return
		}

		subscriptionID, stream := s.hub.Subscribe()
		defer s.hub.Unsubscribe(subscriptionID)
		flusher.Flush()

		for {
			select {
			case <-request.Context().Done():
				return
			case envelope, ok := <-stream:
				if !ok {
					return
				}
				bytes, err := json.Marshal(envelope)
				if err != nil {
					continue
				}
				if _, err := writer.Write([]byte("event: envelope\ndata: " + string(bytes) + "\n\n")); err != nil {
					return
				}
				flusher.Flush()
			}
		}
	})
	return mux
}
