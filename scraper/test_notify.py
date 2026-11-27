"""Lifecycle tests for alert logic. Run: python -m unittest discover -s scraper -v"""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import notify


def ipo(id_, symbol, status, open_d, close_d, quota="FOREIGN_EMPLOYMENT", eligible=True):
    return {
        "id": id_, "symbol": symbol, "company_name": f"{symbol} Limited", "status": status,
        "open_date": open_d, "close_date": close_d, "quota_type": quota, "eligible": eligible,
        "units": 90000, "price": 100.0, "issue_manager": "X Capital", "announcement_url": "https://example.com/a",
    }


def data(today, *ipos, missing=()):
    return {"as_of_date_npt": today, "ipos": list(ipos),
            "crosscheck": {"missing_from_primary": list(missing)}}


class FakeClient:
    def __init__(self, fail=False):
        self.sent, self.fail = [], fail

    def send(self, title, message, **kw):
        if self.fail:
            raise notify.NotifyError("boom")
        self.sent.append((title, kw["priority"]))


class Lifecycle(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.state = {"notified": {}, "stale_alerted": False}
        self.save = lambda s: notify.save_state(s, self.tmp / "s.json")

    def cycle(self, d, client=None, dry=False):
        client = client or FakeClient()
        ev = notify.plan_events(d, self.state)
        fails = notify.deliver(ev, client, self.state, dry_run=dry, save=self.save)
        return client, fails

    def test_full_lifecycle_sends_each_event_exactly_once(self):
        # day 0: announced
        c, _ = self.cycle(data("2026-11-27", ipo("1:8", "AAA", "Upcoming", "2026-11-30", "2026-12-03")))
        self.assertEqual([t for t, _ in c.sent], ["IPO ANNOUNCED: AAA"])
        # same data again -> nothing
        c, _ = self.cycle(data("2026-11-27", ipo("1:8", "AAA", "Upcoming", "2026-11-30", "2026-12-03")))
        self.assertEqual(c.sent, [])
        # opens -> high priority, once
        opened = data("2026-11-30", ipo("1:8", "AAA", "Open", "2026-11-30", "2026-12-03"))
        c, _ = self.cycle(opened)
        self.assertEqual(c.sent, [("IPO OPEN: AAA", 4)])
        c, _ = self.cycle(opened)
        self.assertEqual(c.sent, [])
        # closing day -> one reminder, then silence
        last = data("2026-12-03", ipo("1:8", "AAA", "Open", "2026-11-30", "2026-12-03"))
        c, _ = self.cycle(last)
        self.assertEqual(c.sent, [("LAST DAY: AAA", 4)])
        c, _ = self.cycle(last)
        self.assertEqual(c.sent, [])
        # closed -> never alerts
        c, _ = self.cycle(data("2026-12-04", ipo("1:8", "AAA", "Closed", "2026-11-30", "2026-12-03")))
        self.assertEqual(c.sent, [])

    def test_first_seen_already_open_alerts_once_and_not_announced_later(self):
        d = data("2026-11-27", ipo("2:8", "KPL", "Open", "2026-11-26", "2026-12-01"))
        c, _ = self.cycle(d)
        self.assertEqual(len(c.sent), 1)
        self.assertTrue(c.sent[0][0].startswith("IPO OPEN:"))
        c, _ = self.cycle(d)
        self.assertEqual(c.sent, [])

    def test_first_seen_on_last_day_sends_single_message(self):
        d = data("2026-12-01", ipo("2:8", "KPL", "Open", "2026-11-26", "2026-12-01"))
        c, _ = self.cycle(d)
        self.assertEqual([t for t, _ in c.sent], ["LAST DAY: KPL"])
        c, _ = self.cycle(d)
        self.assertEqual(c.sent, [])

    def test_failed_send_is_not_recorded_and_retries(self):
        d = data("2026-11-27", ipo("3:1", "BBB", "Open", "2026-11-26", "2026-12-01", "GENERAL_PUBLIC"))
        c, fails = self.cycle(d, FakeClient(fail=True))
        self.assertEqual(fails, 1)
        self.assertEqual(self.state["notified"], {})
        c, fails = self.cycle(d)  # ntfy is back
        self.assertEqual((fails, len(c.sent)), (0, 1))

    def test_date_extension_does_not_realert(self):
        self.cycle(data("2026-11-30", ipo("4:1", "CCC", "Open", "2026-11-30", "2026-12-03", "GENERAL_PUBLIC")))
        c, _ = self.cycle(data("2026-12-02", ipo("4:1", "CCC", "Open", "2026-11-30", "2026-12-08", "GENERAL_PUBLIC")))
        self.assertEqual(c.sent, [])

    def test_ineligible_never_alerts(self):
        c, _ = self.cycle(data("2026-11-27", ipo("5:4", "MF", "Open", "2026-11-25", "2026-11-30", "OTHER", False)))
        self.assertEqual(c.sent, [])

    def test_two_quotas_same_company_alert_separately(self):
        c, _ = self.cycle(data(
            "2026-11-27",
            ipo("6:8", "HPHL", "Open", "2026-11-26", "2026-12-01"),
            ipo("6:1", "HPHL", "Upcoming", "2026-12-04", "2026-12-09", "GENERAL_PUBLIC"),
        ))
        self.assertEqual(len(c.sent), 2)

    def test_dry_run_sends_and_records_nothing(self):
        d = data("2026-11-27", ipo("7:8", "DDD", "Open", "2026-11-26", "2026-12-01"))
        c, _ = self.cycle(d, dry=True)
        self.assertEqual((c.sent, self.state["notified"]), ([], {}))

    def test_crosscheck_flag_once(self):
        m = {"company_name": "Zed Hydro Limited", "quota_type": "GENERAL_PUBLIC", "units": 5,
             "text": "Zed Hydro is going to issue...", "url": "https://merolagani.com/x"}
        d = data("2026-11-27", missing=[m])
        c, _ = self.cycle(d)
        self.assertEqual(len(c.sent), 1)
        self.assertTrue(c.sent[0][0].startswith("UNVERIFIED"))
        c, _ = self.cycle(d)
        self.assertEqual(c.sent, [])

    def test_legacy_seed_state_file_loads(self):
        p = self.tmp / "seed.json"
        p.write_text('{"notified": []}')
        self.assertEqual(notify.load_state(p), {"notified": {}, "stale_alerted": False})


class Layout(unittest.TestCase):
    """The alert layout the user asked for: title, company, quota type, one button."""

    def _event(self, quota, status="Open"):
        d = data("2026-11-27", ipo("9:8", "KPL", status, "2026-11-26", "2026-12-01", quota))
        d["ipos"][0]["company_name"] = "Kantipur Pharmaceuticals Lab Limited"
        return notify.plan_events(d, {"notified": {}, "stale_alerted": False})[0]

    def test_foreign_body_is_company_then_type_only(self):
        with mock.patch.dict("os.environ", {"DASHBOARD_URL": "https://me.github.io/nepse-ipo-tracker/"}):
            ev = self._event("FOREIGN_EMPLOYMENT")
        self.assertEqual(ev.title, "IPO OPEN: KPL")
        self.assertEqual(ev.message, "Kantipur Pharmaceuticals Lab Limited\nForeign Employment")

    def test_general_body(self):
        ev = self._event("GENERAL_PUBLIC", "Upcoming")
        self.assertEqual(ev.title, "IPO ANNOUNCED: KPL")
        self.assertEqual(ev.message, "Kantipur Pharmaceuticals Lab Limited\nGeneral Public")

    def test_exactly_one_button_to_the_dashboard(self):
        with mock.patch.dict("os.environ", {"DASHBOARD_URL": "https://me.github.io/nepse-ipo-tracker/"}):
            ev = self._event("FOREIGN_EMPLOYMENT")
            self.assertEqual(ev.actions, [{"action": "view", "label": "View details",
                                           "url": "https://me.github.io/nepse-ipo-tracker/"}])
            self.assertEqual(notify.tap_url(), "https://me.github.io/nepse-ipo-tracker/")

    def test_without_dashboard_url_no_button_and_tap_falls_back_to_meroshare(self):
        with mock.patch.dict("os.environ", {"DASHBOARD_URL": ""}), mock.patch("notify.load_dotenv"):
            ev = self._event("FOREIGN_EMPLOYMENT")
            self.assertEqual(ev.actions, [])
            self.assertEqual(notify.tap_url(), notify.CLICK_URL)

    def test_rejects_non_http_dashboard_url(self):
        with mock.patch.dict("os.environ", {"DASHBOARD_URL": "javascript:alert(1)"}), mock.patch("notify.load_dotenv"):
            self.assertIsNone(notify.dashboard_url())


class ClientBehaviour(unittest.TestCase):
    def test_rejects_unsafe_topic(self):
        with self.assertRaises(notify.NotifyError):
            notify.NtfyClient("bad topic/with slash")

    def test_retries_429_using_retry_after_then_succeeds(self):
        r429 = mock.Mock(status_code=429, headers={"Retry-After": "2"}, text="")
        r200 = mock.Mock(status_code=200, headers={}, text="")
        with mock.patch("notify.requests.post", side_effect=[r429, r200]) as post, \
             mock.patch("notify.time.sleep") as sleep:
            notify.NtfyClient("abc").send("t", "m")
        self.assertEqual(post.call_count, 2)
        sleep.assert_called_with(2)

    def test_client_error_is_not_retried(self):
        r403 = mock.Mock(status_code=403, headers={}, text="forbidden")
        with mock.patch("notify.requests.post", return_value=r403) as post:
            with self.assertRaises(notify.NotifyError):
                notify.NtfyClient("abc").send("t", "m")
        self.assertEqual(post.call_count, 1)

    def test_gives_up_after_retries(self):
        r500 = mock.Mock(status_code=503, headers={}, text="")
        with mock.patch("notify.requests.post", return_value=r500), mock.patch("notify.time.sleep"):
            with self.assertRaises(notify.NotifyError):
                notify.NtfyClient("abc").send("t", "m", tries=3)


if __name__ == "__main__":
    unittest.main()
