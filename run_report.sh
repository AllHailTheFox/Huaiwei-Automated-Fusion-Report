#!/bin/bash
# Wrapper invoked by cron (cron strips env, so source /etc/environment first).
set -e

if [ -f /etc/environment ]; then
    set -a
    . /etc/environment
    set +a
fi

cd /app
echo "[$(date)] Running scheduled FusionSolar report..."
python /app/main.py
echo "[$(date)] Report run finished."
