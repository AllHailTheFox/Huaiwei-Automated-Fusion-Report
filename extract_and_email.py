#!/usr/bin/env python3
"""
FusionSolar TNB Billing Alert System
Fetches the full billing-cycle grid data (15th → today) and emails a summary.

Alert schedule:
  - Day 10–14  → PRE_BILLING alert (5 days before bill resets)
  - Day 23+    → MID_CYCLE alert (monitor mid-cycle accumulation)

Manual override: set FORCE_ALERT=PRE_BILLING or FORCE_ALERT=MID_CYCLE
"""

import os
import logging
import asyncio
import smtplib
from datetime import datetime, timedelta
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Load .env if present
env_file = Path('.env')
if env_file.exists():
    with open(env_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                key, value = line.split('=', 1)
                os.environ.setdefault(key, value)

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("ERROR: Playwright not installed. Run: pip install playwright && playwright install chromium")
    exit(1)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Browser-based data extractor
# ---------------------------------------------------------------------------

class FusionSolarMonitor:
    def __init__(self, username: str, password: str, station_id: str):
        self.username = username
        self.password = password
        self.station_id = station_id
        self.base_url = "https://intl.fusionsolar.huawei.com"

    async def _login(self, page) -> bool:
        logger.info(f"Logging in as {self.username}...")
        await page.goto(f"{self.base_url}/login", wait_until="networkidle")
        await page.wait_for_load_state("domcontentloaded")
        await page.wait_for_timeout(3000)

        username_input = page.locator(
            "input[placeholder*='count'], input[placeholder*='mail'], input[type='text']"
        ).first
        await username_input.wait_for(timeout=5000)
        await username_input.fill(self.username)
        await page.locator("input[type='password']").first.fill(self.password)

        await page.locator(".loginBtn").first.wait_for(timeout=5000)
        await page.locator(".loginBtn").first.click()
        await page.wait_for_url(lambda url: "login" not in url, timeout=15000)
        await page.wait_for_load_state("networkidle", timeout=15000)
        logger.info("Login successful")
        return True

    async def _navigate_to_station(self, page):
        url = (
            f"{self.base_url}/uniportal/pvmswebsite/assets/build/cloud.html"
            f"?app-id=smartpvms&instance-id=smartpvms"
            f"&zone-id=c307b3ac-14c6-4c45-8549-1b342f85a3f1"
            f"#/view/station/NE={self.station_id}/overview"
        )
        await page.goto(url, wait_until="networkidle")
        await page.wait_for_load_state("domcontentloaded")
        await page.wait_for_timeout(3000)

        # Dismiss popups
        for selector in [".close-btn", ".icon-close", "[class*='close']"]:
            try:
                await page.locator(selector).first.click(timeout=2000)
                await page.wait_for_timeout(300)
            except Exception:
                pass

    async def _get_day_data(self, page, date_str: str) -> dict | None:
        logger.info(f"  Extracting {date_str}...")
        try:
            date_input = page.locator("input[placeholder='Select date']").first
            await date_input.wait_for(timeout=5000)
            await date_input.click()
            await page.wait_for_timeout(300)
            await date_input.fill(date_str)
            await date_input.press("Enter")
            await page.wait_for_timeout(3000)

            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(2000)

            lines = [l.strip() for l in (await page.inner_text("body")).split('\n') if l.strip()]

            fed = from_g = 0.0
            for i, line in enumerate(lines):
                if i == 0:
                    continue
                if 'Fed to grid' in line:
                    try:
                        fed = float(lines[i - 1].split()[0])
                    except (ValueError, IndexError):
                        pass
                if 'From grid' in line:
                    try:
                        from_g = float(lines[i - 1].split()[0])
                    except (ValueError, IndexError):
                        pass

            return {'date': date_str, 'export': fed, 'import': from_g}
        except Exception as e:
            logger.warning(f"  Could not get data for {date_str}: {e}")
            return None

    async def get_cycle_data(self, start_date: datetime, end_date: datetime) -> list[dict]:
        """
        Returns a list of daily dicts for the date range [start_date, end_date].
        Each dict: {'date': str, 'export': float, 'import': float}
        """
        logger.info(f"Fetching cycle data: {start_date.date()} → {end_date.date()}")
        results = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await (await browser.new_context()).new_page()

            await self._login(page)
            await self._navigate_to_station(page)

            current = start_date
            while current.date() <= end_date.date():
                row = await self._get_day_data(page, current.strftime("%Y-%m-%d"))
                if row:
                    results.append(row)
                current += timedelta(days=1)

            await browser.close()

        return results


# ---------------------------------------------------------------------------
# Email builder
# ---------------------------------------------------------------------------

def _billing_cycle_bounds(billing_day: int) -> tuple[datetime, datetime]:
    today = datetime.now()
    if today.day >= billing_day:
        start = datetime(today.year, today.month, billing_day)
    else:
        if today.month == 1:
            start = datetime(today.year - 1, 12, billing_day)
        else:
            start = datetime(today.year, today.month - 1, billing_day)
    return start, today


def build_email_html(daily_data: list[dict], alert_type: str, billing_day: int = 15) -> str:
    total_export = sum(d['export'] for d in daily_data)
    total_import = sum(d['import'] for d in daily_data)
    net_excess = (total_export - total_import) * 0.95

    cycle_start = daily_data[0]['date'] if daily_data else '—'
    cycle_end   = daily_data[-1]['date'] if daily_data else '—'
    days_count  = len(daily_data)
    now_str     = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Daily rows for table
    rows_html = ""
    for d in daily_data:
        day_net = (d['export'] - d['import']) * 0.95
        color = "#388e3c" if day_net > 0 else "#1565c0"  # Green if positive excess, blue if negative (importing)
        rows_html += f"""
        <tr>
            <td style="padding:6px 10px;border-bottom:1px solid #eee;">{d['date']}</td>
            <td style="padding:6px 10px;border-bottom:1px solid #eee;text-align:right;">{d['export']:.2f}</td>
            <td style="padding:6px 10px;border-bottom:1px solid #eee;text-align:right;">{d['import']:.2f}</td>
            <td style="padding:6px 10px;border-bottom:1px solid #eee;text-align:right;color:{color};font-weight:bold;">{day_net:+.2f}</td>
        </tr>"""

    days_until_billing = billing_day - datetime.now().day if datetime.now().day < billing_day else (billing_day + 30 - datetime.now().day)

    if alert_type == "PRE_BILLING":
        header_color = "#d32f2f"
        badge_bg = "#ffebee"
        badge_text = f"⚠️ PRE-BILLING ALERT — {days_until_billing} Days Before Bill"
        subtitle = f"Your billing cycle ends on the {billing_day}th. Turn on AC or high-consumption appliances to reduce excess storage penalty."
        excess_color = "#388e3c" if net_excess > 0 else "#1565c0"
        tips_heading = f"Reduce Excess Before the {billing_day}th"
        tips = [
            "Turn on air conditioning",
            "Run the washing machine / dryer",
            "Turn on electric water heater",
            "Charge electric vehicle (if available)",
            "Leave appliances on during peak solar hours",
        ]
        cycle_note = f"Billing cycle resets on the {billing_day}th — excess carried over is penalised by TNB."
    elif alert_type == "TEST":
        header_color = "#5c6bc0"
        badge_bg = "#e8eaf6"
        badge_text = "🧪 TEST — Billing Cycle Summary"
        subtitle = "Manual test run. This shows the current billing cycle data."
        excess_color = "#388e3c" if net_excess > 0 else "#1565c0"
        tips_heading = "This is a Test Alert"
        tips = [
            "This was triggered manually via FORCE_ALERT=TEST",
            "Data shown is real — pulled live from FusionSolar",
            f"Billing cycle resets on the {billing_day}th of each month",
        ]
        cycle_note = f"Test alert sent {datetime.now().strftime('%Y-%m-%d %H:%M')}."
    else:  # MID_CYCLE
        header_color = "#e65100"
        badge_bg = "#fff3e0"
        badge_text = "📊 MID-CYCLE CHECK"
        subtitle = "New billing cycle is underway. Monitor your accumulation to stay ahead of storage costs."
        excess_color = "#1565c0" if net_excess > 0 else "#388e3c"
        tips_heading = "Tips for the Rest of the Cycle"
        tips = [
            "Monitor daily export — if rising fast, increase consumption",
            "Spread AC usage across the day",
            "Avoid letting excess accumulate past RM 50 threshold",
            f"Next penalty alert: {billing_day - 5}th of next month",
        ]
        cycle_note = f"You still have time to manage excess before the {billing_day}th billing date."

    tips_html = "".join(f"<li style='margin-bottom:6px;'>{t}</li>" for t in tips)

    net_label = "USE MORE ENERGY NOW 🔌" if net_excess > 0 else "YOU ARE NET IMPORTER ✓"
    net_bg    = "#e8f5e9" if net_excess > 0 else "#e3f2fd"

    return f"""<html xmlns="http://www.w3.org/1999/xhtml">
<head><meta charset="utf-8" /></head>
<body style="font-family:Arial,sans-serif;margin:0;padding:0;background:#f5f5f5;">
<table width="100%" style="background:#f5f5f5;">
<tr><td align="center" style="padding:20px 0;">
<table width="640" style="background:white;border-collapse:collapse;">
<tr style="background:{header_color};color:white;">
<td style="padding:24px 30px;">
<h2 style="margin:0 0 8px 0;font-size:24px;color:white;">{badge_text}</h2>
<p style="margin:0 0 4px 0;font-size:15px;color:rgba(255,255,255,0.9);">{subtitle}</p>
<p style="margin:0;font-size:12px;color:rgba(255,255,255,0.7);">Cycle: {cycle_start} to {cycle_end} ({days_count} days)</p>
</td>
</tr>
<tr style="background:{net_bg};">
<td style="padding:30px;text-align:center;border-bottom:3px solid {excess_color};">
<p style="margin:0 0 8px 0;font-size:12px;text-transform:uppercase;color:#888;letter-spacing:1px;">Net Excess After 5% Loss</p>
<p style="margin:0 0 10px 0;font-size:56px;font-weight:900;color:{excess_color};line-height:1;">{net_excess:+.2f} kWh</p>
<p style="margin:0 0 6px 0;font-size:15px;font-weight:bold;color:{excess_color};">{net_label}</p>
<p style="margin:0;font-size:12px;color:#999;">({total_export:.2f} exported minus {total_import:.2f} imported) times 0.95</p>
</td>
</tr>
<tr>
<td style="padding:20px 30px;">
<p style="margin:0 0 10px 0;font-size:13px;color:#333;"><strong>Exported to Grid:</strong> {total_export:.2f} kWh</p>
<p style="margin:0;font-size:13px;color:#333;"><strong>Imported from Grid:</strong> {total_import:.2f} kWh</p>
</td>
</tr>
<tr>
<td style="padding:0 30px 20px 30px;">
<p style="margin:0 0 12px 0;font-size:13px;color:#333;font-weight:bold;">Daily Breakdown</p>
<table width="100%" style="border-collapse:collapse;font-size:12px;color:#333;">
<tr style="background:#f5f5f5;border-bottom:1px solid #ddd;">
<th style="padding:8px;text-align:left;color:#666;">Date</th>
<th style="padding:8px;text-align:right;color:#666;">Export kWh</th>
<th style="padding:8px;text-align:right;color:#666;">Import kWh</th>
<th style="padding:8px;text-align:right;color:#666;">Net kWh</th>
</tr>
{rows_html}
<tr style="background:#f9f9f9;font-weight:bold;border-top:2px solid #ddd;">
<td style="padding:10px;">TOTAL</td>
<td style="padding:10px;text-align:right;">{total_export:.2f}</td>
<td style="padding:10px;text-align:right;">{total_import:.2f}</td>
<td style="padding:10px;text-align:right;color:{excess_color};font-size:14px;">{net_excess:+.2f}</td>
</tr>
</table>
</td>
</tr>
<tr style="background:#f9f9f9;">
<td style="padding:20px 30px;">
<p style="margin:0 0 10px 0;font-size:13px;color:{header_color};font-weight:bold;">{tips_heading}</p>
<ul style="margin:0;padding-left:18px;font-size:12px;color:#555;">{tips_html}</ul>
<p style="margin:12px 0 0 0;font-size:12px;color:#777;">{cycle_note}</p>
</td>
</tr>
<tr style="border-top:1px solid #ddd;">
<td style="padding:15px 30px;text-align:center;font-size:11px;color:#999;">
Automated alert from FusionSolar Monitor | {now_str}
</td>
</tr>
</table>
</td></tr>
</table>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Email sender
# ---------------------------------------------------------------------------

class EmailAlert:
    def __init__(self, sender_email: str, app_password: str):
        self.sender_email = sender_email
        self.app_password = app_password

    def send(self, recipients: list[str], subject: str, body_html: str) -> bool:
        to_str = ", ".join(recipients)
        try:
            logger.info(f"Sending email to: {to_str}")
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.sender_email
            msg['To'] = to_str
            msg.attach(MIMEText(body_html, 'html'))

            with smtplib.SMTP("smtp.gmail.com", 587) as server:
                server.starttls()
                server.login(self.sender_email, self.app_password)
                server.sendmail(self.sender_email, recipients, msg.as_string())

            logger.info("Email sent successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def main():
    username      = os.getenv('FUSIONSOLAR_USERNAME')
    password      = os.getenv('FUSIONSOLAR_PASSWORD')
    email_pwd     = os.getenv('EMAIL_PASSWORD', '').replace(' ', '')  # strip spaces from app password
    station_id    = os.getenv('STATION_ID', '72289258')
    billing_day   = int(os.getenv('BILLING_DAY', '15'))
    recipients_raw = os.getenv('RECIPIENT_EMAILS', '')
    recipients    = [r.strip() for r in recipients_raw.split(',') if r.strip()]

    if not all([username, password, email_pwd]):
        logger.error("Missing env vars: FUSIONSOLAR_USERNAME / FUSIONSOLAR_PASSWORD / EMAIL_PASSWORD")
        return False

    if not recipients:
        logger.error("No recipients. Set RECIPIENT_EMAILS=a@b.com,c@d.com in .env")
        return False

    # PRE_BILLING window: 5 days before billing_day (e.g. day 10–14 for billing_day=15)
    pre_billing_start = billing_day - 5
    mid_cycle_start   = billing_day + 8  # ~8 days after reset

    # Determine alert type
    force = os.getenv('FORCE_ALERT', '').upper()
    today = datetime.now().day

    if force in ('PRE_BILLING', 'MID_CYCLE', 'TEST'):
        alert_type = force
        logger.info(f"Manual override: FORCE_ALERT={alert_type}")
    elif pre_billing_start <= today < billing_day:
        alert_type = "PRE_BILLING"
    elif today >= mid_cycle_start:
        alert_type = "MID_CYCLE"
    else:
        logger.info(f"No alert scheduled for day {today} (billing day={billing_day}). Set FORCE_ALERT to override.")
        return True

    subject_map = {
        "PRE_BILLING": f"⚠️ TNB Excess Energy — 5 Days Before Bill ({datetime.now().strftime('%B %d')})",
        "MID_CYCLE":   f"📊 TNB Mid-Cycle Energy Check ({datetime.now().strftime('%B %d')})",
        "TEST":        f"🧪 FusionSolar Test Alert ({datetime.now().strftime('%B %d')})",
    }

    # Date range: billing cycle start → today
    # For TEST mode, allow custom start date via TEST_START_DATE=YYYY-MM-DD
    if alert_type == "TEST" and os.getenv('TEST_START_DATE'):
        cycle_start = datetime.strptime(os.getenv('TEST_START_DATE'), "%Y-%m-%d")
        cycle_end = datetime.now()
    else:
        cycle_start, cycle_end = _billing_cycle_bounds(billing_day)
    logger.info(f"Billing period: {cycle_start.date()} → {cycle_end.date()} (billing day={billing_day})")

    monitor = FusionSolarMonitor(username, password, station_id)
    daily_data = await monitor.get_cycle_data(cycle_start, cycle_end)

    if not daily_data:
        logger.error("No data retrieved for billing cycle")
        return False

    body = build_email_html(daily_data, alert_type, billing_day)
    emailer = EmailAlert(username, email_pwd)
    return emailer.send(recipients, subject_map[alert_type], body)


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
