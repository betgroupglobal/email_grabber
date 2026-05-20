Offensive Guide for Penetration Testers: Complete Attack Simulation with Maximum Defensive Value
“Purple Team Red Teaming” – 2026 Edition
Purpose: This guide helps authorized red teamers design and execute realistic, end-to-end adversary simulations that stress-test modern defenses while providing defenders with the highest possible signal and learning opportunities. Every phase is engineered to generate detectable (and non-detectable) artifacts so blue/purple teams can improve detection, response, and resilience.
Core Principles for High-Value Simulations

Assume Breach + Full Kill Chain – Always emulate realistic dwell time, not just initial access.
Layered OpSec with Intentional Noise – Use stealth techniques, but also run noisier variants so defenders can tune their alerts.
Document Everything – Provide defenders with full TTP matrix, IOCs, and detection opportunities after each phase.
Debrief-Driven – End every engagement with a joint purple team review.
Legal & Scoped – Rules of Engagement (RoE) must explicitly allow simulation of these techniques.


Full Attack Simulation Workflow (MITRE ATT&CK Aligned)
Phase 0: Preparation & Infrastructure (Resource Development)

Build Custom Infrastructure
Use Terraform + private Git repos for redirectors.
Provision burnable domains, valid EV/OV certificates.
Set up C2 servers with domain fronting / Cloudfront / Azure Front Door.

Implant Generation
Generate multiple variants per framework (clean + noisy).
Compile with different obfuscation levels (Rust/Go preferred over C#).

Lab Validation
Test against latest Defender for Endpoint, CrowdStrike Falcon, SentinelOne Singularity, Palo Alto Cortex.


Defender Deliverable: Share infrastructure IOCs (domains, cert fingerprints, redirector IPs) post-engagement.

Phase 1: Initial Access (TA0001)
Simulate multiple vectors for comprehensive coverage:

Phishing (Gophish + custom templates + HTML smuggling).
Malicious documents (macro + DDE + Follina-style).
Supply-chain / trusted binary proxying.
Public-facing application exploit (if in scope).

OpSec Variations:

Low & slow (1–2 weeks).
Loud “spray and pray” for detection tuning.

Defender Focus: Email gateway, attachment sandboxing, user behavior analytics.

Phase 2: Execution & Defense Evasion (TA0002 + TA0005)
Core Techniques to Simulate:

In-Memory Execution Only (Reflective DLL, Process Hollowing, APC Injection).
Indirect Syscalls + NTDLL Unhooking.
AMSI/ETW Bypass + Patching.
LOLBin Chains (rundll32 → certutil → bitsadmin → mshta).
Sleep Obfuscation (Ekko / Gargoyle / FOLIAGE).

Recommended Frameworks (2026 Priority Order):

Havoc – Best built-in evasion suite.
Sliver (Go) – Excellent for stealth + multi-protocol.
Custom Mythic agents or Nighthawk.
Heavily modified Cobalt Strike (only as baseline for comparison).

Simulation Tip: Deploy both highly evasive and default-configuration implants so defenders see the difference in detection rates.

Phase 3: Persistence (TA0003)
Simulate multiple mechanisms ranked by stealth:

WMI Event Subscriptions (high value).
COM Hijacking / DLL Side-loading.
Scheduled Tasks + Registry Run keys (noisy baseline).
Systemd timers / Cron (Linux).
Kernel callbacks / BYOVD (if in scope and authorized).

Defender Deliverable: Full list of persistence artifacts + removal scripts.

Phase 4: Privilege Escalation (TA0004)

Token manipulation, UAC bypasses (SweetPotato variants).
Kerberoasting / AS-REP roasting.
Kernel exploits (only if unpatched systems exist).

Simulation Rule: Attempt escalation on every compromised host to generate maximum telemetry.

Phase 5: Credential Access (TA0006)

LSASS dumping (custom Mimikatz alternatives).
DPAPI / Browser credential theft.
Kerberos ticket attacks (Rubeus).
Password spraying / credential stuffing (limited).

Defender Focus: Credential Guard, LSA Protection, Protected Process Light.

Phase 6: Discovery & Lateral Movement (TA0007 + TA0008)

SharpHound / BloodHound collection (run in stages).
WMIExec / WinRM / SMBExec.
RDP / SSH key theft.
Living-off-the-Land (PowerShell, net, dsquery).

Key Simulation: Perform both noisy enumeration and stealthy “targeted only” movement.

Phase 7: Collection & Exfiltration (TA0009 + TA0010)

Screenshot / keylogging (limited duration).
File staging via trusted services (OneDrive, SharePoint, GitHub).
DNS / HTTPS / WireGuard exfil with jitter.

Defender Value: Exfil volume, timing, and destination analysis.

Phase 8: Command & Control (TA0011) – Deep Evasion Focus
Primary Evasion Tactics to Test:









































TacticImplementationDetection Surface CreatedDefensive Learning OpportunityMalleable / Procedural C2Custom profiles mimicking Office 365, Slack, GitHubJitter analysis, TLS fingerprinting, behavioral NDRTune anomaly baselinesTrusted Service RoutingMicrosoft Graph API, Discord webhooksCloud API abuse detectionIdentity threat detectionSleep + Memory ObfuscationEkko + stack spoofingMemory scanner timing attacksAdvanced EDR memory huntingProtocol DiversityHTTPS → WireGuard → DNS fallbackProtocol anomaly rulesMulti-protocol correlationIndirect SyscallsFull syscall evasionKernel telemetry gapsSyscall monitoring maturity
Execution Order Recommendation:

Start with stealthiest implant (Sliver/Havoc hardened).
After 48–72 hours, introduce noisier variant.
Attempt C2 migration between profiles.


Phase 9: Impact & Cleanup (TA0040)

Simulated ransomware note (no actual encryption).
Full artifact cleanup + timestomping.
Optional: Leave “golden” IOCs for blue team training.


Post-Engagement Purple Team Package (Maximum Defensive Value)
Deliver to blue team:

Full ATT&CK Navigator heatmap of executed techniques.
Raw telemetry samples (Sysmon, EDR exports).
IOC list (hashes, domains, mutexes, registry keys).
Detection gap analysis.
Recommended Sigma / YARA / hunting queries.
Recorded timeline of evasion success/failure.
“What worked vs what got caught” matrix.


OpSec & Safety Rules for Red Teamers

Never use default tool configurations in production.
Maintain separate “stealth” and “noisy” implant sets.
Always have an escape hatch (kill switch).
Document every command for reproducibility.
Rotate infrastructure aggressively.

Final Recommendation: Structure every engagement as a multi-week campaign with at least two distinct adversary personas (e.g., sophisticated nation-state vs. ransomware affiliate) to give defenders exposure to different TTP maturity levels.

Would you like me to expand any section into a step-by-step playbook?
Examples:

Full Havoc hardened deployment workflow
Sliver multi-protocol C2 setup
Purple team debrief template
Complete ATT&CK Navigator layer export
Detection rule repository for defenders

Just specify the focus area and I’ll deliver the detailed implementation guide