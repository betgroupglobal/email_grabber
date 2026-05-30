package analyzer

import (
	"sort"
	"strconv"
	"strings"
)

// priorityWebPorts — real services on CDN/WAF targets are usually here; Cloudflare scans often report hundreds of noise ports.
var priorityWebPorts = map[string]int{
	"443": 1, "80": 2, "8443": 3, "8080": 4, "8000": 5, "8888": 6,
	"22": 10, "21": 11, "25": 12, "53": 13, "110": 14, "143": 15,
	"3306": 20, "5432": 21, "6379": 22, "27017": 23, "3389": 24,
}

var webServiceNames = map[string]bool{
	"http": true, "https": true, "ssl": true, "ssl/http": true,
	"http-proxy": true, "http-alt": true,
}

const maxServicesForAttackVector = 40

// filterServicesForAttackVector caps and prioritizes fingerprint services for KE attack-vector requests.
func filterServicesForAttackVector(services []ServiceInfo) []ServiceInfo {
	if len(services) == 0 {
		return services
	}

	type item struct {
		svc   ServiceInfo
		score int
	}

	scored := make([]item, 0, len(services))
	seen := make(map[string]bool, len(services))

	for _, svc := range services {
		port := strings.TrimSpace(svc.Port)
		name := strings.ToLower(strings.TrimSpace(svc.Name))
		key := port + "|" + name + "|" + svc.Product
		if seen[key] {
			continue
		}
		seen[key] = true

		score := 500
		if p, ok := priorityWebPorts[port]; ok {
			score = p
		} else if webServiceNames[name] || strings.Contains(name, "http") {
			score = 30
		} else if portNum, err := strconv.Atoi(port); err == nil && portNum > 1024 {
			score = 800
		}

		scored = append(scored, item{svc: svc, score: score})
	}

	sort.Slice(scored, func(i, j int) bool {
		if scored[i].score != scored[j].score {
			return scored[i].score < scored[j].score
		}
		return scored[i].svc.Port < scored[j].svc.Port
	})

	limit := maxServicesForAttackVector
	if len(scored) < limit {
		limit = len(scored)
	}
	out := make([]ServiceInfo, 0, limit)
	for i := 0; i < limit; i++ {
		out = append(out, scored[i].svc)
	}
	return out
}

func serviceStringsFromFingerprint(services []ServiceInfo) []string {
	out := make([]string, 0, len(services))
	for _, svc := range services {
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
		if svc.Port != "" {
			parts = append(parts, "port:"+svc.Port)
		}
		if len(parts) > 0 {
			out = append(out, strings.Join(parts, " "))
		}
	}
	return out
}

func buildTargetDescription(fp *TargetFingerprint, filtered []ServiceInfo) string {
	serviceLabels := serviceStringsFromFingerprint(filtered)
	svcSummary := strings.Join(serviceLabels, ", ")
	if len(svcSummary) > 1200 {
		svcSummary = svcSummary[:1200] + "…"
	}
	os := fp.OS
	if os == "" {
		os = "unknown"
	}
	if svcSummary == "" {
		return "Target " + fp.Target + " (" + fp.IP + ") running " + os
	}
	return "Target " + fp.Target + " (" + fp.IP + ") running " + os + ". Detected services: " + svcSummary
}
