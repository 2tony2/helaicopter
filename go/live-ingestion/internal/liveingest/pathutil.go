package liveingest

import (
	"crypto/sha1"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"path/filepath"
	"regexp"
	"strings"
	"time"
)

var codexSessionPattern = regexp.MustCompile(`([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})\.jsonl$`)

func discoverSource(path, claudeRoot, codexRoot string) (SourceFile, bool) {
	cleanPath := filepath.Clean(path)
	claudeProjects := filepath.Join(claudeRoot, "projects")
	codexSessions := filepath.Join(codexRoot, "sessions")

	if rel, err := filepath.Rel(claudeProjects, cleanPath); err == nil && !strings.HasPrefix(rel, "..") {
		segments := strings.Split(rel, string(filepath.Separator))
		if len(segments) < 2 || !strings.HasSuffix(cleanPath, ".jsonl") {
			return SourceFile{}, false
		}
		projectPath := segments[0]
		filename := segments[len(segments)-1]
		sessionID := strings.TrimSuffix(filename, filepath.Ext(filename))
		return SourceFile{
			Provider:       "claude",
			Path:           cleanPath,
			SessionID:      sessionID,
			ProjectPath:    projectPath,
			ProjectName:    claudeProjectDisplayName(projectPath),
			ConversationID: conversationID("claude", sessionID),
		}, true
	}

	if rel, err := filepath.Rel(codexSessions, cleanPath); err == nil && !strings.HasPrefix(rel, "..") {
		if !strings.HasSuffix(cleanPath, ".jsonl") {
			return SourceFile{}, false
		}
		filename := filepath.Base(cleanPath)
		sessionID := strings.TrimSuffix(filename, filepath.Ext(filename))
		if matches := codexSessionPattern.FindStringSubmatch(filename); len(matches) == 2 {
			sessionID = matches[1]
		}
		return SourceFile{
			Provider:       "codex",
			Path:           cleanPath,
			SessionID:      sessionID,
			ProjectPath:    "codex:unknown",
			ProjectName:    "Unknown",
			ConversationID: conversationID("codex", sessionID),
		}, true
	}

	return SourceFile{}, false
}

func conversationID(provider, sessionID string) string {
	return provider + ":" + sessionID
}

func claudeProjectDisplayName(projectPath string) string {
	if strings.HasPrefix(projectPath, "-") {
		fullPath := strings.Replace(strings.TrimPrefix(projectPath, "-"), "-", "/", -1)
		segments := strings.Split(fullPath, "/")
		parts := make([]string, 0, len(segments))
		for _, segment := range segments {
			if segment != "" {
				parts = append(parts, segment)
			}
		}
		if len(parts) > 3 {
			return strings.Join(parts[len(parts)-3:], "/")
		}
		if len(parts) > 0 {
			return strings.Join(parts, "/")
		}
	}
	return projectPath
}

func codexProjectPath(cwd string) string {
	if strings.TrimSpace(cwd) == "" {
		return "codex:unknown"
	}
	return "codex:" + strings.ReplaceAll(cwd, "/", "-")
}

func codexProjectDisplayName(cwd string) string {
	if strings.TrimSpace(cwd) == "" {
		return "Unknown"
	}
	segments := make([]string, 0)
	for _, segment := range strings.Split(cwd, "/") {
		if segment != "" {
			segments = append(segments, segment)
		}
	}
	if len(segments) > 3 {
		return strings.Join(segments[len(segments)-3:], "/")
	}
	return strings.Join(segments, "/")
}

func makeBaseEventID(source SourceFile, lineNumber uint64) string {
	digest := sha1.Sum([]byte(source.Path))
	return fmt.Sprintf("%s:%s:%s:%d", source.Provider, source.SessionID, hex.EncodeToString(digest[:8]), lineNumber)
}

func utcTimestamp(value time.Time) string {
	if value.IsZero() {
		value = time.Now().UTC()
	}
	return value.UTC().Format("2006-01-02 15:04:05.000")
}

func mustJSON(value any) string {
	bytes, err := json.Marshal(value)
	if err != nil {
		return "{}"
	}
	return string(bytes)
}

func zeroCost() string {
	return "0.00000000"
}

func firstNonEmpty(values ...string) string {
	for _, value := range values {
		if strings.TrimSpace(value) != "" {
			return value
		}
	}
	return ""
}
