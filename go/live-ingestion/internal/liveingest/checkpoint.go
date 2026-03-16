package liveingest

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sync"
)

type CheckpointStore struct {
	path string
	mu   sync.RWMutex
	data map[string]FileCheckpoint
}

func NewCheckpointStore(path string) (*CheckpointStore, error) {
	store := &CheckpointStore{
		path: path,
		data: map[string]FileCheckpoint{},
	}

	bytes, err := os.ReadFile(path)
	if err != nil {
		if os.IsNotExist(err) {
			return store, nil
		}
		return nil, fmt.Errorf("read checkpoints: %w", err)
	}

	if len(bytes) == 0 {
		return store, nil
	}
	if err := json.Unmarshal(bytes, &store.data); err != nil {
		return nil, fmt.Errorf("decode checkpoints: %w", err)
	}
	return store, nil
}

func (s *CheckpointStore) Get(path string) (FileCheckpoint, bool) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	checkpoint, ok := s.data[path]
	return checkpoint, ok
}

func (s *CheckpointStore) MarkCurrent(checkpoint FileCheckpoint) {
	s.mu.Lock()
	defer s.mu.Unlock()
	existing, ok := s.data[checkpoint.Path]
	if !ok || checkpoint.LineNumber >= existing.LineNumber || checkpoint.Offset >= existing.Offset {
		s.data[checkpoint.Path] = checkpoint
	}
}

func (s *CheckpointStore) UpdateMany(checkpoints []FileCheckpoint) error {
	if len(checkpoints) == 0 {
		return nil
	}

	s.mu.Lock()
	defer s.mu.Unlock()

	for _, checkpoint := range checkpoints {
		existing, ok := s.data[checkpoint.Path]
		if !ok || checkpoint.LineNumber >= existing.LineNumber || checkpoint.Offset >= existing.Offset {
			s.data[checkpoint.Path] = checkpoint
		}
	}

	if err := os.MkdirAll(filepath.Dir(s.path), 0o755); err != nil {
		return fmt.Errorf("create checkpoint dir: %w", err)
	}

	bytes, err := json.MarshalIndent(s.data, "", "  ")
	if err != nil {
		return fmt.Errorf("encode checkpoints: %w", err)
	}

	tempPath := s.path + ".tmp"
	if err := os.WriteFile(tempPath, bytes, 0o644); err != nil {
		return fmt.Errorf("write temp checkpoints: %w", err)
	}
	if err := os.Rename(tempPath, s.path); err != nil {
		return fmt.Errorf("replace checkpoints: %w", err)
	}
	return nil
}
