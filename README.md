# NEPSE IPO Alert

A free, installable web app (PWA) that tracks open and upcoming NEPSE IPOs and pushes an alert to your phone
the moment one you can apply for is announced or opens.

Built for a Nepali investor working abroad (eligible for the **10% foreign-employment quota** and the
**general public quota** on MeroShare). Everything runs at **$0/month**:

| Part | What it does | Where it runs |
|---|---|---|
| Scraper (`scraper/`) | Reads IPO data twice a day, writes `public/data/ipos.json`, sends alerts | GitHub Actions |
| Dashboard (`src/`) | Vue 3 PWA with live JST/NPT countdowns | GitHub Pages |
| Alerts | Push notifications to your phone | [ntfy.sh](https://ntfy.sh) (free) + the ntfy app |

> Always confirm on MeroShare (<https://cdsc.com.np>) before applying. This app is a notifier, not an
> authority.

---

## How it works

```
GitHub Actions (09:15 and 18:15 JST)
  └─ scraper/fetch_ipos.py
       ├─ ShareSansar JSON feed  (primary, one tab per quota)
       ├─ MeroLagani announcements (cross-check)
       ├─ writes public/data/ipos.json
       └─ scraper/notify.py ──► ntfy.sh ──► ntfy app on your phone
  └─ commits ipos.json + notified_state.json ──► Deploy workflow ──► GitHub Pages ──► the PWA
```

**Alerts you get** (only for foreign-employment and general-public issues):

| Alert | When | Priority |
|---|---|---|
| Announced | An eligible IPO first appears as upcoming | normal |
| Open now | The IPO's opening day | high |
| Last day | The closing day (a safety net in case you missed it) | high |
| Unverified notice | MeroLagani lists an eligible IPO that ShareSansar does not | normal |
| Tracker not updating | The scraper has failed for 30+ hours | high |

Every alert has the same layout: a title (`IPO OPEN: KPL`), the company name and quota type
(Foreign Employment or General Public), and one **View details** button that opens the dashboard, where all
the scraped details are. (To apply, open MeroShare yourself at <https://cdsc.com.np>.) Tapping the notification itself opens the dashboard too. The
workflow sets the dashboard address from your repository automatically (`DASHBOARD_URL`); for local runs you can put
`DASHBOARD_URL=https://<you>.github.io/nepse-ipo-tracker/` in `.env`.

Each alert is sent **once**. What was sent is recorded in `scraper/notified_state.json`, and a message is only
recorded after ntfy accepted it, so a failed send is retried on the next run instead of being lost.
Mutual funds, local-resident IPOs, right shares and debentures never trigger alerts.

---

## Setup (about 15 minutes)

### 1. Put the code on GitHub

1. Create a new **public** repository on GitHub. Keep the name `nepse-ipo-tracker`. (The deploy workflow reads the
   repo name itself, so another name also works.)
2. In this folder:

   ```bash
   git init -b main
   git add .
   git status        # check that .env is NOT listed
   git commit -m "Initial commit"
   git remote add origin https://github.com/<your-username>/nepse-ipo-tracker.git
   git push -u origin main
   ```

   Before pushing, make sure `scraper/notified_state.json` still contains `{"notified": []}` so your first run
   sends the alerts for currently open IPOs.

### 2. Create your private ntfy topic

A topic is the "mailbox name" alerts are sent to. **Treat it like a password**: anyone who knows it can read or
forge your alerts.

```bash
python3 -m venv .venv
.venv/bin/pip install -r scraper/requirements.txt
.venv/bin/python scraper/notify.py --generate-topic
```

Copy the output (for example `nepse-ipo-AbC123...`). To keep a copy for local testing, put
`NTFY_TOPIC=<that value>` in a file named `.env` (it is git-ignored).

### 3. Add the topic as a GitHub secret

Repository **Settings → Secrets and variables → Actions → New repository secret**

- Name: `NTFY_TOPIC`
- Secret: the topic only, with no `NTFY_TOPIC=` prefix and no quotes

### 4. Turn on GitHub Pages

Repository **Settings → Pages → Build and deployment → Source: GitHub Actions**
(not "Deploy from a branch"). Without this the deploy workflow fails at `configure-pages` with
*"Get Pages site failed … Not Found"*.

Then open **Actions → Deploy PWA to GitHub Pages → Run workflow**. When it finishes, your app is at
`https://<your-username>.github.io/nepse-ipo-tracker/`.

### 5. Set up your phone (do this before the first scrape)

1. Install the free **ntfy** app: [iPhone](https://apps.apple.com/app/ntfy/id1625396347) ·
   [Android](https://play.google.com/store/apps/details?id=io.heckel.ntfy)
2. In ntfy tap **+**, paste your topic **name**, keep the server as `ntfy.sh`, tap **Subscribe**, allow
   notifications.
3. Open your app, tap the 🔔 button, paste the topic once, and tap **Send test notification**. Your phone should
   buzz within seconds. (The topic is stored only in that browser, never uploaded to GitHub.)

### 6. Run the first scrape

**Actions → Scrape IPOs → Run workflow** (leave "dry run" unchecked). Within about a minute you should get one
alert per eligible IPO that is currently open or upcoming. From then on it runs by itself at 09:15 and 18:15 JST.

---

## Install the app on your phone

**iPhone**
1. Open the site in **Safari**.
2. Tap the **Share** button, then **Add to Home Screen**, then **Add**.

**Android**
1. Open the site in **Chrome**.
2. Tap **Install app** in the banner, or the ⋮ menu → **Install app** / **Add to Home screen**.
   (The 🔔 setup panel also has an install button when your browser allows it.)

Once installed it opens full-screen and works offline with the last saved data. When a new version of the app is
available, a **Reload** bar appears at the bottom.

---

## Local development

```bash
npm install
npm run dev                 # app at http://localhost:5173/nepse-ipo-tracker/
npm run build               # type-check + production build
npm run preview             # serve the production build (this is what has the service worker)

# scraper
.venv/bin/python scraper/fetch_ipos.py --dry-run     # scrape; print alerts instead of sending
.venv/bin/python scraper/fetch_ipos.py --no-notify   # scrape only
.venv/bin/python scraper/notify.py --test            # send one test alert to your real topic
.venv/bin/python -m unittest discover -s scraper     # alert-logic tests
```

Deploying somewhere other than GitHub Pages (Vercel, Cloudflare Pages)? Build with `VITE_BASE=/ npm run build`.

> **Careful when testing locally:** running `fetch_ipos.py` *without* `--dry-run` while `NTFY_TOPIC` is set sends
> real alerts and records them in `scraper/notified_state.json`. If you then commit that file, GitHub will think
> those alerts were already sent.

---

## Good to know

- **Re-sending the same alerts** (for example to test your phone): replace `scraper/notified_state.json` with
  `{"notified": {}, "stale_alerted": false}`, commit, and run **Scrape IPOs** again. Run `git pull` first, because the
  workflow commits to the repo too.
- **Dry run on GitHub:** the "dry run" checkbox on the manual run prints the alerts in the log and records nothing.
- **Timing:** GitHub can start scheduled runs 15–60 minutes late. The "Announced" alert, usually days before an IPO
  opens, is your real head start.
- **Closing time:** the data gives only the closing *date*. The countdown targets the end of that day in Nepal time
  and is labelled "approx." The real MeroShare cut-off may be earlier, so do not wait for the last minute.
- **Missed alerts?** ntfy keeps unread messages for 12 hours. If your phone was off longer, check the dashboard.
  The closing-day reminder is a second chance.
- **Repository inactivity:** GitHub pauses scheduled workflows after 60 days without repo activity. The twice-daily
  data commits count as activity, so this should not happen.
- **If the scraper breaks:** the workflow turns red (GitHub emails you), the old data is kept untouched, and after
  30 hours without a successful update you get a "Tracker is not updating" alert and the app shows a warning bar.

## Troubleshooting

| Symptom | Likely cause and fix |
|---|---|
| Deploy fails at `configure-pages` ("Not Found") | Pages is not enabled. Settings → Pages → Source: **GitHub Actions**, then re-run. |
| Scrape run fails with "NTFY_TOPIC is not set" | The secret is missing or misspelled. Re-add it exactly as `NTFY_TOPIC`. |
| Log says "sent …" but the phone shows nothing | The topic in the ntfy app differs from the secret. Compare them character by character. |
| The test button works but scrape alerts do not arrive | They already fired earlier (see `notified_state.json`). Reset it as described above. |
| Scraper log says "suspicious empty result" | ShareSansar returned an empty feed. It refuses to treat that as "no IPOs", so nothing is overwritten. Re-run later. |
| Dashboard shows an old "Updated" time | Scraper failing or the site cache lagging. Check **Actions → Scrape IPOs**. |

## Data sources

- **Primary:** ShareSansar's issue feed, which has a separate tab for each quota, including "IPO to Migrant
  Workers" (the 10% foreign-employment quota).
- **Cross-check:** MeroLagani's upcoming-IPO announcements. If it lists an eligible IPO that ShareSansar lacks, you
  get an "unverified notice" and the dashboard shows an orange banner.

Quota is taken from the offer letter's first-named group, then the source tab. Open/upcoming/closed is recomputed
from the dates in Nepal time (UTC+05:45), and any disagreement with the source's own status is recorded in
`ipos.json`'s `warnings`.

## Project layout

```
scraper/        fetch_ipos.py (scrape), notify.py (alerts), test_notify.py, notified_state.json
public/data/    ipos.json (generated; the app reads this)
src/            Vue app (components, composables, utils)
.github/workflows/  scrape_ipos.yml (twice daily), deploy.yml (GitHub Pages)
```
