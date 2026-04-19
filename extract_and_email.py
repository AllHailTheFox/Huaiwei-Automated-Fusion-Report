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
        color = "#d32f2f" if day_net > 0 else "#388e3c"
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

    return f"""<!DOCTYPE html>
<html>
<body style="margin:0;padding:0;background:#f0f2f5;font-family:Arial,sans-serif;">
<div style="max-width:640px;margin:30px auto;background:white;border-radius:12px;overflow:hidden;box-shadow:0 4px 12px rgba(0,0,0,0.1);">

  <!-- Header -->
  <div style="background:{header_color};padding:24px 30px;">
    <h1 style="color:white;margin:0;font-size:22px;">{badge_text}</h1>
    <p style="color:rgba(255,255,255,0.85);margin:8px 0 0;font-size:14px;">{subtitle}</p>
    <p style="color:rgba(255,255,255,0.7);margin:4px 0 0;font-size:12px;">Cycle: {cycle_start} → {cycle_end} &nbsp;({days_count} days)</p>
  </div>

  <!-- NET EXCESS HERO -->
  <div style="background:{net_bg};padding:28px 30px;text-align:center;border-bottom:3px solid {excess_color};">
    <div style="font-size:12px;text-transform:uppercase;letter-spacing:1px;color:#888;margin-bottom:8px;">Net Excess This Cycle (after 5% loss)</div>
    <div style="font-size:56px;font-weight:900;color:{excess_color};line-height:1;">{net_excess:+.2f} kWh</div>
    <div style="font-size:14px;font-weight:bold;color:{excess_color};margin-top:8px;">{net_label}</div>
    <div style="font-size:11px;color:#999;margin-top:6px;">= ({total_export:.2f} exported − {total_import:.2f} imported) × 0.95</div>
  </div>

  <!-- Sub-stats -->
  <div style="padding:20px 30px 0;">
    <div style="display:flex;gap:12px;flex-wrap:wrap;">
      <div style="flex:1;min-width:140px;background:{badge_bg};border-radius:8px;padding:16px;text-align:center;">
        <div style="font-size:11px;text-transform:uppercase;color:#888;margin-bottom:4px;">Total Exported to Grid</div>
        <div style="font-size:28px;font-weight:bold;color:#333;">{total_export:.2f}</div>
        <div style="font-size:12px;color:#888;">kWh</div>
      </div>
      <div style="flex:1;min-width:140px;background:#e8f5e9;border-radius:8px;padding:16px;text-align:center;">
        <div style="font-size:11px;text-transform:uppercase;color:#888;margin-bottom:4px;">Total Imported from Grid</div>
        <div style="font-size:28px;font-weight:bold;color:#333;">{total_import:.2f}</div>
        <div style="font-size:12px;color:#888;">kWh</div>
      </div>
    </div>
  </div>

  <!-- Daily breakdown table -->
  <div style="padding:20px 30px 0;">
    <h3 style="margin:0 0 12px;color:#333;font-size:15px;">Daily Breakdown</h3>
    <table style="width:100%;border-collapse:collapse;font-size:13px;">
      <thead>
        <tr style="background:#f5f5f5;">
          <th style="padding:8px 10px;text-align:left;color:#555;font-weight:600;">Date</th>
          <th style="padding:8px 10px;text-align:right;color:#555;font-weight:600;">Exported (kWh)</th>
          <th style="padding:8px 10px;text-align:right;color:#555;font-weight:600;">Imported (kWh)</th>
          <th style="padding:8px 10px;text-align:right;color:#555;font-weight:600;">Net after 5% (kWh)</th>
        </tr>
      </thead>
      <tbody>{rows_html}</tbody>
      <tfoot>
        <tr style="background:#fafafa;font-weight:bold;font-size:14px;">
          <td style="padding:10px;border-top:2px solid #ddd;">CYCLE TOTAL</td>
          <td style="padding:10px;border-top:2px solid #ddd;text-align:right;">{total_export:.2f}</td>
          <td style="padding:10px;border-top:2px solid #ddd;text-align:right;">{total_import:.2f}</td>
          <td style="padding:10px;border-top:2px solid #ddd;text-align:right;color:{excess_color};font-size:16px;">{net_excess:+.2f}</td>
        </tr>
      </tfoot>
    </table>
  </div>

  <!-- Tips -->
  <div style="padding:20px 30px 0;">
    <div style="background:#f9f9f9;border-left:4px solid {header_color};padding:16px;border-radius:4px;">
      <h3 style="margin:0 0 10px;color:{header_color};font-size:14px;">{tips_heading}</h3>
      <ul style="margin:0;padding-left:18px;color:#555;font-size:13px;">{tips_html}</ul>
    </div>
    <p style="color:#777;font-size:13px;margin-top:12px;">{cycle_note}</p>
  </div>

  <!-- Footer -->
  <div style="padding:20px 30px 24px;">
    <hr style="border:none;border-top:1px solid #eee;margin-bottom:16px;">
    <p style="color:#bbb;font-size:11px;text-align:center;margin:0;">
      Automated alert from FusionSolar Monitor &nbsp;|&nbsp; {now_str}
    </p>
  </div>

</div>
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
