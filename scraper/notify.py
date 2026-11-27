#!/usr/bin/env python3
"""ntfy.sh push alerts for eligible NEPSE issues.

Alert events (eligible = FOREIGN_EMPLOYMENT or GENERAL_PUBLIC, never Closed):
  announced : an eligible issue is first seen as Upcoming            (priority default)
  opened    : an eligible issue is Open and we have not said so yet  (priority high)
  closing   : last day to apply, sent once more as a safety net      (priority high)
  flagged   : MeroLagani announces an eligible issue ShareSansar lacks (priority default)
  health    : the scraper has been failing, so data is going stale   (priority high)

No-duplicate / no-missed rules:
  * Every sent event is recorded per issue id in scraper/notified_state.json.
  * State is written ONLY after ntfy accepted the message (HTTP 200), and immediately
    after each message, so a crash half-way never loses or repeats alerts.
  * A failed send is not recorded and is retried on the next run.
  * Extending an issue's dates does not re-alert (the issue id does not contain dates).

Usage:
  python scraper/notify.py --generate-topic   # print a fresh random topic name
  python scraper/notify.py --test             # send one test notification
The topic is read from the NTFY_TOPIC env var (or a git-ignored .env file) and is
never printed or logged, because anyone who knows it can read or forge your alerts.

Every alert looks the same: a title ("IPO OPEN: KPL"), the company name and quota type,
and ONE button, "View details", that opens the dashboard (DASHBOARD_URL). Tapping the
notification itself opens the dashboard too. Without DASHBOARD_URL the tap falls back to
MeroShare and no button is shown.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import sys
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parent.parent
STATE_PATH = ROOT / "scraper" / "notified_state.json"
DATA_PATH = ROOT / "public" / "data" / "ipos.json"

CLICK_URL = "https://cdsc.com.np"  # MeroShare entry point requested for tap action
DEFAULT_SERVER = "https://ntfy.sh"
STALE_HOURS = 30  # twice-daily schedule + GitHub scheduling delay + one retry margin
PRUNE_DAYS = 180

TYPE_LABEL = {
    "FOREIGN_EMPLOYMENT": "Foreign Employment",
    "GENERAL_PUBLIC": "General Public",
}
PRIORITY = {"default": 3, "high": 4}


class NotifyError(Exception):
    """A notification could not be delivered."""


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


# ------------------------------------------------------------------------ config
def load_dotenv(path: Path = ROOT / ".env") -> None:
    """Tiny .env reader so local runs work without exporting variables."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def generate_topic() -> str:
    # 24 URL-safe chars ~ 144 bits: unguessable, and valid ntfy topic characters.
    return "nepse-ipo-" + secrets.token_urlsafe(18).replace("-", "x").replace("_", "y")


# ------------------------------------------------------------------------ client
class NtfyClient:
    def __init__(self, topic: str, server: str = DEFAULT_SERVER) -> None:
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", topic):
            raise NotifyError("NTFY_TOPIC must be 1-64 chars of letters, digits, '_' or '-'")
        self._topic = topic
        self._server = server.rstrip("/")

    def send(
        self,
        title: str,
        message: str,
        *,
        priority: int = 3,
        tags: list[str] | None = None,
        click: str | None = None,
        actions: list[dict[str, Any]] | None = None,
        tries: int = 4,
    ) -> None:
        # JSON publishing keeps non-ASCII text safe (HTTP headers are not) and keeps the
        # topic out of the URL, and therefore out of any proxy or error log line.
        payload: dict[str, Any] = {
            "topic": self._topic,
            "title": title,
            "message": message,
            "priority": priority,
            "tags": tags or [],
        }
        if click:
            payload["click"] = click
        if actions:
            payload["actions"] = actions

        last = "unknown error"
        for attempt in range(1, tries + 1):
            try:
                r = requests.post(self._server, json=payload, timeout=20)
            except requests.RequestException as exc:
                last = f"network error ({exc.__class__.__name__})"
                time.sleep(min(5 * attempt, 30))
                continue
            if r.status_code == 200:
                return
            if r.status_code == 429:
                wait = _retry_after(r) or 5 * attempt
                last = f"rate limited (HTTP 429), waited {wait}s"
                time.sleep(min(wait, 60))
                continue
            if r.status_code >= 500:
                last = f"ntfy server error (HTTP {r.status_code})"
                time.sleep(min(5 * attempt, 30))
                continue
            # 4xx other than 429 will not get better by retrying.
            raise NotifyError(f"ntfy rejected the message (HTTP {r.status_code}): {r.text[:200]}")
        raise NotifyError(f"gave up after {tries} attempts: {last}")


