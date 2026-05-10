# ☀️ Solar Billing Report

Your electricity bill doesn't reset on the 1st of the month — it resets on a fixed day (like the 15th). That makes it a pain to figure out how much you've actually exported since your last billing date. You'd have to open the solar app every day, write down the numbers, and add them up yourself.

This tool does it for you. It logs into your solar monitoring system, counts every day from your billing reset date to today, calculates your net surplus after heat loss, and emails you a clean summary on whatever days you choose. No app-trawling, no mental math.

Currently works with **Huawei FusionSolar** (the most common solar inverter platform). If your portal URL is different, you can change it — see `FUSIONSOLAR_BASE_URL` below.

---

## 👋 Quick Check: "Hey, what's my excess right now?"

If you just want a quick answer without any setup fuss:

| Your setup | One command |
|---|---|
| **Already ran setup once before** | `bash Get_today_stats` |
| **Fresh install, never used this** | See below — pick a path |

That's it. One command, no Docker, no waiting for email. The table prints right in your terminal.

---

## 📖 What does it actually do?

Every month, your electricity retailer measures your **export** (power you sent back to the grid) and your **import** (power you took from the grid). Your bill resets on a fixed day — for example, the **15th** of every month.

This tool:

1. **Logs into your solar monitoring portal** (FusionSolar) using your normal login
2. **Reads your daily grid data** — how many kWh you exported ("Fed to Grid") and imported ("From Grid") for every day since the last billing reset
3. **Deducts a small percentage for heat loss** (default 5%) — because some power is lost as heat in the cables, and your retailer only pays you for what actually reaches the grid
4. **Emails you a clean summary** with a day-by-day breakdown

---

## 🚀 Two Ways to Use This

| Method | What you need | Good for |
|---|---|---|
| **💻 Direct** | Python 3.11+ installed | Quick checks (`bash Get_today_stats`), trying it out |
| **🐳 Docker** | Docker installed on your NAS or computer | Automated weekly emails, set-and-forget |

You can run **both** at the same time — Docker handles the weekly email, and you use `bash Get_today_stats` for quick checks whenever you want.

---

## 💻 Option 1: Direct (Quick Checks & Testing)

Best for: "Hey, what's the number right now?" without opening any app.

### Step 1: Install Python

> **Already have Python 3.11+? Skip to Step 2.**

