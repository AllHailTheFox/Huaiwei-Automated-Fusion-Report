# ☀️ Solar Billing Report

Your electricity bill doesn't reset on the 1st of the month — it resets on a fixed day (like the 15th). That makes it a pain to figure out how much you've actually exported since your last billing date. You'd have to open the solar app every day, write down the numbers, and add them up yourself.

This tool does it for you. It logs into your solar monitoring system, counts every day from your billing reset date to today, calculates your net surplus after heat loss, and emails you a clean summary on whatever days you choose. No app-trawling, no mental math.

Currently works with **Huawei FusionSolar** (the most common solar inverter platform). If your portal URL is different, you can change it — see `FUSIONSOLAR_BASE_URL` below.

---

## 📖 What does it actually do?

Every month, your electricity retailer measures your **export** (power you sent back to the grid) and your **import** (power you took from the grid). Your bill resets on a fixed day — for example, the **15th** of every month.

This tool:

1. **Logs into your solar monitoring portal** (FusionSolar) using your normal login
2. **Reads your daily grid data** — how many kWh you exported ("Fed to Grid") and imported ("From Grid") for every day since the last billing reset
3. **Deducts a small percentage for heat loss** (default 5%) — because some power is lost as heat in the cables, and your retailer only pays you for what actually reaches the grid
4. **Emails you a clean summary** with a day-by-day breakdown

You can also preview the report in your terminal without sending an email — handy for a quick check.

---

## 🚀 Two Ways to Run This

There are two ways to use this tool. Pick whichever feels easier:

| Method | What you need | Good for |
|---|---|---|
| **🐳 Docker** (recommended) | Docker installed on your computer or NAS | Set it once, forget it — runs automatically on a schedule |
| **💻 Direct (no Docker)** | Python 3.11+ installed | If you don't want to install Docker, or just want to try it out |

Don't worry if you don't know what Docker or Python is — the instructions below walk you through everything.

---

## 🐳 Option 1: Docker (Easiest — Recommended)

Docker is like a little pre-packed lunchbox that contains everything the tool needs to run. You don't need to install Python or any libraries — Docker handles all of that.

### Step 1: Install Docker

