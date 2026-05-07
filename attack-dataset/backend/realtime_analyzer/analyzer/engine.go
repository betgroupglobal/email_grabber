// Package analyzer provides real-time target analysis:
//   - Port scanning (Nmap integration)
//   - Service fingerprinting
//   - Vulnerability correlation via the Knowledge Engine
//   - Attack vector requests
package analyzer

import (
	"bytes"
	"context"
	"encoding/json"
	"encoding/xml"
	"fmt"
	"io"
	"log"
	"net/http"
	"os/exec"
	"strings"
	"sync"
	"time"

	"github.com/opsec/realtime_analyzer/config"
)

// ── Nmap XML types ────────────────────────────────────────────────────────────

type NmapRun struct {
	XMLName xml.Name   `xml:"nmaprun"`
	Hosts   []NmapHost `xml:"host"`
}

type NmapHost struct {
	Addresses []NmapAddress `xml:"address"`
	Ports     NmapPorts     `xml:"ports"`
	OS        NmapOS        `xml:"os"`
}

type NmapAddress struct {
	Addr     string `xml:"addr,attr"`
	AddrType string `xml:"addrtype,attr"`
}

type NmapPorts struct {
	Ports []NmapPort `xml:"port"`
}

type NmapPort struct {
	Protocol string      `xml:"protocol,attr"`
	Portid   string      `xml:"portid,attr"`
	State    NmapState   `xml:"state"`
	Service  NmapService `xml:"service"`
}

type NmapState struct {
	State string `xml:"state,attr"`
}

type NmapService struct {
	Name    string `xml:"name,attr"`
	Product string `xml:"product,attr"`
	Version string `xml:"version,attr"`
}

type NmapOS struct {
	OsMatches []NmapOsMatch `xml:"osmatch"`
}

type NmapOsMatch struct {
	Name     string `xml:"name,attr"`
	Accuracy string `xml:"accuracy,attr"`
}

// ── Target Fingerprint ────────────────────────────────────────────────────────

type ServiceInfo struct {
	Port     string `json:"port"`
	Protocol string `json:"protocol"`
	Name     string `json:"name"`
	Product  string `json:"product"`
	Version  string `json:"version"`
}

type TargetFingerprint struct {
	Target   string        `json:"target"`
	IP       string        `json:"ip"`
	OS       string        `json:"os"`
	Services []ServiceInfo `json:"services"`
	ScanTime time.Time     `json:"scan_time"`
}

// ── Knowledge Engine types ─────────────────────────────────────────────────

type AttackVectorRequest struct {
	TargetDescription string   `json:"target_description"`
	DetectedServices  []string `json:"detected_services"`
	DetectedOS        string   `json:"detected_os"`
	TopChains         int      `json:"top_chains"`
}

type AttackRecord struct {
	ID            int    `json:"id"`
	Title         string `json:"title"`
	Category      string `json:"category"`
	AttackType    string `json:"attack_type"`
	MitreTechnique string `json:"mitre_technique"`
	Impact        string `json:"impact"`
	DetectionMethod string `json:"detection_method"`
	Solution      string `json:"solution"`
	ToolsUsed     string `json:"tools_used"`
	AttackSteps   string `json:"attack_steps"`
}

type AttackStep struct {
	Phase          string       `json:"phase"`
	Attack         AttackRecord `json:"attack"`
	Rationale      string       `json:"rationale"`
	MitreTechnique string       `json:"mitre_technique"`
}

type AttackChain struct {
	ChainID            string       `json:"chain_id"`
	TargetDescription  string       `json:"target_description"`
	Confidence         float64      `json:"confidence"`
	Steps              []AttackStep `json:"steps"`
	EstimatedImpact    string       `json:"estimated_impact"`
	OpsecNotes         string       `json:"opsec_notes"`
}

type AttackVectorResponse struct {
	TargetDescription string        `json:"target_description"`
	Chains            []AttackChain `json:"chains"`
}

// ── Analysis Session ─────────────────────────────────────────────────────────

type Session struct {
	ID          string             `json:"id"`
	Target      string             `json:"target"`
	Fingerprint *TargetFingerprint `json:"fingerprint,omitempty"`
	Vectors     *AttackVectorResponse `json:"vectors,omitempty"`
	StartedAt   time.Time          `json:"started_at"`
	Status      string             `json:"status"` // scanning | analysing | ready | error
	Error       string             `json:"error,omitempty"`
}

// ── Engine ────────────────────────────────────────────────────────────────────

type Engine struct {
	cfg      *config.Config
	mu       sync.RWMutex
	sessions map[string]*Session
}

func NewEngine(cfg *config.Config) *Engine {
	return &Engine{
		cfg:      cfg,
		sessions: make(map[string]*Session),
	}
}

func (e *Engine) StartSession(ctx context.Context, sessionID, target string) *Session {
	sess := &Session{
		ID:        sessionID,
		Target:    target,
		StartedAt: time.Now(),
		Status:    "scanning",
	}
	e.mu.Lock()
	e.sessions[sessionID] = sess
	e.mu.Unlock()

	go e.runAnalysis(ctx, sess)
	return sess
}

