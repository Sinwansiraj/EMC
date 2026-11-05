"""Common job record, text helpers and a polite HTTP client."""
from __future__ import annotations

import html
import re
import time
from dataclasses import dataclass, field
from datetime import date, datetime

import requests

USER_AGENT = "PersonalJobAgent/1.0 (single-user job search; respects robots.txt and API limits)"


@dataclass
class Job:
    source: str
    platform: str
    url: str
    title: str
    company: str
    location: str = ""
    description: str = ""
    external_id: str = ""
    apply_url: str = ""
    remote: bool = False
    salary_min: int | None = None
    salary_max: int | None = None
    posted_at: str | None = None
    deadline: str | None = None
    partial: bool = False          # True when only an alert snippet is available
    extra: dict = field(default_factory=dict)


class Http:
    """requests session with a per-host minimum interval between calls."""

    def __init__(self, min_interval: float = 1.5, timeout: int = 25):
        self.s = requests.Session()
        self.s.headers["User-Agent"] = USER_AGENT
        self.min_interval = min_interval
        self.timeout = timeout
        self._last: dict[str, float] = {}

    def get(self, url: str, **kw) -> requests.Response:
        host = re.sub(r"^https?://([^/]+).*", r"\1", url)
        wait = self.min_interval - (time.time() - self._last.get(host, 0))
        if wait > 0:
            time.sleep(wait)
        self._last[host] = time.time()
        r = self.s.get(url, timeout=self.timeout, **kw)
        return r


_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"[ \t\r\f\v]+")


def html_to_text(s: str | None) -> str:
    if not s:
        return ""
    s = html.unescape(s)                     # Greenhouse double-escapes content
    s = re.sub(r"(?i)<\s*(br|/p|/li|/h\d|/div|/tr|/td|/th|/table)\s*/?>", "\n", s)
    s = re.sub(r"(?i)<\s*li[^>]*>", "\n- ", s)
    s = _TAG.sub(" ", s)
    s = html.unescape(s)
    s = _WS.sub(" ", s)
    return re.sub(r"\n\s*\n+", "\n", s).strip()


# ---------- salary ----------
_LPA = re.compile(r"(?i)(?:₹|rs\.?|inr)?\s*(\d+(?:\.\d+)?)\s*(?:-|–|to)\s*(\d+(?:\.\d+)?)\s*(?:lpa|lakhs?(?:\s*per\s*annum)?|l\b)")
_LPA_SINGLE = re.compile(r"(?i)(?:upto|up to|max(?:imum)?)\s*(?:₹|rs\.?|inr)?\s*(\d+(?:\.\d+)?)\s*(?:lpa|lakhs?)")
_INR_RANGE = re.compile(r"(?i)(?:₹|rs\.?|inr)\s*([\d,]{5,})\s*(?:-|–|to)\s*(?:₹|rs\.?|inr)?\s*([\d,]{5,})\s*(per\s*(month|annum|year)|/\s*(month|year|yr|mo))?")


def parse_salary_inr(text: str) -> tuple[int | None, int | None]:
    """Return (min, max) annual INR if the text states a salary range. Monthly figures x12."""
    if not text:
        return None, None
    m = _LPA.search(text)
    if m:
        a, b = float(m.group(1)), float(m.group(2))
        if 0 < a <= b < 200:
            return int(a * 100000), int(b * 100000)
    m = _LPA_SINGLE.search(text)
    if m:
        return None, int(float(m.group(1)) * 100000)
    m = _INR_RANGE.search(text)
    if m:
        a, b = int(m.group(1).replace(",", "")), int(m.group(2).replace(",", ""))
        period = (m.group(3) or "").lower()
        if "month" in period or "mo" in period:
            a, b = a * 12, b * 12
        if a <= b:
            return a, b
    return None, None


# ---------- deadline ----------
_DEADLINE = re.compile(
    r"(?i)(?:apply\s+by|last\s+date(?:\s+to\s+apply)?|deadline|applications?\s+close[sd]?(?:\s+on)?|closing\s+date)"
    r"\s*[:\-]?\s*([0-9]{1,2}[\s/.-][A-Za-z0-9]{1,9}[\s/.-],?\s*[0-9]{2,4}|[A-Za-z]{3,9}\s+[0-9]{1,2},?\s+[0-9]{4})")
_DATE_FORMATS = ["%d %B %Y", "%d %b %Y", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%B %d %Y", "%b %d %Y",
                 "%d %B, %Y", "%d %b, %Y", "%B %d, %Y", "%b %d, %Y", "%d/%m/%y", "%d-%b-%Y"]


def parse_deadline(text: str) -> str | None:
    if not text:
        return None
    m = _DEADLINE.search(text)
    if not m:
        return None
    raw = re.sub(r"\s+", " ", m.group(1)).strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def is_remote(location: str, description: str, keywords: list[str]) -> bool:
    loc = (location or "").lower()
    if any(k in loc for k in keywords):
        return True
    head = (description or "")[:600].lower()
    return any(k in head for k in ("fully remote", "100% remote", "remote-first", "work from home"))


def iso(d) -> str | None:
    if d is None:
        return None
    if isinstance(d, (int, float)):
        # epoch ms (Lever)
        from datetime import timezone
        return datetime.fromtimestamp(d / 1000 if d > 1e11 else d, timezone.utc).date().isoformat()
    if isinstance(d, (date, datetime)):
        return d.isoformat()
    return str(d)[:10]
