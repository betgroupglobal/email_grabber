package analyzer

import "fmt"

// ScanOptions carries optional scan parameters from POST /scan (orchestrator + UI).
type ScanOptions struct {
	ScanArgs        []string
	AggressionLevel int
	ScanType        string
}

// timingFromAggression maps 1–10 aggression to nmap -T0..-T5.
func timingFromAggression(level int) string {
	switch {
	case level <= 2:
		return "-T1"
	case level <= 4:
		return "-T2"
	case level <= 6:
		return "-T3"
	case level <= 8:
		return "-T4"
	default:
		return "-T5"
	}
}

// topPortsForScanType adjusts port coverage for orchestrator adaptive scan types.
func topPortsForScanType(scanType string, scanTimeoutSec int) string {
	switch scanType {
	case "quick":
		return "20"
	case "web_application":
		return "80,443,8080,8443,8000,8888"
	case "ssh_brute_force":
		return "22"
	case "database_enumeration":
		return "3306,5432,1433,1521,27017,6379,9200"
	case "comprehensive":
		if scanTimeoutSec <= 60 {
			return "500"
		}
		return "1000"
	default:
		return topPortsForTimeout(scanTimeoutSec)
	}
}

func topPortsForTimeout(scanTimeoutSec int) string {
	switch {
	case scanTimeoutSec <= 30:
		return "20"
	case scanTimeoutSec <= 60:
		return "50"
	case scanTimeoutSec <= 120:
		return "200"
	case scanTimeoutSec <= 180:
		return "500"
	default:
		return "1000"
	}
}

func buildDefaultNmapArgs(target string, scanTimeoutSec int, opts ScanOptions) []string {
	hostTimeout := scanTimeoutSec - 5
	if hostTimeout < 30 {
		hostTimeout = 30
	}

	timing := "-T3"
	if opts.AggressionLevel > 0 {
		timing = timingFromAggression(opts.AggressionLevel)
	}

	topPorts := topPortsForScanType(opts.ScanType, scanTimeoutSec)
	if opts.ScanType == "" {
		topPorts = topPortsForTimeout(scanTimeoutSec)
	}

	// Explicit port list (e.g. web_application) uses -p instead of --top-ports.
	portArg := []string{"--top-ports", topPorts}
	if opts.ScanType != "" && opts.ScanType != "comprehensive" && opts.ScanType != "quick" {
		portArg = []string{"-p", topPorts}
	}

	args := []string{
		"--open",
		timing,
		"-oX", "-",
	}
	args = append(args, portArg...)
	args = append(args,
		"--host-timeout", fmt.Sprintf("%ds", hostTimeout),
		"--max-retries", "2",
	)
	return args
}
