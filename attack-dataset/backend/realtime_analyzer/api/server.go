// Package api exposes the real-time analyzer over HTTP + WebSocket.
package api

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"time"

	"github.com/opsec/realtime_analyzer/analyzer"
	"github.com/opsec/realtime_analyzer/config"
)

type Server struct {
	cfg    *config.Config
	engine *analyzer.Engine
	mux    *http.ServeMux
}

func NewServer(cfg *config.Config, engine *analyzer.Engine) *Server {
	s := &Server{cfg: cfg, engine: engine, mux: http.NewServeMux()}
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
	s.mux.HandleFunc("GET /health", s.health)
	s.mux.HandleFunc("POST /scan", s.startScan)
	s.mux.HandleFunc("GET /sessions", s.listSessions)
	s.mux.HandleFunc("GET /sessions/{id}", s.getSession)
	s.mux.HandleFunc("GET /sessions/{id}/stream", s.streamSession)
}

func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v)
}

func (s *Server) health(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, map[string]string{"status": "ok", "service": "realtime-analyzer"})
}

func (s *Server) startScan(w http.ResponseWriter, r *http.Request) {
	var body struct {
		Target string `json:"target"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil || body.Target == "" {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "target required"})
		return
	}

	sessionID := fmt.Sprintf("sess-%d", time.Now().UnixMilli())
	sess := s.engine.StartSession(r.Context(), sessionID, body.Target)
	writeJSON(w, http.StatusAccepted, sess)
}

func (s *Server) listSessions(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, s.engine.ListSessions())
}

func (s *Server) getSession(w http.ResponseWriter, r *http.Request) {
	id := r.PathValue("id")
	sess, ok := s.engine.GetSession(id)
	if !ok {
		writeJSON(w, http.StatusNotFound, map[string]string{"error": "session not found"})
		return
	}
	writeJSON(w, http.StatusOK, sess)
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
			data, _ := json.Marshal(map[string]string{"error": "session not found"})
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
