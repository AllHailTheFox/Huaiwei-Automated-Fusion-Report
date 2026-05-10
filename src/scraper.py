import logging
from datetime import datetime, timedelta

from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)


class FusionSolarMonitor:
    def __init__(self, username: str, password: str, site_id: str, base_url: str):
        self.username = username
        self.password = password
        self.site_id = site_id
        self.base_url = base_url

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
            f"#/view/station/NE={self.site_id}/overview"
        )
        await page.goto(url, wait_until="networkidle")
        await page.wait_for_load_state("domcontentloaded")
        await page.wait_for_timeout(3000)

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
        logger.info(f"Fetching cycle data: {start_date.date()} -> {end_date.date()}")
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
