import os
import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class Config:
    fusionsolar_username: str
    fusionsolar_password: str
    fusionsolar_base_url: str
    email_password: str
    recipient_emails: list[str]
    site_id: str
    billing_day: int
    heat_loss_percent: float
    cron_schedule: str
    run_on_start: bool
    output_dir: str


def load_config() -> Config:
    env_file = Path('.env')
    if env_file.exists():
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    os.environ.setdefault(key, value)

    username = os.getenv('FUSIONSOLAR_USERNAME', '')
    password = os.getenv('FUSIONSOLAR_PASSWORD', '')
    email_pwd = os.getenv('EMAIL_PASSWORD', '').replace(' ', '')

    if not all([username, password, email_pwd]):
        logger.error("Missing required env vars: FUSIONSOLAR_USERNAME / FUSIONSOLAR_PASSWORD / EMAIL_PASSWORD")
        raise SystemExit(1)

    recipients_raw = os.getenv('RECIPIENT_EMAILS', '')
    recipients = [r.strip() for r in recipients_raw.split(',') if r.strip()]
    if not recipients:
        logger.error("No recipients. Set RECIPIENT_EMAILS=a@b.com,c@d.com in .env")
        raise SystemExit(1)

    return Config(
        fusionsolar_username=username,
        fusionsolar_password=password,
        fusionsolar_base_url=os.getenv('FUSIONSOLAR_BASE_URL', 'https://intl.fusionsolar.huawei.com'),
        email_password=email_pwd,
        recipient_emails=recipients,
        site_id=os.getenv('SITE_ID', '72289258'),
        billing_day=int(os.getenv('BILLING_DAY', '15')),
        heat_loss_percent=float(os.getenv('HEAT_LOSS_PERCENT', '5')),
        cron_schedule=os.getenv('CRON_SCHEDULE', '0 8 * * 5'),
        run_on_start=os.getenv('RUN_ON_START', 'false').lower() == 'true',
        output_dir=os.getenv('OUTPUT_DIR', '/data'),
    )
