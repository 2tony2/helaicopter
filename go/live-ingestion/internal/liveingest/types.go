package liveingest

import "time"

type SourceFile struct {
	Provider       string
	Path           string
	SessionID      string
	ProjectPath    string
	ProjectName    string
	ConversationID string
}

type ProcessedLine struct {
	Source     SourceFile
	Checkpoint FileCheckpoint
	Envelope   *NormalizedEnvelope
}

type FileCheckpoint struct {
	Path       string      `json:"path"`
	Provider   string      `json:"provider"`
	FileID     string      `json:"fileId"`
	Offset     int64       `json:"offset"`
	LineNumber uint64      `json:"lineNumber"`
	State      ParserState `json:"state"`
}

type ParserState struct {
	Claude ClaudeState `json:"claude,omitempty"`
	Codex  CodexState  `json:"codex,omitempty"`
}

type NormalizedEnvelope struct {
	Provider          string               `json:"provider"`
	ConversationID    string               `json:"conversationId"`
	SessionID         string               `json:"sessionId"`
	SourcePath        string               `json:"sourcePath"`
	SourceLine        uint64               `json:"sourceLine"`
	EventID           string               `json:"eventId"`
	EventType         string               `json:"eventType"`
	EventTime         string               `json:"eventTime"`
	ProjectPath       string               `json:"projectPath"`
	ProjectName       string               `json:"projectName"`
	ConversationEvent ConversationEventRow `json:"conversationEvent"`
	MessageEvents     []MessageEventRow    `json:"messageEvents,omitempty"`
	ToolEvents        []ToolEventRow       `json:"toolEvents,omitempty"`
	UsageEvents       []UsageEventRow      `json:"usageEvents,omitempty"`
	Payload           map[string]any       `json:"payload,omitempty"`
}

type ConversationEventRow struct {
	Provider                string `json:"provider"`
	ConversationID          string `json:"conversation_id"`
	SessionID               string `json:"session_id"`
	EventID                 string `json:"event_id"`
	EventTime               string `json:"event_time"`
	Ordinal                 uint32 `json:"ordinal"`
	EventType               string `json:"event_type"`
	ProjectPath             string `json:"project_path"`
	ProjectName             string `json:"project_name"`
	GitBranch               string `json:"git_branch"`
	Model                   string `json:"model"`
	MessageID               string `json:"message_id"`
	MessageIndex            uint32 `json:"message_index"`
	MessageRole             string `json:"message_role"`
	ToolCallID              string `json:"tool_call_id"`
	ToolName                string `json:"tool_name"`
	ToolStatus              string `json:"tool_status"`
	SubagentID              string `json:"subagent_id"`
	SubagentType            string `json:"subagent_type"`
	UsageInputTokens        int64  `json:"usage_input_tokens"`
	UsageOutputTokens       int64  `json:"usage_output_tokens"`
	UsageCacheWriteTokens   int64  `json:"usage_cache_write_tokens"`
	UsageCacheReadTokens    int64  `json:"usage_cache_read_tokens"`
	UsageReasoningTokens    int64  `json:"usage_reasoning_tokens"`
	EstimatedInputCost      string `json:"estimated_input_cost"`
	EstimatedOutputCost     string `json:"estimated_output_cost"`
	EstimatedCacheWriteCost string `json:"estimated_cache_write_cost"`
	EstimatedCacheReadCost  string `json:"estimated_cache_read_cost"`
	EstimatedTotalCost      string `json:"estimated_total_cost"`
	IsTerminalEvent         uint8  `json:"is_terminal_event"`
	PayloadJSON             string `json:"payload_json"`
}

type MessageEventRow struct {
	Provider           string `json:"provider"`
	ConversationID     string `json:"conversation_id"`
	SessionID          string `json:"session_id"`
	EventID            string `json:"event_id"`
	MessageID          string `json:"message_id"`
	MessageIndex       uint32 `json:"message_index"`
	MessageTime        string `json:"message_time"`
	Ordinal            uint32 `json:"ordinal"`
	ProjectPath        string `json:"project_path"`
	ProjectName        string `json:"project_name"`
	GitBranch          string `json:"git_branch"`
	Model              string `json:"model"`
	Role               string `json:"role"`
	AuthorName         string `json:"author_name"`
	MessageKind        string `json:"message_kind"`
	ContentText        string `json:"content_text"`
	ContentJSON        string `json:"content_json"`
	InputTokens        int64  `json:"input_tokens"`
	OutputTokens       int64  `json:"output_tokens"`
	CacheWriteTokens   int64  `json:"cache_write_tokens"`
	CacheReadTokens    int64  `json:"cache_read_tokens"`
	ReasoningTokens    int64  `json:"reasoning_tokens"`
	EstimatedTotalCost string `json:"estimated_total_cost"`
	HasToolCalls       uint8  `json:"has_tool_calls"`
	IsError            uint8  `json:"is_error"`
}

