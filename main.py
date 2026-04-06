from __future__ import annotations

import hashlib
import ipaddress
import os
import random
import re
import socket
import ssl
import subprocess
import time
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple
from urllib.parse import parse_qsl, urlparse

import requests
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box
from rich.live import Live
from rich.align import Align
from rich.spinner import Spinner

# Optional deps
try:
    import psutil
except Exception:
    psutil = None

try:
    import dns.resolver
    import dns.reversename
except Exception:
    dns = None  # type: ignore

# Optional phone metadata 
try:
    import phonenumbers  # type: ignore
    from phonenumbers import geocoder, carrier, number_type  # type: ignore
except Exception:
    phonenumbers = None  # type: ignore

# Optional speedtest
try:
    import speedtest  # type: ignore
except Exception:
    speedtest = None  # type: ignore

# Optional EXIF reader
try:
    from PIL import Image  # type: ignore
    from PIL.ExifTags import TAGS  # type: ignore
except Exception:
    Image = None  # type: ignore
    TAGS = None  # type: ignore

APP_NAME = "HackGuard"
APP_VERSION = "1.6.0"
UA = {"User-Agent": f"{APP_NAME}/{APP_VERSION}"}
TIMEOUT = 12

console = Console()


# --------------------
# No-scroll helpers
# --------------------
def clear():
    os.system("cls" if os.name == "nt" else "clear")


def pause():
    input("\nPress ENTER to continue...")


def safe_int(s: str) -> Optional[int]:
    try:
        return int(s)
    except Exception:
        return None


def is_ip(s: str) -> bool:
    for af in (socket.AF_INET, socket.AF_INET6):
        try:
            socket.inet_pton(af, s)
            return True
        except Exception:
            pass
    return False


def ensure_url(u: str) -> str:
    u = u.strip()
    if not u.startswith(("http://", "https://")):
        u = "https://" + u
    return u