def _retry_after(r: requests.Response) -> int | None:
    try:
        return max(1, int(float(r.headers.get("Retry-After", ""))))
    except ValueError:
        return None


def get_client() -> NtfyClient | None:
    load_dotenv()
    topic = os.environ.get("NTFY_TOPIC", "").strip()
    if not topic:
        return None
    return NtfyClient(topic, os.environ.get("NTFY_SERVER", DEFAULT_SERVER))


def dashboard_url() -> str | None:
    """Where the alert's button / tap should go: the PWA that shows the scraped details."""
    load_dotenv()
    url = os.environ.get("DASHBOARD_URL", "").strip()
    return url if url.startswith(("https://", "http://")) else None


def tap_url() -> str:
    return dashboard_url() or CLICK_URL


# ------------------------------------------------------------------------- state
def load_state(path: Path = STATE_PATH) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        raw = {}
    notified = raw.get("notified")
    if not isinstance(notified, dict):  # seed file used an empty list
        notified = {}
    return {"notified": notified, "stale_alerted": bool(raw.get("stale_alerted", False))}


def save_state(state: dict[str, Any], path: Path = STATE_PATH) -> None:
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def prune_state(state: dict[str, Any], live_ids: set[str], now: datetime) -> None:
    """Forget long-gone issues so the file does not grow forever."""
    for ipo_id in list(state["notified"]):
        if ipo_id in live_ids:
            continue
        stamps = [s for s in state["notified"][ipo_id].values() if isinstance(s, str)]
        newest = max(stamps) if stamps else ""
        try:
            age = now - datetime.fromisoformat(newest.replace("Z", "+00:00"))
        except ValueError:
            continue
        if age.days > PRUNE_DAYS:
            del state["notified"][ipo_id]


# ------------------------------------------------------------------------ events
@dataclass
class Event:
    ipo_id: str
    kind: str  # announced | opened | closing | flagged | health
    title: str
    message: str
    priority: int
    tags: list[str]
    actions: list[dict[str, Any]] = field(default_factory=list)
    marks: list[str] = field(default_factory=list)  # state kinds to record once delivered


def _describe(ipo: dict[str, Any]) -> str:
    return f"{ipo['company_name']}\n{TYPE_LABEL.get(ipo['quota_type'], ipo['quota_type'])}"


def _actions() -> list[dict[str, Any]]:
    url = dashboard_url()
    return [{"action": "view", "label": "View details", "url": url}] if url else []


def plan_events(data: dict[str, Any], state: dict[str, Any]) -> list[Event]:
    today = date.fromisoformat(data["as_of_date_npt"])
    events: list[Event] = []

    for ipo in data["ipos"]:
        if not ipo.get("eligible") or ipo["status"] == "Closed":
            continue
        rec = state["notified"].get(ipo["id"], {})
        sym = ipo["symbol"]
        last_day = date.fromisoformat(ipo["close_date"]) == today

        if ipo["status"] == "Upcoming":
            if "announced" not in rec:
                events.append(Event(
                    ipo["id"], "announced", f"IPO ANNOUNCED: {sym}", _describe(ipo),
                    PRIORITY["default"], ["calendar"], _actions(), ["announced"],
                ))
        elif ipo["status"] == "Open":
            if "opened" not in rec:
                # Never send "opened" and "closing" back to back for the same issue.
                title = f"LAST DAY: {sym}" if last_day else f"IPO OPEN: {sym}"
                marks = ["announced", "opened"] + (["closing"] if last_day else [])
                events.append(Event(
                    ipo["id"], "opened", title, _describe(ipo),
                    PRIORITY["high"], ["rotating_light"], _actions(), marks,
                ))
            elif last_day and "closing" not in rec:
                events.append(Event(
                    ipo["id"], "closing", f"LAST DAY: {sym}", _describe(ipo),
                    PRIORITY["high"], ["alarm_clock"], _actions(), ["closing"],
                ))

    for item in data.get("crosscheck", {}).get("missing_from_primary", []):
        ident = re.sub(r"[^a-z0-9]+", "-", item["company_name"].lower()).strip("-")
        ipo_id = f"xc:{ident}:{item['quota_type']}:{item.get('units')}"
        if "flagged" in state["notified"].get(ipo_id, {}):
            continue
        events.append(Event(
            ipo_id, "flagged", f"UNVERIFIED IPO: {item['company_name']}",
            f"{item['text']}\n\nSeen in a second source but not yet in the main data feed. "
            "Check MeroShare directly.",
            PRIORITY["default"], ["warning"], _actions(), ["flagged"],
        ))
    return events


