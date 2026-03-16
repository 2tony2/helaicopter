package liveingest

import "testing"

func TestEventHubReplaysEventsAfterLastSeenID(t *testing.T) {
	hub := NewEventHub(8)

	first := NormalizedEnvelope{EventID: "event-1", SessionID: "session-1"}
	second := NormalizedEnvelope{EventID: "event-2", SessionID: "session-1"}
	third := NormalizedEnvelope{EventID: "event-3", SessionID: "session-1"}

	hub.Broadcast(first)
	hub.Broadcast(second)
	hub.Broadcast(third)

	subscriptionID, replay, stream := hub.Subscribe("event-1")
	defer hub.Unsubscribe(subscriptionID)

	if len(replay) != 2 {
		t.Fatalf("expected 2 replay envelopes, got %d", len(replay))
	}
	if replay[0].EventID != "event-2" || replay[1].EventID != "event-3" {
		t.Fatalf("unexpected replay order: %#v", replay)
	}

	next := NormalizedEnvelope{EventID: "event-4", SessionID: "session-1"}
	hub.Broadcast(next)

	select {
	case envelope := <-stream:
		if envelope.EventID != "event-4" {
			t.Fatalf("expected live event-4, got %q", envelope.EventID)
		}
	default:
		t.Fatal("expected live envelope after subscribe")
	}
}

func TestEventHubFallsBackToBufferedReplayWhenCursorMissing(t *testing.T) {
	hub := NewEventHub(2)
	hub.Broadcast(NormalizedEnvelope{EventID: "event-1"})
	hub.Broadcast(NormalizedEnvelope{EventID: "event-2"})
	hub.Broadcast(NormalizedEnvelope{EventID: "event-3"})

	subscriptionID, replay, _ := hub.Subscribe("event-missing")
	defer hub.Unsubscribe(subscriptionID)

	if len(replay) != 2 {
		t.Fatalf("expected buffered replay size 2, got %d", len(replay))
	}
	if replay[0].EventID != "event-2" || replay[1].EventID != "event-3" {
		t.Fatalf("unexpected buffered replay: %#v", replay)
	}
}