def http_json(url: str) -> dict:
    r = requests.get(url, headers=UA, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def run_cmd(cmd: List[str], timeout: int = 40) -> Tuple[int, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, shell=False)
        out = (p.stdout or "") + (p.stderr or "")
        return p.returncode, out.strip()
    except subprocess.TimeoutExpired:
        return 124, "Command timed out."
    except FileNotFoundError:
        return 127, "Command not found on this system."
    except Exception as e:
        return 1, f"Failed to run command: {e}"


def file_hash(path: str, algo: str = "sha256") -> str:
    h = hashlib.new(algo)
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def pager(text: str, title: str = "Output"):
    """Single-screen viewer (no scroll). n/b/q."""
    lines = (text or "").splitlines()
    if not lines:
        clear()
        console.print(Panel("(empty)", title=title, border_style="white"))
        input("Press ENTER...")
        return

    h = max(22, console.size.height)
    page_lines = max(8, h - 8)
    page = 0
    pages = max(1, (len(lines) + page_lines - 1) // page_lines)

    while True:
        clear()
        console.print(Panel(f"{title}\n[dim]n=next • b=back • q=quit[/dim]", border_style="white", padding=(0, 1)))
        start = page * page_lines
        chunk = "\n".join(lines[start:start + page_lines])
        console.print(Panel(chunk, border_style="white"))
        console.print(f"[dim]Page {page+1}/{pages}[/dim]")
        cmd = input("Command (n/b/q): ").strip().lower() or "q"
        if cmd == "q":
            break
        if cmd == "n":
            page = min(pages - 1, page + 1)
        elif cmd == "b":
            page = max(0, page - 1)


# --------------------
# Gradient helpers (perfect L->R by columns)
# --------------------
def _hex_to_rgb(h: str) -> Tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _rgb_to_hex(r: int, g: int, b: int) -> str:
    return f"#{r:02x}{g:02x}{b:02x}"


def gradient_text_lr_multiline(s: str, start: str = "#7a00ff", end: str = "#ff3bd4") -> Text:
    """Perfect gradient left->right by column index across all lines."""
    sr, sg, sb = _hex_to_rgb(start)
    er, eg, eb = _hex_to_rgb(end)
    lines = s.splitlines() or [s]
    max_len = max(1, max((len(line) for line in lines), default=1))

    out = Text()
    for li, line in enumerate(lines):
        for x, ch in enumerate(line):
            t = x / (max_len - 1) if max_len > 1 else 0.0
            r = int(sr + (er - sr) * t)
            g = int(sg + (eg - sg) * t)
            b = int(sb + (eb - sb) * t)
            out.append(ch, style=_rgb_to_hex(r, g, b))
        if li != len(lines) - 1:
            out.append("\n")
    return out


# --------------------
# Header 
# --------------------
ASCII_LOGO = r"""
██╗  ██╗ █████╗  ██████╗██╗  ██╗ ██████╗ ██╗   ██╗ █████╗ ██████╗ ██████╗
██║  ██║██╔══██╗██╔════╝██║ ██╔╝██╔════╝ ██║   ██║██╔══██╗██╔══██╗██╔══██╗
███████║███████║██║     █████╔╝ ██║  ███╗██║   ██║███████║██████╔╝██║  ██║
██╔══██║██╔══██║██║     ██╔═██╗ ██║   ██║██║   ██║██╔══██║██╔══██╗██║  ██║
██║  ██║██║  ██║╚██████╗██║  ██╗╚██████╔╝╚██████╔╝██║  ██║██║  ██║██████╔╝
╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝ ╚═════╝  ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═════╝
""".strip("\n")


def header_renderables() -> List[object]:
    return [
        Text("\n"),
        gradient_text_lr_multiline(ASCII_LOGO, start="#7a00ff", end="#ff3bd4"),
        Text("\n"),
        Text(f"{APP_NAME} v{APP_VERSION}\n", style="dim"),
    ]


# --------------------
# Loading screen 
# --------------------
def show_loading_screen(message: str = "Loading...", seconds: float = 0.55) -> None:
    """
    Full-screen loading screen with centered logo + spinner.
    Uses Live(screen=True) so it replaces the terminal content (no scroll).
    """
    hints = [
        "Hardening checks...",
        "Resolving signals...",
        "Rendering UI...",
        "Refreshing modules...",
        "Validating input...",
        "Building panels...",
        "Indexing tools...",
        "Stabilizing output...",
    ]
    hint = random.choice(hints)

    logo = gradient_text_lr_multiline(ASCII_LOGO, start="#7a00ff", end="#ff3bd4")
    spinner = Spinner("dots", text=f"[dim]{message}[/dim]")

    body = Group(
        Align.center(Text(""), vertical="top"),
        Align.center(logo, vertical="middle"),
        Align.center(Text(f"{APP_NAME} v{APP_VERSION}", style="dim")),
        Align.center(Text("")),
        Align.center(spinner),
        Align.center(Text(hint, style="dim")),
        Align.center(Text("")),
    )

    with Live(body, console=console, screen=True, refresh_per_second=30):
        time.sleep(max(0.12, seconds))


# --------------------
# Menu build + page reveal
# --------------------
@dataclass
class MenuItem:
    n: int
    left_col: bool
    label: str
    fn: Callable[[], None]


def _menu_columns(page_index: int) -> Tuple[str, str]:
    if page_index == 0:
        return "Network Scanner", "Info / Domain / Email"
    if page_index == 1:
        return "Network / Web", "System / Utilities"
    if page_index == 2:
        return "Site", "OSINT Helpers"
    return "Social", "Social / Utilities"


def build_menu_renderables(page_index: int) -> Group:
    header_parts = header_renderables()

    page = PAGES[page_index]
    left = [it for it in page if it.left_col]
    right = [it for it in page if not it.left_col]
    rows = max(len(left), len(right))

    def fmt(it: MenuItem) -> str:
        return f"[{it.n:02d}] {it.label}"

    left_lines = [fmt(left[i]) if i < len(left) else "" for i in range(rows)]
    right_lines = [fmt(right[i]) if i < len(right) else "" for i in range(rows)]

    col_l, col_r = _menu_columns(page_index)
    table = Table(box=box.SQUARE, show_header=True, header_style="white")
    table.add_column(col_l, style="white", overflow="fold")
    table.add_column(col_r, style="white", overflow="fold")
    for i in range(rows):
        table.add_row(left_lines[i], right_lines[i])

    footer = Panel.fit(
        "[dim]B: Back[/dim]   [dim]N: Next[/dim]   [dim]Q: Exit[/dim]",
        border_style="white",
        padding=(0, 1),
    )
    prompt = Text("Choose an option (1-30): ", style="magenta", end="")

    return Group(*header_parts, table, footer, prompt)


def render_menu(page_index: int):
    clear()
    console.print(build_menu_renderables(page_index))


def animate_page_reveal(page_index: int, duration: float = 0.18):
    """
    Reveal the rendered menu from top to bottom (line-by-line) without scrolling.
    """
    renderable = build_menu_renderables(page_index)

    tmp = Console(width=console.size.width, record=True)
    tmp.print(renderable)
    full = tmp.export_text(styles=False)


    lines = full.splitlines()
    total = len(lines)

    steps = min(total, 40)
    sleep_t = max(0.004, duration / max(1, steps))

    with Live("", console=console, screen=True, refresh_per_second=60) as live:
        for i in range(1, steps + 1):
            shown = int(total * (i / steps))
            live.update("\n".join(lines[:shown]))
            time.sleep(sleep_t)
        live.update(full)


# --------------------
# Tools (1–30)
# --------------------
def tool_ip_lookup():
    clear()
    console.print(Panel("IP Lookup (public intel)", border_style="white"))
    target = input("IP (blank = your public IP): ").strip()

    if not target:
        info = http_json("https://ipinfo.io/json")
        t = Table(box=box.SIMPLE, show_header=False)
        t.add_column("k", style="dim", width=18)
        t.add_column("v")
        for k in ("ip", "city", "region", "country", "loc", "org", "timezone"):
            if k in info:
                t.add_row(k, str(info.get(k)))
        console.print(t)
        pause()
        return

    if not is_ip(target):
        console.print("[red]Invalid IP.[/red]")
        pause()
        return

    data = http_json(
        f"http://ip-api.com/json/{target}?fields=status,message,country,regionName,city,zip,lat,lon,timezone,isp,org,as,query"
    )
    if data.get("status") != "success":
        console.print(f"[red]Lookup failed:[/red] {data.get('message','unknown')}")
        pause()
        return

    t = Table(box=box.SIMPLE, show_header=False)
    t.add_column("k", style="dim", width=18)
    t.add_column("v")
    for k in ("query", "country", "regionName", "city", "zip", "timezone", "isp", "org", "as", "lat", "lon"):
        if k in data:
            t.add_row(k, str(data.get(k)))
    console.print(t)
    pause()


def tool_domain_lookup():
    clear()
    console.print(Panel("Domain Lookup (DNS + RDAP)", border_style="white"))
    domain = input("Domain (example.com): ").strip().lower()
    if not domain:
        console.print("[red]No domain provided.[/red]")
        pause()
        return

    records: Dict[str, List[str]] = {"A": [], "AAAA": [], "MX": [], "NS": [], "TXT": []}

    for fam, lab in ((socket.AF_INET, "A"), (socket.AF_INET6, "AAAA")):
        try:
            infos = socket.getaddrinfo(domain, None, fam, socket.SOCK_STREAM)
            records[lab] = sorted(set(i[4][0] for i in infos))
        except Exception:
            pass

    if dns is not None:
        def add_rr(rr: str):
            try:
                ans = dns.resolver.resolve(domain, rr)
                records[rr] = [str(r) for r in ans]
            except Exception:
                pass
        for rr in ("MX", "NS", "TXT"):
            add_rr(rr)

    t = Table(box=box.SIMPLE, title=f"DNS: {domain}")
    t.add_column("Type", style="dim", width=6)
    t.add_column("Value")
    for rr, vals in records.items():
        for v in vals[:6]:
            t.add_row(rr, v)
        if len(vals) > 6:
            t.add_row(rr, f"... (+{len(vals)-6} more)")
    if dns is None:
        t.add_row("NOTE", "Install dnspython for MX/NS/TXT: pip install dnspython")
    console.print(t)

    try:
        rdap = http_json(f"https://rdap.org/domain/{domain}")
        handle = rdap.get("handle") or rdap.get("name") or "N/A"
        status = ", ".join(rdap.get("status", []) or []) or "N/A"
        rt = Table(box=box.SIMPLE, title="RDAP")
        rt.add_column("Field", style="dim", width=14)
        rt.add_column("Value")
        rt.add_row("handle/name", str(handle))
        rt.add_row("status", status)
        console.print(rt)
    except Exception:
        console.print("[dim]RDAP not available for this domain.[/dim]")

    pause()


def tool_port_scanner():
    clear()
    console.print(Panel(
        "Port Scanner (defensive, limited)\n"
        "[dim]Only test systems you own or have explicit permission to test.\n"
        "No ranges, no mass scanning.[/dim]",
        border_style="white"
    ))
    host = input("Host (domain/IP): ").strip()
    if not host:
        console.print("[red]No host provided.[/red]")
        pause()
        return

    mode = (input("Mode: (c)ommon ports or (m)anual list? [c]: ").strip().lower() or "c")
    if mode == "m":
        raw = input("Ports (comma) e.g. 22,80,443: ").strip()
        ports = []
        for p in raw.split(","):
            p = p.strip()
            if p.isdigit():
                ports.append(int(p))
        ports = [p for p in ports if 1 <= p <= 65535][:50]
        if not ports:
            console.print("[red]No valid ports.[/red]")
            pause()
            return
    else:
        ports = [21, 22, 25, 53, 80, 110, 143, 443, 445, 587, 993, 995, 3389]

    timeout = 0.6
    open_ports = []
    for p in ports:
        try:
            with socket.create_connection((host, p), timeout=timeout):
                open_ports.append(p)
        except Exception:
            pass

    lines = [f"{host}:{p} OPEN" for p in open_ports] or ["No open ports found in the tested list."]
    pager("\n".join(lines), title="Scan results (OPEN only)")

    clear()
    console.print(Panel("Port Scanner Summary", border_style="white"))
    console.print(f"Host: {host}")
    console.print(f"Tested ports: {len(ports)}")
    console.print(f"Open ports: {len(open_ports)}")
    pause()


def tool_ping_host():
    clear()
    console.print(Panel("Ping Host", border_style="white"))
    host = input("Host: ").strip()
    count = safe_int(input("Count [4]: ").strip() or "4") or 4
    cmd = ["ping", "-n", str(count), host] if os.name == "nt" else ["ping", "-c", str(count), host]
    code, out = run_cmd(cmd, timeout=25)
    pager(out, title=f"ping exit={code}")


def tool_phone_number_info():
    clear()
    console.print(Panel(
        "Phone Number Info (metadata only)\n"
        "[dim]No owner/subscriber lookup. Only validation/format + country/type if available.[/dim]",
        border_style="white"
    ))
    number = input("Phone number (with +country code preferred): ").strip()
    if not number:
        console.print("[red]No number provided.[/red]")
        pause()
        return

    if phonenumbers is None:
        console.print("[yellow]Optional dependency missing: phonenumbers[/yellow]")
        console.print("Install: pip install phonenumbers")
        pause()
        return

    region_hint = input("Region hint (e.g. ES) [blank to auto]: ").strip().upper() or None
    try:
        pn = phonenumbers.parse(number, region_hint)
        valid = phonenumbers.is_valid_number(pn)
        possible = phonenumbers.is_possible_number(pn)

        country = geocoder.description_for_number(pn, "en") or "N/A"
        carr = carrier.name_for_number(pn, "en") or "N/A"
        typ = str(number_type(pn)).replace("PhoneNumberType.", "")
        e164 = phonenumbers.format_number(pn, phonenumbers.PhoneNumberFormat.E164)

        t = Table(box=box.SIMPLE, show_header=False)
        t.add_column("k", style="dim", width=16)
        t.add_column("v")
        t.add_row("possible", str(possible))
        t.add_row("valid", str(valid))
        t.add_row("E.164", e164)
        t.add_row("country/area", country)
        t.add_row("carrier", carr)
        t.add_row("type", typ)
        console.print(t)
    except Exception as e:
        console.print(f"[red]Parse failed:[/red] {e}")

    pause()


def tool_email_lookup_safe():
    clear()
    console.print(Panel(
        "Email Lookup (safe domain checks)\n"
        "[dim]No person lookup / no existence checking.\n"
        "We only validate syntax and inspect the email domain (MX/SPF/DMARC/RDAP).[/dim]",
        border_style="white"
    ))
    email = input("Email: ").strip()
    if not email:
        console.print("[red]No email provided.[/red]")
        pause()
        return

    syntax_ok = bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email))
    domain = email.split("@")[-1].lower() if "@" in email else ""

    t = Table(box=box.SIMPLE, show_header=False)
    t.add_column("k", style="dim", width=16)
    t.add_column("v")
    t.add_row("syntax_ok", str(syntax_ok))
    t.add_row("domain", domain or "N/A")
    console.print(t)

    if not domain:
        pause()
        return

    results = {"MX": [], "SPF": [], "DMARC": []}
    if dns is not None:
        try:
            mx = dns.resolver.resolve(domain, "MX")
            results["MX"] = [str(r) for r in mx]
        except Exception:
            pass
        try:
            txt = dns.resolver.resolve(domain, "TXT")
            for r in txt:
                s = str(r)
                if "v=spf1" in s.lower():
                    results["SPF"].append(s)
        except Exception:
            pass
        try:
            dmarc = dns.resolver.resolve(f"_dmarc.{domain}", "TXT")
            results["DMARC"] = [str(r) for r in dmarc]
        except Exception:
            pass

    out = []
    for k, vals in results.items():
        out.append(f"{k}:")
        out.extend([f"  {v}" for v in (vals or ["(none found)"])])
        out.append("")
    pager("\n".join(out), title="Email domain signals")

    try:
        rdap = http_json(f"https://rdap.org/domain/{domain}")
        handle = rdap.get("handle") or rdap.get("name") or "N/A"
        status = ", ".join(rdap.get("status", []) or []) or "N/A"
        pager(f"handle/name: {handle}\nstatus: {status}", title="RDAP summary")
    except Exception:
        pass

    pause()


