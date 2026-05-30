package main

import (
	"context"
	"log"
	"os"
	"os/signal"
	"syscall"

	"github.com/opsec/realtime_analyzer/analyzer"
	"github.com/opsec/realtime_analyzer/api"
	"github.com/opsec/realtime_analyzer/config"
)

func main() {
	cfg := config.Load()

	log.Printf("[realtime-analyzer] starting on %s", cfg.ListenAddr)

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	// Graceful shutdown on SIGINT/SIGTERM
	go func() {
		ch := make(chan os.Signal, 1)
		signal.Notify(ch, syscall.SIGINT, syscall.SIGTERM)
		<-ch
		log.Println("[realtime-analyzer] shutting down…")
		cancel()
	}()

	engine := analyzer.NewEngine(cfg)

	srv := api.NewServer(cfg, engine)
	if err := srv.Run(ctx); err != nil {
		log.Fatalf("[realtime-analyzer] fatal: %v", err)
	}
}
