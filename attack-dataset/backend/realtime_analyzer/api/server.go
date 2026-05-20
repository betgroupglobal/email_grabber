// Package api exposes the real-time analyzer over HTTP + WebSocket.
package api

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os/exec"
	"sort"
	"time"

	"github.com/opsec/realtime_analyzer/analyzer"
	"github.com/opsec/realtime_analyzer/config"
)

type Server struct {
	cfg       *config.Config
	engine    *analyzer.Engine
	mux       *http.ServeMux
	startedAt time.Time
}

func NewServer(cfg *config.Config, engine *analyzer.Engine) *Server {
	s := &Server{
		cfg:       cfg,
		engine:    engine,
		mux:       http.NewServeMux(),
		startedAt: time.Now(),
	}
	s.routes()
	return s
}

func (s *Server) Run(ctx context.Context) error {
	srv := &http.Server{
		Addr:    s.cfg.ListenAddr,
		Handler: s.mux,
	}
	go func() {
		<-ctx.Done()
		_ = srv.Shutdown(context.Background())
	}()
	if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		return err
	}
	return nil
}

func (s *Server) routes() {
	s.mux.HandleFunc("GET /health", s.cors(s.health))
	s.mux.HandleFunc("POST /scan", s.cors(s.startScan))
	s.mux.HandleFunc("GET /sessions", s.cors(s.listSessions))
	s.mux.HandleFunc("GET /sessions/{id}", s.cors(s.getSession))
	s.mux.HandleFunc("GET /sessions/{id}/fingerprint", s.cors(s.getSessionFingerprint))
	s.mux.HandleFunc("GET /sessions/{id}/stream", s.cors(s.streamSession))
}

// cors middleware adds CORS headers to allow browser requests
func (s *Server) cors(next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization")

		if r.Method == "OPTIONS" {
			w.WriteHeader(http.StatusOK)
			return
		}

		next(w, r)
	}
}

func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v)
}

func writeError(w http.ResponseWriter, status int, code, message string) {
	writeJSON(w, status, map[string]string{
		"error":   message,
		"code":    code,
		"message": message,
	})
}

func (s *Server) health(w http.ResponseWriter, r *http.Request) {
	total, scanning, analysing := s.engine.Stats()
	writeJSON(w, http.StatusOK, map[string]any{
		"status":              "ok",
		"service":             "realtime-analyzer",
		"uptime_sec":          time.Since(s.startedAt).Seconds(),
		"active_sessions":     total,
		"scanning_sessions":   scanning,
		"analysing_sessions":  analysing,
		"nmap_available":      nmapAvailable(s.cfg.NmapBin),
		"knowledge_engine_url": s.cfg.KnowledgeEngineURL,
	})
}

func nmapAvailable(bin string) bool {
	_, err := exec.LookPath(bin)
	return err == nil
}

func (s *Server) startScan(w http.ResponseWriter, r *http.Request) {
	var body struct {
		Target          string   `json:"target"`
		ScanTimeoutSec  int      `json:"scan_timeout_sec"`
		ScanArgs        []string `json:"scan_args"`
		AggressionLevel int      `json:"aggression_level"`
		ScanType        string   `json:"scan_type"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		writeError(w, http.StatusBadRequest, "invalid_json", "request body must be valid JSON")
		return
	}
	if body.Target == "" {
		writeError(w, http.StatusBadRequest, "target_required", "target is required (IP, hostname, or CIDR)")
		return
	}
	if body.ScanTimeoutSec < 0 {
		writeError(w, http.StatusBadRequest, "invalid_timeout", "scan_timeout_sec must be zero or positive")
		return
	}

	opts := analyzer.ScanOptions{
		ScanArgs:        body.ScanArgs,
		AggressionLevel: body.AggressionLevel,
		ScanType:        body.ScanType,
	}

	sessionID := fmt.Sprintf("sess-%d", time.Now().UnixMilli())
	sess := s.engine.StartSession(context.Background(), sessionID, body.Target, body.ScanTimeoutSec, opts)
	writeJSON(w, http.StatusAccepted, sess)
}

func (s *Server) listSessions(w http.ResponseWriter, r *http.Request) {
	sessions := s.engine.ListSessions()
	sort.Slice(sessions, func(i, j int) bool {
		return sessions[i].StartedAt.After(sessions[j].StartedAt)
	})
	writeJSON(w, http.StatusOK, sessions)
}

func (s *Server) getSession(w http.ResponseWriter, r *http.Request) {
	id := r.PathValue("id")
	sess, ok := s.engine.GetSession(id)
	if !ok {
		writeError(w, http.StatusNotFound, "session_not_found", fmt.Sprintf("no scan session with id %q", id))
		return
	}
	writeJSON(w, http.StatusOK, sess)
}

func (s *Server) getSessionFingerprint(w http.ResponseWriter, r *http.Request) {
	id := r.PathValue("id")
	sess, ok := s.engine.GetSession(id)
	if !ok {
		writeError(w, http.StatusNotFound, "session_not_found", fmt.Sprintf("no scan session with id %q", id))
		return
	}
	if sess.Fingerprint == nil {
		writeError(w, http.StatusNotFound, "fingerprint_unavailable", "fingerprint not ready yet; session may still be scanning")
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{
		"session_id": id,
		"target":     sess.Target,
		"status":     sess.Status,
		"fingerprint": sess.Fingerprint,
	})
}

// streamSession is a simple SSE endpoint that polls the session until it's done.
func (s *Server) streamSession(w http.ResponseWriter, r *http.Request) {
	id := r.PathValue("id")

	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")

	flusher, ok := w.(http.Flusher)
	if !ok {
		http.Error(w, "streaming not supported", http.StatusInternalServerError)
		return
	}

	for {
		select {
		case <-r.Context().Done():
			return
		case <-time.After(500 * time.Millisecond):
		}

		sess, ok := s.engine.GetSession(id)
		if !ok {
			data, _ := json.Marshal(map[string]string{
				"error":   "session not found",
				"code":    "session_not_found",
				"message": fmt.Sprintf("no scan session with id %q", id),
			})
			fmt.Fprintf(w, "data: %s\n\n", data)
			flusher.Flush()
			return
		}

		data, _ := json.Marshal(sess)
		fmt.Fprintf(w, "data: %s\n\n", data)
		flusher.Flush()

		if sess.Status == "ready" || sess.Status == "error" {
			log.Printf("[stream] session %s finished (%s)", id, sess.Status)
			return
		}
	}
}