def tool_email_header_analyzer():
    clear()
    console.print(Panel(
        "Email Header Analyzer (paste headers)\n"
        "[dim]Paste raw headers (not the body). End with a single line containing: END[/dim]",
        border_style="white"
    ))
    lines = []
    while True:
        line = input()
        if line.strip() == "END":
            break
        lines.append(line)
    raw = "\n".join(lines).strip()
    if not raw:
        console.print("[red]No headers provided.[/red]")
        pause()
        return

    received = re.findall(r"^Received:.*(?:\n\s+.*)*", raw, flags=re.MULTILINE)
    auth = re.search(r"^Authentication-Results:\s*(.*(?:\n\s+.*)*)", raw,
                     flags=re.MULTILINE | re.IGNORECASE)
    from_ = re.search(r"^From:\s*(.*)$", raw, flags=re.MULTILINE)

    summary = []
    summary.append(f"From: {from_.group(1).strip() if from_ else 'N/A'}")
    summary.append(f"Received hops: {len(received)}")
    summary.append("")
    summary.append("Authentication-Results:")
    summary.append(auth.group(1).strip() if auth else "N/A")
    pager("\n".join(summary), title="Header summary")

    if received:
        pager("\n\n".join(received), title="Received chain")

    pause()


def tool_hash_generator():
    clear()
    console.print(Panel("Hash Generator", border_style="white"))
    text = input("Text to hash: ")
    algo = (input("Algo (sha256/md5) [sha256]: ").strip().lower() or "sha256")
    if algo not in ("sha256", "md5"):
        console.print("[red]Unsupported algo.[/red]")
        pause()
        return
    h = hashlib.new(algo)
    h.update(text.encode("utf-8", errors="ignore"))
    console.print(f"\n[bold]{algo.upper()}[/bold]: {h.hexdigest()}")
    pause()