- **Windows / Mac:** Download Docker Desktop from [docker.com](https://www.docker.com/products/docker-desktop/) and install it (just click Next through the installer)
- **Synology NAS:** Open **Package Center** → search for "Docker" → Install
- **UGREEN NAS:** Open the **App Manager** → search for "Docker" → Install
- **Other NAS (QNAP, Asustor, etc.):** Check your NAS app store for "Docker" or "Container Manager" — most modern NAS have it built-in
- **Linux (Ubuntu/Debian):** Open a terminal and paste:
  ```bash
  sudo apt install docker.io docker-compose
  ```

### Step 2: Get the code

Open a terminal (Command Prompt on Windows, Terminal on Mac/Linux) and run:

```bash
git clone https://github.com/AllHailTheFox/Huaiwei-Automated-Fusion-Report.git
cd Huaiwei-Automated-Fusion-Report
```

> If `git` gives you an error, you can also download the code as a ZIP file from the GitHub page and extract it.

### Step 3: Create your configuration file

Copy the example configuration to create your own:

```bash
cp .env.example .env
```

Now open the `.env` file in any text editor (Notepad, TextEdit, VS Code). You'll see something like this:

```env
FUSIONSOLAR_USERNAME=your_fusionsolar_email@gmail.com
FUSIONSOLAR_PASSWORD=your_fusionsolar_password
FUSIONSOLAR_BASE_URL=https://intl.fusionsolar.huawei.com
EMAIL_PASSWORD=xxxxxxxxxxxxxxxxxxxx
RECIPIENT_EMAILS=you@gmail.com,partner@yahoo.com
SITE_ID=72289258
BILLING_DAY=15
HEAT_LOSS_PERCENT=5
CRON_SCHEDULE=0 8 * * 5
RUN_ON_START=false
```

Here's what each setting means:

| Setting | What to put there |
|---|---|
| `FUSIONSOLAR_USERNAME` | The email address you use to log into FusionSolar |
| `FUSIONSOLAR_PASSWORD` | The password you use to log into FusionSolar |
| `FUSIONSOLAR_BASE_URL` | Your FusionSolar portal address. The default works for most users (international portal). If you use a regional portal (e.g. `https://eu5.fusionsolar.huawei.com`), change it here. |
| `EMAIL_PASSWORD` | **Not your normal Gmail password!** See Step 4 below to generate a special App Password |
| `RECIPIENT_EMAILS` | Who should receive the report? Separate multiple emails with commas |
| `SITE_ID` | Your solar installation ID — see "Finding Your Site ID" below |
| `BILLING_DAY` | The day of the month your electricity bill resets (most people: 15) |
| `HEAT_LOSS_PERCENT` | How much your electricity retailer deducts for cable heat loss. If unsure, leave at 5 |
| `CRON_SCHEDULE` | When to send the report automatically. Leave as-is for every Friday 8 AM (see "Changing the Schedule" below) |
| `RUN_ON_START` | Keep this as `false` for now |

> **Tip:** The `.env` file is like a settings card. Keep it safe — it contains your passwords.

### Step 4: Create a Gmail App Password

This is the trickiest part. Gmail won't let this tool use your regular password for security reasons. You need to create a special **App Password** just for this tool.

1. Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
2. If asked, log into your Gmail account
3. Under "Select app", choose **Mail**
4. Under "Select device", choose **Other (Custom name)** — type "Solar Report"
5. Click **Generate**
6. Google will show you a **16-character password** that looks like: `abcd efgh ijkl mnop`

**Important:** Copy the password exactly as shown, but **remove the spaces**. In the example above, you'd put `abcdefghijklmnop` (all one word, no spaces). Paste it into the `EMAIL_PASSWORD` field in your `.env` file.

> **Don't have App Passwords as an option?** You need to enable **2-Step Verification** on your Google account first. Go to [myaccount.google.com/security](https://myaccount.google.com/security) and turn on "2-Step Verification". Then come back to this step.

### Step 5: Find your Site ID

Your `SITE_ID` is a number that identifies your solar installation. Here's how to find it:

1. Log into [FusionSolar](https://intl.fusionsolar.huawei.com) in your web browser
2. Click on your installation to open the monitoring dashboard
3. Look at the web address (URL) in your browser's address bar
4. You'll see something like: `.../view/station/NE=72289258/overview`

The number after `NE=` is your Site ID. In this example: `72289258`

Put that number into the `SITE_ID` field in your `.env` file.

### Step 6: Build and start

In your terminal, run:

```bash
docker compose build
docker compose up -d
```

The first build takes a minute or two as it downloads the necessary components. After that, the tool is running in the background and will email you every Friday at 8 AM.

**To test it right now**, run:

```bash
bash run.sh
```
> Or if you're on Windows: `docker compose run --rm fusionsolar-extractor python /app/main.py`

You should receive an email within a minute or two.

---

## 💻 Option 2: Direct (No Docker)

If you already have Python installed or don't want to use Docker, you can run the tool directly.

### Step 1: Install Python

> **Already have Python? Skip to Step 2.**

- **Windows / Mac:** Download Python from [python.org](https://www.python.org/downloads/) and install it. **Important:** during installation, check the box that says **"Add Python to PATH"**
- **Linux:** Python is usually already installed. To check, open a terminal and type: `python3 --version`

### Step 2: Get the code and set up

Open a terminal and run:

```bash
git clone https://github.com/AllHailTheFox/Huaiwei-Automated-Fusion-Report.git
cd Huaiwei-Automated-Fusion-Report
```

> Don't have `git`? Download the code as a ZIP from the GitHub page and unzip it.

Install the required libraries:

```bash
pip install -r requirements.txt
playwright install chromium
```

The second command installs a web browser (Chromium) that the tool uses to log into FusionSolar and read your data.

### Step 3: Create your `.env` file

Same as **Step 3** in the Docker section above — copy `.env.example` to `.env`, then fill in your details.

### Step 4: Get a Gmail App Password

Same as **Step 4** in the Docker section above.

### Step 5: Find your Site ID

Same as **Step 5** in the Docker section above.

### Step 6: Run it

**Preview the report (no email sent):**
```bash
bash run.sh --preview
```
You'll see a table in your terminal showing your daily export/import data. Great for a quick sanity check.

**Send the email report:**
```bash
bash run.sh
```

There's also a shortcut for the preview:
```bash
bash Get_today_stats
```

> **Tip:** The `bash` prefix works on all systems (Windows, Mac, Linux) and doesn't require any special permissions. If you're on Linux, `./run.sh --preview` also works.

---

## 🤖 Setting It Up to Run Automatically (Cron)

Once you've tested it and it works, you can set it to run automatically every week.

### If you're using Docker

The Docker container runs its own internal schedule — you don't need to do anything extra. It uses the `CRON_SCHEDULE` setting from your `.env` file (default: every Friday at 8 AM).

To change when it runs, edit `CRON_SCHEDULE` in `.env`, then restart the container:

```bash
docker compose up -d --force-recreate
```

### If you're running directly (no Docker)

You'll use your computer's built-in scheduler called **cron**. Open a terminal and type:

```bash
crontab -e
```

If this is your first time, it might ask you to pick an editor — choose **nano** (the easiest one).

Add this line (replace `/path/to/folder` with the actual path to your project folder):

```
0 8 * * 5 cd /path/to/Huaiwei-Automated-Fusion-Report && bash run.sh >> report.log 2>&1
```

This tells your computer: "Every Friday at 8 AM, go to the project folder and run the report. Save any messages to a file called report.log."

Save and exit (in nano: `Ctrl+X`, then `Y`, then `Enter`).

---

## 🧪 Quick Reference: All Commands in One Place

| What you want to do | Command |
|---|---|
| Preview report | `bash run.sh --preview` or `bash Get_today_stats` |
| Send report now | `bash run.sh` |
| Set up automatic weekly report | See "Setting It Up to Run Automatically" above |

---

## ❓ Common Questions

**Q: The email never arrived!**
A: Check your spam folder. If it's not there, run `bash run.sh` and watch for error messages. The most common issue is the App Password — make sure there are no spaces in it.

**Q: The preview shows "No data"**
A: Make sure your `FUSIONSOLAR_BASE_URL` is correct. If you use a regional portal (like `eu5.fusionsolar.huawei.com`), the default URL won't work.

**Q: What's the heat loss thing?**
A: When electricity travels through cables, some of it turns into heat and is lost. Your electricity retailer only pays you for the power that actually reaches the grid, not what leaves your inverter. This percentage varies by country — 5% is a common default. Your retailer can tell you the exact number.

**Q: Can I send the report to multiple people?**
A: Yes! In `RECIPIENT_EMAILS`, separate emails with commas: `you@gmail.com,your.partner@gmail.com`

---

## 📁 What's in this folder (if you're curious)

| File | What it does |
|---|---|
| `main.py` | The main program — fetches your solar data and sends the email |
| `run.sh` | A helper that loads your settings from `.env` and runs `main.py` |
| `Get_today_stats` | Shortcut to preview the report |
| `.env` | Your settings (username, password, etc.) — keep this safe! |
| `.env.example` | A blank template to copy when setting up |
| `scripts/extract_solar_browser.py` | A separate tool to export data as a CSV file (for spreadsheet nerds) |
| `Dockerfile` + `docker-compose.yml` | Settings for the Docker version |
| `entrypoint.sh` + `run_report.sh` | Internal helpers for the Docker version |
| `requirements.txt` | A shopping list of Python libraries this tool needs |
| `crontab.example` | Examples of different schedule times |

---

## 📄 What the email looks like

The email contains:

- **A summary at the top** — your net surplus (or deficit) for the current billing period
- **Total exported and imported** — the raw numbers in kWh
- **A day-by-day table** — how much you exported, imported, and your net for each day
- **Colour coding** — green for surplus days, red for deficit days
- **Days until next billing reset** — so you know how much of the billing period is left

The console preview (`--preview`) shows the same information as a table in your terminal.

---

## 🛠 Requirements (the technical stuff)

- **Docker mode:** Docker Engine with Compose (or Docker Desktop)
- **Direct mode:** Python 3.11 or newer + `playwright install chromium`
- **Email:** A Gmail account with 2-Step Verification and an App Password
- **Solar account:** A Huawei FusionSolar (or compatible) portal login
