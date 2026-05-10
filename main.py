#!/usr/bin/env python3
import argparse
import asyncio
import logging
from datetime import datetime

from src.config import load_config
from src.scraper import FusionSolarMonitor
from src.email_builder import _billing_cycle_bounds, build_email_html, print_console_report
from src.email_sender import EmailAlert

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="FusionSolar Weekly Solar Report")
    parser.add_argument(
        '--preview',
        action='store_true',
        help='Print report to console instead of sending email'
    )
    return parser.parse_args()


async def main():
    args = parse_args()
    config = load_config()

    cycle_start, cycle_end = _billing_cycle_bounds(config.billing_day)
    logger.info(f"Billing period: {cycle_start.date()} -> {cycle_end.date()} (billing day={config.billing_day})")

    monitor = FusionSolarMonitor(
        config.fusionsolar_username,
        config.fusionsolar_password,
        config.site_id,
        config.fusionsolar_base_url,
    )
    daily_data = await monitor.get_cycle_data(cycle_start, cycle_end)

    if not daily_data:
        logger.error("No data retrieved for billing cycle")
        return False

    if args.preview:
        print_console_report(daily_data, config.billing_day, config.heat_loss_percent)
        return True

    loss_mult = 1 - config.heat_loss_percent / 100
    total_export = sum(d['export'] for d in daily_data)
    total_import = sum(d['import'] for d in daily_data)
    net_excess = (total_export - total_import) * loss_mult
    subject = f"Weekly Solar Report - {datetime.now().strftime('%B %d, %Y')}"

    body = build_email_html(daily_data, config.billing_day, config.heat_loss_percent)
    plain_text = (
        f"{subject}\n\n"
        f"Billing cycle: {cycle_start.date()} to {cycle_end.date()}\n\n"
        f"NET EXCESS (after {config.heat_loss_percent:.0f}% loss): {net_excess:+.2f} kWh\n"
        f"Total Exported: {total_export:.2f} kWh\n"
        f"Total Imported: {total_import:.2f} kWh\n\n"
        f"Sent: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )

    emailer = EmailAlert(config.fusionsolar_username, config.email_password)
    return emailer.send(config.recipient_emails, subject, body, plain_text)


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
