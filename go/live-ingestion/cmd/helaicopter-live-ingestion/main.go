package main

import (
	"context"
	"log/slog"
	"os"
	"os/signal"
	"syscall"

	"github.com/curative/helaicopter/go/live-ingestion/internal/liveingest"
)

func main() {
	cfg, err := liveingest.LoadConfig()
	if err != nil {
		slog.Error("invalid configuration", "error", err)
		os.Exit(1)
	}

	logger := slog.New(slog.NewTextHandler(os.Stdout, &slog.HandlerOptions{Level: cfg.LogLevel}))
	service, err := liveingest.NewService(cfg, logger)
	if err != nil {
		logger.Error("failed to initialize service", "error", err)
		os.Exit(1)
	}

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	if err := service.Run(ctx); err != nil {
		logger.Error("service exited with error", "error", err)
		os.Exit(1)
	}
}
