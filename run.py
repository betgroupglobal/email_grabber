import asyncio
import random
import aiohttp
from aiohttp import ClientSession, TCPConnector, ClientTimeout
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin, urlparse
from typing import Set, List

# ==========================================
# TARGET CONFIGURATION
# ==========================================
TARGET_DOMAINS = [
    "https://woocasino.com",
    "https://nationalcasino.com",
    "https://7bitcasino.com",
    "https://rickycasino.com",
    "https://wildfortune.com",
    "https://casinonic.com",
    "https://kingbillycasino.com",
    "https://bitstarz.com",
    "https://playamo.com",
    "https://bobcasino.com",
    "https://spinsamurai.com",
    "https://hellspin.com",
    "https://aussieplay.com",
    "https://fairgo.com",
    "https://uptownpokies.com",
    "https://skycrown.com", # Corrected from skycrown casino.com
    "https://slotsempire.com",
    "https://raptorspin.com",
    "https://goldencrowncasino.com",
    "https://bizzocasino.com"
]

# Regex to catch emails specifically related to business/partners
# We prioritize anything not 'support' or 'no-reply'
BUSINESS_KEYWORDS = ['affiliate', 'partner', 'marketing', 'media', 'business', 'vip', 'manager']
EXCLUDE_KEYWORDS = ['support', 'help', 'noreply', 'no-reply', 'bounce']

EMAIL_REGEX = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15'
]

class TargetedSpider:
    def __init__(self):
        self.url_queue = asyncio.Queue()
        self.visited: Set[str] = set()
        self.found_emails: Set[str] = set()
        self.running = True

    def is_business_email(self, email):
        """Score emails. Business/VIP emails are gold."""
        email_lower = email.lower()
        
        # Immediate exclusion
        if any(x in email_lower for x in EXCLUDE_KEYWORDS):
            return 0
        
        # High priority (Affiliate/Marketing)
        if any(x in email_lower for x in BUSINESS_KEYWORDS):
            return 2
            
        # Standard info/contact
        return 1

    async def fetch(self, session, url):
        headers = {'User-Agent': random.choice(USER_AGENTS)}
        try:
            timeout = ClientTimeout(total=10)
            # We use ssl=False because many of these offshore casinos have cert issues
            async with session.get(url, headers=headers, timeout=timeout, ssl=False) as resp:
                if resp.status == 200:
                    return await resp.text(limit=500000)
        except Exception as e:
            pass # Silent fail to keep log clean
        return None

    def extract_emails(self, html):
        """Extracts, scores, and categorizes emails."""
        raw_emails = EMAIL_REGEX.findall(html)
        business_contacts = []
        general_contacts = []
        
        for email in raw_emails:
            if email not in self.found_emails:
                self.found_emails.add(email)
                score = self.is_business_email(email)
                
                if score == 2:
                    business_contacts.append(email)
                    print(f"[!!!] VIP/BUSINESS EMAIL: {email}")
                elif score == 1:
                    general_contacts.append(email)
                    print(f"[+] General Email: {email}")
        
        # Write to file immediately
        if business_contacts:
            with open("vip_leads.txt", "a") as f:
                for e in business_contacts:
                    f.write(f"{e}\n")

    async def worker(self, session, worker_id):
        while self.running:
            try:
                url = await asyncio.wait_for(self.url_queue.get(), timeout=1.0)
                
                if url in self.visited:
                    continue

                self.visited.add(url)
                html = await self.fetch(session, url)
                
                if html:
                    self.extract_emails(html)
                    self.queue_links(url, html)
                
                # Polite delay
                await asyncio.sleep(random.uniform(0.2, 0.8))

            except asyncio.TimeoutError:
                continue
            except Exception:
                continue

    def queue_links(self, base_url, html):
        """
        Logic: 
        1. Only follow INTERNAL links (keep within the target casino).
        2. Prioritize 'About Us', 'Affiliates', 'Contact' pages.
        """
        soup = BeautifulSoup(html, 'lxml')
        base_domain = urlparse(base_url).netloc
        
        for link in soup.find_all('a', href=True):
            href = link['href']
            full_url = urljoin(base_url, href)
            parsed = urlparse(full_url)
            
            if parsed.netloc != base_domain:
                continue
            
            # Normalization
            clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            if parsed.query: clean_url += f"?{parsed.query}"
            
            # Depth Control: Don't go deeper than 3 levels or infinite loops
            depth = clean_url.rstrip('/').count('/')
            if depth > 4:
                continue

            # Priority Boost for specific pages
            text = link.get_text().lower()
            if any(k in text for k in ['affiliate', 'contact', 'partner', 'vip', 'marketing']):
                # Push to front of queue logic (here we just add to queue)
                pass

            if clean_url not in self.visited:
                self.url_queue.put_nowait(clean_url)

    async def run(self):
        # Configure connector limits (these are big sites, don't hammer)
        connector = TCPConnector(limit=20, limit_per_host=2)
        
        async with ClientSession(connector=connector) as session:
            # 1. Seed the Queue with our Target Domains
            print(f"[*] Seeding Queue with {len(TARGET_DOMAINS)} Target Casinos...")
            for domain in TARGET_DOMAINS:
                self.url_queue.put_nowait(domain)
            
            # 2. Launch Workers
            tasks = []
            for i in range(20): # 20 Concurrent workers
                t = asyncio.create_task(self.worker(session, i))
                tasks.append(t)
            
            # 3. Monitor
            while True:
                await asyncio.sleep(5)
                if self.url_queue.empty() and all(t.done() for t in tasks):
                    break
            
            self.running = False
            for t in tasks: t.cancel()
            print("[*] Targeted Sweep Complete.")

if __name__ == "__main__":
    print(r"""
   ____  _       _    _                 _ 
  |  _ \(_) __ _| | _(_) ___ _ __   __| |
  | | | | |/ _` | |/ / |/ _ \ '_ \ / _` |
  | |_| | | (_| |   <| |  __/ | | | (_| |
  |____/|_|\__,_|_|\_\_|\___|_| |_|\__,_|
           LONG TAIL EXTRACTOR
    """)
    
    spider = TargetedSpider()
    try:
        asyncio.run(spider.run())
    except KeyboardInterrupt:
        print("\n[!] Stopped.")