type ToolEventRow struct {
	Provider           string `json:"provider"`
	ConversationID     string `json:"conversation_id"`
	SessionID          string `json:"session_id"`
	EventID            string `json:"event_id"`
	ToolCallID         string `json:"tool_call_id"`
	ToolName           string `json:"tool_name"`
	StartedAt          string `json:"started_at"`
	FinishedAt         string `json:"finished_at"`
	DurationMS         uint64 `json:"duration_ms"`
	Ordinal            uint32 `json:"ordinal"`
	ProjectPath        string `json:"project_path"`
	ProjectName        string `json:"project_name"`
	GitBranch          string `json:"git_branch"`
	Model              string `json:"model"`
	ParentMessageID    string `json:"parent_message_id"`
	ParentMessageIndex uint32 `json:"parent_message_index"`
	ToolStatus         string `json:"tool_status"`
	SubagentID         string `json:"subagent_id"`
	SubagentType       string `json:"subagent_type"`
	InputPayloadJSON   string `json:"input_payload_json"`
	OutputPayloadJSON  string `json:"output_payload_json"`
	ErrorText          string `json:"error_text"`
	InputTokens        int64  `json:"input_tokens"`
	OutputTokens       int64  `json:"output_tokens"`
	CacheWriteTokens   int64  `json:"cache_write_tokens"`
	CacheReadTokens    int64  `json:"cache_read_tokens"`
	ReasoningTokens    int64  `json:"reasoning_tokens"`
	EstimatedTotalCost string `json:"estimated_total_cost"`
}

type UsageEventRow struct {
	Provider                string `json:"provider"`
	ConversationID          string `json:"conversation_id"`
	SessionID               string `json:"session_id"`
	EventID                 string `json:"event_id"`
	EventTime               string `json:"event_time"`
	Ordinal                 uint32 `json:"ordinal"`
	ProjectPath             string `json:"project_path"`
	ProjectName             string `json:"project_name"`
	GitBranch               string `json:"git_branch"`
	Model                   string `json:"model"`
	MessageID               string `json:"message_id"`
	MessageIndex            uint32 `json:"message_index"`
	ToolCallID              string `json:"tool_call_id"`
	UsageSource             string `json:"usage_source"`
	InputTokens             int64  `json:"input_tokens"`
	OutputTokens            int64  `json:"output_tokens"`
	CacheWriteTokens        int64  `json:"cache_write_tokens"`
	CacheReadTokens         int64  `json:"cache_read_tokens"`
	ReasoningTokens         int64  `json:"reasoning_tokens"`
	EstimatedInputCost      string `json:"estimated_input_cost"`
	EstimatedOutputCost     string `json:"estimated_output_cost"`
	EstimatedCacheWriteCost string `json:"estimated_cache_write_cost"`
	EstimatedCacheReadCost  string `json:"estimated_cache_read_cost"`
	EstimatedTotalCost      string `json:"estimated_total_cost"`
}

type ClaudeState struct {
	ProjectPath  string                       `json:"projectPath,omitempty"`
	ProjectName  string                       `json:"projectName,omitempty"`
	GitBranch    string                       `json:"gitBranch,omitempty"`
	Model        string                       `json:"model,omitempty"`
	Speed        string                       `json:"speed,omitempty"`
	MessageIndex uint32                       `json:"messageIndex,omitempty"`
	PendingTools map[string]ClaudePendingTool `json:"pendingTools,omitempty"`
}

type ClaudePendingTool struct {
	ToolCallID         string         `json:"toolCallId"`
	ToolName           string         `json:"toolName"`
	Input              map[string]any `json:"input,omitempty"`
	StartedAt          string         `json:"startedAt"`
	Model              string         `json:"model,omitempty"`
	GitBranch          string         `json:"gitBranch,omitempty"`
	ParentMessageID    string         `json:"parentMessageId"`
	ParentMessageIndex uint32         `json:"parentMessageIndex"`
	SubagentType       string         `json:"subagentType,omitempty"`
}

type CodexState struct {
	ProjectPath       string              `json:"projectPath,omitempty"`
	ProjectName       string              `json:"projectName,omitempty"`
	Model             string              `json:"model,omitempty"`
	ReasoningEffort   string              `json:"reasoningEffort,omitempty"`
	MessageIndex      uint32              `json:"messageIndex,omitempty"`
	PreviousUsage     CodexUsageTotals    `json:"previousUsage,omitempty"`
	PendingBlocks     []CodexPendingBlock `json:"pendingBlocks,omitempty"`
	LastAssistantAt   string              `json:"lastAssistantAt,omitempty"`
	LastAssistantLine uint64              `json:"lastAssistantLine,omitempty"`
	PendingReasoning  int64               `json:"pendingReasoning,omitempty"`
}

type CodexUsageTotals struct {
	InputTokens           int64 `json:"inputTokens,omitempty"`
	CachedInputTokens     int64 `json:"cachedInputTokens,omitempty"`
	OutputTokens          int64 `json:"outputTokens,omitempty"`
	ReasoningOutputTokens int64 `json:"reasoningOutputTokens,omitempty"`
}

type CodexPendingBlock struct {
	Kind         string         `json:"kind"`
	Text         string         `json:"text,omitempty"`
	Thinking     string         `json:"thinking,omitempty"`
	ToolCallID   string         `json:"toolCallId,omitempty"`
	ToolName     string         `json:"toolName,omitempty"`
	Input        map[string]any `json:"input,omitempty"`
	Result       string         `json:"result,omitempty"`
	IsError      bool           `json:"isError,omitempty"`
	StartedAt    string         `json:"startedAt,omitempty"`
	SubagentID   string         `json:"subagentId,omitempty"`
	SubagentType string         `json:"subagentType,omitempty"`
}

type RuntimeStats struct {
	StartedAt            time.Time `json:"startedAt"`
	QueuedLines          int64     `json:"queuedLines"`
	PersistedLines       int64     `json:"persistedLines"`
	InsertedConversation int64     `json:"insertedConversationEvents"`
	InsertedMessages     int64     `json:"insertedMessageEvents"`
	InsertedTools        int64     `json:"insertedToolEvents"`
	InsertedUsage        int64     `json:"insertedUsageEvents"`
	RetryCount           int64     `json:"retryCount"`
	LastFlushAt          string    `json:"lastFlushAt,omitempty"`
	LastError            string    `json:"lastError,omitempty"`
}
