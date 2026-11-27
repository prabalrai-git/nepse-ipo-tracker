#!/usr/bin/env python3
"""Fetch NEPSE issue (IPO/FPO/MF/...) data and write public/data/ipos.json.

Accuracy design (the goal is: no fake alerts, no missed alerts)
----------------------------------------------------------------
PRIMARY source  : ShareSansar's JSON feed behind /existing-issues. It has one tab per
                  issue kind, including a dedicated "IPO to Migrant Workers" tab.
CROSS-CHECK     : MeroLagani's "Upcoming IPO" announcements. An eligible issue that
                  MeroLagani announces but ShareSansar lacks is reported under
                  `crosscheck.missing_from_primary` instead of being silently lost.

Known traps handled here (all verified against the live site):
  * The feed needs a session cookie from a prior page load, otherwise it returns an
    empty result with HTTP 202.
  * A page size (`length`) above 50 returns an EMPTY result with no error. We use 50
    and treat any suspiciously empty tab as a hard failure, never as "no IPOs".
  * Open/Upcoming/Closed is derived from the dates in Asia/Kathmandu, then compared
    with the site's own status code; disagreements are recorded, not hidden.
  * On any fatal error the previous ipos.json is left untouched (exit code 1), so a
    broken scrape can never wipe good data or trigger bogus alerts.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import requests
import urllib3
from bs4 import BeautifulSoup

import notify

ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = ROOT / "public" / "data" / "ipos.json"

SS_BASE = "https://www.sharesansar.com"
SS_ISSUES = f"{SS_BASE}/existing-issues"
ML_UPCOMING = "https://merolagani.com/Ipo.aspx?type=upcoming"

NPT = ZoneInfo("Asia/Kathmandu")
PAGE_SIZE = 50  # >50 silently returns nothing on ShareSansar
MAX_PAGES = 8
KEEP_CLOSED_DAYS = 30
UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)

# ShareSansar tab id -> (label, instrument, default_quota, minimum plausible recordsTotal).
# The minimum is a tripwire: the real totals are in the hundreds, so a tiny/zero
# total means the feed silently failed and we must not trust it.
TABS: dict[int, tuple[str, str, str, int]] = {
    8: ("IPO to Migrant Workers", "IPO", "FOREIGN_EMPLOYMENT", 30),
    1: ("IPO", "IPO", "GENERAL_PUBLIC", 100),
    2: ("FPO", "FPO", "GENERAL_PUBLIC", 5),
    5: ("IPO-Local", "IPO", "OTHER", 30),
    4: ("Mutual Fund", "MUTUAL_FUND", "OTHER", 20),
    3: ("Right Share", "RIGHT_SHARE", "OTHER", 50),
    7: ("Bonds/Debentures", "DEBENTURE", "OTHER", 20),
}
# Tabs where one company can legitimately appear in several separate issues over time.
REPEATABLE_TABS = {2, 3, 4, 7}

SOURCE_STATUS = {-2: "Pipeline", -1: "Upcoming", 0: "Open", 1: "Closed"}

FOREIGN_RE = re.compile(
    r"foreign[ -]+employ|foreign[ -]+(nepalese[ -]+)?(employees|workers)|migrant|"
    r"working[ -]+abroad|baideshik|remittance",
    re.I,
)
GENERAL_RE = re.compile(r"general[ -]+public", re.I)


class FatalScrapeError(Exception):
    """The primary source cannot be trusted; do not overwrite existing data."""


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


# --------------------------------------------------------------------------- HTTP
class Http:
    """requests.Session with retries and a verify=False fallback for SSL quirks."""

    def __init__(self) -> None:
        self.s = requests.Session()
        self.s.headers.update(
            {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"}
        )
        self.insecure_hosts: set[str] = set()

    def get(self, url: str, *, tries: int = 3, **kw: Any) -> requests.Response:
        host = requests.utils.urlparse(url).netloc
        last: Exception | None = None
        for attempt in range(1, tries + 1):
            verify = host not in self.insecure_hosts
            try:
                r = self.s.get(url, timeout=30, verify=verify, **kw)
                if r.status_code >= 500:
                    raise requests.HTTPError(f"HTTP {r.status_code}")
                return r
            except requests.exceptions.SSLError as exc:
                log(f"  SSL error for {host} ({exc.__class__.__name__}); retrying with verify=False")
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                self.insecure_hosts.add(host)
                last = exc
            except (requests.RequestException, ValueError) as exc:
                last = exc
                log(f"  attempt {attempt}/{tries} failed for {url}: {exc}")
                time.sleep(2 * attempt)
        raise FatalScrapeError(f"could not fetch {url}: {last}")


# ----------------------------------------------------------------------- helpers
def strip_html(value: Any) -> str:
    if value is None:
        return ""
    return BeautifulSoup(str(value), "lxml").get_text(" ", strip=True)


def first_href(value: Any) -> str | None:
    if not value:
        return None
    a = BeautifulSoup(str(value), "lxml").find("a", href=True)
    return a["href"] if a else None


def parse_date(value: Any) -> str | None:
    """ISO date string, or None for blank / placeholder dates such as -0001-11-30."""
    if not value:
        return None
    try:
        d = date.fromisoformat(str(value)[:10])
    except ValueError:
        return None
    return d.isoformat() if d.year >= 2000 else None


def to_number(value: Any) -> float | None:
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None


def norm_name(name: str) -> str:
    n = re.sub(r"[^a-z0-9 ]", " ", name.lower())
    n = re.sub(r"\b(limited|ltd|pvt|private|public|company|co)\b", " ", n)
    return re.sub(r"\s+", " ", n).strip()


def derive_status(open_d: str | None, close_d: str | None, today: date) -> str | None:
    if not open_d or not close_d:
        return None
    o, c = date.fromisoformat(open_d), date.fromisoformat(close_d)
    if today < o:
        return "Upcoming"
    if today <= c:
        return "Open"  # open through the closing date (issues close late that day)
    return "Closed"


def first_audience(announcement_url: str | None) -> str:
    """Audience of the FIRST tranche named in an offer-letter slug.

    Combined letters read "... N units ipo shares to <audience A> and M units ipo shares
    to <audience B> from <dates>". Each tranche has its own row on ShareSansar (in its own
    tab), so a row must be classified by its first tranche only; otherwise a locals row
    would be mislabelled as foreign-employment and alert twice.
    """
    slug = (announcement_url or "").rsplit("/", 1)[-1].replace("-", " ")
    after_units = re.split(r"\bunits?\b", slug, maxsplit=1)[-1]
    return re.split(r"\band\s+(?:is\s+\w+\s+its\s+)?[\d ]+units?\b", after_units, maxsplit=1)[0]


def foreign_tranche_units(announcement_url: str | None) -> int | None:
    """Units of a foreign-employment tranche that is *secondary* in a combined letter."""
    slug = (announcement_url or "").rsplit("/", 1)[-1].replace("-", " ")
    m = re.search(r"\band\s+(?:is\s+\w+\s+its\s+)?(\d+)\s+units?\s+ipo\s+shares\s+to\s+([a-z ]+?)\s+from\b", slug)
    return int(m.group(1)) if m and FOREIGN_RE.search(m.group(2)) else None


def classify_quota(tab: int, announcement_url: str | None) -> tuple[str, str]:
    """Return (quota_type, quota_source).

    The offer letter's first-tranche audience is the closest thing to ground truth, so it
    wins when it conclusively names a class; otherwise the ShareSansar tab decides.
    """
    label, instrument, default_quota, _ = TABS[tab]
    audience = first_audience(announcement_url)
    if FOREIGN_RE.search(audience):
        return "FOREIGN_EMPLOYMENT", "offer_letter"
    if instrument in ("IPO", "FPO") and tab != 5 and GENERAL_RE.search(audience):
        return "GENERAL_PUBLIC", "offer_letter"
    if tab == 8:  # the migrant tab is FE by definition, even if the slug is odd
        return "FOREIGN_EMPLOYMENT", "tab"
    return default_quota, "tab"


# ------------------------------------------------------------- ShareSansar (primary)
def fetch_tab(http: Http, tab: int) -> list[dict[str, Any]]:
    label, _, _, min_total = TABS[tab]
    rows: list[dict[str, Any]] = []
    start = 0
    total = None
    for _ in range(MAX_PAGES):
        r = http.get(
            SS_ISSUES,
            params={"draw": 1, "start": start, "length": PAGE_SIZE, "type": tab},
            headers={"X-Requested-With": "XMLHttpRequest", "Referer": SS_ISSUES},
        )
        try:
            payload = r.json()
        except ValueError as exc:
            raise FatalScrapeError(f"tab {tab} ({label}): non-JSON response (HTTP {r.status_code})") from exc
        total = int(payload.get("recordsTotal", 0))
        page = payload.get("data") or []
        if total < min_total or not page:
            raise FatalScrapeError(
                f"tab {tab} ({label}): suspicious empty result (total={total}, rows={len(page)}, "
                f"HTTP {r.status_code}); refusing to treat this as 'no IPOs'"
            )
        rows.extend(page)
        start += PAGE_SIZE
        # Newest/undated first, closed history after. Stop once we have reached closed rows.
        if start >= total or page[-1].get("status") == 1:
            break
    log(f"  tab {tab:<2} {label:<24} total={total:<4} fetched={len(rows)}")
    return rows


def fetch_sector(http: Http, company_url: str | None) -> str | None:
    if not company_url:
        return None
    try:
        r = http.get(company_url, tries=2)
        soup = BeautifulSoup(r.text, "lxml")
        td = soup.find("td", string=re.compile(r"^\s*Sector\s*$"))
        nxt = td.find_next_sibling("td") if td else None
        return nxt.get_text(" ", strip=True) if nxt else None
    except FatalScrapeError:
        return None


def normalise_row(tab: int, raw: dict[str, Any], today: date, warnings: list[str]) -> dict[str, Any] | None:
    label, instrument, _, _ = TABS[tab]
    company = raw.get("company") or {}
    symbol = strip_html(company.get("symbol"))
    name = strip_html(company.get("companyname"))
    if not symbol or not name:
        warnings.append(f"tab {tab}: row without symbol/name skipped (companyid={raw.get('companyid')})")
        return None

    src_code = raw.get("status")
    src_status = SOURCE_STATUS.get(src_code, f"Unknown({src_code})")
    open_d = parse_date(raw.get("opening_date"))
    close_d = parse_date(raw.get("closing_date"))

    # Issues without dates yet (pipeline) cannot be alerted on; counted, not listed.
    if not open_d or not close_d:
        return None
    status = derive_status(open_d, close_d, today)
    assert status is not None
    conflict = src_status in ("Upcoming", "Open", "Closed") and src_status != status
    if conflict:
        warnings.append(
            f"status mismatch {symbol} [{label}]: site says {src_status}, dates "
            f"{open_d}..{close_d} say {status} (using dates)"
        )

    ann_url = raw.get("announcement_link") or first_href(raw.get("view"))
    quota, quota_source = classify_quota(tab, ann_url)
    if quota != TABS[tab][2]:
        warnings.append(
            f"quota override {symbol} [{label}]: tab default {TABS[tab][2]} but offer letter says {quota}"
        )

    key = f"{raw.get('companyid')}:{tab}"
    if tab in REPEATABLE_TABS:
        key += f":{open_d}"

    return {
        "id": key,
        "symbol": symbol,
        "company_name": name,
        "sector": None,  # filled in later for active issues only
        "units": int(to_number(raw.get("total_units")) or 0) or None,
        "price": to_number(raw.get("issue_price")),
        "open_date": open_d,
        "close_date": close_d,
        "issue_manager": (raw.get("issue_manager") or "").strip() or None,
        "status": status,
        "quota_type": quota,
        "quota_source": quota_source,
        "instrument": instrument,
        "eligible": quota in ("FOREIGN_EMPLOYMENT", "GENERAL_PUBLIC"),
        "source_status": src_status,
        "status_conflict": conflict,
        "announcement_url": ann_url,
        "_company_url": first_href(company.get("symbol")),
        "_tab": tab,
        "_fe_tranche_units": foreign_tranche_units(ann_url),
        "source": "sharesansar",
    }


# ------------------------------------------------------------ MeroLagani (cross-check)
ML_RE = re.compile(
    r"^(?P<name>.+?) is going to issue its (?P<units>[\d,\.]+) units of (?P<kind>IPO|FPO) shares to (?P<aud>.+?) starting from",
    re.I,
)


def fetch_merolagani(http: Http) -> list[dict[str, Any]]:
    r = http.get(ML_UPCOMING)
    soup = BeautifulSoup(r.text, "lxml")
    out = []
    for block in soup.select(".announcement-list .media"):
        a = block.select_one(".media-body a")
        if not a:
            continue
        text = re.sub(r"\s+", " ", a.get_text(" ", strip=True))
        m = ML_RE.match(text)
        if not m:
            continue
        aud = m.group("aud")
        quota = (
            "FOREIGN_EMPLOYMENT" if FOREIGN_RE.search(aud)
            else "GENERAL_PUBLIC" if GENERAL_RE.search(aud)
            else "OTHER"
        )
        date_el = block.select_one("small.text-muted")
        out.append(
            {
                "company_name": m.group("name"),
                "units": int(float(m.group("units").replace(",", ""))),
                "quota_type": quota,
                "kind": m.group("kind").upper(),
                "announced": date_el.get_text(strip=True) if date_el else None,
                "text": text,
                "url": "https://merolagani.com" + a["href"] if a["href"].startswith("/") else a["href"],
            }
        )
    return out


def crosscheck(primary: list[dict[str, Any]], ml: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Eligible issues MeroLagani announces that the primary feed does not have."""
    have = {(norm_name(i["company_name"]), i["quota_type"], i["units"]) for i in primary}
    have_loose = {(norm_name(i["company_name"]), i["quota_type"]) for i in primary}
    missing = []
    for a in ml:
        if a["quota_type"] not in ("FOREIGN_EMPLOYMENT", "GENERAL_PUBLIC"):
            continue
        k = (norm_name(a["company_name"]), a["quota_type"])
        if (k[0], k[1], a["units"]) not in have:
            a = dict(a, units_differ=k in have_loose)
            missing.append(a)
    return missing


