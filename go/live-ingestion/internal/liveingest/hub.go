package liveingest

import (
	"sync"
)

type EventHub struct {
	mu      sync.RWMutex
	nextID  int
	streams map[int]chan NormalizedEnvelope
}

func NewEventHub() *EventHub {
	return &EventHub{
		streams: map[int]chan NormalizedEnvelope{},
	}
}

func (h *EventHub) Subscribe() (int, <-chan NormalizedEnvelope) {
	h.mu.Lock()
	defer h.mu.Unlock()
	h.nextID++
	id := h.nextID
	channel := make(chan NormalizedEnvelope, 128)
	h.streams[id] = channel
	return id, channel
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
	h.mu.RLock()
	defer h.mu.RUnlock()
	for _, channel := range h.streams {
		select {
		case channel <- envelope:
		default:
		}
	}
}
