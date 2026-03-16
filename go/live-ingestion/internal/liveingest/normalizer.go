package liveingest

import (
	"encoding/json"
	"fmt"
	"regexp"
	"strconv"
	"strings"
	"time"
)

const toolResultMaxLength = 12000

var exitCodePattern = regexp.MustCompile(`Process exited with code (\d+)`)

func normalizeLine(source SourceFile, lineNumber uint64, rawLine string, state ParserState) (ParserState, *NormalizedEnvelope) {
	switch source.Provider {
	case "claude":
		return normalizeClaudeLine(source, lineNumber, rawLine, state)
	case "codex":
		return normalizeCodexLine(source, lineNumber, rawLine, state)
	default:
		return state, nil
	}
}

func normalizeClaudeLine(source SourceFile, lineNumber uint64, rawLine string, state ParserState) (ParserState, *NormalizedEnvelope) {
	if state.Claude.PendingTools == nil {
		state.Claude.PendingTools = map[string]ClaudePendingTool{}
	}
	if state.Claude.ProjectPath == "" {
		state.Claude.ProjectPath = source.ProjectPath
	}
	if state.Claude.ProjectName == "" {
		state.Claude.ProjectName = source.ProjectName
	}

	var payload map[string]any
	if err := json.Unmarshal([]byte(rawLine), &payload); err != nil {
		return state, nil
	}

	eventType := "claude." + stringValue(payload["type"])
	eventTime := parseClaudeTimestamp(payload["timestamp"])
	gitBranch := firstNonEmpty(stringValue(payload["gitBranch"]), state.Claude.GitBranch)
	if gitBranch != "" {
		state.Claude.GitBranch = gitBranch
	}

	if message, ok := payload["message"].(map[string]any); ok {
		if model := stringValue(message["model"]); model != "" {
			state.Claude.Model = model
		}
	}

	envelope := newEnvelope(source, lineNumber, eventType, eventTime, state.Claude.ProjectPath, state.Claude.ProjectName, payload)
	envelope.ConversationEvent.GitBranch = state.Claude.GitBranch
	envelope.ConversationEvent.Model = state.Claude.Model

	messagePayload, _ := payload["message"].(map[string]any)
	role := stringValue(messagePayload["role"])
	envelope.ConversationEvent.MessageRole = role

	switch stringValue(payload["type"]) {
	case "assistant":
		messageRows, usageRows, pendingMeta := normalizeClaudeAssistant(source, lineNumber, eventTime, messagePayload, &state.Claude)
		envelope.MessageEvents = messageRows
		envelope.UsageEvents = usageRows
		if len(messageRows) > 0 {
			envelope.ConversationEvent.MessageID = messageRows[0].MessageID
			envelope.ConversationEvent.MessageIndex = messageRows[0].MessageIndex
			envelope.ConversationEvent.MessageRole = messageRows[0].Role
		}
		if len(usageRows) > 0 {
			envelope.ConversationEvent.UsageInputTokens = usageRows[0].InputTokens
			envelope.ConversationEvent.UsageOutputTokens = usageRows[0].OutputTokens
			envelope.ConversationEvent.UsageCacheWriteTokens = usageRows[0].CacheWriteTokens
			envelope.ConversationEvent.UsageCacheReadTokens = usageRows[0].CacheReadTokens
			envelope.ConversationEvent.UsageReasoningTokens = usageRows[0].ReasoningTokens
		}
		if pendingMeta.ToolCallID != "" {
			envelope.ConversationEvent.ToolCallID = pendingMeta.ToolCallID
			envelope.ConversationEvent.ToolName = pendingMeta.ToolName
			envelope.ConversationEvent.SubagentType = pendingMeta.SubagentType
		}
	case "user":
		messageRows, toolRows := normalizeClaudeUser(source, lineNumber, eventTime, messagePayload, &state.Claude)
		envelope.MessageEvents = messageRows
		envelope.ToolEvents = toolRows
		if len(messageRows) > 0 {
			envelope.ConversationEvent.MessageID = messageRows[0].MessageID
			envelope.ConversationEvent.MessageIndex = messageRows[0].MessageIndex
			envelope.ConversationEvent.MessageRole = messageRows[0].Role
		}
		if len(toolRows) > 0 {
			envelope.ConversationEvent.ToolCallID = toolRows[0].ToolCallID
			envelope.ConversationEvent.ToolName = toolRows[0].ToolName
			envelope.ConversationEvent.ToolStatus = toolRows[0].ToolStatus
			envelope.ConversationEvent.SubagentType = toolRows[0].SubagentType
		}
	}

	return state, envelope
}

type pendingToolMeta struct {
	ToolCallID   string
	ToolName     string
	SubagentType string
}