def tool_file_hash_analyzer():
    clear()
    console.print(Panel("File Hash Analyzer (hash + compare)", border_style="white"))
    path = input("File path: ").strip().strip('"')
    if not os.path.isfile(path):
        console.print("[red]File not found.[/red]")
        pause()
        return
    sha256 = file_hash(path, "sha256")
    md5 = file_hash(path, "md5")
    console.print(f"\nSHA256: {sha256}\nMD5:    {md5}\n")
    expected = input("Expected hash (optional): ").strip().lower()
    if expected:
        ok = expected in (sha256.lower(), md5.lower())
        console.print("[green]MATCH ✅[/green]" if ok else "[red]NO MATCH ❌[/red]")
    pause()


def tool_tls_checker():
    clear()
    console.print(Panel("TLS Certificate Checker", border_style="white"))
    host = input("Host [example.com]: ").strip() or "example.com"
    port = safe_int(input("Port [443]: ").strip() or "443") or 443

    ctx = ssl.create_default_context()
    try:
        with socket.create_connection((host, port), timeout=8) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as s:
                cert = s.getpeercert()
                proto = s.version()
                cipher = s.cipher()
    except Exception as e:
        console.print(f"[red]TLS failed:[/red] {e}")
        pause()
        return

    subject = dict(x[0] for x in cert.get("subject", []))
    issuer = dict(x[0] for x in cert.get("issuer", []))

    t = Table(box=box.SIMPLE, show_header=False)
    t.add_column("k", style="dim", width=16)
    t.add_column("v")
    t.add_row("protocol", str(proto))
    t.add_row("cipher", f"{cipher[0]} ({cipher[1]} bits)" if cipher else "N/A")
    t.add_row("CN", subject.get("commonName", "N/A"))
    t.add_row("issuer", issuer.get("commonName", "N/A"))
    t.add_row("notBefore", cert.get("notBefore") or "N/A")
    t.add_row("notAfter", cert.get("notAfter") or "N/A")
    console.print(t)
    pause()


def tool_http_probe():
    clear()
    console.print(Panel("HTTP Probe (headers + redirects + basic security headers)", border_style="white"))
    url = ensure_url(input("URL [example.com]: ").strip() or "example.com")
    method = (input("Method (HEAD/GET) [HEAD]: ").strip().upper() or "HEAD")
    if method not in ("HEAD", "GET"):
        method = "HEAD"

    try:
        if method == "HEAD":
            r = requests.head(url, headers=UA, timeout=TIMEOUT, allow_redirects=True)
            if r.status_code >= 400:
                r = requests.get(url, headers=UA, timeout=TIMEOUT, allow_redirects=True)
        else:
            r = requests.get(url, headers=UA, timeout=TIMEOUT, allow_redirects=True)
    except Exception as e:
        console.print(f"[red]HTTP failed:[/red] {e}")
        pause()
        return

    sec_headers = [
        "Strict-Transport-Security", "Content-Security-Policy", "X-Frame-Options",
        "X-Content-Type-Options", "Referrer-Policy", "Permissions-Policy"
    ]
    present = {h: r.headers.get(h) for h in sec_headers if h in r.headers}

    t = Table(box=box.SIMPLE, title="Summary")
    t.add_column("Field", style="dim", width=16)
    t.add_column("Value")
    t.add_row("final_url", r.url)
    t.add_row("status", str(r.status_code))
    t.add_row("redirects", str(len(r.history)))
    t.add_row("server", r.headers.get("Server", "N/A"))
    t.add_row("content-type", r.headers.get("Content-Type", "N/A"))
    console.print(t)

    if r.history:
        chain = "\n".join([f"{h.status_code} {h.url}" for h in r.history] + [f"{r.status_code} {r.url}"])
        pager(chain, title="Redirect chain")

    if present:
        sh = "\n".join([f"{k}: {v}" for k, v in present.items()])
        pager(sh, title="Security headers (present)")
    else:
        console.print("[yellow]No common security headers detected (not definitive).[/yellow]")
        pause()


