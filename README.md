# FusionSolar Weekly Solar Report

Automated weekly email summary of your Huawei FusionSolar billing-cycle grid data — designed for Malaysian TNB billing cycles where excess exported energy is penalised.

## How it works

TNB bills on a fixed day each month (default: **15th**). If you export more energy than you import during a cycle, TNB charges a storage penalty on the excess. This tool:

1. Logs into FusionSolar International and scrapes **daily grid data** (Fed to Grid / From Grid) for every day from the billing reset date to today
2. Calculates cumulative net excess with a **5% heat-loss deduction**
3. Emails a summary with a **daily breakdown table** to all configured recipients

The container runs its own cron internally and fires the report on a schedule you control via `CRON_SCHEDULE` (default: every Friday at 8 AM). You can also trigger a report manually any time.

---

## Quick Start

### 1. Clone and configure

```bash
git clone https://github.com/AllHailTheFox/Huaiwei-Automated-Fusion-Report.git
cd Huaiwei-Automated-Fusion-Report
cp .env.example .env
```

Edit `.env`:

```env
FUSIONSOLAR_USERNAME=your_fusionsolar_email@gmail.com
FUSIONSOLAR_PASSWORD=your_fusionsolar_password
EMAIL_PASSWORD=xxxxxxxxxxxxxxxxxxxx
RECIPIENT_EMAILS=you@gmail.com,partner@yahoo.com
STATION_ID=72289258
BILLING_DAY=15
CRON_SCHEDULE=0 8 * * 5
RUN_ON_START=false
```

### 2. Generate a Gmail App Password

Your normal Gmail password **will not work**. You need an **App Password**:

1. Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
2. Select app: **Mail**, device: **Other** → name it "FusionSolar"
3. Copy the generated password into `EMAIL_PASSWORD`

> **Important:** Copy the password exactly as shown — do **not** include spaces. The app password is 16 characters with no spaces (Google may display it with spaces for readability, ignore them).
>
> **Requires 2-Step Verification to be enabled on your Google account.**

### 3. Build and run with Docker

```bash
docker compose build
docker compose up -d
```

The container will stay up running cron internally and fire the report on schedule.

---

## Manual Triggers

### Fire a report right now (one-off)

```bash
docker compose run --rm fusionsolar-extractor python /app/extract_and_email.py
```

This spins up a temporary container, runs the script once, sends the email, and exits. Does not affect the running scheduled container.

### Fire a report on next container start

Set in `.env`:

```env
RUN_ON_START=true
```

Then:

```bash
docker compose up -d --force-recreate
```

After it sends, **flip `RUN_ON_START` back to `false`** — otherwise every container restart will trigger another email.

### Change the schedule

Edit `CRON_SCHEDULE` in `.env` (standard 5-field cron syntax), then:

```bash
docker compose up -d --force-recreate
```

Examples:

| Schedule | Cron |
|---|---|
| Every Friday 8 AM | `0 8 * * 5` |
| Every Monday 8 AM | `0 8 * * 1` |
| Mondays and Fridays 8 AM | `0 8 * * 1,5` |
| 1st of every month 8 AM | `0 8 1 * *` |

---

## Configuration Reference

All settings live in your `.env` file:

| Variable | Required | Default | Description |
|---|---|---|---|
| `FUSIONSOLAR_USERNAME` | Yes | — | Your FusionSolar login email |
| `FUSIONSOLAR_PASSWORD` | Yes | — | Your FusionSolar password |
| `EMAIL_PASSWORD` | Yes | — | Gmail app password (no spaces) |
| `RECIPIENT_EMAILS` | Yes | — | Comma-separated list of recipients |
| `STATION_ID` | Yes | `72289258` | From your FusionSolar monitoring URL |
| `BILLING_DAY` | No | `15` | Day of month your bill resets |
| `CRON_SCHEDULE` | No | `0 8 * * 5` | When to send the report (cron syntax) |
| `RUN_ON_START` | No | `false` | If `true`, sends a report when the container starts |

---

## NAS / Server Deployment (Synology / Linux)

Copy files to your NAS, build, and start:

```bash
scp -r . user@your-nas-ip:/volume2/docker/fusionsolar-extractor/
ssh user@your-nas-ip
cd /volume2/docker/fusionsolar-extractor
docker compose build
docker compose up -d
```

You do **not** need a host crontab — the container schedules itself via `CRON_SCHEDULE`.

To verify it's running cleanly:

```bash
docker ps | grep fusion         # should show "Up X minutes"
docker logs fusionsolar-extractor   # should show "Cron started, schedule: ..."
```

---

## Finding Your Station ID

Your `STATION_ID` is in the FusionSolar monitoring URL:

```
.../view/station/NE=72289258/overview
                    ^^^^^^^^^
                    This is your Station ID
```

---

## Files

| File | Purpose |
|---|---|
| `extract_and_email.py` | Main script — fetches cycle data and sends email |
| `extract_solar_browser.py` | Standalone CSV exporter for any date range |
| `entrypoint.sh` | Container entry point — installs cron job, runs cron in foreground |
| `run_report.sh` | Wrapper invoked by cron (sources env, runs Python script) |
| `Dockerfile` | Container definition |
| `docker-compose.yml` | Docker Compose config |
| `requirements.txt` | Python dependencies |
| `.env.example` | Configuration template |
| `crontab.example` | Schedule examples and manual-trigger reference |

---

## Email Preview

The report email includes:

- **Summary card** — net excess after 5% loss for the current billing cycle
- **Total exported / imported** — raw kWh totals
- **Daily breakdown table** — per-day export / import / net values, colour-coded
- **Days until next reset** — based on your `BILLING_DAY`

---

## Requirements

- Docker (or Python 3.11+ with `playwright install chromium`)
- A Gmail account with an App Password
- Huawei FusionSolar International account