func (e *Engine) GetSession(id string) (*Session, bool) {
	e.mu.RLock()
	defer e.mu.RUnlock()
	s, ok := e.sessions[id]
	return s, ok
}

func (e *Engine) ListSessions() []*Session {
	e.mu.RLock()
	defer e.mu.RUnlock()
	out := make([]*Session, 0, len(e.sessions))
	for _, s := range e.sessions {
		out = append(out, s)
	}
	return out
}

func (e *Engine) runAnalysis(ctx context.Context, sess *Session) {
	// Step 1 — Nmap scan
	fp, err := e.nmapScan(ctx, sess.Target)
	if err != nil {
		e.setError(sess, fmt.Sprintf("nmap scan failed: %v", err))
		return
	}

	e.mu.Lock()
	sess.Fingerprint = fp
	sess.Status = "analysing"
	e.mu.Unlock()

	log.Printf("[analyzer] session %s: fingerprint ready, %d services detected", sess.ID, len(fp.Services))

	// Step 2 — Ask Knowledge Engine for attack vectors
	vectors, err := e.queryKnowledgeEngine(ctx, fp)
	if err != nil {
		e.setError(sess, fmt.Sprintf("knowledge engine query failed: %v", err))
		return
	}

	e.mu.Lock()
	sess.Vectors = vectors
	sess.Status = "ready"
	e.mu.Unlock()

	log.Printf("[analyzer] session %s: %d attack chains built", sess.ID, len(vectors.Chains))
}

func (e *Engine) setError(sess *Session, msg string) {
	e.mu.Lock()
	sess.Status = "error"
	sess.Error = msg
	e.mu.Unlock()
	log.Printf("[analyzer] session %s ERROR: %s", sess.ID, msg)
}

// ── Nmap ──────────────────────────────────────────────────────────────────────

func (e *Engine) nmapScan(ctx context.Context, target string) (*TargetFingerprint, error) {
	args := []string{
		"-sV",         // version detection
		"-O",          // OS detection (requires root; gracefully degrades)
		"--open",      // only open ports
		"-T4",         // aggressive timing
		"-oX", "-",    // XML output to stdout
		"--top-ports", "1000",
		target,
	}

	log.Printf("[nmap] scanning %s…", target)
	cmd := exec.CommandContext(ctx, e.cfg.NmapBin, args...)
	out, err := cmd.Output()
	if err != nil {
		// Non-fatal: nmap may partially succeed
		log.Printf("[nmap] warning: %v", err)
	}

	return parseNmapXML(target, out)
}

func parseNmapXML(target string, xmlData []byte) (*TargetFingerprint, error) {
	var run NmapRun
	if err := xml.Unmarshal(xmlData, &run); err != nil {
		return &TargetFingerprint{
			Target:   target,
			IP:       target,
			ScanTime: time.Now(),
		}, nil // return empty fingerprint rather than failing hard
	}

	fp := &TargetFingerprint{
		Target:   target,
		ScanTime: time.Now(),
	}

	for _, host := range run.Hosts {
		// IP
		for _, addr := range host.Addresses {
			if addr.AddrType == "ipv4" || addr.AddrType == "ipv6" {
				fp.IP = addr.Addr
			}
		}
		// OS
		if len(host.OS.OsMatches) > 0 {
			fp.OS = host.OS.OsMatches[0].Name
		}
		// Services
		for _, port := range host.Ports.Ports {
			if port.State.State != "open" {
				continue
			}
			fp.Services = append(fp.Services, ServiceInfo{
				Port:     port.Portid,
				Protocol: port.Protocol,
				Name:     port.Service.Name,
				Product:  port.Service.Product,
				Version:  port.Service.Version,
			})
		}
	}

	return fp, nil
}

// ── Knowledge Engine client ───────────────────────────────────────────────────

func (e *Engine) queryKnowledgeEngine(
	ctx context.Context,
	fp *TargetFingerprint,
) (*AttackVectorResponse, error) {
	services := make([]string, 0, len(fp.Services))
	for _, svc := range fp.Services {
		parts := []string{}
		if svc.Name != "" {
			parts = append(parts, svc.Name)
		}
		if svc.Product != "" {
			parts = append(parts, svc.Product)
		}
		if svc.Version != "" {
			parts = append(parts, svc.Version)
		}
		if len(parts) > 0 {
			services = append(services, strings.Join(parts, " "))
		}
	}

	desc := fmt.Sprintf("Target %s running %s. Detected services: %s",
		fp.Target, fp.OS, strings.Join(services, ", "))

	reqBody := AttackVectorRequest{
		TargetDescription: desc,
		DetectedServices:  services,
		DetectedOS:        fp.OS,
		TopChains:         3,
	}

	body, _ := json.Marshal(reqBody)
	url := e.cfg.KnowledgeEngineURL + "/attack-vector"

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, url, bytes.NewReader(body))
	if err != nil {
		return nil, err
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	data, _ := io.ReadAll(resp.Body)
	var result AttackVectorResponse
	if err := json.Unmarshal(data, &result); err != nil {
		return nil, fmt.Errorf("decode error: %w", err)
	}
	return &result, nil
}