def tool_dns_deep():
    clear()
    console.print(Panel("DNS Deep Lookup (A/AAAA + MX/NS/TXT/SOA + PTR)", border_style="white"))
    target = input("Domain or IP: ").strip()
    records: Dict[str, List[str]] = {"A": [], "AAAA": [], "MX": [], "NS": [], "TXT": [], "SOA": [], "PTR": []}

    if is_ip(target):
        if dns is not None:
            try:
                rev = dns.reversename.from_address(target)
                ans = dns.resolver.resolve(rev, "PTR")
                records["PTR"] = [str(r).rstrip(".") for r in ans]
            except Exception as e:
                records["PTR"] = [f"PTR failed: {e}"]
        else:
            try:
                host, _, _ = socket.gethostbyaddr(target)
                records["PTR"] = [host]
            except Exception as e:
                records["PTR"] = [f"Reverse failed: {e}"]
        pager("\n".join(records["PTR"]) or "(no PTR)", title=f"PTR for {target}")
        return

    for fam, lab in ((socket.AF_INET, "A"), (socket.AF_INET6, "AAAA")):
        try:
            infos = socket.getaddrinfo(target, None, fam, socket.SOCK_STREAM)
            records[lab] = sorted(set(i[4][0] for i in infos))
        except Exception:
            pass

    if dns is not None:
        def add_rr(rr: str):
            try:
                ans = dns.resolver.resolve(target, rr)
                records[rr] = [str(r) for r in ans]
            except Exception:
                pass
        for rr in ("MX", "NS", "TXT", "SOA"):
            add_rr(rr)

    t = Table(box=box.SIMPLE, title=f"DNS: {target}")
    t.add_column("Type", style="dim", width=6)
    t.add_column("Value")
    for rr, vals in records.items():
        for v in vals[:6]:
            t.add_row(rr, v)
        if len(vals) > 6:
            t.add_row(rr, f"... (+{len(vals)-6} more)")
    if dns is None:
        t.add_row("NOTE", "Install dnspython for MX/NS/TXT/SOA: pip install dnspython")
    console.print(t)
    pause()


def tool_traceroute():
    clear()
    console.print(Panel("Traceroute", border_style="white"))
    host = input("Host: ").strip()
    cmd = ["tracert", host] if os.name == "nt" else ["traceroute", host]
    code, out = run_cmd(cmd, timeout=65)
    pager(out, title=f"trace exit={code}")


def tool_robots_sitemap():
    clear()
    console.print(Panel("robots.txt + sitemap", border_style="white"))
    base = ensure_url(input("Domain or URL [example.com]: ").strip() or "example.com")
    p = urlparse(base)
    origin = f"{p.scheme}://{p.netloc}"

    robots_url = origin + "/robots.txt"
    try:
        r = requests.get(robots_url, headers=UA, timeout=TIMEOUT)
        pager(r.text, title=f"robots.txt — HTTP {r.status_code}")
    except Exception as e:
        console.print(f"[red]robots failed:[/red] {e}")
        pause()
        return

    clear()
    console.print(Panel("Sitemap candidates", border_style="white"))
    candidates = [origin + "/sitemap.xml", origin + "/sitemap_index.xml", origin + "/sitemap/sitemap.xml"]
    t = Table(box=box.SIMPLE)
    t.add_column("URL", style="dim")
    t.add_column("Result")
    for u in candidates:
        try:
            rr = requests.get(u, headers=UA, timeout=TIMEOUT)
            t.add_row(u, f"{rr.status_code} ({len(rr.content)} bytes)")
        except Exception:
            t.add_row(u, "failed")
    console.print(t)
    pause()


def tool_system_monitor():
    clear()
    console.print(Panel("System Resource Monitor (psutil)", border_style="white"))
    if psutil is None:
        console.print("[yellow]psutil not installed. Install: pip install psutil[/yellow]")
        pause()
        return
    cpu = psutil.cpu_percent(interval=0.4)
    vm = psutil.virtual_memory()
    disk = psutil.disk_usage(str(Path.cwd().anchor))

    t = Table(box=box.SIMPLE, show_header=False)
    t.add_column("k", style="dim", width=16)
    t.add_column("v")
    t.add_row("CPU", f"{cpu}%")
    t.add_row("RAM", f"{vm.percent}% ({vm.used/1e9:.2f}/{vm.total/1e9:.2f} GB)")
    t.add_row("Disk", f"{disk.percent}% ({disk.used/1e9:.2f}/{disk.total/1e9:.2f} GB)")
    console.print(t)
    pause()


def tool_local_listeners():
    clear()
    console.print(Panel("Local Listeners (psutil)", border_style="white"))
    if psutil is None:
        console.print("[yellow]psutil not installed. Install: pip install psutil[/yellow]")
        pause()
        return
    conns = psutil.net_connections(kind="inet")
    listen = []
    for c in conns:
        if (c.status or "").upper() == "LISTEN":
            if c.laddr:
                listen.append(f"{c.laddr.ip}:{c.laddr.port}")
    listen = sorted(set(listen))[:300]
    pager("\n".join(listen) if listen else "(none)", title="LISTEN sockets")
    pause()


def tool_quick_internet_check():
    clear()
    console.print(Panel("Quick Internet Check (1.1.1.1:443)", border_style="white"))
    host, port = "1.1.1.1", 443
    t0 = time.time()
    try:
        with socket.create_connection((host, port), timeout=4):
            ms = (time.time() - t0) * 1000
            console.print(f"[green]OK ✅[/green] {host}:{port} in {ms:.1f} ms")
    except Exception as e:
        ms = (time.time() - t0) * 1000
        console.print(f"[red]FAIL ❌[/red] {ms:.1f} ms — {e}")
    pause()


def tool_tree():
    clear()
    console.print(Panel("Directory Tree (compact)", border_style="white"))
    root = Path(input("Folder [.] : ").strip() or ".").resolve()
    if not root.exists():
        console.print("[red]Not found.[/red]")
        pause()
        return
    max_items = safe_int(input("Max entries [150]: ").strip() or "150") or 150
    out = []
    count = 0
    for p in root.rglob("*"):
        if count >= max_items:
            out.append("... (+more)")
            break
        rel = str(p.relative_to(root))
        out.append(rel + ("/" if p.is_dir() else ""))
        count += 1
    pager("\n".join(out), title=f"Tree: {root}")
    pause()


