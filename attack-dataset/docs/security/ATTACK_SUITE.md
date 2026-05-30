Penetration Testing Attack Suite Plan 2026
“Maximum Defensive Value” Purple Team Simulation Framework
This plan transforms the OpsecAI Offensive Tool Reference into a structured, end-to-end penetration testing methodology. It ensures complete kill-chain coverage, realistic adversary emulation, and rich telemetry for the defensive team.
Core Objectives

Execute full MITRE ATT&CK coverage with both stealthy and noisy variants.
Generate high-quality detection opportunities for blue/purple teams.
Document every artifact, IOC, and TTP for post-engagement knowledge transfer.
Prioritize OpSec while intentionally creating observable signals.


Phase 0: Preparation & Resource Development
Goal: Build resilient, attributable infrastructure.
Tools & Techniques:

Terraform + Ansible – IaC for redirectors and C2 servers.
Docker / Kubernetes – Containerized C2 (private registry).
AWS/Azure/GCP CLI – Cloud infrastructure with least-privilege roles.
Git + GitHub (private) – Version control, avoid committing secrets.
Chisel (preferred) or self-hosted Ngrok alternative – Tunneling.
OpenSSL / Stunnel – Valid certificates and traffic encryption.

OpSec: Rotate domains/IPs, use private repos, least-privilege IAM.
Defender Deliverable: Full infrastructure IOC list (domains, cert fingerprints, cloud logs).

Phase 1: Reconnaissance
Goal: Map targets while generating tunable network/DNS noise.
Network Scanning:

Primary: RustScan or Nmap (-T2, decoys, randomized ports).
High-speed baseline: Masscan (rate-limited, authorized only).

DNS & Subdomain Enumeration:

Amass (passive-first) → Subfinder → Assetfinder.
Passive: theHarvester, Sublist3r, Recon-ng.
OSINT: Shodan/Censys (API, rate-limited).

Web Reconnaissance:

Burp Suite (custom UA, timing) + OWASP ZAP.
Directory brute: Ffuf or Feroxbuster (delays, custom wordlists).
CMS: Wpscan (if applicable).

Wireless (if in scope):

Kismet (passive) → Aircrack-ng suite.

Defender Value: Share PCAPs, DNS query logs, and scan patterns.

Phase 2: Initial Access
Goal: Multiple realistic entry points.
Phishing & Social Engineering:

Gophish (custom domains, templates, HTML smuggling).

Exploitation:

Metasploit (custom payloads only) + MSFVenom.
SQLMap (tamper scripts, delays) for web apps.
Password attacks: Hydra / Medusa (rate-limited, jitter).

Defender Deliverable: Phishing campaign metrics, malicious document samples.

Phase 3: Execution
Goal: Establish initial foothold with layered evasion.
Primary C2 Frameworks (priority order):

Sliver (Go) – Best OpSec baseline.
Havoc – Strong sleep obfuscation & syscalls.
Mythic or heavily customized Cobalt Strike.

Execution Techniques:

PowerShell (encoded, AMSI bypass).
LOLBins: Rundll32, Regsvr32, MSHTA, Certutil, Bitsadmin, WMIC.
Reflective DLL Injection + Process Hollowing.
Netcat / Socat (encrypted via Stunnel).

Simulation: Deploy stealth variant + noisy default variant.

Phase 4: Persistence
Goal: Multiple mechanisms with varying visibility.
Windows:

Preferred: WMI Event Subscription, COM Hijacking, DLL Side-loading.
Noisy baseline: Registry Run Keys, Scheduled Tasks, Services.

Linux:

Systemd Timers (preferred), Cron, rc.local.

C2 Persistence:

Custom profiles in Sliver/Havoc/Mythic.

Defender Deliverable: Removal scripts + enumeration commands.

Phase 5: Privilege Escalation
Goal: Generate credential and kernel telemetry.
Windows:

Rubeus (Kerberoasting/AS-REP).
UAC bypass: SweetPotato variants.
Mimikatz (custom build only, in-memory).

Linux:

SUID binaries, Capabilities, Kernel exploits (if unpatched).

Defender Value: LSASS access attempts, Kerberos logs, UAC events.

Phase 6: Defense Evasion
Goal: Stress EDR/AV and logging.
Techniques:

AMSI/ETW bypass, indirect syscalls, NTDLL unhooking.
wevtutil + SDelete (log clearing, with caution).
Stunnel / OpenSSL for traffic obfuscation.
Sleep obfuscation (Ekko-style in Havoc).

Defender Deliverable: Evasion success timeline and bypassed controls.

Phase 7: Credential Access & Discovery
Credential Access:

Rubeus, custom Mimikatz, LaZagne, Procdump, SecretsDump.
Offline cracking: Hashcat + John the Ripper.

Discovery:

SharpHound / BloodHound.
LOLBins: WMIC, net, tasklist, PowerView, Impacket.


Phase 8: Lateral Movement
Windows:

Preferred: WMIExec, WinRM, Impacket.
Noisy: PsExec, CrackMapExec.

Linux:

SSH (key-based), SCP, RSYNC.


Phase 9: Collection & Exfiltration
Collection:

PowerShell / Python scripts.
Limited: Frida screenshots (research mode).

Exfiltration:

Chisel, SCP, Curl / Wget (encrypted).
LOLBins: Certutil, Bitsadmin.
Fallback: DNSCat / Iodine (heavily obfuscated).


Phase 10: Impact & Cleanup
Simulated Impact:

hping3 / Slowloris (authorized DoS only).
Ransomware note drop (no real encryption).

Cleanup:

SDelete, Shred, timestomping, log clearing.


Purple Team Deliverables (Maximum Defensive Knowledge Transfer)

Full ATT&CK Navigator layer with executed techniques.
Raw telemetry samples (Sysmon, EDR JSON, PCAPs).
Comprehensive IOC repository (hashes, domains, mutexes, registry keys).
“Stealth vs Noisy” comparison matrix.
Recommended detection rules (Sigma/YARA).
Joint debrief playbook with gap analysis.
Tool substitution examples used during the test.


OpSec & Simulation Rules

Never use default configurations in production.
Always test in isolated lab first.
Maintain separate stealth/noisy implant sets.
Operate during business hours with jitter.
Rotate infrastructure aggressively.
Document every command for reproducibility.

This plan directly maps to the OpsecAI Offensive Tool Reference while ensuring every major tool category is exercised. It gives defenders the richest possible dataset for improving detection, hunting, and response.