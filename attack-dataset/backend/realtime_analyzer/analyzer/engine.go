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
	"os"
	"os/exec"
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
	ID              int    `json:"id"`
	Title           string `json:"title"`
	Category        string `json:"category"`
	AttackType      string `json:"attack_type"`
	MitreTechnique  string `json:"mitre_technique"`
	Impact          string `json:"impact"`
	DetectionMethod string `json:"detection_method"`
	Solution        string `json:"solution"`
	ToolsUsed       string `json:"tools_used"`
	AttackSteps     string `json:"attack_steps"`
}

// UnmarshalJSON handles both string and object representations of an attack record.
// The simple API returns "attack": "Description" (string), while the full API
// returns "attack": { "title": "...", ... } (object).
func (a *AttackRecord) UnmarshalJSON(data []byte) error {
	// Try unmarshalling as a plain string first
	var str string
	if err := json.Unmarshal(data, &str); err == nil {
		a.Title = str
		return nil
	}
	// Fallback to object unmarshalling
	type raw AttackRecord
	var r raw
	if err := json.Unmarshal(data, &r); err != nil {
		return err
	}
	*a = AttackRecord(r)
	return nil
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
	ID               string                `json:"id"`
	Target           string                `json:"target"`
	ScanTimeoutSec   int                   `json:"scan_timeout_sec,omitempty"`
	ScanType         string                `json:"scan_type,omitempty"`
	AggressionLevel  int                   `json:"aggression_level,omitempty"`
	Fingerprint      *TargetFingerprint    `json:"fingerprint,omitempty"`
	Vectors          *AttackVectorResponse `json:"vectors,omitempty"`
	StartedAt        time.Time             `json:"started_at"`
	CompletedAt      *time.Time            `json:"completed_at,omitempty"`
	DurationSec      float64               `json:"duration_sec,omitempty"`
	ServiceCount     int                   `json:"service_count,omitempty"`
	OpenPortCount    int                   `json:"open_port_count,omitempty"`
	Status           string                `json:"status"` // scanning | analysing | ready | error
	Error            string                `json:"error,omitempty"`
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

func (e *Engine) StartSession(ctx context.Context, sessionID, target string, scanTimeoutSec int, opts ScanOptions) *Session {
	if scanTimeoutSec <= 0 {
		scanTimeoutSec = 120
	}
	sess := &Session{
		ID:              sessionID,
		Target:          target,
		ScanTimeoutSec:  scanTimeoutSec,
		ScanType:        opts.ScanType,
		AggressionLevel: opts.AggressionLevel,
		StartedAt:       time.Now(),
		Status:          "scanning",
	}
	e.mu.Lock()
	e.sessions[sessionID] = sess
	e.mu.Unlock()

	go e.runAnalysis(ctx, sess, opts)
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

func (e *Engine) runAnalysis(ctx context.Context, sess *Session, opts ScanOptions) {
	// Step 1 — Nmap scan
	fp, err := e.nmapScan(ctx, sess.Target, sess.ScanTimeoutSec, opts)
	if err != nil {
		e.setError(sess, fmt.Sprintf("nmap scan failed: %v", err))
		return
	}

	e.mu.Lock()
	sess.Fingerprint = fp
	sess.ServiceCount = len(fp.Services)
	sess.OpenPortCount = countUniquePorts(fp.Services)
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
	e.finalizeSessionLocked(sess)
	e.mu.Unlock()

	log.Printf("[analyzer] session %s: %d attack chains built", sess.ID, len(vectors.Chains))
}

func countUniquePorts(services []ServiceInfo) int {
	seen := make(map[string]struct{}, len(services))
	for _, s := range services {
		if s.Port != "" {
			seen[s.Port] = struct{}{}
		}
	}
	return len(seen)
}

func (e *Engine) finalizeSessionLocked(sess *Session) {
	now := time.Now()
	sess.CompletedAt = &now
	sess.DurationSec = now.Sub(sess.StartedAt).Seconds()
	if sess.Fingerprint != nil {
		sess.ServiceCount = len(sess.Fingerprint.Services)
		sess.OpenPortCount = countUniquePorts(sess.Fingerprint.Services)
	}
}

func (e *Engine) setError(sess *Session, msg string) {
	e.mu.Lock()
	sess.Status = "error"
	sess.Error = msg
	e.finalizeSessionLocked(sess)
	e.mu.Unlock()
	log.Printf("[analyzer] session %s ERROR: %s", sess.ID, msg)
}

// Stats returns aggregate session counts for health reporting.
func (e *Engine) Stats() (total, scanning, analysing int) {
	e.mu.RLock()
	defer e.mu.RUnlock()
	for _, s := range e.sessions {
		total++
		switch s.Status {
		case "scanning":
			scanning++
		case "analysing":
			analysing++
		}
	}
	return
}

// ── Nmap ──────────────────────────────────────────────────────────────────────

func (e *Engine) nmapScan(ctx context.Context, target string, scanTimeoutSec int, opts ScanOptions) (*TargetFingerprint, error) {
	if scanTimeoutSec <= 0 {
		scanTimeoutSec = 120
	}

	var args []string
	if len(opts.ScanArgs) > 0 {
		args = append([]string(nil), opts.ScanArgs...)
		hasXML := false
		hasTarget := false
		for _, a := range args {
			if a == "-oX" {
				hasXML = true
			}
			if a == target {
				hasTarget = true
			}
		}
		if !hasXML {
			args = append(args, "-oX", "-")
		}
		if !hasTarget {
			args = append(args, target)
		}
	} else {
		args = buildDefaultNmapArgs(target, scanTimeoutSec, opts)
		// OS detection (-O) requires root; use unprivileged connect scan when non-root.
		if os.Geteuid() != 0 {
			args = append(args, "-sT", "-Pn")
		}
		args = append(args, target)
	}

	// Enforce a hard timeout independent of the request context
	scanCtx, cancel := context.WithTimeout(ctx, time.Duration(scanTimeoutSec)*time.Second)
	defer cancel()

	log.Printf("[nmap] scanning %s (timeout %ds) args=%v", target, scanTimeoutSec, args)
	cmd := exec.CommandContext(scanCtx, e.cfg.NmapBin, args...)
	var stderr bytes.Buffer
	cmd.Stderr = &stderr
	out, err := cmd.Output()
	if err != nil {
		if scanCtx.Err() == context.DeadlineExceeded {
			log.Printf("[nmap] scan of %s timed out after %ds — using partial results", target, scanTimeoutSec)
		} else {
			// Non-fatal: nmap may partially succeed (e.g. no root for OS detection)
			log.Printf("[nmap] warning for %s: %v stderr=%q", target, err, stderr.String())
		}
	}

	return parseNmapXML(target, out)
}

func parseNmapXML(target string, xmlData []byte) (*TargetFingerprint, error) {
	var run NmapRun
	if err := xml.Unmarshal(xmlData, &run); err != nil {
		log.Printf("[nmap] XML parse error for %s: %v (data len=%d)", target, err, len(xmlData))
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
	filtered := filterServicesForAttackVector(fp.Services)
	services := serviceStringsFromFingerprint(filtered)
	desc := buildTargetDescription(fp, filtered)

	reqBody := AttackVectorRequest{
		TargetDescription: desc,
		DetectedServices:  services,
		DetectedOS:        fp.OS,
		TopChains:         3,
	}

	body, err := json.Marshal(reqBody)
	if err != nil {
		return nil, err
	}
	url := e.cfg.KnowledgeEngineURL + "/attack-vector"

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, url, bytes.NewReader(body))
	if err != nil {
		return nil, err
	}
	req.Header.Set("Content-Type", "application/json")

	if e.cfg.ServiceAPIKey != "" {
		req.Header.Set("X-Service-API-Key", e.cfg.ServiceAPIKey)
		req.Header.Set("X-Service-Name", "analyzer")
	}

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	data, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, err
	}

	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		snippet := string(data)
		if len(snippet) > 240 {
			snippet = snippet[:240] + "…"
		}
		return nil, fmt.Errorf("knowledge engine attack-vector HTTP %d: %s", resp.StatusCode, snippet)
	}

	var result AttackVectorResponse
	if err := json.Unmarshal(data, &result); err != nil {
		return nil, fmt.Errorf("decode error: %w", err)
	}

	if result.TargetDescription == "" {
		result.TargetDescription = desc
	}
	if result.Chains == nil {
		result.Chains = []AttackChain{}
	}
	return &result, nil
}