def tool_rdap_standalone():
    clear()
    console.print(Panel("RDAP (Modern WHOIS) — standalone", border_style="white"))
    target = input("IP or domain: ").strip().lower()
    kind = "ip" if is_ip(target) else "domain"
    try:
        data = http_json(f"https://rdap.org/{kind}/{target}")
        handle = data.get("handle") or data.get("name") or "N/A"
        status = ", ".join(data.get("status", []) or []) or "N/A"
        pager(f"Query: {target}\nKind: {kind}\nhandle/name: {handle}\nstatus: {status}", title="RDAP summary")
    except Exception as e:
        console.print(f"[red]RDAP failed:[/red] {e}")
        pause()


def tool_speedtest():
    clear()
    console.print(Panel("Network Speed Test (optional)", border_style="white"))
    if speedtest is None:
        console.print("[yellow]speedtest-cli not installed. Install: pip install speedtest-cli[/yellow]")
        pause()
        return
    console.print("[dim]Running speed test...[/dim]")
    st = speedtest.Speedtest()
    st.get_best_server()
    down = st.download()
    up = st.upload()
    ping = st.results.ping

    t = Table(box=box.SIMPLE, show_header=False)
    t.add_column("k", style="dim", width=16)
    t.add_column("v")
    t.add_row("Ping", f"{ping:.1f} ms")
    t.add_row("Download", f"{down/1e6:.2f} Mbps")
    t.add_row("Upload", f"{up/1e6:.2f} Mbps")
    console.print(t)
    pause()


# --------------------
# SAFE 
# --------------------
def tool_website_vuln_scanner_passive():
    clear()
    console.print(Panel(
        "Website Vulnerability Scanner (PASSIVE)\n"
        "[dim]No exploitation. Only passive signals/checks.[/dim]",
        border_style="white"
    ))
    url = ensure_url(input("URL [example.com]: ").strip() or "example.com")

    try:
        r = requests.get(url, headers=UA, timeout=TIMEOUT, allow_redirects=True)
    except Exception as e:
        console.print(f"[red]HTTP failed:[/red] {e}")
        pause()
        return

    final = r.url
    p = urlparse(final)
    host = p.netloc

    findings = []
    info = []

    if p.scheme != "https":
        findings.append("Final URL is not HTTPS.")
    else:
        info.append("HTTPS detected on final URL.")

    required = [
        "Strict-Transport-Security",
        "Content-Security-Policy",
        "X-Frame-Options",
        "X-Content-Type-Options",
        "Referrer-Policy",
    ]
    missing = [h for h in required if h not in r.headers]
    if missing:
        findings.append("Missing common security headers: " + ", ".join(missing))
    else:
        info.append("Common security headers appear present.")

    srv = r.headers.get("Server", "")
    if srv:
        findings.append(f"Server header exposed: {srv} (not always bad, but reduces OPSEC).")

    origin = f"{p.scheme}://{p.netloc}"
    try:
        rr = requests.get(origin + "/robots.txt", headers=UA, timeout=TIMEOUT)
        if rr.status_code == 200 and rr.text.strip():
            info.append("robots.txt found (may reveal paths).")
        else:
            info.append("robots.txt not found or empty.")
    except Exception:
        info.append("robots.txt check failed.")

    report = []
    report.append(f"Input URL: {url}")
    report.append(f"Final URL: {final}")
    report.append(f"Status: {r.status_code}")
    report.append(f"Redirects: {len(r.history)}")
    report.append("")
    report.append("INFO:")
    report.extend([f"  - {x}" for x in (info or ["(none)"])])
    report.append("")
    report.append("FINDINGS (passive):")
    report.extend([f"  - {x}" for x in (findings or ["(none)"])])
    report.append("")
    report.append("NOTE: These are signals, not proof of a vulnerability.")

    pager("\n".join(report), title="Passive Website Scan")
    pause()


def tool_website_info_scanner():
    clear()
    console.print(Panel("Website Info Scanner (passive)", border_style="white"))
    url = ensure_url(input("URL [example.com]: ").strip() or "example.com")
    try:
        r = requests.get(url, headers=UA, timeout=TIMEOUT, allow_redirects=True)
    except Exception as e:
        console.print(f"[red]HTTP failed:[/red] {e}")
        pause()
        return

    final = r.url
    p = urlparse(final)
    host = p.netloc

    lines = [
        f"Input URL: {url}",
        f"Final URL: {final}",
        f"Status: {r.status_code}",
        f"Redirects: {len(r.history)}",
        f"Server: {r.headers.get('Server', 'N/A')}",
        f"Content-Type: {r.headers.get('Content-Type', 'N/A')}",
        "",
        "Security headers:"
    ]

    sec_headers = [
        "Strict-Transport-Security", "Content-Security-Policy", "X-Frame-Options",
        "X-Content-Type-Options", "Referrer-Policy", "Permissions-Policy"
    ]
    for h in sec_headers:
        v = r.headers.get(h)
        lines.append(f"  {h}: {v if v else '(missing)'}")

    lines.append("")
    lines.append(f"DNS quick look for: {host}")
    try:
        a = sorted({x[4][0] for x in socket.getaddrinfo(host, None, socket.AF_INET, socket.SOCK_STREAM)})
        lines.append(f"  A: {', '.join(a) if a else '(none)'}")
    except Exception:
        lines.append("  A: (failed)")

    pager("\n".join(lines), title="Website Info Scanner")
    pause()


def tool_website_url_scanner():
    clear()
    console.print(Panel("Website URL Scanner (parse + simple flags)", border_style="white"))
    raw = input("URL: ").strip()
    if not raw:
        console.print("[red]No URL provided.[/red]")
        pause()
        return

    url = ensure_url(raw)
    p = urlparse(url)

    flags = []
    if p.scheme != "https":
        flags.append("Not HTTPS (consider HTTPS where possible).")
    if "@" in p.netloc:
        flags.append("Contains '@' in netloc (can be used for confusing URLs).")
    if p.port and p.port not in (80, 443):
        flags.append(f"Non-standard port in URL: {p.port}")
    if len(url) > 200:
        flags.append("Very long URL (>200 chars) — often tracking or obfuscation.")
    if any(x in (p.path or "").lower() for x in ("login", "verify", "account", "security")):
        flags.append("Sensitive-looking path keywords (be cautious).")
    if any(x in url.lower() for x in ("redirect=", "url=", "next=", "target=", "continue=")):
        flags.append("Contains common redirect parameters (open-redirect risk).")

    params = parse_qsl(p.query, keep_blank_values=True)

    t = Table(box=box.SIMPLE, show_header=False, title="Parsed URL")
    t.add_column("k", style="dim", width=16)
    t.add_column("v")
    t.add_row("normalized", url)
    t.add_row("scheme", p.scheme or "N/A")
    t.add_row("host", p.netloc or "N/A")
    t.add_row("path", p.path or "/")
    t.add_row("query_len", str(len(p.query)))
    t.add_row("params", str(len(params)))
    t.add_row("fragment", p.fragment or "N/A")
    console.print(t)

    if params:
        pt = Table(box=box.SIMPLE, title="Query parameters")
        pt.add_column("key", style="dim")
        pt.add_column("value")
        for k, v in params[:40]:
            pt.add_row(k, v if v else "(blank)")
        if len(params) > 40:
            pt.add_row("...", f"+{len(params)-40} more")
        console.print(pt)

    if flags:
        pager("\n".join(f"- {x}" for x in flags), title="Flags")
    else:
        console.print("[green]No obvious red flags found (simple heuristics).[/green]")
        pause()