func normalizeClaudeAssistant(source SourceFile, lineNumber uint64, eventTime time.Time, message map[string]any, state *ClaudeState) ([]MessageEventRow, []UsageEventRow, pendingToolMeta) {
	blocks := make([]map[string]any, 0)
	content, _ := message["content"].([]any)
	pendingMeta := pendingToolMeta{}
	hasToolCalls := false
	pendingToolIDs := make([]string, 0)

	for _, rawBlock := range content {
		block, ok := rawBlock.(map[string]any)
		if !ok {
			continue
		}
		blockType := stringValue(block["type"])
		switch blockType {
		case "text":
			blocks = append(blocks, map[string]any{
				"type": "text",
				"text": stringValue(block["text"]),
			})
		case "thinking":
			thinking := stringValue(block["thinking"])
			blocks = append(blocks, map[string]any{
				"type":      "thinking",
				"thinking":  thinking,
				"charCount": len(thinking),
			})
		case "tool_use":
			hasToolCalls = true
			toolCallID := stringValue(block["id"])
			toolName := stringValue(block["name"])
			inputMap := mapValue(block["input"])
			subagentType := ""
			if toolName == "Task" {
				subagentType = stringValue(inputMap["subagent_type"])
			}
			state.PendingTools[toolCallID] = ClaudePendingTool{
				ToolCallID:         toolCallID,
				ToolName:           toolName,
				Input:              inputMap,
				StartedAt:          utcTimestamp(eventTime),
				Model:              state.Model,
				GitBranch:          state.GitBranch,
				ParentMessageID:    "",
				ParentMessageIndex: state.MessageIndex,
				SubagentType:       subagentType,
			}
			pendingToolIDs = append(pendingToolIDs, toolCallID)
			if pendingMeta.ToolCallID == "" {
				pendingMeta = pendingToolMeta{
					ToolCallID:   toolCallID,
					ToolName:     toolName,
					SubagentType: subagentType,
				}
			}
			blocks = append(blocks, map[string]any{
				"type":      "tool_call",
				"toolUseId": toolCallID,
				"toolName":  toolName,
				"input":     inputMap,
			})
		}
	}

	messageID := stringValue(message["uuid"])
	if messageID == "" {
		messageID = fmt.Sprintf("%s:assistant:%d", source.ConversationID, lineNumber)
	}
	for _, toolCallID := range pendingToolIDs {
		pending := state.PendingTools[toolCallID]
		pending.ParentMessageID = messageID
		state.PendingTools[toolCallID] = pending
	}

	preview := buildMessagePreview(blocks)
	usage := mapValue(message["usage"])
	messageRow := MessageEventRow{
		Provider:           source.Provider,
		ConversationID:     source.ConversationID,
		SessionID:          source.SessionID,
		EventID:            makeBaseEventID(source, lineNumber) + ":message:0",
		MessageID:          messageID,
		MessageIndex:       state.MessageIndex,
		MessageTime:        utcTimestamp(eventTime),
		Ordinal:            state.MessageIndex,
		ProjectPath:        state.ProjectPath,
		ProjectName:        state.ProjectName,
		GitBranch:          state.GitBranch,
		Model:              firstNonEmpty(stringValue(message["model"]), state.Model),
		Role:               "assistant",
		AuthorName:         "",
		MessageKind:        "message",
		ContentText:        preview,
		ContentJSON:        mustJSON(blocks),
		InputTokens:        int64Value(usage["input_tokens"]),
		OutputTokens:       int64Value(usage["output_tokens"]),
		CacheWriteTokens:   int64Value(usage["cache_creation_input_tokens"]),
		CacheReadTokens:    int64Value(usage["cache_read_input_tokens"]),
		ReasoningTokens:    0,
		EstimatedTotalCost: zeroCost(),
		HasToolCalls:       boolToUInt8(hasToolCalls),
		IsError:            0,
	}
	state.MessageIndex++

	usageRows := []UsageEventRow{}
	if len(usage) > 0 {
		usageRows = append(usageRows, UsageEventRow{
			Provider:                source.Provider,
			ConversationID:          source.ConversationID,
			SessionID:               source.SessionID,
			EventID:                 makeBaseEventID(source, lineNumber) + ":usage:0",
			EventTime:               utcTimestamp(eventTime),
			Ordinal:                 messageRow.MessageIndex,
			ProjectPath:             state.ProjectPath,
			ProjectName:             state.ProjectName,
			GitBranch:               state.GitBranch,
			Model:                   messageRow.Model,
			MessageID:               messageID,
			MessageIndex:            messageRow.MessageIndex,
			ToolCallID:              "",
			UsageSource:             "assistant_message",
			InputTokens:             messageRow.InputTokens,
			OutputTokens:            messageRow.OutputTokens,
			CacheWriteTokens:        messageRow.CacheWriteTokens,
			CacheReadTokens:         messageRow.CacheReadTokens,
			ReasoningTokens:         0,
			EstimatedInputCost:      zeroCost(),
			EstimatedOutputCost:     zeroCost(),
			EstimatedCacheWriteCost: zeroCost(),
			EstimatedCacheReadCost:  zeroCost(),
			EstimatedTotalCost:      zeroCost(),
		})
	}

	return []MessageEventRow{messageRow}, usageRows, pendingMeta
}