# --------------------------------------------------------------------------- main
def sort_key(i: dict[str, Any]) -> tuple:
    order = {"Open": 0, "Upcoming": 1, "Closed": 2}[i["status"]]
    if i["status"] == "Closed":
        d = -date.fromisoformat(i["close_date"]).toordinal()
    elif i["status"] == "Open":
        d = date.fromisoformat(i["close_date"]).toordinal()
    else:
        d = date.fromisoformat(i["open_date"]).toordinal()
    return (order, d, not i["eligible"], i["symbol"])


def run() -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    today = now.astimezone(NPT).date()
    warnings: list[str] = []
    http = Http()

    log("ShareSansar (primary):")
    http.get(SS_ISSUES)  # establishes the session/XSRF cookies the JSON feed requires
    raw_by_tab: dict[int, list[dict[str, Any]]] = {t: fetch_tab(http, t) for t in TABS}

    items: list[dict[str, Any]] = []
    pipeline_skipped = 0
    for tab, rows in raw_by_tab.items():
        for raw in rows:
            item = normalise_row(tab, raw, today, warnings)
            if item is None:
                if raw.get("company") and not parse_date(raw.get("opening_date")):
                    pipeline_skipped += 1
                continue
            items.append(item)

    # De-duplicate defensively (same id twice would double-notify).
    uniq: dict[str, dict[str, Any]] = {}
    for it in items:
        uniq.setdefault(it["id"], it)
    items = list(uniq.values())

    cutoff = today - timedelta(days=KEEP_CLOSED_DAYS)
    items = [
        i for i in items
        if i["status"] != "Closed" or date.fromisoformat(i["close_date"]) >= cutoff
    ]

    # Sector only for issues that matter (a handful of requests).
    sectors: dict[str, str | None] = {}
    for it in items:
        if it["status"] == "Closed":
            continue
        url = it["_company_url"]
        if url not in sectors:
            sectors[url] = fetch_sector(http, url)
        it["sector"] = sectors[url]
    # Safety net: a combined letter names a foreign-employment tranche, but the migrant
    # tab has no matching live row -> we would otherwise miss that alert silently.
    fe_names = {norm_name(i["company_name"]) for i in items
                if i["quota_type"] == "FOREIGN_EMPLOYMENT" and i["status"] != "Closed"}
    orphan_fe: list[dict[str, Any]] = []
    for it in items:
        if (it["_fe_tranche_units"] and it["status"] != "Closed"
                and norm_name(it["company_name"]) not in fe_names):
            msg = (f"{it['company_name']}: combined offer letter names a foreign-employment tranche of "
                   f"{it['_fe_tranche_units']} units but no foreign-employment row exists in the feed")
            warnings.append("CROSS-CHECK: " + msg)
            orphan_fe.append({"company_name": it["company_name"], "units": it["_fe_tranche_units"],
                              "quota_type": "FOREIGN_EMPLOYMENT", "reason": "combined_letter_no_fe_row",
                              "text": msg, "url": it["announcement_url"]})
    for it in items:
        for k in ("_company_url", "_tab", "_fe_tranche_units"):
            it.pop(k, None)
    items.sort(key=sort_key)

    log("MeroLagani (cross-check):")
    ml_ok, ml_items, missing = True, [], []
    try:
        ml_items = fetch_merolagani(http)
        active = [i for i in items if i["status"] != "Closed"]
        missing = crosscheck(active, ml_items)
        log(f"  {len(ml_items)} upcoming announcements, {len(missing)} not found in primary feed")
    except FatalScrapeError as exc:
        ml_ok = False
        warnings.append(f"cross-check source unavailable: {exc}")
        log(f"  unavailable: {exc}")

    missing = missing + orphan_fe
    for m in missing:
        if m.get("reason"):
            continue
        warnings.append(f"CROSS-CHECK: MeroLagani announces '{m['text']}' but ShareSansar has no matching entry")

    counts = {s: sum(1 for i in items if i["status"] == s) for s in ("Open", "Upcoming", "Closed")}
    counts["eligible_active"] = sum(1 for i in items if i["eligible"] and i["status"] != "Closed")
    counts["pipeline_skipped"] = pipeline_skipped

    return {
        "last_updated_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "as_of_date_npt": today.isoformat(),
        "sources": {
            "primary": {"name": "sharesansar", "url": SS_ISSUES, "ok": True},
            "crosscheck": {"name": "merolagani", "url": ML_UPCOMING, "ok": ml_ok},
        },
        "counts": counts,
        "warnings": warnings,
        "crosscheck": {"missing_from_primary": missing},
        "ipos": items,
    }


def write_atomic(data: dict[str, Any]) -> None:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, OUT_PATH)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Scrape NEPSE issues and send ntfy alerts.")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the alerts that would be sent; send nothing, record nothing")
    ap.add_argument("--no-notify", action="store_true", help="scrape only, skip alerts entirely")
    args = ap.parse_args(argv)

    try:
        data = run()
    except FatalScrapeError as exc:
        log(f"FATAL: {exc}\nipos.json was NOT modified.")
        if not args.no_notify:
            notify.report_failure(dry_run=args.dry_run)
        return 1
    write_atomic(data)
    c = data["counts"]
    log(
        f"Wrote {OUT_PATH.relative_to(ROOT)}: {c['Open']} open, {c['Upcoming']} upcoming, "
        f"{c['Closed']} recently closed ({c['eligible_active']} eligible & active); "
        f"{len(data['warnings'])} warning(s)"
    )
    for w in data["warnings"]:
        log(f"  ! {w}")
    if args.no_notify:
        return 0
    return notify.run_notifications(data, dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