- **Windows / Mac:** Download from [python.org](https://www.python.org/downloads/) and install. **Check "Add Python to PATH" during setup.**
- **Linux (Ubuntu/Debian):** `sudo apt install python3 python3-pip`
- **UGREEN / Synology NAS:** Python might already be installed. Check with `python3 --version`.

### Step 2: Get the code

```bash
git clone https://github.com/AllHailTheFox/Huaiwei-Automated-Fusion-Report.git
cd Huaiwei-Automated-Fusion-Report
```

> No `git`? Download the ZIP from GitHub and unzip it.

### Step 3: Install dependencies (one time only)

```bash
pip3 install -r requirements.txt
python3 -m playwright install chromium
```

> The second command installs a small browser that the tool uses to log into FusionSolar. This is the biggest download (~200MB) — only needed once.

### Step 4: Create your config file

Copy and fill in your details:

```bash
cp .env.example .env
```

Open `.env` in any text editor (nano, vim, Notepad). Here's what each setting means:

| Setting | What to put there |
|---|---|
| `FUSIONSOLAR_USERNAME` | Your FusionSolar login email |
| `FUSIONSOLAR_PASSWORD` | Your FusionSolar password |
| `FUSIONSOLAR_BASE_URL` | Portal address. Default works for most users. Change if you use a regional portal (e.g. `https://eu5.fusionsolar.huawei.com`) |
| `EMAIL_PASSWORD` | See **"Getting a Gmail App Password"** below |
| `RECIPIENT_EMAILS` | Who gets the email? Separate multiple with commas |
| `SITE_ID` | Your installation ID — see **"Finding Your Site ID"** below |
| `BILLING_DAY` | Day your electricity bill resets (default: 15) |
| `HEAT_LOSS_PERCENT` | Heat loss % your retailer deducts. If unsure, leave at 5 |
| `CRON_SCHEDULE` | When to auto-send (Docker only). Default: every Fri 8 AM |
| `RUN_ON_START` | Leave as `false` for now |

> **Tip:** The `.env` file is like a settings card. Keep it safe — it contains your passwords.

### Step 5: Getting a Gmail App Password

This is the trickiest part. Gmail won't let this tool use your regular password for security reasons. You need a special **App Password**:

1. Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
2. Sign into your Gmail account
3. Under "Select app", choose **Mail**
4. Under "Select device", choose **Other (Custom name)** — type "Solar Report"
5. Click **Generate**
6. Google shows a **16-character password** like: `abcd efgh ijkl mnop`

**Important:** Copy it exactly, but **remove the spaces**. So `abcd efgh ijkl mnop` becomes `abcdefghijklmnop`. Paste into `EMAIL_PASSWORD` in `.env`.

> **No App Passwords option?** Enable **2-Step Verification** first at [myaccount.google.com/security](https://myaccount.google.com/security), then come back.

### Step 6: Find your Site ID

1. Log into [FusionSolar](https://intl.fusionsolar.huawei.com)
2. Click your installation to open the dashboard
3. Look at the web address — you'll see: `.../view/station/NE=72289258/overview`

The number after `NE=` is your Site ID. Put it in `SITE_ID` in `.env`.

### Step 7: Run it

```bash
# Quick preview (no email)
bash Get_today_stats

# Or the long way:
bash run.sh --preview

# Send an email report:
bash run.sh
```

No `chmod +x` needed — `bash` prefix works as-is.

---

## 🐳 Option 2: Docker (Automated Weekly Emails)

Best for: "Email me every Friday without me touching anything."

Docker is like a pre-packed lunchbox — everything the tool needs is inside. You don't install Python or libraries on your NAS.

### Step 1: Install Docker

- **Windows / Mac:** Download [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- **UGREEN NAS:** Open **App Manager** → search "Docker" → Install
- **Synology NAS:** Open **Package Center** → search "Docker" → Install
- **Other NAS (QNAP, Asustor):** Check your app store for "Docker" or "Container Manager"
- **Linux:** `sudo apt install docker.io docker-compose`

### Step 2: Get the code & configure

```bash
git clone https://github.com/AllHailTheFox/Huaiwei-Automated-Fusion-Report.git
cd Huaiwei-Automated-Fusion-Report
cp .env.example .env
```

Then fill in `.env` exactly as described in **Steps 4-6** above (App Password, Site ID, etc.).

### Step 3: Build and start

```bash
docker compose build
docker compose up -d
```

The first build takes a minute or two. After that, the container runs in the background and emails you automatically based on your `CRON_SCHEDULE` (default: every Friday 8 AM).

### Step 4: Trigger an email right now

Change `RUN_ON_START` to `true` in `.env`, then restart:

```bash
docker compose up -d --force-recreate
```

The container sends a report immediately on startup, then continues on its regular schedule.

**Don't forget to flip `RUN_ON_START` back to `false` afterwards,** or it'll email you every time the NAS reboots (power outage, update, etc.).

---

## 🔧 Everyday Usage

| What you want | Command |
|---|---|
| **Quick check — what's my excess?** | `bash Get_today_stats` |
| **Send email now (direct mode)** | `bash run.sh` |
| **Send email now (Docker mode)** | Set `RUN_ON_START=true` → `docker compose up -d --force-recreate` |
| **Check if Docker container is running** | `docker ps \| grep fusion` |
| **See what the container is doing** | `docker logs fusionsolar-extractor` |
| **See last 20 lines of logs** | `docker logs fusionsolar-extractor --tail 20` |
| **Clean up old stopped containers** | `docker container prune -f` |
| **Stop the Docker container** | `docker compose down` |
| **Restart after config change** | `docker compose up -d --force-recreate` |

---

## 🤖 Setting Up Automatic Weekly Emails

### Docker mode (already automatic)

The container runs its own internal cron using your `CRON_SCHEDULE` setting. That's it — nothing else to do.

To change the schedule, edit `CRON_SCHEDULE` in `.env`, then restart:
```bash
docker compose up -d --force-recreate
```

Examples:

| Schedule | `CRON_SCHEDULE` value |
|---|---|
| Every Friday 8 AM | `0 8 * * 5` |
| Every Monday 8 AM | `0 8 * * 1` |
| Friday + Saturday + Sunday 8 AM | `0 8 * * 5,6,0` |
| 1st of every month 8 AM | `0 8 1 * *` |

### Direct mode (Linux cron)

```bash
crontab -e
```

Add this line (replace the path):
```
0 8 * * 5 cd /path/to/Huaiwei-Automated-Fusion-Report && bash run.sh >> report.log 2>&1
```

---

## ❓ Common Questions

**Q: The `bash Get_today_stats` says "python: command not found"**
A: Your system might use `python3`. Install Python if missing, then run the one-time setup: `pip3 install -r requirements.txt && python3 -m playwright install chromium`

**Q: The email never arrived!**
A: Check spam. If not there, run `docker logs fusionsolar-extractor` (Docker) or `bash run.sh` (direct) and watch for errors. Most common: App Password has spaces in it.

**Q: The preview shows "No data"**
A: Check your `FUSIONSOLAR_BASE_URL`. If you use a regional portal (like `eu5.fusionsolar.huawei.com`), the default URL won't work.

**Q: What's the heat loss thing?**
A: When electricity travels through cables, some turns into heat and is lost. Your retailer only pays for what reaches the grid. 5% is a common default.

**Q: Can I send the report to multiple people?**
A: Yes — separate emails with commas: `you@gmail.com,partner@gmail.com`

**Q: Why does `docker compose run --rm` show "Cron started"?**
A: Because `docker compose run` runs the container's entrypoint, which starts cron. That command is meant for testing inside the running container. For one-off emails, use `RUN_ON_START=true` instead.

---

## 📁 What's in this folder (if you're curious)

| File | What it does |
|---|---|
| `main.py` | The main program — fetches solar data and sends the email |
| `run.sh` | Helper that loads `.env` and runs `main.py` |
| `Get_today_stats` | Shortcut for `bash run.sh --preview` |
| `.env` | Your settings (passwords, etc.) — keep safe! |
| `.env.example` | Blank template to copy |
| `src/` | The brains of the operation (config, scraper, email builder, email sender) |
| `scripts/extract_solar_browser.py` | Standalone tool to export data as CSV |
| `Dockerfile` + `docker-compose.yml` | Docker build and run settings |
| `entrypoint.sh` + `run_report.sh` | Docker internal scripts |
| `requirements.txt` | Python library list |
| `crontab.example` | Schedule examples |

---

## 📄 What the email looks like

- **Net surplus** for the current billing period (after heat loss)
- **Total exported / imported** in kWh
- **Day-by-day table** — export, import, net (green = surplus, red = deficit)
- **Days until next billing reset**

Console preview (`--preview`) shows the same table in your terminal.

---

## 🛠 Requirements

- **Direct mode:** Python 3.11+ + `playwright install chromium`
- **Docker mode:** Docker Engine with Compose (or Docker Desktop)
- **Email:** Gmail account with 2-Step Verification + App Password
- **Solar account:** Huawei FusionSolar (or compatible) portal login
