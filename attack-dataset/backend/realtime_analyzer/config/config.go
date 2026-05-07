package config

import (
	"os"
)

type Config struct {
	ListenAddr         string
	KnowledgeEngineURL string
	OrchestratorURL    string
	NmapBin            string
}

func Load() *Config {
	return &Config{
		ListenAddr:         getenv("ANALYZER_ADDR", ":8001"),
		KnowledgeEngineURL: getenv("KNOWLEDGE_ENGINE_URL", "http://localhost:8000"),
		OrchestratorURL:    getenv("ORCHESTRATOR_URL", "http://localhost:3000"),
		NmapBin:            getenv("NMAP_BIN", "nmap"),
	}
}

func getenv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}
