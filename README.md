# FusionSolar TNB Billing Alert

Automated email alerts to help reduce TNB (Tenaga Nasional Berhad) excess energy storage penalties for Huawei FusionSolar solar installations in Malaysia.

## How it works

TNB bills on the **15th of every month**. If you export more energy than you import during a cycle, TNB charges a storage penalty on the excess. This tool:

1. Logs into FusionSolar International and scrapes **daily grid data** (Fed to Grid / From Grid) for every day from the **15th to today**
2. Calculates cumulative net excess with a 5% heat-loss deduction
3. Emails a summary with a **daily breakdown table** to all configured recipients

**Two alert types are sent automatically:**

| Day of Month | Alert | Purpose |
|---|---|---|
| 10–14 | PRE_BILLING | 5 days left — turn on AC / high-consumption appliances |
| 23+ | MID_CYCLE | Monitor mid-cycle accumulation |

You can also trigger either alert manually at any time.

---

## Quick Start

### 1. Clone and configure

```bash
git clone https://github.com/AllHailTheFox/Huaiwei-Automated-Fusion-Report.git
cd Huaiwei-Automated-Fusion-Report
cp .env.example .env
```

Edit `.env` and fill in your values:

```env
FUSIONSOLAR_USERNAME=your_fusionsolar_email@gmail.com
FUSIONSOLAR_PASSWORD=your_fusionsolar_password
EMAIL_PASSWORD=xxxx_xxxx_xxxx_xxxx       # Gmail app password (see below)
RECIPIENT_EMAILS=you@gmail.com,partner@gmail.com
STATION_ID=72289258                       # From your FusionSolar monitoring URL
```

### 2. Generate a Gmail App Password

Your normal Gmail password won't work. You need an **App Password**:

1. Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
2. Select app: **Mail**, device: **Other** → name it "FusionSolar"
3. Copy the 16-character password into `EMAIL_PASSWORD` in `.env`

> **Requires 2-Step Verification to be enabled on your Google account.**

### 3. Build and run with Docker

```bash
docker compose build
docker compose run --rm fusionsolar-extractor
```

---

## Manual Trigger

Force an alert regardless of what day it is:

```bash
# 5-days-before-bill alert
FORCE_ALERT=PRE_BILLING docker compose run --rm fusionsolar-extractor

# Mid-cycle check alert
FORCE_ALERT=MID_CYCLE docker compose run --rm fusionsolar-extractor
```

---

## NAS / Server Deployment (Synology / Linux)

### Copy files to your NAS

```bash
scp -r . user@your-nas-ip:/volume2/docker/fusionsolar-extractor/
```

### Build the image on the NAS

```bash
ssh user@your-nas-ip
cd /volume2/docker/fusionsolar-extractor
docker compose build
```

### Set up cron (runs daily at 8 AM, script auto-decides if alert is needed)

```bash
crontab -e
```

Add:

```
0 8 * * * cd /volume2/docker/fusionsolar-extractor && docker compose run --rm fusionsolar-extractor >> /var/log/fusionsolar.log 2>&1
```

See `crontab.example` for more scheduling options.

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
| `extract_and_email.py` | Main script — fetches full cycle data and sends email |
| `extract_solar_browser.py` | Standalone CSV exporter for any date range |
| `Dockerfile` | Container definition |
| `docker-compose.yml` | Docker Compose config |
| `entrypoint.sh` | Container entry point |
| `requirements.txt` | Python dependencies |
| `.env.example` | Configuration template |
| `crontab.example` | Cron schedule examples |

---

## Email Preview

The alert email includes:

- **Summary cards** — total exported, total imported, net excess for the billing cycle
- **Daily breakdown table** — per-day export / import / net values
- **Colour-coded net** — red if excess (penalty risk), green if net importer
- **Action tips** — what to do to reduce penalty

---

## Requirements

- Docker (or Python 3.11+ with `playwright install chromium`)
- A Gmail account with an App Password
- Huawei FusionSolar International account