func normalizeClaudeUser(source SourceFile, lineNumber uint64, eventTime time.Time, message map[string]any, state *ClaudeState) ([]MessageEventRow, []ToolEventRow) {
	messageRows := make([]MessageEventRow, 0)
	toolRows := make([]ToolEventRow, 0)
	contentValue, exists := message["content"]
	if !exists {
		return messageRows, toolRows
	}

	switch content := contentValue.(type) {
	case string:
		if strings.TrimSpace(content) != "" {
			messageRows = append(messageRows, singleClaudeUserMessage(source, lineNumber, eventTime, state, content, 0))
		}
	case []any:
		textIndex := 0
		for blockIndex, rawBlock := range content {
			block, ok := rawBlock.(map[string]any)
			if !ok {
				continue
			}
			switch stringValue(block["type"]) {
			case "text":
				text := stringValue(block["text"])
				if strings.TrimSpace(text) == "" {
					continue
				}
				messageRows = append(messageRows, singleClaudeUserMessage(source, lineNumber, eventTime, state, text, textIndex))
				textIndex++
			case "tool_result":
				toolRows = append(toolRows, buildClaudeToolRow(source, lineNumber, eventTime, state, blockIndex, block))
			}
		}
	}

	return messageRows, toolRows
}

func singleClaudeUserMessage(source SourceFile, lineNumber uint64, eventTime time.Time, state *ClaudeState, text string, textIndex int) MessageEventRow {
	messageID := fmt.Sprintf("%s:user:%d:%d", source.ConversationID, lineNumber, textIndex)
	row := MessageEventRow{
		Provider:           source.Provider,
		ConversationID:     source.ConversationID,
		SessionID:          source.SessionID,
		EventID:            makeBaseEventID(source, lineNumber) + ":message:" + strconv.Itoa(textIndex),
		MessageID:          messageID,
		MessageIndex:       state.MessageIndex,
		MessageTime:        utcTimestamp(eventTime),
		Ordinal:            state.MessageIndex,
		ProjectPath:        state.ProjectPath,
		ProjectName:        state.ProjectName,
		GitBranch:          state.GitBranch,
		Model:              state.Model,
		Role:               "user",
		AuthorName:         "",
		MessageKind:        "message",
		ContentText:        truncate(text, 4000),
		ContentJSON:        mustJSON([]map[string]any{{"type": "text", "text": text}}),
		EstimatedTotalCost: zeroCost(),
	}
	state.MessageIndex++
	return row
}

func buildClaudeToolRow(source SourceFile, lineNumber uint64, eventTime time.Time, state *ClaudeState, blockIndex int, block map[string]any) ToolEventRow {
	toolCallID := stringValue(block["tool_use_id"])
	pending, ok := state.PendingTools[toolCallID]
	if ok {
		delete(state.PendingTools, toolCallID)
	}

	resultText := toolResultText(block["content"])
	isError := boolValue(block["is_error"])
	status := "completed"
	if isError {
		status = "error"
	}

	model := state.Model
	gitBranch := state.GitBranch
	parentMessageID := ""
	parentMessageIndex := uint32(0)
	subagentType := ""
	toolName := "unknown"
	inputPayload := "{}"
	startedAt := utcTimestamp(eventTime)
	if ok {
		model = firstNonEmpty(pending.Model, model)
		gitBranch = firstNonEmpty(pending.GitBranch, gitBranch)
		parentMessageID = pending.ParentMessageID
		parentMessageIndex = pending.ParentMessageIndex
		subagentType = pending.SubagentType
		toolName = firstNonEmpty(pending.ToolName, toolName)
		inputPayload = mustJSON(pending.Input)
		startedAt = pending.StartedAt
	}

	return ToolEventRow{
		Provider:           source.Provider,
		ConversationID:     source.ConversationID,
		SessionID:          source.SessionID,
		EventID:            makeBaseEventID(source, lineNumber) + ":tool:" + strconv.Itoa(blockIndex),
		ToolCallID:         firstNonEmpty(toolCallID, fmt.Sprintf("%s:tool:%d", source.ConversationID, blockIndex)),
		ToolName:           toolName,
		StartedAt:          startedAt,
		FinishedAt:         utcTimestamp(eventTime),
		DurationMS:         durationMillis(startedAt, eventTime),
		Ordinal:            uint32(blockIndex),
		ProjectPath:        state.ProjectPath,
		ProjectName:        state.ProjectName,
		GitBranch:          gitBranch,
		Model:              model,
		ParentMessageID:    parentMessageID,
		ParentMessageIndex: parentMessageIndex,
		ToolStatus:         status,
		SubagentID:         "",
		SubagentType:       subagentType,
		InputPayloadJSON:   inputPayload,
		OutputPayloadJSON:  mustJSON(map[string]any{"result": resultText}),
		ErrorText:          ternaryString(isError, resultText, ""),
		InputTokens:        0,
		OutputTokens:       0,
		CacheWriteTokens:   0,
		CacheReadTokens:    0,
		ReasoningTokens:    0,
		EstimatedTotalCost: zeroCost(),
	}
}

