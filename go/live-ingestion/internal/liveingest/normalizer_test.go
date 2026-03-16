package liveingest

import (
	"testing"
)

func TestNormalizeClaudeAssistantAndToolResult(t *testing.T) {
	source := SourceFile{
		Provider:       "claude",
		Path:           "/tmp/claude/projects/-demo/session-1.jsonl",
		SessionID:      "session-1",
		ProjectPath:    "-demo",
		ProjectName:    "demo",
		ConversationID: "claude:session-1",
	}

	state := ParserState{}
	var envelope *NormalizedEnvelope
	state, envelope = normalizeLine(source, 1, `{"type":"assistant","uuid":"assistant-1","timestamp":1710000000000,"message":{"role":"assistant","model":"claude-3-7-sonnet","content":[{"type":"text","text":"hello"},{"type":"tool_use","id":"tool-1","name":"Task","input":{"subagent_type":"worker"}}],"usage":{"input_tokens":10,"output_tokens":5,"cache_creation_input_tokens":2,"cache_read_input_tokens":1}}}`, state)
	if envelope == nil {
		t.Fatal("expected Claude assistant envelope")
	}
	if len(envelope.MessageEvents) != 1 {
		t.Fatalf("expected 1 message row, got %d", len(envelope.MessageEvents))
	}
	if len(envelope.UsageEvents) != 1 {
		t.Fatalf("expected 1 usage row, got %d", len(envelope.UsageEvents))
	}
	if _, ok := state.Claude.PendingTools["tool-1"]; !ok {
		t.Fatal("expected pending tool to be tracked")
	}

	state, envelope = normalizeLine(source, 2, `{"type":"user","uuid":"user-1","timestamp":1710000001000,"message":{"role":"user","content":[{"type":"tool_result","tool_use_id":"tool-1","content":"ok","is_error":false},{"type":"text","text":"thanks"}]}}`, state)
	if envelope == nil {
		t.Fatal("expected Claude user envelope")
	}
	if len(envelope.ToolEvents) != 1 {
		t.Fatalf("expected 1 tool row, got %d", len(envelope.ToolEvents))
	}
	if len(envelope.MessageEvents) != 1 {
		t.Fatalf("expected 1 user message row, got %d", len(envelope.MessageEvents))
	}
	if envelope.ToolEvents[0].SubagentType != "worker" {
		t.Fatalf("expected worker subagent type, got %q", envelope.ToolEvents[0].SubagentType)
	}
}

func TestNormalizeCodexTokenCountFlushesPendingBlocks(t *testing.T) {
	source := SourceFile{
		Provider:       "codex",
		Path:           "/tmp/codex/sessions/2026/03/16/rollout-test-12345678-1234-1234-1234-123456789abc.jsonl",
		SessionID:      "12345678-1234-1234-1234-123456789abc",
		ProjectPath:    "codex:unknown",
		ProjectName:    "Unknown",
		ConversationID: "codex:12345678-1234-1234-1234-123456789abc",
	}

	state := ParserState{}
	state, _ = normalizeLine(source, 1, `{"timestamp":"2026-03-16T10:00:00Z","type":"session_meta","payload":{"id":"12345678-1234-1234-1234-123456789abc","cwd":"/Users/tony/Code/helaicopter"}}`, state)
	state, _ = normalizeLine(source, 2, `{"timestamp":"2026-03-16T10:00:01Z","type":"turn_context","payload":{"model":"gpt-5","reasoning_effort":"medium"}}`, state)
	state, _ = normalizeLine(source, 3, `{"timestamp":"2026-03-16T10:00:02Z","type":"response_item","payload":{"type":"message","role":"assistant","content":[{"type":"output_text","text":"working"}]}}`, state)
	state, _ = normalizeLine(source, 4, `{"timestamp":"2026-03-16T10:00:03Z","type":"response_item","payload":{"type":"function_call","name":"exec_command","arguments":"{\"cmd\":\"date\"}","call_id":"call-1"}}`, state)
	state, _ = normalizeLine(source, 5, `{"timestamp":"2026-03-16T10:00:04Z","type":"response_item","payload":{"type":"function_call_output","call_id":"call-1","output":"Process exited with code 0"}}`, state)
	state, envelope := normalizeLine(source, 6, `{"timestamp":"2026-03-16T10:00:05Z","type":"event_msg","payload":{"type":"token_count","info":{"total_token_usage":{"input_tokens":12,"cached_input_tokens":3,"output_tokens":8,"reasoning_output_tokens":2,"total_tokens":25},"last_token_usage":{"input_tokens":12,"cached_input_tokens":3,"output_tokens":8,"reasoning_output_tokens":2,"total_tokens":25},"model_context_window":128000}}}`, state)
	if envelope == nil {
		t.Fatal("expected token_count envelope")
	}
	if len(envelope.MessageEvents) != 1 {
		t.Fatalf("expected 1 assistant message row, got %d", len(envelope.MessageEvents))
	}
	if len(envelope.ToolEvents) != 1 {
		t.Fatalf("expected 1 tool row, got %d", len(envelope.ToolEvents))
	}
	if len(envelope.UsageEvents) != 1 {
		t.Fatalf("expected 1 usage row, got %d", len(envelope.UsageEvents))
	}
	if envelope.ToolEvents[0].ToolName != "Shell" {
		t.Fatalf("expected Shell tool, got %q", envelope.ToolEvents[0].ToolName)
	}
	if envelope.MessageEvents[0].ReasoningTokens != 2 {
		t.Fatalf("expected reasoning tokens to flush, got %d", envelope.MessageEvents[0].ReasoningTokens)
	}
}