# ---------------------------------------------------------------------- delivery
def _now() -> datetime:
    return datetime.now(timezone.utc)


def deliver(
    events: list[Event],
    client: NtfyClient | None,
    state: dict[str, Any],
    *,
    dry_run: bool,
    save=save_state,
    now=_now,
) -> int:
    """Send each event; record it only after ntfy accepted it. Returns failure count."""
    failures = 0
    for ev in events:
        label = f"[{ev.kind}] {ev.title}"
        if dry_run:
            log(f"DRY-RUN would send {label}\n    " + ev.message.replace("\n", "\n    "))
            continue
        assert client is not None
        try:
            client.send(ev.title, ev.message, priority=ev.priority, tags=ev.tags,
                        click=tap_url(), actions=ev.actions)
        except NotifyError as exc:
            failures += 1
            log(f"FAILED to send {label}: {exc} (will retry next run)")
            continue
        stamp = now().strftime("%Y-%m-%dT%H:%M:%SZ")
        rec = state["notified"].setdefault(ev.ipo_id, {})
        for mark in ev.marks:
            rec.setdefault(mark, stamp)
        save(state)
        log(f"sent {label}")
    return failures


def run_notifications(data: dict[str, Any], *, dry_run: bool = False) -> int:
    """Called after a successful scrape. Returns 0 on success, 1 on any problem."""
    client = get_client()
    if client is None and not dry_run:
        msg = "NTFY_TOPIC is not set, so no alerts can be sent."
        if os.environ.get("GITHUB_ACTIONS") == "true":
            log(f"ERROR: {msg} Add it under Settings > Secrets and variables > Actions.")
            return 1
        log(f"WARNING: {msg} Skipping notifications; state left untouched.")
        return 0

    state = load_state()
    events = plan_events(data, state)
    log(f"{len(events)} alert(s) to send")
    failures = deliver(events, client, state, dry_run=dry_run)
    if not dry_run:
        # The scrape worked, so any earlier "scraper is failing" episode is over.
        state["stale_alerted"] = False
        prune_state(state, {i["id"] for i in data["ipos"]}, _now())
        save_state(state)
    return 1 if failures else 0


def report_failure(*, dry_run: bool = False) -> None:
    """Called when the scrape itself failed: warn once if the data has gone stale."""
    try:
        updated = json.loads(DATA_PATH.read_text(encoding="utf-8")).get("last_updated_utc")
        age_h = (_now() - datetime.fromisoformat(updated.replace("Z", "+00:00"))).total_seconds() / 3600
    except (FileNotFoundError, json.JSONDecodeError, AttributeError, ValueError):
        age_h = float("inf")  # never had a good scrape
    if age_h < STALE_HOURS:
        return
    state = load_state()
    if state["stale_alerted"]:
        return
    age_txt = "a long time" if age_h == float("inf") else f"{age_h:.0f} hours"
    title, body = "IPO tracker is not updating", (
        f"The scraper has failed and the data is {age_txt} old. New IPOs may be missed. "
        "Check the GitHub Actions run, and look at MeroShare directly."
    )
    if dry_run:
        log(f"DRY-RUN would send [health] {title}: {body}")
        return
    client = get_client()
    if client is None:
        return
    try:
        client.send(title, body, priority=PRIORITY["high"], tags=["warning"],
                    click=tap_url(), actions=_actions())
    except NotifyError as exc:
        log(f"FAILED to send health alert: {exc}")
        return
    state["stale_alerted"] = True
    save_state(state)
    log("sent [health] alert")


# --------------------------------------------------------------------------- CLI
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--generate-topic", action="store_true", help="print a random topic name")
    ap.add_argument("--test", action="store_true", help="send one test notification")
    args = ap.parse_args()
    if args.generate_topic:
        print(generate_topic())
        return 0
    if args.test:
        client = get_client()
        if client is None:
            log("NTFY_TOPIC is not set (export it or put it in .env).")
            return 1
        try:
            client.send("NEPSE IPO Alert: test", "If you can read this, alerts are working.",
                        priority=PRIORITY["high"], tags=["white_check_mark"], click=tap_url(),
                        actions=_actions())
        except NotifyError as exc:
            log(f"Test failed: {exc}")
            return 1
        log("Test notification accepted by ntfy.")
        return 0
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