func normalizeCodexLine(source SourceFile, lineNumber uint64, rawLine string, state ParserState) (ParserState, *NormalizedEnvelope) {
	var entry map[string]any
	if err := json.Unmarshal([]byte(rawLine), &entry); err != nil {
		return state, nil
	}

	if state.Codex.ProjectPath == "" {
		state.Codex.ProjectPath = source.ProjectPath
		state.Codex.ProjectName = source.ProjectName
	}

	eventTime := parseISOTime(stringValue(entry["timestamp"]))
	baseType := stringValue(entry["type"])
	payload := mapValue(entry["payload"])
	eventType := "codex." + baseType
	if payloadType := stringValue(payload["type"]); payloadType != "" {
		eventType += "." + payloadType
	}

	if baseType == "session_meta" {
		if cwd := stringValue(payload["cwd"]); cwd != "" {
			state.Codex.ProjectPath = codexProjectPath(cwd)
			state.Codex.ProjectName = codexProjectDisplayName(cwd)
		}
	}
	if baseType == "turn_context" {
		if model := stringValue(payload["model"]); model != "" {
			state.Codex.Model = model
		}
		if effort := stringValue(payload["reasoning_effort"]); effort != "" {
			state.Codex.ReasoningEffort = effort
		}
	}

	envelope := newEnvelope(source, lineNumber, eventType, eventTime, state.Codex.ProjectPath, state.Codex.ProjectName, entry)
	envelope.ConversationEvent.Model = state.Codex.Model

	switch baseType {
	case "response_item":
		applyCodexResponseItem(source, lineNumber, eventTime, payload, &state.Codex, envelope)
	case "event_msg":
		applyCodexEventMessage(source, lineNumber, eventTime, payload, &state.Codex, envelope)
	}

	return state, envelope
}

