"""
scheduler/weekly_summary.py
============================
Sends the weekly performance digest to the admin every Thursday.
Triggered by GitHub Actions weekly-audit.yml cron.
"""

import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import config as cfg


def build_html(published: list, rejected_count: int,
               week_start: datetime, site_url: str) -> str:
    wins   = sum(1 for s in published if s.get('result') == 'WIN')
    losses = sum(1 for s in published if s.get('result') == 'LOSS')
    pending_results = sum(1 for s in published if not s.get('result'))
    accuracy = f'{wins/(wins+losses)*100:.0f}%' if (wins + losses) > 0 else 'Pending'

    rows = ''.join(
        f"""<tr>
          <td style="padding:10px 14px;border-bottom:1px solid #1c1c1c;
                     font-family:'Courier New',monospace;font-size:11px;color:#d4d0c8">
            {s.get('home_team','?')} vs {s.get('away_team','?')}
          </td>
          <td style="padding:10px 14px;border-bottom:1px solid #1c1c1c;font-size:11px;color:#888">
            {s.get('league_name','?')}
          </td>
          <td style="padding:10px 14px;border-bottom:1px solid #1c1c1c;font-size:11px;color:#c8973a">
            {s.get('market','')} {s.get('outcome','')} @ {s.get('odds','')}
          </td>
          <td style="padding:10px 14px;border-bottom:1px solid #1c1c1c;font-size:11px;
                     color:{'#5aaa72' if s.get('result')=='WIN' else '#aa5a5a' if s.get('result')=='LOSS' else '#555'}">
            {s.get('result','—')}
          </td>
        </tr>"""
        for s in published
    )

    return f"""
<div style="font-family:'Courier New',monospace;max-width:640px;margin:0 auto;
            background:#080808;color:#d4d0c8;padding:40px 36px">

  <p style="font-size:9px;letter-spacing:0.35em;color:#c8973a;
            text-transform:uppercase;margin:0 0 28px">
    AFRICAN BETTING INTELLIGENCE NETWORK · WEEKLY AUDIT
  </p>

  <h1 style="font-size:22px;font-weight:600;color:#fff;margin:0 0 8px;
             letter-spacing:-0.02em">
    Week of {week_start.strftime('%d %b %Y')}
  </h1>
  <p style="font-size:12px;color:#555;margin:0 0 36px">
    Thursday audit reminder — review all signals and log outcomes
  </p>

  <table style="width:100%;border-collapse:collapse;margin-bottom:32px">
    <tr>
      <td style="padding:12px 14px;border:1px solid #1c1c1c;
                 font-size:9px;letter-spacing:0.15em;color:#444;text-transform:uppercase">
        Signals published
      </td>
      <td style="padding:12px 14px;border:1px solid #1c1c1c;font-size:20px;color:#fff">
        {len(published)}
        <span style="font-size:11px;color:#444"> / {cfg.WEEKLY_SIGNAL_CAP} cap</span>
      </td>
    </tr>
    <tr>
      <td style="padding:12px 14px;border:1px solid #1c1c1c;
                 font-size:9px;letter-spacing:0.15em;color:#444;text-transform:uppercase">
        Wins / Losses
      </td>
      <td style="padding:12px 14px;border:1px solid #1c1c1c;font-size:20px;color:#fff">
        <span style="color:#5aaa72">{wins}W</span>
        &nbsp;
        <span style="color:#aa5a5a">{losses}L</span>
        &nbsp;
        <span style="font-size:11px;color:#444">{pending_results} pending</span>
      </td>
    </tr>
    <tr>
      <td style="padding:12px 14px;border:1px solid #1c1c1c;
                 font-size:9px;letter-spacing:0.15em;color:#444;text-transform:uppercase">
        Accuracy this week
      </td>
      <td style="padding:12px 14px;border:1px solid #1c1c1c;
                 font-size:20px;color:#c8973a">
        {accuracy}
      </td>
    </tr>
    <tr>
      <td style="padding:12px 14px;border:1px solid #1c1c1c;
                 font-size:9px;letter-spacing:0.15em;color:#444;text-transform:uppercase">
        Signals rejected
      </td>
      <td style="padding:12px 14px;border:1px solid #1c1c1c;font-size:20px;color:#555">
        {rejected_count}
      </td>
    </tr>
  </table>

  {'<table style="width:100%;border-collapse:collapse;margin-bottom:32px">' +
   '<tr style="background:#0a0a0a">' +
   '<th style="padding:8px 14px;text-align:left;font-size:8px;letter-spacing:0.2em;color:#444;font-weight:400;text-transform:uppercase">Match</th>' +
   '<th style="padding:8px 14px;text-align:left;font-size:8px;letter-spacing:0.2em;color:#444;font-weight:400;text-transform:uppercase">League</th>' +
   '<th style="padding:8px 14px;text-align:left;font-size:8px;letter-spacing:0.2em;color:#444;font-weight:400;text-transform:uppercase">Signal</th>' +
   '<th style="padding:8px 14px;text-align:left;font-size:8px;letter-spacing:0.2em;color:#444;font-weight:400;text-transform:uppercase">Result</th>' +
   '</tr>' + rows + '</table>' if published else
   '<p style="color:#444;font-size:12px">No signals published this week.</p>'}

  <div style="margin-bottom:28px">
    <p style="font-size:11px;color:#555;margin:0 0 6px">
      📋 Complete your Thursday audit checklist:
    </p>
    <ol style="font-size:11px;color:#555;padding-left:18px;line-height:2.2;margin:0">
      <li>Mark WIN / LOSS / VOID for every signal above</li>
      <li>Write a one-paragraph post-mortem for each</li>
      <li>Review rejected signals — were any rejections wrong?</li>
      <li>Check GitHub Actions — any red runs this week?</li>
      <li>Update the public performance log on the dashboard</li>
    </ol>
  </div>

  <a href="{site_url}/admin"
     style="display:inline-block;background:#c8973a;color:#000;
            font-family:'Courier New',monospace;font-size:9px;
            letter-spacing:0.2em;text-transform:uppercase;
            padding:11px 24px;text-decoration:none;margin-bottom:36px">
    Open Admin Panel →
  </a>

  <p style="font-size:9px;color:#2a2a2a;margin:0">
    AFRICAN BETTING INTELLIGENCE NETWORK · Weekly audit email
    · Sent every Thursday automatically
  </p>
</div>
"""


