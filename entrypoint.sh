#!/bin/bash
set -e

if [ -z "$FUSIONSOLAR_USERNAME" ] || [ -z "$FUSIONSOLAR_PASSWORD" ] || [ -z "$EMAIL_PASSWORD" ]; then
    echo "ERROR: Missing required environment variables (FUSIONSOLAR_USERNAME, FUSIONSOLAR_PASSWORD, EMAIL_PASSWORD)"
    exit 1
fi

CRON_SCHEDULE="${CRON_SCHEDULE:-0 8 * * 5}"

# Cron strips the environment, so persist current env vars to /etc/environment
# (run_report.sh will source these before invoking python).
{
    echo "FUSIONSOLAR_USERNAME=${FUSIONSOLAR_USERNAME}"
    echo "FUSIONSOLAR_PASSWORD=${FUSIONSOLAR_PASSWORD}"
    echo "EMAIL_PASSWORD=${EMAIL_PASSWORD}"
    echo "RECIPIENT_EMAILS=${RECIPIENT_EMAILS}"
    echo "STATION_ID=${STATION_ID:-72289258}"
    echo "BILLING_DAY=${BILLING_DAY:-15}"
    echo "OUTPUT_DIR=${OUTPUT_DIR:-/data}"
    echo "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
} > /etc/environment

# Install the cron job. /etc/cron.d entries need a username field.
echo "${CRON_SCHEDULE} root /app/run_report.sh >> /proc/1/fd/1 2>> /proc/1/fd/2" > /etc/cron.d/fusionsolar
chmod 0644 /etc/cron.d/fusionsolar

echo "Cron started, schedule: ${CRON_SCHEDULE}"

if [ "${RUN_ON_START:-false}" = "true" ]; then
    echo "RUN_ON_START=true — running report once at startup..."
    /app/run_report.sh || echo "Initial run failed (cron schedule will continue)"
fi

# Run cron in foreground so the container stays alive and logs go to stdout.
exec cron -f