func applyCodexResponseItem(source SourceFile, lineNumber uint64, eventTime time.Time, payload map[string]any, state *CodexState, envelope *NormalizedEnvelope) {
	switch stringValue(payload["type"]) {
	case "message":
		role := stringValue(payload["role"])
		switch role {
		case "user":
			content, _ := payload["content"].([]any)
			for blockIndex, rawBlock := range content {
				block := mapValue(rawBlock)
				if stringValue(block["type"]) != "input_text" {
					continue
				}
				text := stringValue(block["text"])
				if strings.HasPrefix(text, "<") || strings.TrimSpace(text) == "" {
					continue
				}
				row := MessageEventRow{
					Provider:           source.Provider,
					ConversationID:     source.ConversationID,
					SessionID:          source.SessionID,
					EventID:            makeBaseEventID(source, lineNumber) + ":message:" + strconv.Itoa(len(envelope.MessageEvents)),
					MessageID:          fmt.Sprintf("%s:user:%d:%d", source.ConversationID, lineNumber, blockIndex),
					MessageIndex:       state.MessageIndex,
					MessageTime:        utcTimestamp(eventTime),
					Ordinal:            state.MessageIndex,
					ProjectPath:        state.ProjectPath,
					ProjectName:        state.ProjectName,
					Model:              state.Model,
					Role:               "user",
					MessageKind:        "message",
					ContentText:        truncate(text, 4000),
					ContentJSON:        mustJSON([]map[string]any{{"type": "text", "text": text}}),
					EstimatedTotalCost: zeroCost(),
				}
				state.MessageIndex++
				envelope.MessageEvents = append(envelope.MessageEvents, row)
			}
			if len(envelope.MessageEvents) > 0 {
				envelope.ConversationEvent.MessageID = envelope.MessageEvents[0].MessageID
				envelope.ConversationEvent.MessageIndex = envelope.MessageEvents[0].MessageIndex
				envelope.ConversationEvent.MessageRole = "user"
			}
		case "assistant":
			for _, rawBlock := range sliceValue(payload["content"]) {
				block := mapValue(rawBlock)
				if stringValue(block["type"]) == "output_text" && strings.TrimSpace(stringValue(block["text"])) != "" {
					state.PendingBlocks = append(state.PendingBlocks, CodexPendingBlock{
						Kind: "text",
						Text: stringValue(block["text"]),
					})
				}
			}
			state.LastAssistantAt = utcTimestamp(eventTime)
			state.LastAssistantLine = lineNumber
		}
	case "reasoning":
		for _, rawBlock := range sliceValue(payload["summary"]) {
			block := mapValue(rawBlock)
			text := stringValue(block["text"])
			if strings.TrimSpace(text) == "" {
				continue
			}
			state.PendingBlocks = append(state.PendingBlocks, CodexPendingBlock{
				Kind:     "thinking",
				Thinking: text,
			})
		}
		state.LastAssistantAt = utcTimestamp(eventTime)
		state.LastAssistantLine = lineNumber
	case "function_call":
		toolName := codexToolDisplayName(stringValue(payload["name"]))
		input := parseJSONStringObject(stringValue(payload["arguments"]))
		subagentType := ""
		if stringValue(payload["name"]) == "spawn_agent" {
			subagentType = stringValue(input["agent_type"])
		}
		state.PendingBlocks = append(state.PendingBlocks, CodexPendingBlock{
			Kind:         "tool_call",
			ToolCallID:   stringValue(payload["call_id"]),
			ToolName:     toolName,
			Input:        input,
			StartedAt:    utcTimestamp(eventTime),
			SubagentType: subagentType,
		})
		state.LastAssistantAt = utcTimestamp(eventTime)
		state.LastAssistantLine = lineNumber
	case "function_call_output":
		updatePendingCodexTool(state, stringValue(payload["call_id"]), stringValue(payload["output"]), codexCommandErrored(stringValue(payload["output"])))
	case "custom_tool_call":
		state.PendingBlocks = append(state.PendingBlocks, CodexPendingBlock{
			Kind:       "tool_call",
			ToolCallID: stringValue(payload["call_id"]),
			ToolName:   codexToolDisplayName(stringValue(payload["name"])),
			Input:      map[string]any{"patch": stringValue(payload["input"])},
			StartedAt:  utcTimestamp(eventTime),
		})
		state.LastAssistantAt = utcTimestamp(eventTime)
		state.LastAssistantLine = lineNumber
	case "custom_tool_call_output":
		output := parseCustomToolOutput(stringValue(payload["output"]))
		updatePendingCodexTool(state, stringValue(payload["call_id"]), output, codexCustomToolErrored(stringValue(payload["output"])))
	case "web_search_call":
		action := mapValue(payload["action"])
		input := map[string]any{}
		if value := stringValue(action["type"]); value != "" {
			input["type"] = value
		}
		if value := stringValue(action["query"]); value != "" {
			input["query"] = value
		}
		if queries := stringSlice(action["queries"]); len(queries) > 0 {
			input["queries"] = queries
		}
		state.PendingBlocks = append(state.PendingBlocks, CodexPendingBlock{
			Kind:       "tool_call",
			ToolCallID: fmt.Sprintf("web-search-%d", lineNumber),
			ToolName:   codexToolDisplayName("web_search_call"),
			Input:      input,
			Result:     ternaryString(stringValue(payload["status"]) != "", "Status: "+stringValue(payload["status"]), ""),
			StartedAt:  utcTimestamp(eventTime),
		})
		state.LastAssistantAt = utcTimestamp(eventTime)
		state.LastAssistantLine = lineNumber
	}
}

