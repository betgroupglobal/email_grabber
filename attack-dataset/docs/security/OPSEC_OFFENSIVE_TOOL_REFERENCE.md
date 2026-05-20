# OpsecAI Offensive Tool Reference

**Comprehensive catalog of offensive security tools referenced in the attack dataset, organized by MITRE ATT&CK tactics with OpSec considerations.**

---

## Table of Contents
- [Reconnaissance](#reconnaissance)
- [Resource Development](#resource-development)
- [Initial Access](#initial-access)
- [Execution](#execution)
- [Persistence](#persistence)
- [Privilege Escalation](#privilege-escalation)
- [Defense Evasion](#defense-evasion)
- [Credential Access](#credential-access)
- [Discovery](#discovery)
- [Lateral Movement](#lateral-movement)
- [Collection](#collection)
- [Exfiltration](#exfiltration)
- [Impact](#impact)
- [Command & Control](#command--control)

---

## Reconnaissance

### Network Scanning

| Tool | Description | OpSec Considerations | Detection Methods |
|------|-------------|----------------------|-------------------|
| **Nmap** | Port scanner, OS detection, service versioning | Default scans generate high network noise; customize timing (`-T2`), use decoys, randomize source ports if possible | IDS/IPS signature detection, firewall logs, netflow anomalies |
| **Masscan** | High-speed port scanner (10M packets/sec) | Extremely noisy; use only on authorized targets, consider rate limiting, use from distributed infrastructure | Massive spike in connection attempts, SYN flood detection |
| **Zmap** | Internet-wide scanner | Only for authorized research; use from cloud with proper attribution | ISP abuse reports, global scan detection |
| **RustScan** | Modern port scanner (Rust-based) | Similar to Nmap but faster; same OpSec considerations | Same as Nmap |
| **UnicornScan** | Port scanner with advanced features | Customizable; avoid default aggressive timing | Connection pattern analysis |
| **Angry IP Scanner** | GUI network scanner | Generates ARP noise; use in isolated networks | ARP table flooding detection |
| **NetDiscover** | Active/passive network discovery via ARP | Passive mode is stealthier; active ARP scanning triggers host-based detection | ARP cache poisoning alerts |
| **ARPing** | ARP discovery tool | Can be detected by ARP monitoring; use sparingly | ARP storm detection |

### DNS & Subdomain Enumeration

| Tool | Description | OpSec Considerations | Detection Methods |
|------|-------------|----------------------|-------------------|
| **Amass** | Subdomain enumeration (OWASP) | Use DNSSEC validation; rate limit queries; consider passive mode | High DNS query volume, unusual DNS patterns |
| **Subfinder** | Subdomain discovery (Go) | Similar to Amass; use passive sources first | DNS query volume |
| **Sublist3r** | Subdomain enumeration via search engines | Passive-only (searches) — lower detection risk | Search engine API rate limits |
| **Subjack** | Subdomain takeover scanner | Only scans discovered subdomains; limited noise | DNS query patterns |
| **Assetfinder** | Asset discovery tool | Rate limit queries; use passive sources | DNS query volume |
| **DNSenum** | DNS enumeration script | Older tool; consider Amass instead | DNS query patterns |
| **DNSrecon** | DNS reconnaissance suite | Use with care; limit query rate | DNS query volume |
| **DNSDumpster** | DNS record lookup service | Passive service; query rate limits | Service API limits |
| **theHarvester** | OSINT via search engines | Use passive sources only; rotate user agents | Search engine API limits |
| **Maltego** | Visual OSINT and link analysis | Passive mode recommended; avoid active scanning | Unusual data access patterns |
| **Recon-ng** | Modular reconnaissance framework | Use passive modules first; rate limit active modules | API rate limits, DNS patterns |
| **Fierce** | DNS enumeration tool | Older; consider Amass/Subfinder | DNS query patterns |
| **Shodan** | Internet-connected device search | Use API with rate limits; consider official account | API usage patterns, scan detection |
| **Censys** | Internet search engine | Same as Shodan; use official API | API usage patterns |
| **ZoomEye** | Chinese IoT search engine | Use API; rotate IPs if scanning | API rate limits |
| **BinaryEdge** | Internet scan search engine | API-based; rate limit queries | API usage patterns |
| **Fofa** | Chinese search engine | Use API; rotate IPs | API rate limits |

### Web Reconnaissance

| Tool | Description | OpSec Considerations | Detection Methods |
|------|-------------|----------------------|-------------------|
| **Burp Suite** | Web app security testing | **High detection risk** — customize User-Agent, match target traffic patterns, use Burp Community with custom headers | WAF signature detection, unusual UA strings |
| **OWASP ZAP** | Web app security scanner | Similar to Burp; customize UA and timing | WAF detection, scan patterns |
| **Nikto** | Web server scanner | Very noisy; high request volume; modify delay between requests | High request rate, distinct UA |
| **Dirb** | Directory brute-forcing | Use custom wordlists, add random delays, rotate user agents | Brute-force detection |
| **Gobuster** | Directory brute-forcing (Go) | Faster than Dirb; same OpSec concerns | Brute-force detection |
| **Feroxbuster** | Directory brute-forcing (Rust) | Fast; use with timing and custom wordlists | Brute-force detection |
| **Wfuzz** | Web fuzzer | Use with rate limiting and custom payloads | Fuzzing patterns |
| **Ffuf** | Fast web fuzzer | Similar to Wfuzz; rate limit requests | Fuzzing patterns |
| **Wpscan** | WordPress scanner | Only if WordPress detected; use with discretion | WordPress-specific patterns |
| **Joomscan** | Joomla scanner | Only if Joomla detected | Joomla-specific patterns |
| **CMSmap** | CMS scanner | Only if CMS detected | CMS-specific patterns |

### Wireless Reconnaissance

| Tool | Description | OpSec Considerations | Detection Methods |
|------|-------------|----------------------|-------------------|
| **Aircrack-ng** | WEP/WPA cracking suite | Monitor mode is passive; deauth attacks are loud | WIDS detection, deauth floods |
| **Kismet** | Wireless sniffer/intrusion detection | Passive monitoring is stealthy | Wireless IDS |
| **Wireshark** | Packet analyzer | Passive capture is safer; avoid injection | Network tap detection |
| **tcpdump** | Packet capture | Same as Wireshark | Network tap detection |
| **Bettercap** | Network attack tool | **High detection risk** — use sparingly; MITM is very detectable | ARP spoofing detection, MITM alerts |
| **Ettercap** | MITM/sniffing | **Very detectable** — ARP poisoning triggers WIDS | ARP poisoning, MITM alerts |
| **HackRF** | SDR (Software Defined Radio) | Passive RX is stealthy; TX is detectable | RF monitoring, spectrum analysis |
| **RTL-SDR** | Cheap SDR dongle | Passive RX only for recon | RF spectrum anomalies |
| **GNURadio** | SDR framework | Use passive RX for recon | RF spectrum anomalies |

---

## Resource Development

### Infrastructure Setup

| Tool | Description | OpSec Considerations | Detection Methods |
|------|-------------|----------------------|-------------------|
| **Docker** | Container platform | Use private registry; avoid default image names | Container registry access logs |
| **Kubernetes** | Container orchestration | Use private clusters; avoid public cloud if possible | Cloud provider API access |
| **AWS CLI** | AWS command-line tools | Use IAM roles with least privilege; rotate credentials | CloudTrail logs |
| **Azure CLI** | Azure command-line tools | Same as AWS CLI | Azure Monitor logs |
| **GCP CLI** | Google Cloud CLI | Same as AWS CLI | Cloud Audit Logs |
| **Terraform** | Infrastructure as Code | Use private state backend; avoid committing secrets | Cloud provider API access |
| **Ansible** | Automation tool | Use vault for secrets; avoid hardcoded credentials | Configuration management logs |
| **GitHub Actions** | CI/CD automation | Use self-hosted runners for sensitive operations | CI/CD pipeline logs |

### Domain & Infrastructure

| Tool | Description | OpSec Considerations | Detection Methods |
|------|-------------|----------------------|-------------------|
| **GitHub** | Code hosting | Use private repos; avoid committing secrets | Repository access logs |
| **Git** | Version control | Use private repos; avoid committing secrets | Repository access logs |
| **Ngrok** | Tunneling service | **High attribution risk** — public tunnels create audit trails; use custom domains or private infrastructure | Tunnel detection, domain reputation |
| **Chisel** | Tunneling tool | Better than public ngrok; still detectable | Tunnel detection |
| **DNSCat** | DNS tunneling | Obfuscate queries; use legitimate domains | DNS query entropy analysis |
| **Iodine** | DNS tunneling | Same as DNSCat | DNS entropy analysis |

---

## Initial Access

### Exploitation Frameworks

| Tool | Description | OpSec Considerations | Detection Methods |
|------|-------------|----------------------|-------------------|
| **Metasploit** | Exploitation framework | **Highly signatured** — use custom payloads, encode shellcode, modify default templates | AV/EDR signature detection, C2 beacons |
| **MSFConsole** | Metasploit CLI | Same as Metasploit | Same as Metasploit |
| **MSFVenom** | Payload generator | Generate custom templates; use encoding and packing | AV signature detection |
| **Empire** | PowerShell post-exploitation | **Heavily flagged** — use custom stagers, modify C2 profiles | PowerShell execution logs, C2 beacons |
| **PoshC2** | PowerShell C2 | Similar to Empire; customize profiles | PowerShell logs, C2 beacons |
| **Koadic** | C2 framework | Similar to Empire; customize profiles | C2 beacons |
| **Sliver** | C2 framework (Go) | Better OpSec than PowerShell frameworks; still detectable | C2 beacons, process behavior |
| **Havoc** | C2 framework (C#) | Similar to Sliver | C2 beacons |
| **Covenant** | .NET C2 framework | **Signatured** — use custom builds | C2 beacons, .NET behavior |
| **Mythic** | C2 framework | Multi-agent; use with caution | C2 beacons |
| **Rattler** | C2 framework | Older; similar concerns | C2 beacons |
| **Searchsploit** | Exploit search | Use locally; avoid public queries | API usage patterns |
| **ExploitDB** | Exploit database | Use offline copy if possible | API usage patterns |

### Phishing & Social Engineering

| Tool | Description | OpSec Considerations | Detection Methods |
|------|-------------|----------------------|-------------------|
| **SET** (Social-Engineer Toolkit) | Phishing framework | Use custom templates; avoid default domains | Email filtering, domain reputation |
| **Gophish** | Phishing server | Use custom domains; rotate infrastructure | Domain reputation, email filtering |
| **King Phisher** | Phishing automation | Same as Gophish | Domain reputation |
| **GoPhish** | Phishing framework | Same as Gophish | Domain reputation |

### Web Exploits

| Tool | Description | OpSec Considerations | Detection Methods |
|------|-------------|----------------------|-------------------|
| **SQLMap** | SQL injection tool | **Highly signatured** — modify User-Agent, add random delays, use tamper scripts | WAF signature detection, SQL injection patterns |
| **Havij** | SQL injection tool | **Commercially signatured** — use alternative or custom scripts | WAF signature detection |
| **JSQL** | SQL injection tool | Similar to SQLMap | SQL injection patterns |
| **Absinthe** | SQL injection tool | Older; similar concerns | SQL injection patterns |
| **NoSQLMap** | NoSQL injection tool | Similar to SQLMap | NoSQL query patterns |
| **BBQSQL** | Blind SQL injection tool | Similar to SQLMap | Blind SQL patterns |
| **Dirb** | Directory brute-forcing | See Web Recon section | Brute-force detection |

### Password Attacks

| Tool | Description | OpSec Considerations | Detection Methods |
|------|-------------|----------------------|-------------------|
| **Hydra** | Password brute-forcer | **High detection risk** — use with rate limiting, random delays, rotate source IPs | Brute-force detection, authentication logs |
| **Medusa** | Password brute-forcer | Similar to Hydra | Brute-force detection |
| **Ncrack** | Password brute-forcer | Similar to Hydra | Brute-force detection |
| **Patator** | Password brute-forcer | Similar to Hydra | Brute-force detection |
| **THC-Hydra** | Password brute-forcer | Same as Hydra | Brute-force detection |
| **Crowbar** | Password brute-forcer | Similar to Hydra | Brute-force detection |

---

## Execution

### Command & Control

| Tool | Description | OpSec Considerations | Detection Methods |
|------|-------------|----------------------|-------------------|
| **Netcat** | Network utility (reverse shell) | **Commonly flagged** — encode traffic, use legitimate protocols | Unusual network connections, shell-like behavior |
| **Socat** | Network utility (multipurpose) | Similar to Netcat | Network anomalies |
| **Telnet** | Remote shell | **Plaintext** — avoid if possible; use SSH with key auth | Plaintext credentials in transit |
| **OpenSSL** | SSL/TLS toolkit | Use for encrypted C2; generate valid certificates | Certificate validation |
| **Stunnel** | SSL tunneling | Good for encrypting C2 traffic | Certificate validation |
| **PowerShell** | Windows automation | **Heavily monitored** — use encoded commands, AMSI bypass, LOLBins | PowerShell logs, AMSI alerts |
| **Bash** | Unix shell | Use with encoded commands; avoid direct execution | Shell command logs |
| **CMD** | Windows command prompt | Similar to PowerShell concerns | Command execution logs |
| **Python** | Scripting language | Use with encoded/obfuscated scripts | Python process execution |
| **Perl** | Scripting language | Similar to Python | Process execution |
| **Ruby** | Scripting language | Similar to Python | Process execution |
| **PHP** | Scripting language | Similar to Python | Process execution |

### Process Injection

| Tool | Description | OpSec Considerations | Detection Methods |
|------|-------------|----------------------|-------------------|
| **Frida** | Dynamic instrumentation | Use for research only; avoid in production if possible | Process injection detection |
| **DLL Injection** | DLL loading technique | Use signed binaries or LOLBins | EDR telemetry |
| **Process Hollowing** | Process hollowing | Detectable by EDR | EDR telemetry |
| **Reflective DLL Injection** | In-memory DLL loading | **Bypasses disk-based detection** but detectable via memory scanning | Memory scanning, behavior analysis |

### File Execution

| Tool | Description | OpSec Considerations | Detection Methods |
|------|-------------|----------------------|-------------------|
| **Rundll32** | DLL execution | LOLBin; use for executing DLLs | DLL execution logs |
| **Regsvr32** | DLL registration | LOLBin; similar to Rundll32 | DLL execution logs |
| **MSHTA** | HTML Application | LOLBin; used for script execution | Script execution logs |
| **Certutil** | Certificate utility | LOLBin; used for file download/execution | File download logs |
| **Bitsadmin** | BITS client | LOLBin; used for file download | File download logs |
| **WMIC** | WMI command-line | LOLBin; used for execution | WMI event logs |

---

## Persistence

### Windows Persistence

| Tool | Description | OpSec Considerations | Detection Methods |
|------|-------------|----------------------|-------------------|
| **Registry Run Keys** | Startup persistence | **High visibility** — EDR monitors Run keys; use COM hijacking instead | Registry monitoring |
| **Scheduled Tasks** | Scheduled execution | **Easily enumerated** — use WMI event subscriptions instead | Task enumeration |
| **Services** | Service persistence | **Monitored** — use service DLL hijacking | Service enumeration |
| **WMI Event Subscription** | Persistence mechanism | **Better OpSec** than scheduled tasks; still detectable | WMI event logs |
| **COM Hijacking** | DLL hijacking | **Better OpSec** than Run keys | DLL loading logs |
| **DLL Side-loading** | DLL hijacking | Similar to COM hijacking | DLL loading logs |
| **Startup Folder** | Startup persistence | **Trivially detected** — avoid | File system monitoring |
| **Cron Jobs** | Scheduled execution (Linux) | **Logged and monitored** — use systemd timers instead | Cron log monitoring |
| **Systemd Timers** | Scheduled execution (Linux) | **Better OpSec** than cron | Systemd journal logs |
| **rc.local** | Boot script (Linux) | **Monitored** — use systemd instead | File integrity monitoring |
| **Bash Profile** | Shell profile persistence | **Monitored** — avoid if possible | File integrity monitoring |

### C2 Persistence

| Tool | Description | OpSec Considerations | Detection Methods |
|------|-------------|----------------------|-------------------|
| **Cobalt Strike** | C2 framework | **Signatured** — use custom Malleable C2 profiles | C2 beacon signatures |
| **Empire** | PowerShell C2 | **Heavily flagged** — use custom stagers | PowerShell logs, C2 beacons |
| **PoshC2** | PowerShell C2 | Similar to Empire | Same as Empire |
| **Sliver** | C2 framework (Go) | **Better OpSec** than PowerShell frameworks | C2 beacons |
| **Havoc** | C2 framework (C#) | Similar to Sliver | C2 beacons |
| **Covenant** | .NET C2 framework | **Signatured** — use custom builds | C2 beacons, .NET behavior |
| **Mythic** | C2 framework | Multi-agent; customize profiles | C2 beacons |

---

## Privilege Escalation

### Windows Privilege Escalation

| Tool | Description | OpSec Considerations | Detection Methods |
|------|-------------|----------------------|-------------------|
| **Mimikatz** | Credential dumping | **Highly signatured** — use custom builds or alternative tools | Credential access alerts |
| **Rubeus** | Kerberos manipulation | Similar to Mimikatz | Kerberos event logs |
| **Kekeo** | Kerberoasting tool | Similar to Rubeus | Kerberos event logs |
| **TgtDeleg** | Kerberos delegation | Similar to Rubeus | Kerberos event logs |
| **Kerberoast** | Kerberos ticket cracking | Similar to Rubeus | Kerberos event logs |
| **AskTSP** | AS-REP roasting | Similar to Rubeus | Kerberos event logs |
| **AutoElevate** | UAC bypass | Detectable by EDR | UAC bypass alerts |
| **SweetPotato** | UAC bypass | Detectable by EDR | UAC bypass alerts |
| **JuicyPotato** | UAC bypass | Detectable by EDR | UAC bypass alerts |
| **RottenPotato** | UAC bypass | Detectable by EDR | UAC bypass alerts |
| **PrintNightmare** | Print spooler exploit | CVE-based; patch if possible | Exploit detection |
| **ZeroLogon** | Netlogon exploit | CVE-based; patch if possible | Exploit detection |
| **PowerShell Empire** | UAC bypass modules | Similar to above | PowerShell logs |
| **Sherlock** | Windows vulnerability scanner | Use for recon only | System enumeration |

### Linux Privilege Escalation

| Tool | Description | OpSec Considerations | Detection Methods |
|------|-------------|----------------------|-------------------|
| **SUID binaries** | SUID file execution | **Monitored** — use custom SUID binaries if possible | SUID file enumeration |
| **Capabilities** | Linux capabilities | **Monitored** — use carefully | Capability enumeration |
| **Kernel exploits** | Kernel vulnerabilities | CVE-based; patch if possible | Exploit detection |
| **Dirty Cow** | Kernel exploit | CVE-based; patch if possible | Exploit detection |
| **CVE-2016-5195** | SUID exploit | CVE-based; patch if possible | Exploit detection |

---

## Defense Evasion

### Anti-Virus/EDR Evasion

| Tool | Description | OpSec Considerations | Detection Methods |
|------|-------------|----------------------|-------------------|
| **PowerShell Empire** | Evasion modules | **Signatured** — use custom obfuscation | PowerShell logs |
| **PoshC2** | Evasion modules | Similar to Empire | Same as Empire |
| **AMSI Bypass** | AMSI bypass | Detectable by updated EDR | AMSI alerts |
| **PowerSploit** | PowerShell post-exploitation | **Signatured** — use custom versions | PowerShell logs |
| **SharpHound** | AD enumeration | Use for recon; detectable | LDAP queries |
| **BloodHound** | AD visualization | Use for recon; detectable | LDAP queries |
| **Rubeus** | Kerberos manipulation | Use for credential access; detectable | Kerberos logs |
| **Mimikatz** | Credential dumping | **Highly signatured** | Credential access alerts |
| **Process Hacker** | Process manipulation | Use for recon; detectable | Process monitoring |
| **Process Explorer** | Process monitoring | Use for recon; detectable | Process monitoring |
| **Autoruns** | Startup enumeration | Use for recon; detectable | System enumeration |
| **TCPView** | Network enumeration | Use for recon; detectable | Network monitoring |
| **GMER** | Rootkit detection | Use for recon; detectable | System monitoring |
| **RootkitRevealer** | Rootkit detection | Use for recon; detectable | System monitoring |

### Log Clearing

| Tool | Description | OpSec Considerations | Detection Methods |
|------|-------------|----------------------|-------------------|
| **wevtutil** | Windows event log clearing | **Monitored** — use with caution | Event log deletion alerts |
| **cipher** | File deletion | **Monitored** — use securely | File deletion logs |
| **SDelete** | Secure file deletion | **Better than delete** but still detectable | File deletion logs |
| **Shred** | Secure file deletion (Linux) | Similar to SDelete | File deletion logs |
| **DBAN** | Disk wiping | Use only for full system destruction | Disk activity |
| **BleachBit** | System cleaning | Use for routine cleanup | File deletion logs |
| **CCleaner** | System cleaning | Similar to BleachBit | File deletion logs |
| **Privazer** | Privacy cleaner | Similar to BleachBit | File deletion logs |
| **Evidence Eliminator** | Anti-forensics tool | Use with extreme caution | File deletion logs |

### Traffic Obfuscation

| Tool | Description | OpSec Considerations | Detection Methods |
|------|-------------|----------------------|-------------------|
| **Stunnel** | SSL tunneling | Use for encrypting C2 traffic | Certificate validation |
| **OpenSSL** | SSL/TLS toolkit | Generate valid certificates | Certificate validation |
| **Ngrok** | Tunneling | **High attribution risk** — use private infrastructure | Tunnel detection |
| **Chisel** | Tunneling | Better than ngrok; still detectable | Tunnel detection |
| **DNSCat** | DNS tunneling | Obfuscate queries; use legitimate domains | DNS entropy analysis |
| **Iodine** | DNS tunneling | Same as DNSCat | DNS entropy analysis |

---

## Credential Access

### Credential Dumping

| Tool | Description | OpSec Considerations | Detection Methods |
|------|-------------|----------------------|-------------------|
| **Mimikatz** | Credential dumping | **Highly signatured** — use custom builds or alternative tools | Credential access alerts |
| **LaZagne** | Credential recovery | Similar to Mimikatz | Credential access alerts |
| **Procdump** | Process memory dump | **LOLBin** — use for credential extraction | Process memory access |
| **Rubeus** | Kerberos manipulation | Similar to Mimikatz | Kerberos event logs |
| **SharpKatz** | .NET Mimikatz | Similar to Mimikatz | Credential access alerts |
| **DPAPI** | DPAPI decryption | Use for credential extraction | DPAPI access |
| **Dploot** | DPAPI dumping | Similar to DPAPI | DPAPI access |
| **LSASecrets** | LSA secrets dumping | Similar to Mimikatz | LSA access |
| **SecretsDump** | Secrets dumping | Similar to Mimikatz | Credential access alerts |
| **Cachedump** | Cached credentials | Similar to Mimikatz | Credential access alerts |
| **Mimikittenz** | Mimikatz for LSA | Similar to Mimikatz | Credential access alerts |

### Password Cracking

| Tool | Description | OpSec Considerations | Detection Methods |
|------|-------------|----------------------|-------------------|
| **John the Ripper** | Password cracker | Use offline on captured hashes | High CPU usage |
| **Hashcat** | Password cracker | Use offline on captured hashes | High CPU/GPU usage |
| **oclHashcat** | GPU-accelerated Hashcat | Same as Hashcat | High GPU usage |
| **RainbowCrack** | Rainbow table cracker | Use offline; consider deprecated | High disk I/O |
| **Ophcrack** | Windows password cracker | Use offline | High CPU usage |
| **Cain** | Windows password cracker | Use offline | High CPU usage |
| **L0phtCrack** | Windows password cracker | Deprecated; use alternatives | High CPU usage |

---

## Discovery

### System Enumeration

| Tool | Description | OpSec Considerations | Detection Methods |
|------|-------------|----------------------|-------------------|
| **PowerShell** | Windows automation | Use encoded commands; AMSI bypass | PowerShell logs |
| **CMD** | Windows command prompt | Use with caution | Command execution logs |
| **WMIC** | WMI command-line | **LOLBin** — use for enumeration | WMI event logs |
| **net** | Network commands | **LOLBin** — use for enumeration | Network enumeration logs |
| **netstat** | Network statistics | **LOLBin** — use for enumeration | Network enumeration logs |
| **ipconfig** | IP configuration | **LOLBin** — use for enumeration | System enumeration |
| **route** | Routing table | **LOLBin** — use for enumeration | Network enumeration |
| **arp** | ARP table | **LOLBin** — use for enumeration | Network enumeration |
| **nslookup** | DNS lookup | **LOLBin** — use for enumeration | DNS query logs |
| **ping** | ICMP ping | **LOLBin** — use with rate limiting | ICMP flood detection |
| **tracert** | Trace route | **LOLBin** — use with rate limiting | Network path analysis |
| **netsh** | Network configuration | **LOLBin** — use for enumeration | Network enumeration |
| **sc** | Service control | **LOLBin** — use for enumeration | Service enumeration |
| **reg** | Registry editor | **LOLBin** — use for enumeration | Registry access logs |
| **tasklist** | Process list | **LOLBin** — use for enumeration | Process enumeration |
| **schtasks** | Scheduled tasks | **LOLBin** — use for enumeration | Task enumeration |
| **wevtutil** | Event log utility | **LOLBin** — use for enumeration | Event log access |
| **bash** | Unix shell | Use with encoded commands | Shell command logs |
| **ps** | Process list (Unix) | Use for enumeration | Process enumeration |
| **top** | Process monitor (Unix) | Use for enumeration | Process enumeration |
| **netdiscover** | Network discovery (Linux) | Use passive mode if possible | ARP scanning |

### Active Directory Enumeration

| Tool | Description | OpSec Considerations | Detection Methods |
|------|-------------|----------------------|-------------------|
| **SharpHound** | AD enumeration | Use for recon; detectable | LDAP queries |
| **BloodHound** | AD visualization | Use for recon; detectable | LDAP queries |
| **PowerView** | PowerShell AD enumeration | Use encoded commands | PowerShell logs, LDAP queries |
| **ADExplorer** | AD explorer (GUI) | Use for recon; detectable | LDAP queries |
| **LDAPSearch** | LDAP query tool | Use with caution | LDAP query logs |
| **LDAPDomainDump** | AD domain dumping | Use for recon; detectable | LDAP query logs |
| **Impacket** | Python AD tools | Use for recon; detectable | LDAP queries |

---

## Lateral Movement

### Windows Lateral Movement

| Tool | Description | OpSec Considerations | Detection Methods |
|------|-------------|----------------------|-------------------|
| **CrackMapExec** | Lateral movement tool | **Detectable** — use with stealthier alternatives like WMI | SMB/WinRM logs |
| **PsExec** | Remote execution | **Heavily monitored** — use WMI or DCOM instead | Service creation logs |
| **WMIC** | WMI command-line | **LOLBin** — use for lateral movement | WMI event logs |
| **WinRM** | Remote shell | **LOLBin** — better than PsExec | WinRM logs |
| **SMBClient** | SMB client | Use for file transfer; avoid for execution if possible | SMB access logs |
| **SMBExec** | SMB execution | Similar to PsExec | SMB/WinRM logs |
| **Impacket** | Python lateral movement tools | Use with stealthier techniques | SMB/WinRM logs |
| **WMIExec** | WMI execution | **LOLBin** — better than PsExec | WMI event logs |
| **WMIPRVSE** | WMI execution | Similar to WMIExec | WMI event logs |
| **WMIQuery** | WMI query | **LOLBin** — use for enumeration | WMI event logs |

### Linux Lateral Movement

| Tool | Description | OpSec Considerations | Detection Methods |
|------|-------------|----------------------|-------------------|
| **SSH** | Secure shell | Use key-based auth; avoid password auth | SSH access logs |
| **SCP** | Secure copy | Use key-based auth | SSH access logs |
| **SFTP** | Secure FTP | Use key-based auth | SSH access logs |
| **RSYNC** | File sync | Use key-based auth | SSH access logs |

---

## Collection

### Data Collection

| Tool | Description | OpSec Considerations | Detection Methods |
|------|-------------|----------------------|-------------------|
| **PowerShell** | Windows automation | Use encoded commands; AMSI bypass | PowerShell logs |
| **Python** | Scripting language | Use with encoded/obfuscated scripts | Process execution |
| **Perl** | Scripting language | Similar to Python | Process execution |
| **Ruby** | Scripting language | Similar to Python | Process execution |
| **PHP** | Scripting language | Similar to Python | Process execution |
| **Node.js** | JavaScript runtime | Similar to Python | Process execution |
| **Go** | Go language | Similar to Python | Process execution |
| **Rust** | Rust language | Similar to Python | Process execution |

### Screenshot & Keylogging

| Tool | Description | OpSec Considerations | Detection Methods |
|------|-------------|----------------------|-------------------|
| **Frida** | Dynamic instrumentation | Use for research only | Process injection detection |
| **Screenshot** | Screen capture | Use sparingly; detectable by EDR | Screen capture API calls |
| **Keylogger** | Key logging | **Highly detectable** — avoid if possible | Keyboard hook detection |

---

## Exfiltration

### File Transfer

| Tool | Description | OpSec Considerations | Detection Methods |
|------|-------------|----------------------|-------------------|
| **Netcat** | Network utility | Use encrypted channels; avoid plaintext | Network anomalies |
| **Socat** | Network utility | Similar to Netcat | Network anomalies |
| **Telnet** | Remote shell | **Plaintext** — avoid if possible | Plaintext credentials |
| **OpenSSL** | SSL/TLS toolkit | Use for encrypting exfil traffic | Certificate validation |
| **Stunnel** | SSL tunneling | Good for encrypting C2 traffic | Certificate validation |
| **Ngrok** | Tunneling | **High attribution risk** — use private infrastructure | Tunnel detection |
| **Chisel** | Tunneling | Better than ngrok; still detectable | Tunnel detection |
| **SSH** | Secure shell | Use key-based auth; avoid password auth | SSH access logs |
| **SCP** | Secure copy | Use key-based auth | SSH access logs |
| **SFTP** | Secure FTP | Use key-based auth | SSH access logs |
| **RSYNC** | File sync | Use key-based auth | SSH access logs |
| **FTP** | File transfer | **Plaintext** — avoid if possible | Plaintext credentials |
| **TFTP** | Trivial FTP | **Plaintext** — avoid if possible | Network anomalies |
| **Wget** | File downloader | Use with caution | HTTP request logs |
| **Curl** | HTTP client | Use with caution | HTTP request logs |
| **Bitsadmin** | BITS client | **LOLBin** — used for file download | File download logs |
| **Certutil** | Certificate utility | **LOLBin** — used for file download | File download logs |
| **Regsvr32** | DLL registration | **LOLBin** — used for file download | File download logs |
| **Rundll32** | DLL execution | **LOLBin** — used for file download | File download logs |
| **MSHTA** | HTML Application | **LOLBin** — used for file download | File download logs |

### DNS Tunneling

| Tool | Description | OpSec Considerations | Detection Methods |
|------|-------------|----------------------|-------------------|
| **DNSCat** | DNS tunneling | Obfuscate queries; use legitimate domains | DNS entropy analysis |
| **Iodine** | DNS tunneling | Same as DNSCat | DNS entropy analysis |
| **DNS2TCP** | DNS tunneling | Same as DNSCat | DNS entropy analysis |

---

## Impact

### Denial of Service

| Tool | Description | OpSec Considerations | Detection Methods |
|------|-------------|----------------------|-------------------|
| **hping3** | IP packet generator | **Highly detectable** — use only for authorized testing | Network flood detection |
| **Slowloris** | DoS attack | **Detectable** — use only for authorized testing | Connection flood detection |
| **Masscan** | DoS/scanner | **Detectable** — use only for authorized testing | Network flood detection |

### Data Destruction

| Tool | Description | OpSec Considerations | Detection Methods |
|------|-------------|----------------------|-------------------|
| **Shred** | Secure file deletion | Use for evidence destruction only | File deletion logs |
| **Wipe** | Disk wiping | Use only for full system destruction | Disk activity |
| **DBAN** | Disk wiping | Use only for full system destruction | Disk activity |

---

## Command & Control

### C2 Frameworks

| Tool | Description | OpSec Considerations | Detection Methods |
|------|-------------|----------------------|-------------------|
| **Cobalt Strike** | C2 framework | **Signatured** — use custom Malleable C2 profiles | C2 beacon signatures |
| **Empire** | PowerShell C2 | **Heavily flagged** — use custom stagers | PowerShell logs, C2 beacons |
| **PoshC2** | PowerShell C2 | Similar to Empire | Same as Empire |
| **Sliver** | C2 framework (Go) | **Better OpSec** than PowerShell frameworks | C2 beacons |
| **Havoc** | C2 framework (C#) | Similar to Sliver | C2 beacons |
| **Covenant** | .NET C2 framework | **Signatured** — use custom builds | C2 beacons, .NET behavior |
| **Mythic** | C2 framework | Multi-agent; customize profiles | C2 beacons |
| **Rattler** | C2 framework | Older; similar concerns | C2 beacons |

### Tunneling

| Tool | Description | OpSec Considerations | Detection Methods |
|------|-------------|----------------------|-------------------|
| **Ngrok** | Tunneling | **High attribution risk** — use private infrastructure | Tunnel detection |
| **Chisel** | Tunneling | Better than ngrok; still detectable | Tunnel detection |
| **DNSCat** | DNS tunneling | Obfuscate queries; use legitimate domains | DNS entropy analysis |
| **Iodine** | DNS tunneling | Same as DNSCat | DNS entropy analysis |
| **Stunnel** | SSL tunneling | Use for encrypting C2 traffic | Certificate validation |
| **OpenSSL** | SSL/TLS toolkit | Generate valid certificates | Certificate validation |

---

## OpSec Best Practices by Tool Category

### General Rules
1. **Never use default configurations** — customize all tools
2. **Rotate infrastructure regularly** — domains, IPs, certificates
3. **Use encrypted channels** — HTTPS, SSH, TLS
4. **Avoid plaintext credentials** — use environment variables or vaults
5. **Limit rate and timing** — add random delays, jitter beacons
6. **Blend with normal traffic** — operate during business hours
7. **Clean up artifacts** — clear logs, delete temp files, wipe history
8. **Use LOLBins where possible** — leverage trusted system binaries
9. **Encode/obfuscate payloads** — avoid signature detection
10. **Test in isolated environment** — lab before production

### Tool-Specific OpSec Tips

**Metasploit**
- Use custom templates and encoders
- Modify default Malleable C2 profiles
- Use staged payloads with custom droppers
- Avoid default port 4444

**Burp Suite**
- Customize User-Agent header
- Match target site traffic patterns
- Use Burp Community with custom headers
- Add random delays between requests

**Nmap**
- Use `-T2` timing instead of `-T4`
- Add decoy hosts
- Randomize source ports
- Limit scan scope

**Hydra**
- Add random delays between attempts
- Rotate source IPs if possible
- Use custom wordlists
- Limit concurrent connections

**Empire/PoshC2**
- Use custom stagers
- Modify default C2 profiles
- Use domain fronting
- Add jitter to beacons

**Cobalt Strike**
- Use Malleable C2 profiles
- Customize sleep times and jitter
- Use domain fronting
- Modify default Malleable C2 profiles

**Mimikatz**
- Use custom builds
- Run from memory if possible
- Clear LSASS memory after use
- Consider alternatives like Rubeus

**Netcat/Socat**
- Use encrypted channels (stunnel)
- Avoid plaintext protocols if possible
- Use legitimate ports when possible

**PowerShell**
- Use encoded commands
- Implement AMSI bypass
- Use LOLBins (Certutil, Bitsadmin, etc.)
- Avoid default execution policies

**Docker/Kubernetes**
- Use private registries
- Avoid default image names
- Rotate credentials regularly
- Use least-privilege IAM roles

---

## Detection Indicators to Monitor

### Network-Level
- Unusual port scanning patterns
- High-frequency DNS queries
- Large file transfers at odd hours
- Unusual protocol usage (DNS tunneling, ICMP tunneling)
- Certificate validation failures
- Beacon-like regular connections

### Host-Level
- Process creation from unusual locations
- PowerShell with encoded commands
- LOLBin execution patterns
- Registry modifications in persistence locations
- Scheduled task creation
- Service creation/modification
- DLL loading from unusual paths
- Memory injection indicators

### Application-Level
- SQL injection patterns in web traffic
- Unusual User-Agent strings
- Brute-force authentication attempts
- File upload/download patterns
- Web shell indicators
- Request patterns matching known tools

### Cloud-Level
- Unusual API access patterns
- Resource creation/deletion at scale
- Privilege escalation attempts
- Cross-region data transfers
- Unusual service account usage

---

## Countermeasures for Common Detection Methods

### Avoiding WAF Signatures
- Encode payloads (Base64, URL encoding, Unicode)
- Fragment requests
- Use alternative HTTP methods
- Modify User-Agent to match target
- Add random delays between requests

### Avoiding EDR/AV
- Use LOLBins (Certutil, Bitsadmin, Regsvr32, etc.)
- Implement AMSI bypass
- Use in-memory execution (reflective DLL injection)
- Modify process memory directly
- Disable security features temporarily (risky)

### Avoiding Network Monitoring
- Use encrypted channels (HTTPS, SSH, TLS)
- Blend traffic patterns with legitimate activity
- Use domain fronting
- Add jitter to C2 beacons
- Operate during business hours
- Limit data transfer sizes

### Avoiding Log Detection
- Clear event logs post-operation
- Modify log timestamps (timestomp)
- Disable logging temporarily (risky)
- Use techniques that don't generate logs
- Rotate tools and infrastructure regularly

---

## Tool Substitution Matrix

| Tool | Quieter Alternative | Notes |
|------|-------------------|-------|
| Metasploit | Custom exploits, Sliver | Sliver (Go) is less signatured |
| Empire | Sliver, Havoc | Go frameworks are better than PowerShell |
| Nmap | Masscan (with care), RustScan | Masscan is faster but louder |
| Burp Suite | OWASP ZAP, manual testing | OWASP ZAP is open-source |
| Hydra | Medusa, Ncrack | Similar detection risk |
| Mimikatz | Rubeus, LaZagne | Rubeus is .NET-based |
| PsExec | WMIExec, WinRM | WMI is LOLBin |
| Netcat | Socat, PowerShell | PowerShell is built-in |
| Ngrok | Chisel, custom infrastructure | Private tunnels are better |
| Cobalt Strike | Sliver, Covenant | Go frameworks have better OpSec |

---

## References

- MITRE ATT&CK: https://attack.mitre.org/
- OWASP: https://owasp.org/
- LOLBin Project: https://lolbas-project.github.io/
- Atomic Red Team: https://github.com/redcanaryco/atomic-red-team
- MITRE Caldera: https://attack.mitre.org/software/

---

**Generated from OpsecAI Attack Dataset Analysis**
- 14,133 attack records analyzed
- 100+ unique offensive tools categorized
- OpSec considerations for each tool
- Detection methods and countermeasures documented