def tool_google_dorking():
    clear()
    console.print(Panel("Google Dorking (generator)", border_style="white"))
    console.print("[dim]This only generates queries. It does not hack anything.[/dim]\n")

    base = input("Base keyword (e.g. company name) [blank = skip]: ").strip()
    site = input("site: (example.com) [blank = skip]: ").strip()
    filetype = input("filetype: (pdf/xls/sql/txt) [blank = skip]: ").strip()
    inurl = input("inurl: (admin/login/backup) [blank = skip]: ").strip()
    intitle = input("intitle: (index of / login) [blank = skip]: ").strip()

    parts = []
    if base:
        parts.append(f"\"{base}\"")
    if site:
        parts.append(f"site:{site}")
    if filetype:
        parts.append(f"filetype:{filetype}")
    if inurl:
        parts.append(f"inurl:{inurl}")
    if intitle:
        parts.append(f"intitle:\"{intitle}\"")

    templates = []
    if site:
        templates.append(f"site:{site} \"index of\"")
        templates.append(f"site:{site} ext:env OR ext:ini OR ext:log")
        templates.append(f"site:{site} inurl:admin OR inurl:login")
        templates.append(f"site:{site} \"password\" OR \"passwd\" OR \"api_key\"")
    if base:
        templates.append(f"\"{base}\" filetype:pdf")
        templates.append(f"\"{base}\" \"confidential\"")
        templates.append(f"\"{base}\" \"internal use\"")

    out = []
    if parts:
        out.append("Custom dork:")
        out.append("  " + " ".join(parts))
        out.append("")
    out.append("Templates:")
    out.extend(["  " + t for t in (templates or ["(no templates; add base/site to get more)"])])

    pager("\n".join(out), title="Dorks")
    ans = (input("\nOpen Google search for the custom dork? (y/n) [n]: ").strip().lower() or "n")
    if ans == "y" and parts:
        q = " ".join(parts)
        webbrowser.open(f"https://www.google.com/search?q={requests.utils.quote(q)}")
    pause()


def _random_public_ipv4() -> str:
    while True:
        ip = ipaddress.IPv4Address(random.getrandbits(32))
        if ip.is_private or ip.is_loopback or ip.is_multicast or ip.is_reserved or ip.is_link_local:
            continue
        return str(ip)


def tool_ip_generator():
    clear()
    console.print(Panel("IP Generator", border_style="white"))
    mode = (input("Mode (public/private) [public]: ").strip().lower() or "public")
    count = safe_int(input("How many? [10]: ").strip() or "10") or 10
    count = max(1, min(count, 200))

    ips = []
    if mode == "private":
        priv_blocks = [
            ipaddress.IPv4Network("10.0.0.0/8"),
            ipaddress.IPv4Network("172.16.0.0/12"),
            ipaddress.IPv4Network("192.168.0.0/16"),
        ]
        for _ in range(count):
            net = random.choice(priv_blocks)
            host_int = random.randint(1, net.num_addresses - 2)
            ips.append(str(net.network_address + host_int))
    else:
        for _ in range(count):
            ips.append(_random_public_ipv4())

    pager("\n".join(ips), title=f"Generated IPv4 ({mode})")
    pause()


# --------------------
# Social tools 
# --------------------
def _clean_username(u: str) -> str:
    return u.strip().lstrip("@").strip()


def _username_risk_report(u: str) -> List[str]:
    issues = []
    if not u:
        return ["Empty username."]
    if len(u) < 3:
        issues.append("Too short (<3).")
    if len(u) > 32:
        issues.append("Too long (>32).")
    if any(c.isspace() for c in u):
        issues.append("Contains spaces (usually invalid).")
    if u.startswith(".") or u.endswith(".") or u.startswith("_") or u.endswith("_"):
        issues.append("Starts/ends with '.' or '_' (often restricted).")
    if ".." in u or "__" in u or "._" in u or "_." in u:
        issues.append("Repeated separators: '..', '__', '._', '_.' (often restricted).")
    if any(ch in u for ch in "/\\?&#%"):
        issues.append("Contains URL/control characters: / \\ ? & # % (bad idea).")
    if any(s in u.lower() for s in ("support", "admin", "verify", "official")):
        issues.append("Contains 'support/admin/verify/official' — can look scammy / be flagged.")
    return issues or ["Looks OK (basic checks)."]


def tool_instagram_tiktok_profile_links():
    clear()
    console.print(Panel(
        "Instagram / TikTok: Profile Links (safe)\n"
        "[dim]No enumeration/scraping. Only generates public links for manual review.[/dim]",
        border_style="white"
    ))
    raw = input("Username: ").strip()
    u = _clean_username(raw)
    if not u:
        console.print("[red]No username provided.[/red]")
        pause()
        return

    links = [
        ("Instagram", f"https://www.instagram.com/{u}/"),
        ("TikTok", f"https://www.tiktok.com/@{u}"),
    ]

    t = Table(box=box.SIMPLE, show_header=True)
    t.add_column("Platform", style="dim", width=12)
    t.add_column("Link")
    for p, url in links:
        t.add_row(p, url)
    console.print(t)

    ans = (input("\nOpen links in browser? (y/n) [n]: ").strip().lower() or "n")
    if ans == "y":
        for _, url in links:
            webbrowser.open(url)
    pause()