func applyCodexEventMessage(source SourceFile, lineNumber uint64, eventTime time.Time, payload map[string]any, state *CodexState, envelope *NormalizedEnvelope) {
	if stringValue(payload["type"]) != "token_count" {
		return
	}
	info := mapValue(payload["info"])
	total := mapValue(info["total_token_usage"])
	if len(total) == 0 {
		return
	}

	stepUsage := CodexUsageTotals{
		InputTokens:           int64Value(total["input_tokens"]) - state.PreviousUsage.InputTokens,
		CachedInputTokens:     int64Value(total["cached_input_tokens"]) - state.PreviousUsage.CachedInputTokens,
		OutputTokens:          int64Value(total["output_tokens"]) - state.PreviousUsage.OutputTokens,
		ReasoningOutputTokens: int64Value(total["reasoning_output_tokens"]) - state.PreviousUsage.ReasoningOutputTokens,
	}
	state.PreviousUsage = CodexUsageTotals{
		InputTokens:           int64Value(total["input_tokens"]),
		CachedInputTokens:     int64Value(total["cached_input_tokens"]),
		OutputTokens:          int64Value(total["output_tokens"]),
		ReasoningOutputTokens: int64Value(total["reasoning_output_tokens"]),
	}
	state.PendingReasoning = stepUsage.ReasoningOutputTokens

	if len(state.PendingBlocks) == 0 {
		return
	}

	messageID := fmt.Sprintf("%s:assistant:%d", source.ConversationID, state.LastAssistantLine)
	messageBlocks := make([]map[string]any, 0, len(state.PendingBlocks))
	toolBlockIndexes := make([]int, 0)
	for index, block := range state.PendingBlocks {
		switch block.Kind {
		case "text":
			messageBlocks = append(messageBlocks, map[string]any{"type": "text", "text": block.Text})
		case "thinking":
			messageBlocks = append(messageBlocks, map[string]any{"type": "thinking", "thinking": block.Thinking, "charCount": len(block.Thinking)})
		case "tool_call":
			messageBlocks = append(messageBlocks, map[string]any{
				"type":      "tool_call",
				"toolUseId": block.ToolCallID,
				"toolName":  block.ToolName,
				"input":     block.Input,
				"result":    block.Result,
				"isError":   block.IsError,
			})
			toolBlockIndexes = append(toolBlockIndexes, index)
		}
	}

	messageRow := MessageEventRow{
		Provider:           source.Provider,
		ConversationID:     source.ConversationID,
		SessionID:          source.SessionID,
		EventID:            makeBaseEventID(source, lineNumber) + ":message:0",
		MessageID:          messageID,
		MessageIndex:       state.MessageIndex,
		MessageTime:        firstNonEmpty(state.LastAssistantAt, utcTimestamp(eventTime)),
		Ordinal:            state.MessageIndex,
		ProjectPath:        state.ProjectPath,
		ProjectName:        state.ProjectName,
		Model:              state.Model,
		Role:               "assistant",
		MessageKind:        "message",
		ContentText:        buildMessagePreview(messageBlocks),
		ContentJSON:        mustJSON(messageBlocks),
		InputTokens:        stepUsage.InputTokens,
		OutputTokens:       stepUsage.OutputTokens,
		CacheWriteTokens:   0,
		CacheReadTokens:    stepUsage.CachedInputTokens,
		ReasoningTokens:    stepUsage.ReasoningOutputTokens,
		EstimatedTotalCost: zeroCost(),
		HasToolCalls:       boolToUInt8(len(toolBlockIndexes) > 0),
		IsError:            boolToUInt8(anyCodexToolError(state.PendingBlocks)),
	}
	envelope.MessageEvents = append(envelope.MessageEvents, messageRow)
	envelope.ConversationEvent.MessageID = messageRow.MessageID
	envelope.ConversationEvent.MessageIndex = messageRow.MessageIndex
	envelope.ConversationEvent.MessageRole = "assistant"
	envelope.ConversationEvent.UsageInputTokens = stepUsage.InputTokens
	envelope.ConversationEvent.UsageOutputTokens = stepUsage.OutputTokens
	envelope.ConversationEvent.UsageCacheReadTokens = stepUsage.CachedInputTokens
	envelope.ConversationEvent.UsageReasoningTokens = stepUsage.ReasoningOutputTokens

	envelope.UsageEvents = append(envelope.UsageEvents, UsageEventRow{
		Provider:                source.Provider,
		ConversationID:          source.ConversationID,
		SessionID:               source.SessionID,
		EventID:                 makeBaseEventID(source, lineNumber) + ":usage:0",
		EventTime:               utcTimestamp(eventTime),
		Ordinal:                 messageRow.MessageIndex,
		ProjectPath:             state.ProjectPath,
		ProjectName:             state.ProjectName,
		Model:                   state.Model,
		MessageID:               messageID,
		MessageIndex:            messageRow.MessageIndex,
		UsageSource:             "token_count_delta",
		InputTokens:             stepUsage.InputTokens,
		OutputTokens:            stepUsage.OutputTokens,
		CacheWriteTokens:        0,
		CacheReadTokens:         stepUsage.CachedInputTokens,
		ReasoningTokens:         stepUsage.ReasoningOutputTokens,
		EstimatedInputCost:      zeroCost(),
		EstimatedOutputCost:     zeroCost(),
		EstimatedCacheWriteCost: zeroCost(),
		EstimatedCacheReadCost:  zeroCost(),
		EstimatedTotalCost:      zeroCost(),
	})

	if len(toolBlockIndexes) > 0 {
		inputSplit := splitInt(stepUsage.InputTokens, len(toolBlockIndexes))
		outputSplit := splitInt(stepUsage.OutputTokens, len(toolBlockIndexes))
		cacheReadSplit := splitInt(stepUsage.CachedInputTokens, len(toolBlockIndexes))
		reasoningSplit := splitInt(stepUsage.ReasoningOutputTokens, len(toolBlockIndexes))
		for toolOffset, blockIndex := range toolBlockIndexes {
			block := state.PendingBlocks[blockIndex]
			toolRow := ToolEventRow{
				Provider:           source.Provider,
				ConversationID:     source.ConversationID,
				SessionID:          source.SessionID,
				EventID:            makeBaseEventID(source, lineNumber) + ":tool:" + strconv.Itoa(toolOffset),
				ToolCallID:         block.ToolCallID,
				ToolName:           block.ToolName,
				StartedAt:          firstNonEmpty(block.StartedAt, messageRow.MessageTime),
				FinishedAt:         utcTimestamp(eventTime),
				DurationMS:         durationMillis(firstNonEmpty(block.StartedAt, messageRow.MessageTime), eventTime),
				Ordinal:            uint32(toolOffset),
				ProjectPath:        state.ProjectPath,
				ProjectName:        state.ProjectName,
				Model:              state.Model,
				ParentMessageID:    messageID,
				ParentMessageIndex: messageRow.MessageIndex,
				ToolStatus:         ternaryString(block.IsError, "error", "completed"),
				SubagentID:         block.SubagentID,
				SubagentType:       block.SubagentType,
				InputPayloadJSON:   mustJSON(block.Input),
				OutputPayloadJSON:  mustJSON(map[string]any{"result": block.Result}),
				ErrorText:          ternaryString(block.IsError, block.Result, ""),
				InputTokens:        inputSplit[toolOffset],
				OutputTokens:       outputSplit[toolOffset],
				CacheWriteTokens:   0,
				CacheReadTokens:    cacheReadSplit[toolOffset],
				ReasoningTokens:    reasoningSplit[toolOffset],
				EstimatedTotalCost: zeroCost(),
			}
			envelope.ToolEvents = append(envelope.ToolEvents, toolRow)
		}
		envelope.ConversationEvent.ToolCallID = envelope.ToolEvents[0].ToolCallID
		envelope.ConversationEvent.ToolName = envelope.ToolEvents[0].ToolName
		envelope.ConversationEvent.ToolStatus = envelope.ToolEvents[0].ToolStatus
		envelope.ConversationEvent.SubagentID = envelope.ToolEvents[0].SubagentID
		envelope.ConversationEvent.SubagentType = envelope.ToolEvents[0].SubagentType
	}

	state.MessageIndex++
	state.PendingBlocks = nil
	state.PendingReasoning = 0
}

