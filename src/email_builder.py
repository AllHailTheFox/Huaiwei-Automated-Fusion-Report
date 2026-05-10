import logging
from datetime import datetime

logger = logging.getLogger(__name__)


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


def _days_until_next_reset(billing_day: int) -> int:
    today = datetime.now()
    if today.day < billing_day:
        next_reset = datetime(today.year, today.month, billing_day)
    elif today.month == 12:
        next_reset = datetime(today.year + 1, 1, billing_day)
    else:
        next_reset = datetime(today.year, today.month + 1, billing_day)
    return (next_reset.date() - today.date()).days


def build_email_html(daily_data: list[dict], billing_day: int = 15, heat_loss_percent: float = 5.0) -> str:
    loss_mult = 1 - heat_loss_percent / 100
    total_export = sum(d['export'] for d in daily_data)
    total_import = sum(d['import'] for d in daily_data)
    net_excess = (total_export - total_import) * loss_mult

    cycle_start = daily_data[0]['date'] if daily_data else '-'
    cycle_end = daily_data[-1]['date'] if daily_data else '-'
    days_count = len(daily_data)
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    days_left = _days_until_next_reset(billing_day)

    rows_html = ""
    for d in daily_data:
        day_net = (d['export'] - d['import']) * loss_mult
        color = "#388e3c" if day_net > 0 else "#d32f2f"
        rows_html += f"""
        <tr>
            <td style="padding:6px 10px;border-bottom:1px solid #eee;">{d['date']}</td>
            <td style="padding:6px 10px;border-bottom:1px solid #eee;text-align:right;">{d['export']:.2f}</td>
            <td style="padding:6px 10px;border-bottom:1px solid #eee;text-align:right;">{d['import']:.2f}</td>
            <td style="padding:6px 10px;border-bottom:1px solid #eee;text-align:right;color:{color};font-weight:bold;">{day_net:+.2f}</td>
        </tr>"""

    header_color = "#1565c0"
    excess_color = "#388e3c" if net_excess > 0 else "#d32f2f"
    net_label = "NET EXPORTER (excess to grid)" if net_excess > 0 else "NET IMPORTER (drawing from grid)"
    net_bg = "#e8f5e9" if net_excess > 0 else "#e3f2fd"
    cycle_note = f"Billing cycle resets on the {billing_day}th. {days_left} day(s) until next reset."

    return f"""<html xmlns="http://www.w3.org/1999/xhtml">
<head><meta charset="utf-8" /></head>
<body style="font-family:Arial,sans-serif;margin:0;padding:0;background:#f5f5f5;">
<table width="100%" style="background:#f5f5f5;">
<tr><td align="center" style="padding:20px 0;">
<table width="640" style="background:white;border-collapse:collapse;">
<tr style="background:{header_color};color:white;">
<td style="padding:24px 30px;">
<h2 style="margin:0 0 8px 0;font-size:24px;color:white;">Weekly Solar Report</h2>
<p style="margin:0 0 4px 0;font-size:15px;color:rgba(255,255,255,0.9);">FusionSolar billing-cycle summary</p>
<p style="margin:0;font-size:12px;color:rgba(255,255,255,0.7);">Cycle: {cycle_start} to {cycle_end} ({days_count} days)</p>
</td>
</tr>
<tr style="background:{net_bg};">
<td style="padding:30px;text-align:center;border-bottom:3px solid {excess_color};">
<p style="margin:0 0 8px 0;font-size:12px;text-transform:uppercase;color:#888;letter-spacing:1px;">Net Excess After {heat_loss_percent:.0f}% Loss</p>
<p style="margin:0 0 10px 0;font-size:56px;font-weight:900;color:{excess_color};line-height:1;">{net_excess:+.2f} kWh</p>
<p style="margin:0 0 6px 0;font-size:15px;font-weight:bold;color:{excess_color};">{net_label}</p>
<p style="margin:0;font-size:12px;color:#999;">({total_export:.2f} exported minus {total_import:.2f} imported) times {loss_mult:.2f}</p>
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
<p style="margin:0;font-size:12px;color:#777;">{cycle_note}</p>
</td>
</tr>
<tr style="border-top:1px solid #ddd;">
<td style="padding:15px 30px;text-align:center;font-size:11px;color:#999;">
Automated weekly report from FusionSolar Monitor | {now_str}
</td>
</tr>
</table>
</td></tr>
</table>
</body>
</html>"""


def print_console_report(daily_data: list[dict], billing_day: int = 15, heat_loss_percent: float = 5.0) -> None:
    loss_mult = 1 - heat_loss_percent / 100
    total_export = sum(d['export'] for d in daily_data)
    total_import = sum(d['import'] for d in daily_data)
    net_excess = (total_export - total_import) * loss_mult

    cycle_start = daily_data[0]['date'] if daily_data else '-'
    cycle_end = daily_data[-1]['date'] if daily_data else '-'
    days_left = _days_until_next_reset(billing_day)
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M')

    print(f"\n{'=' * 60}")
    print(f"  Solar Cycle Report — {now_str}")
    print(f"  Billing Period: {cycle_start} to {cycle_end} ({len(daily_data)} days)")
    print(f"{'=' * 60}")
    print(f"  {'Date':<14} {'Export':>8} {'Import':>8} {'Net':>8}")
    print(f"  {'-'*14} {'-'*8} {'-'*8} {'-'*8}")
    for d in daily_data:
        day_net = (d['export'] - d['import']) * loss_mult
        sign = '+' if day_net >= 0 else ''
        print(f"  {d['date']:<14} {d['export']:>8.2f} {d['import']:>8.2f} {sign}{day_net:>7.2f}")
    print(f"  {'-'*14} {'-'*8} {'-'*8} {'-'*8}")
    label = "NET EXPORTER" if net_excess > 0 else "NET IMPORTER"
    sign = '+' if net_excess >= 0 else ''
    print(f"  {'TOTAL':<14} {total_export:>8.2f} {total_import:>8.2f} {sign}{net_excess:>7.2f} kWh  ← {label}")
    print(f"{'=' * 60}")
    print(f"  Loss rate: {heat_loss_percent:.0f}% | Next reset: ~{days_left} days")
    print(f"{'=' * 60}\n")
