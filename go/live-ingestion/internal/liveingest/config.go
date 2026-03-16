package liveingest

import (
	"fmt"
	"log/slog"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"
)

type Config struct {
	ClaudeRoot           string
	CodexRoot            string
	ClickHouse           ClickHouseConfig
	HTTPAddr             string
	StreamReplayCapacity int
	CheckpointPath       string
	StartPosition        string
	FlushInterval        time.Duration
	RescanInterval       time.Duration
	BatchSize            int
	QueueCapacity        int
	MaxRetryDelay        time.Duration
	LogLevel             slog.Level
}

type ClickHouseConfig struct {
	Host               string
	Port               int
	Database           string
	User               string
	Password           string
	Secure             bool
	VerifyTLS          bool
	ConnectTimeout     time.Duration
	SendReceiveTimeout time.Duration
}

func LoadConfig() (Config, error) {
	home, err := os.UserHomeDir()
	if err != nil {
		return Config{}, fmt.Errorf("resolve home directory: %w", err)
	}

	startPosition := strings.ToLower(strings.TrimSpace(getEnv("HELAICOPTER_GO_INGEST_START_POSITION", "end")))
	if startPosition != "beginning" && startPosition != "end" {
		return Config{}, fmt.Errorf("HELAICOPTER_GO_INGEST_START_POSITION must be beginning or end")
	}

	level, err := parseLogLevel(getEnv("HELAICOPTER_GO_INGEST_LOG_LEVEL", "info"))
	if err != nil {
		return Config{}, err
	}

	cfg := Config{
		ClaudeRoot: filepath.Clean(getEnv("HELAICOPTER_GO_INGEST_CLAUDE_ROOT", filepath.Join(home, ".claude"))),
		CodexRoot:  filepath.Clean(getEnv("HELAICOPTER_GO_INGEST_CODEX_ROOT", filepath.Join(home, ".codex"))),
		ClickHouse: ClickHouseConfig{
			Host:               getEnv("HELAICOPTER_CLICKHOUSE_HOST", "127.0.0.1"),
			Port:               getEnvInt("HELAICOPTER_CLICKHOUSE_PORT", 8123),
			Database:           getEnv("HELAICOPTER_CLICKHOUSE_DATABASE", "helaicopter"),
			User:               getEnv("HELAICOPTER_CLICKHOUSE_USER", "helaicopter"),
			Password:           getEnv("HELAICOPTER_CLICKHOUSE_PASSWORD", "helaicopter"),
			Secure:             getEnvBool("HELAICOPTER_CLICKHOUSE_SECURE", false),
			VerifyTLS:          getEnvBool("HELAICOPTER_CLICKHOUSE_VERIFY_TLS", true),
			ConnectTimeout:     getEnvDuration("HELAICOPTER_CLICKHOUSE_CONNECT_TIMEOUT_SECONDS", 5*time.Second),
			SendReceiveTimeout: getEnvDuration("HELAICOPTER_CLICKHOUSE_SEND_RECEIVE_TIMEOUT_SECONDS", 30*time.Second),
		},
		HTTPAddr:             getEnv("HELAICOPTER_GO_INGEST_HTTP_ADDR", "127.0.0.1:4318"),
		StreamReplayCapacity: getEnvInt("HELAICOPTER_GO_INGEST_STREAM_REPLAY_CAPACITY", 1024),
		CheckpointPath:       filepath.Clean(getEnv("HELAICOPTER_GO_INGEST_CHECKPOINT_PATH", filepath.Join("var", "live-ingestion", "checkpoints.json"))),
		StartPosition:        startPosition,
		FlushInterval:        getEnvDuration("HELAICOPTER_GO_INGEST_FLUSH_INTERVAL_MS", 500*time.Millisecond),
		RescanInterval:       getEnvDuration("HELAICOPTER_GO_INGEST_RESCAN_INTERVAL_MS", 2*time.Second),
		BatchSize:            getEnvInt("HELAICOPTER_GO_INGEST_BATCH_SIZE", 256),
		QueueCapacity:        getEnvInt("HELAICOPTER_GO_INGEST_QUEUE_CAPACITY", 8192),
		MaxRetryDelay:        getEnvDuration("HELAICOPTER_GO_INGEST_MAX_RETRY_DELAY_MS", 15*time.Second),
		LogLevel:             level,
	}

	if cfg.BatchSize <= 0 {
		return Config{}, fmt.Errorf("HELAICOPTER_GO_INGEST_BATCH_SIZE must be > 0")
	}
	if cfg.QueueCapacity <= 0 {
		return Config{}, fmt.Errorf("HELAICOPTER_GO_INGEST_QUEUE_CAPACITY must be > 0")
	}
	if cfg.FlushInterval <= 0 {
		return Config{}, fmt.Errorf("HELAICOPTER_GO_INGEST_FLUSH_INTERVAL_MS must be > 0")
	}
	if cfg.RescanInterval <= 0 {
		return Config{}, fmt.Errorf("HELAICOPTER_GO_INGEST_RESCAN_INTERVAL_MS must be > 0")
	}
	if cfg.StreamReplayCapacity < 0 {
		return Config{}, fmt.Errorf("HELAICOPTER_GO_INGEST_STREAM_REPLAY_CAPACITY must be >= 0")
	}

	return cfg, nil
}

func getEnv(name, fallback string) string {
	if value, ok := os.LookupEnv(name); ok && strings.TrimSpace(value) != "" {
		return value
	}
	return fallback
}

func getEnvInt(name string, fallback int) int {
	raw, ok := os.LookupEnv(name)
	if !ok || strings.TrimSpace(raw) == "" {
		return fallback
	}
	value, err := strconv.Atoi(strings.TrimSpace(raw))
	if err != nil {
		return fallback
	}
	return value
}

func getEnvBool(name string, fallback bool) bool {
	raw, ok := os.LookupEnv(name)
	if !ok || strings.TrimSpace(raw) == "" {
		return fallback
	}
	switch strings.ToLower(strings.TrimSpace(raw)) {
	case "1", "true", "yes", "on":
		return true
	case "0", "false", "no", "off":
		return false
	default:
		return fallback
	}
}

func getEnvDuration(name string, fallback time.Duration) time.Duration {
	raw, ok := os.LookupEnv(name)
	if !ok || strings.TrimSpace(raw) == "" {
		return fallback
	}
	if strings.Contains(raw, "ms") || strings.Contains(raw, "s") || strings.Contains(raw, "m") {
		value, err := time.ParseDuration(strings.TrimSpace(raw))
		if err == nil {
			return value
		}
	}
	seconds, err := strconv.ParseFloat(strings.TrimSpace(raw), 64)
	if err != nil {
		return fallback
	}
	return time.Duration(seconds * float64(time.Second))
}

func parseLogLevel(raw string) (slog.Level, error) {
	switch strings.ToLower(strings.TrimSpace(raw)) {
	case "debug":
		return slog.LevelDebug, nil
	case "info", "":
		return slog.LevelInfo, nil
	case "warn", "warning":
		return slog.LevelWarn, nil
	case "error":
		return slog.LevelError, nil
	default:
		return 0, fmt.Errorf("unsupported log level %q", raw)
	}
}