func updatePendingCodexTool(state *CodexState, callID, output string, isError bool) {
	for index := len(state.PendingBlocks) - 1; index >= 0; index-- {
		block := &state.PendingBlocks[index]
		if block.Kind != "tool_call" || block.ToolCallID != callID {
			continue
		}
		block.Result = truncate(output, toolResultMaxLength)
		block.IsError = isError
		if block.ToolName == "Spawn Agent" {
			if agentID := parseSpawnAgentID(output); agentID != "" {
				block.SubagentID = agentID
			}
		}
		return
	}
}

func newEnvelope(source SourceFile, lineNumber uint64, eventType string, eventTime time.Time, projectPath, projectName string, payload any) *NormalizedEnvelope {
	baseEventID := makeBaseEventID(source, lineNumber)
	payloadJSON := mustJSON(payload)
	return &NormalizedEnvelope{
		Provider:       source.Provider,
		ConversationID: source.ConversationID,
		SessionID:      source.SessionID,
		SourcePath:     source.Path,
		SourceLine:     lineNumber,
		EventID:        baseEventID,
		EventType:      eventType,
		EventTime:      utcTimestamp(eventTime),
		ProjectPath:    projectPath,
		ProjectName:    projectName,
		Payload: map[string]any{
			"sourcePath": source.Path,
			"sourceLine": lineNumber,
		},
		ConversationEvent: ConversationEventRow{
			Provider:                source.Provider,
			ConversationID:          source.ConversationID,
			SessionID:               source.SessionID,
			EventID:                 baseEventID,
			EventTime:               utcTimestamp(eventTime),
			Ordinal:                 uint32(lineNumber),
			EventType:               eventType,
			ProjectPath:             projectPath,
			ProjectName:             projectName,
			EstimatedInputCost:      zeroCost(),
			EstimatedOutputCost:     zeroCost(),
			EstimatedCacheWriteCost: zeroCost(),
			EstimatedCacheReadCost:  zeroCost(),
			EstimatedTotalCost:      zeroCost(),
			PayloadJSON:             payloadJSON,
		},
	}
}

func parseClaudeTimestamp(value any) time.Time {
	switch typed := value.(type) {
	case float64:
		return time.UnixMilli(int64(typed)).UTC()
	case int64:
		return time.UnixMilli(typed).UTC()
	case string:
		if milliseconds, err := strconv.ParseInt(typed, 10, 64); err == nil {
			return time.UnixMilli(milliseconds).UTC()
		}
		return parseISOTime(typed)
	default:
		return time.Now().UTC()
	}
}

func parseISOTime(value string) time.Time {
	if parsed, err := time.Parse(time.RFC3339Nano, value); err == nil {
		return parsed.UTC()
	}
	return time.Now().UTC()
}

func mapValue(value any) map[string]any {
	if typed, ok := value.(map[string]any); ok {
		return typed
	}
	return map[string]any{}
}

func sliceValue(value any) []any {
	if typed, ok := value.([]any); ok {
		return typed
	}
	return nil
}

func stringValue(value any) string {
	switch typed := value.(type) {
	case string:
		return typed
	case fmt.Stringer:
		return typed.String()
	default:
		return ""
	}
}

func stringSlice(value any) []string {
	items, ok := value.([]any)
	if !ok {
		return nil
	}
	result := make([]string, 0, len(items))
	for _, item := range items {
		if text := stringValue(item); text != "" {
			result = append(result, text)
		}
	}
	return result
}