def run():
    admin_email   = cfg.ADMIN_EMAIL
    mailgun_key   = cfg.MAILGUN_API_KEY
    mailgun_domain = cfg.MAILGUN_DOMAIN
    site_url      = cfg.SITE_URL

    if not admin_email or not mailgun_key:
        print('No ADMIN_EMAIL or MAILGUN_API_KEY — skipping weekly summary')
        return

    today      = datetime.now(timezone.utc)
    week_start = (today - timedelta(days=today.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0)

    published, rejected_count = [], 0
    if cfg.SIGNALS_DIR.exists():
        for f in cfg.SIGNALS_DIR.glob('*.json'):
            try:
                s       = json.loads(f.read_text())
                created = datetime.fromisoformat(
                    s.get('created_utc', '').replace('Z', '+00:00'))
                if created >= week_start:
                    if s.get('status') == 'published':
                        published.append(s)
                    elif s.get('status') == 'rejected':
                        rejected_count += 1
            except Exception:
                pass

    html    = build_html(published, rejected_count, week_start, site_url)
    subject = f"ABIN · Weekly Audit — {today.strftime('%d %b %Y')}"

    try:
        import httpx
        r = httpx.post(
            f'https://api.mailgun.net/v3/{mailgun_domain}/messages',
            auth=('api', mailgun_key),
            data={
                'from':    f'ABIN Engine <signals@{mailgun_domain}>',
                'to':      admin_email,
                'subject': subject,
                'html':    html,
            },
            timeout=20,
        )
        print(f'Weekly audit email → {admin_email}: {r.status_code}')
    except Exception as e:
        print(f'Email failed: {e}')


if __name__ == '__main__':
    run()
