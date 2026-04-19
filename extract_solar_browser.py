#!/usr/bin/env python3
"""
FusionSolar Grid Data Extractor - Browser Automation
Extracts TNB billing cycle data using Playwright browser automation
"""

import os
import csv
import logging
import asyncio
from datetime import datetime, timedelta
from pathlib import Path

# Load .env file manually
env_file = Path('.env')
if env_file.exists():
    with open(env_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                key, value = line.split('=', 1)
                os.environ[key] = value

try:
    from playwright.async_api import async_playwright, expect
except ImportError:
    print("ERROR: Playwright not installed. Run: pip install playwright")
    print("Then: playwright install chromium")
    exit(1)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class FusionSolarScraper:
    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.base_url = "https://intl.fusionsolar.huawei.com"
        self.browser = None
        self.page = None

    async def login(self):
        """Login to FusionSolar portal"""
        try:
            logger.info(f"Attempting to login as {self.username}...")

            # Navigate to login page
            await self.page.goto(f"{self.base_url}/login", wait_until="networkidle")
            await self.page.wait_for_load_state("domcontentloaded")

            logger.info("Entering credentials...")
            await self.page.wait_for_timeout(3000)

            # Dismiss cookie consent if present
            try:
                cookie_btn = self.page.locator("text=Accept, text=OK, text=Accept All, .cookie-accept, #cookie-accept").first
                await cookie_btn.click(timeout=2000)
                logger.info("Dismissed cookie banner")
                await self.page.wait_for_timeout(500)
            except:
                pass

            # Fill username — use the account/email input specifically
            username_input = self.page.locator("input[placeholder*='count'], input[placeholder*='mail'], input[placeholder*='user'], input[placeholder*='User'], input[type='text']").first
            await username_input.wait_for(timeout=5000)
            await username_input.click()
            await username_input.fill(self.username)
            logger.info(f"Filled username: {self.username}")

            # Fill password
            password_input = self.page.locator("input[type='password']").first
            await password_input.click()
            await password_input.fill(self.password)
            logger.info("Filled password")

            # Screenshot before clicking login
            await self.page.screenshot(path="/data/debug_before_login.png")
            logger.info("Screenshot saved: debug_before_login.png")

            # Click login button — FusionSolar uses div.loginBtn
            login_button = self.page.locator(".loginBtn").first
            await login_button.wait_for(timeout=5000)
            await login_button.click()
            logger.info("Clicked login button")

            # Wait for navigation away from login page
            await self.page.wait_for_url(lambda url: "login" not in url, timeout=15000)
            await self.page.wait_for_load_state("networkidle", timeout=15000)

            await self.page.screenshot(path="/data/debug_after_login.png")
            logger.info("✓ Successfully logged in")
            return True

        except Exception as e:
            logger.error(f"✗ Login error: {e}")
            import traceback
            traceback.print_exc()
            return False

    async def dismiss_popups(self):
        """Dismiss cookie banner and login popup"""
        try:
            # Dismiss "Hello ErvynP" login info popup
            close_btn = self.page.locator(".close-btn, .icon-close, [class*='close']").first
            await close_btn.click(timeout=3000)
            await self.page.wait_for_timeout(500)
        except:
            pass
        try:
            # Dismiss cookie banner
            cookie_btn = self.page.locator("text=OK, text=Accept, text=Got it").first
            await cookie_btn.click(timeout=2000)
        except:
            pass

    async def navigate_to_monitoring(self, station_id):
        """Navigate to station monitoring page"""
        try:
            monitor_url = f"{self.base_url}/uniportal/pvmswebsite/assets/build/cloud.html?app-id=smartpvms&instance-id=smartpvms&zone-id=c307b3ac-14c6-4c45-8549-1b342f85a3f1#/view/station/NE={station_id}/overview"
            logger.info(f"Navigating to monitoring page...")
            await self.page.goto(monitor_url, wait_until="networkidle")
            await self.page.wait_for_load_state("domcontentloaded")
            await self.page.wait_for_timeout(3000)
            await self.dismiss_popups()
            logger.info("✓ Loaded monitoring page")
            return True
        except Exception as e:
            logger.error(f"✗ Navigation error: {e}")
            return False

    async def get_daily_data(self, date_str):
        """Get energy data for a specific date using date picker"""
        try:
            logger.info(f"Extracting data for {date_str}...")

            # Use date picker to select date
            date_input = self.page.locator("input[placeholder='Select date']").first
            await date_input.wait_for(timeout=5000)
            await date_input.click()
            await self.page.wait_for_timeout(500)
            await date_input.fill(date_str)
            await date_input.press("Enter")
            await self.page.wait_for_timeout(3000)

            # Scroll to Energy Management section to load grid data
            await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await self.page.wait_for_timeout(2000)

            # Screenshot
            await self.page.screenshot(path=f"/data/debug_monitor_{date_str}.png", full_page=True)

            # Get full page text
            page_text = await self.page.inner_text("body")
            lines = [l.strip() for l in page_text.split('\n') if l.strip()]
            logger.info(f"All page lines ({len(lines)} total): {lines}")

            # Parse values
            fed_to_grid = yield_today = from_grid = consumed_from_pv = None
            for i, line in enumerate(lines):
                if 'Yield today' in line and i > 0:
                    yield_today = lines[i - 1]
                if 'Fed to grid' in line and i > 0:
                    fed_to_grid = lines[i - 1]
                if 'From grid' in line and i > 0:
                    from_grid = lines[i - 1]
                if 'Consumed from PV' in line and i > 0:
                    consumed_from_pv = lines[i - 1]

            logger.info(f"  Yield today:      {yield_today}")
            logger.info(f"  Fed to grid:      {fed_to_grid}")
            logger.info(f"  From grid:        {from_grid}")
            logger.info(f"  Consumed from PV: {consumed_from_pv}")

            return {
                'date': date_str,
                'yield_today_kwh': yield_today,
                'fed_to_grid_kwh': fed_to_grid,
                'from_grid_kwh': from_grid,
                'consumed_from_pv_kwh': consumed_from_pv,
            }

        except Exception as e:
            logger.error(f"✗ Error extracting data for {date_str}: {e}")
            import traceback
            traceback.print_exc()
            return None

    async def extract_billing_cycle(self, start_date, end_date, station_id="72289258"):
        """Extract data for entire billing cycle"""
        try:
            async with async_playwright() as p:
                self.browser = await p.chromium.launch(headless=True)
                context = await self.browser.new_context()
                self.page = await context.new_page()

                # Login
                if not await self.login():
                    return None

                # Navigate to monitoring
                if not await self.navigate_to_monitoring(station_id):
                    return None

                # Extract data for each day
                all_data = []
                current_date = start_date

                while current_date <= end_date:
                    date_str = current_date.strftime("%Y-%m-%d")
                    data = await self.get_daily_data(date_str)

                    if data:
                        all_data.append(data)

                    current_date += timedelta(days=1)

                await context.close()

                return all_data if all_data else None

        except Exception as e:
            logger.error(f"✗ Extraction error: {e}")
            import traceback
            traceback.print_exc()
            return None

async def main():
    """Main extraction function"""
    username = os.getenv('FUSIONSOLAR_USERNAME')
    password = os.getenv('FUSIONSOLAR_PASSWORD')

    if not username or not password:
        logger.error("✗ Missing credentials in environment variables")
        return False

    output_dir = os.getenv('OUTPUT_DIR', './data')
    os.makedirs(output_dir, exist_ok=True)

    # Get current billing period
    today = datetime.now()
    if today.day >= 15:
        billing_start = datetime(today.year, today.month, 15)
        if today.month == 12:
            billing_end = datetime(today.year + 1, 1, 14)
        else:
            billing_end = datetime(today.year, today.month + 1, 14)
    else:
        if today.month == 1:
            billing_start = datetime(today.year - 1, 12, 15)
        else:
            billing_start = datetime(today.year, today.month - 1, 15)
        billing_end = datetime(today.year, today.month, 14)

    # Extract from billing cycle start (15th) to today
    end_date = datetime.now()
    start_date = billing_start

    logger.info(f"\n{'='*60}")
    logger.info(f"FusionSolar Browser Automation Extractor")
    logger.info(f"{'='*60}")
    logger.info(f"Billing Period: {billing_start.date()} to {billing_end.date()}")
    logger.info(f"Testing extraction: {start_date.date()} to {end_date.date()}")

    scraper = FusionSolarScraper(username, password)
    data = await scraper.extract_billing_cycle(start_date, end_date)

    if data:
        output_file = os.path.join(output_dir, f"tnb_billing_browser_{start_date.strftime('%Y%m%d')}.csv")

        with open(output_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['date', 'yield_today_kwh', 'fed_to_grid_kwh', 'from_grid_kwh', 'consumed_from_pv_kwh'])
            writer.writeheader()
            writer.writerows(data)

        logger.info(f"\n✓ Data saved to {output_file}")
        return True
    else:
        logger.error("✗ No data extracted")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