func int64Value(value any) int64 {
	switch typed := value.(type) {
	case float64:
		return int64(typed)
	case int64:
		return typed
	case int:
		return int64(typed)
	case json.Number:
		if parsed, err := typed.Int64(); err == nil {
			return parsed
		}
	case string:
		if parsed, err := strconv.ParseInt(strings.TrimSpace(typed), 10, 64); err == nil {
			return parsed
		}
	}
	return 0
}

func boolValue(value any) bool {
	switch typed := value.(type) {
	case bool:
		return typed
	case string:
		return strings.EqualFold(typed, "true")
	default:
		return false
	}
}

func boolToUInt8(value bool) uint8 {
	if value {
		return 1
	}
	return 0
}

func buildMessagePreview(blocks []map[string]any) string {
	textParts := make([]string, 0)
	toolNames := make([]string, 0)
	for _, block := range blocks {
		switch stringValue(block["type"]) {
		case "text":
			if text := stringValue(block["text"]); text != "" {
				textParts = append(textParts, text)
			}
		case "thinking":
			if thinking := stringValue(block["thinking"]); thinking != "" {
				textParts = append(textParts, thinking)
			}
		case "tool_call":
			if toolName := stringValue(block["toolName"]); toolName != "" {
				toolNames = append(toolNames, toolName)
			}
		}
	}
	if len(textParts) > 0 {
		return truncate(strings.Join(textParts, "\n\n"), 4000)
	}
	if len(toolNames) > 0 {
		return truncate(strings.Join(toolNames, ", "), 4000)
	}
	return ""
}

func toolResultText(value any) string {
	switch typed := value.(type) {
	case string:
		return truncate(typed, toolResultMaxLength)
	case []any:
		parts := make([]string, 0, len(typed))
		for _, item := range typed {
			block := mapValue(item)
			if text := firstNonEmpty(stringValue(block["text"]), stringValue(block["thinking"])); text != "" {
				parts = append(parts, text)
			}
		}
		return truncate(strings.Join(parts, "\n"), toolResultMaxLength)
	default:
		return truncate(mustJSON(value), toolResultMaxLength)
	}
}

func truncate(value string, limit int) string {
	if len(value) <= limit {
		return value
	}
	return value[:limit]
}

func durationMillis(start string, end time.Time) uint64 {
	startTime, err := time.Parse("2006-01-02 15:04:05.000", start)
	if err != nil {
		return 0
	}
	if end.Before(startTime) {
		return 0
	}
	return uint64(end.Sub(startTime).Milliseconds())
}

func splitInt(total int64, count int) []int64 {
	if count <= 0 {
		return nil
	}
	base := total / int64(count)
	remainder := total % int64(count)
	result := make([]int64, count)
	for index := 0; index < count; index++ {
		result[index] = base
		if int64(index) < remainder {
			result[index]++
		}
	}
	return result
}

func parseJSONStringObject(raw string) map[string]any {
	if strings.TrimSpace(raw) == "" {
		return map[string]any{}
	}
	var parsed map[string]any
	if err := json.Unmarshal([]byte(raw), &parsed); err != nil {
		return map[string]any{"raw": raw}
	}
	return parsed
}

func codexToolDisplayName(raw string) string {
	switch raw {
	case "exec_command":
		return "Shell"
	case "apply_patch":
		return "Patch"
	case "spawn_agent":
		return "Spawn Agent"
	case "send_input":
		return "Send Input"
	case "wait":
		return "Wait"
	case "close_agent":
		return "Close Agent"
	case "web_search_call":
		return "Web Search"
	default:
		return raw
	}
}

func codexCommandErrored(output string) bool {
	matches := exitCodePattern.FindStringSubmatch(output)
	return len(matches) == 2 && matches[1] != "0"
}

func codexCustomToolErrored(output string) bool {
	return strings.Contains(output, `"exit_code":`) && !strings.Contains(output, `"exit_code":0`)
}

func parseCustomToolOutput(output string) string {
	var parsed map[string]any
	if err := json.Unmarshal([]byte(output), &parsed); err == nil {
		if text := stringValue(parsed["output"]); text != "" {
			return text
		}
	}
	return output
}

func parseSpawnAgentID(output string) string {
	var parsed map[string]any
	if err := json.Unmarshal([]byte(output), &parsed); err != nil {
		return ""
	}
	return firstNonEmpty(stringValue(parsed["agent_id"]), stringValue(parsed["agentId"]), stringValue(parsed["id"]))
}

func anyCodexToolError(blocks []CodexPendingBlock) bool {
	for _, block := range blocks {
		if block.Kind == "tool_call" && block.IsError {
			return true
		}
	}
	return false
}

func ternaryString(condition bool, whenTrue, whenFalse string) string {
	if condition {
		return whenTrue
	}
	return whenFalse
}