def tool_username_hygiene_opsec():
    clear()
    console.print(Panel("Username: Hygiene / OPSEC", border_style="white"))
    raw = input("Username (no @ needed): ").strip()
    u = _clean_username(raw)
    if not u:
        console.print("[red]No username provided.[/red]")
        pause()
        return

    issues = _username_risk_report(u)
    console.print(Panel("\n".join(f"- {x}" for x in issues), title="Checks", border_style="white"))

    variants = set()
    variants.add(u.lower())
    variants.add(u.replace(".", "_"))
    variants.add(u.replace("_", "."))
    variants.add(u.replace(".", ""))
    variants.add(u.replace("_", ""))
    variants = {v for v in variants if v and len(v) <= 32}

    console.print(Panel("\n".join(sorted(variants))[:4000], title="Variants to consider (manual)", border_style="white"))
    pause()


def tool_discord_roblox_self_audit():
    clear()
    console.print(Panel(
        "Discord / Roblox: Self-audit checklist (defensive)\n"
        "[dim]For your own accounts. No tracking/lookup of other people.[/dim]",
        border_style="white"
    ))
    checklist = [
        "Enable 2FA (authenticator app).",
        "Review privacy (who can DM you / friend requests).",
        "Disable contact syncing if not needed.",
        "Audit linked accounts and remove unused connections.",
        "Do not post real-time location; avoid routine leaks.",
        "Use unique passwords + password manager.",
        "Check recovery methods and backup codes.",
        "Limit who can see your profile info / bio / inventory (Roblox).",
    ]
    pager("\n".join(f"- {x}" for x in checklist), title="Self-audit")
    pause()


# --------------------
# Menu pages (1–30)
# --------------------
PAGE1: List[MenuItem] = [
    MenuItem(1, True,  "IP Lookup", tool_ip_lookup),
    MenuItem(2, False, "Domain Lookup", tool_domain_lookup),

    MenuItem(3, True,  "IP Port Scanner", tool_port_scanner),
    MenuItem(4, False, "IP Pinger", tool_ping_host),

    MenuItem(5, True,  "Phone Number Lookup (metadata)", tool_phone_number_info),
    MenuItem(6, False, "Email Lookup (safe)", tool_email_lookup_safe),

    MenuItem(7, True,  "Email Header Analyzer", tool_email_header_analyzer),
    MenuItem(8, False, "Hash Generator", tool_hash_generator),

    MenuItem(9, True,  "File Hash Analyzer", tool_file_hash_analyzer),
    MenuItem(10, False, "TLS Certificate Checker", tool_tls_checker),
]

PAGE2: List[MenuItem] = [
    MenuItem(11, True,  "HTTP Probe", tool_http_probe),
    MenuItem(12, False, "DNS Deep Lookup", tool_dns_deep),

    MenuItem(13, True,  "Traceroute", tool_traceroute),
    MenuItem(14, False, "robots.txt + sitemap", tool_robots_sitemap),

    MenuItem(15, True,  "System Resource Monitor (psutil)", tool_system_monitor),
    MenuItem(16, False, "Local Listeners (psutil)", tool_local_listeners),

    MenuItem(17, True,  "Quick Internet Check", tool_quick_internet_check),
    MenuItem(18, False, "Directory Tree (compact)", tool_tree),

    MenuItem(19, True,  "RDAP (standalone)", tool_rdap_standalone),
    MenuItem(20, False, "Network Speed Test (optional)", tool_speedtest),
]

PAGE3: List[MenuItem] = [
    MenuItem(21, True,  "Website Vuln Scanner (passive)", tool_website_vuln_scanner_passive),
    MenuItem(22, False, "Website Info Scanner", tool_website_info_scanner),

    MenuItem(23, True,  "Website URL Scanner", tool_website_url_scanner),
    MenuItem(24, False, "Google Dorking (generator)", tool_google_dorking),

    MenuItem(25, True,  "IP Generator", tool_ip_generator),
    MenuItem(26, False, "Utilities: Reserved", lambda: pager("Reserved for future safe modules.", title="Reserved")),
]

PAGE4: List[MenuItem] = [
    MenuItem(27, True,  "Instagram/TikTok: Profile Links", tool_instagram_tiktok_profile_links),
    MenuItem(28, False, "Username: Hygiene / OPSEC", tool_username_hygiene_opsec),

    MenuItem(29, True,  "Discord/Roblox: Self-Audit", tool_discord_roblox_self_audit),
    MenuItem(30, False, "Utilities: Reserved", lambda: pager("Reserved for future safe modules.", title="Reserved")),
]

PAGES = [PAGE1, PAGE2, PAGE3, PAGE4]


# --------------------
# Main loop
# --------------------
def main():
    page = 0
    while True:
        render_menu(page)
        choice = input().strip().lower()

        if choice == "n":
            new_page = min(len(PAGES) - 1, page + 1)
            if new_page != page:
                show_loading_screen("Switching page...", seconds=0.45)
                animate_page_reveal(new_page, duration=0.14)
            page = new_page
            continue

        if choice == "b":
            new_page = max(0, page - 1)
            if new_page != page:
                show_loading_screen("Switching page...", seconds=0.45)
                animate_page_reveal(new_page, duration=0.14)
            page = new_page
            continue

        if choice in ("q", "exit"):
            show_loading_screen("Exiting...", seconds=0.35)
            clear()
            return

        n = safe_int(choice)
        if n is None:
            continue

        item = None
        for pg in PAGES:
            for it in pg:
                if it.n == n:
                    item = it
                    break
            if item:
                break

        if not item:
            continue

        try:
            show_loading_screen(f"Opening: {item.label}", seconds=0.55)
            item.fn()
            show_loading_screen("Returning to menu...", seconds=0.40)
        except KeyboardInterrupt:
            show_loading_screen("Cancelled...", seconds=0.35)
            clear()
            console.print("[yellow]Cancelled.[/yellow]")
            time.sleep(0.5)
        except Exception as e:
            clear()
            console.print(Panel(str(e), title="Error", border_style="red"))
            pause()


if __name__ == "__main__":
    main()
