package liveingest

import (
	"sync"
)

type EventHub struct {
	mu             sync.RWMutex
	nextID         int
	replayCapacity int
	history        []NormalizedEnvelope
	streams        map[int]chan NormalizedEnvelope
}

func NewEventHub(replayCapacity int) *EventHub {
	return &EventHub{
		replayCapacity: replayCapacity,
		history:        make([]NormalizedEnvelope, 0, replayCapacity),
		streams:        map[int]chan NormalizedEnvelope{},
	}
}

func (h *EventHub) Subscribe(afterEventID string) (int, []NormalizedEnvelope, <-chan NormalizedEnvelope) {
	h.mu.Lock()
	defer h.mu.Unlock()
	h.nextID++
	id := h.nextID
	channel := make(chan NormalizedEnvelope, 128)
	h.streams[id] = channel
	return id, h.replayLocked(afterEventID), channel
}

func (h *EventHub) Unsubscribe(id int) {
	h.mu.Lock()
	defer h.mu.Unlock()
	channel, ok := h.streams[id]
	if !ok {
		return
	}
	delete(h.streams, id)
	close(channel)
}

func (h *EventHub) Broadcast(envelope NormalizedEnvelope) {
	h.mu.Lock()
	if h.replayCapacity > 0 {
		h.history = append(h.history, envelope)
		if len(h.history) > h.replayCapacity {
			h.history = append([]NormalizedEnvelope(nil), h.history[len(h.history)-h.replayCapacity:]...)
		}
	}
	streams := make([]chan NormalizedEnvelope, 0, len(h.streams))
	for _, channel := range h.streams {
		streams = append(streams, channel)
	}
	h.mu.Unlock()

	for _, channel := range streams {
		select {
		case channel <- envelope:
		default:
		}
	}
}

func (h *EventHub) replayLocked(afterEventID string) []NormalizedEnvelope {
	if len(h.history) == 0 {
		return nil
	}
	if afterEventID == "" {
		return nil
	}
	for index := len(h.history) - 1; index >= 0; index-- {
		if h.history[index].EventID != afterEventID {
			continue
		}
		replay := make([]NormalizedEnvelope, len(h.history[index+1:]))
		copy(replay, h.history[index+1:])
		return replay
	}

	replay := make([]NormalizedEnvelope, len(h.history))
	copy(replay, h.history)
	return replay
}

func (h *EventHub) HistorySize() int {
	h.mu.RLock()
	defer h.mu.RUnlock()
	return len(h.history)
}

func (h *EventHub) ReplayCapacity() int {
	h.mu.RLock()
	defer h.mu.RUnlock()
	return h.replayCapacity
}

func (h *EventHub) StreamCount() int {
	h.mu.RLock()
	defer h.mu.RUnlock()
	return len(h.streams)
}
