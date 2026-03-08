"""
telegram/bot_sender.py
=======================
Formats and delivers signals to Telegram.
Supports auto-publish and admin approval mode with inline buttons.
"""

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
import config as cfg

logger = logging.getLogger('abin.telegram')
TG_API = 'https://api.telegram.org/bot{token}/{method}'


def _tg(method: str, payload: dict, retries: int = 3) -> Optional[dict]:
    if not cfg.TELEGRAM_BOT_TOKEN:
        logger.warning('No BOT_TOKEN — skipping Telegram call')
        return None
    try:
        import httpx
    except ImportError:
        logger.error('httpx not installed')
        return None

    url, last = TG_API.format(token=cfg.TELEGRAM_BOT_TOKEN, method=method), None
    for attempt in range(1, retries + 1):
        try:
            with httpx.Client(timeout=15) as c:
                r = c.post(url, json=payload)
                d = r.json()
                if d.get('ok'): return d['result']
                last = d.get('description', '')
                logger.warning(f'TG error (attempt {attempt}): {last}')
        except Exception as e:
            last = str(e)
        if attempt < retries: time.sleep(2 ** attempt)
    logger.error(f'TG call {method} failed: {last}')
    return None


def _bar(score: int, width: int = 12) -> str:
    filled = round(score / 100 * width)
    return '█' * filled + '░' * (width - filled)


# ── MESSAGE FORMATTERS ────────────────────────────────────────────────────────

def format_signal(s: dict) -> str:
    conf = s.get('confidence', 0)
    if conf >= 80:   tier = '🔥 HIGH CONFIDENCE'
    elif conf >= 65: tier = '✅ CONFIDENCE'
    else:            tier = '⚠️ SPECULATIVE'

    lines = [
        '⚽  *AFRICAN BETTING INTELLIGENCE*',
        '─' * 32,
        '',
        f"🏆  *{s.get('league_name', 'African Football')}*",
        '',
        f"⚔️   *{s.get('home_team', '?')}*",
        f"   vs  *{s.get('away_team', '?')}*",
        '',
        f"📋  *Signal:* {s.get('market', '')} — {s.get('outcome', '')}",
        f"💰  *Odds:* {s.get('odds', '?')}",
        f"⏰  *Kick-off:* {s.get('kick_off', 'TBC')}",
        '',
        f"{tier}",
        f"`{_bar(conf)}` {conf}/100",
        '',
        '📊  *Model Insight*',
        s.get('model_insight', ''),
    ]

    if cfg.FEATURES.get('include_affiliate_links'):
        lines += ['', f"🔗  *Place at Betway:* {cfg.AFFILIATE_LINKS.get('betway', '')}"]

    lines += [
        '', '─' * 32,
        '⚡  _African Betting Intelligence Network_',
        f"_Signal ID: {s.get('id', '?')}_",
    ]
    return '\n'.join(lines)


def format_admin_preview(s: dict) -> str:
    return (
        f"🔔 *SIGNAL PENDING REVIEW*  ID: `{s.get('id', '?')}`\n\n"
        f"🏆 {s.get('league_name', '?')}\n"
        f"⚔️ {s.get('home_team')} vs {s.get('away_team')}\n"
        f"📋 {s.get('market')} → *{s.get('outcome')}* @ {s.get('odds')}\n"
        f"🎯 Confidence: *{s.get('confidence')}/100*  |  Edge: {s.get('edge', '?')}\n"
        f"⏰ {s.get('kick_off', 'TBC')}\n\n"
        f"_{s.get('model_insight', '')}_\n\n"
        f"React ✅ to approve  ·  ❌ to reject"
    )


def format_weekly_summary(signals: list[dict]) -> str:
    wins   = sum(1 for s in signals if s.get('result') == 'WIN')
    losses = sum(1 for s in signals if s.get('result') == 'LOSS')
    acc    = f'{wins/(wins+losses)*100:.0f}%' if (wins+losses) > 0 else 'Pending'
    return (
        f"📈  *WEEKLY PERFORMANCE SUMMARY*\n{'─'*30}\n\n"
        f"Signals: {len(signals)}  |  W: {wins}  L: {losses}\n"
        f"Accuracy: *{acc}*\n\n"
        f"_African Betting Intelligence Network_"
    )


def format_error_alert(module: str, error: str) -> str:
    return (
        f"⚠️  *SYSTEM ERROR*\n\n"
        f"Module: `{module}`\n"
        f"Error: `{str(error)[:300]}`\n\n"
        f"_Check GitHub Actions logs for full traceback_"
    )


# ── SENDER ────────────────────────────────────────────────────────────────────

class TelegramSender:

    def send_signal(self, signal: dict) -> bool:
        result = _tg('sendMessage', {
            'chat_id': cfg.TELEGRAM_CHANNEL_ID,
            'text': format_signal(signal),
            'parse_mode': 'Markdown',
            'disable_web_page_preview': True,
        })
        if result:
            signal['telegram_msg_id'] = result.get('message_id')
            logger.info(f"Signal {signal['id']} published → channel")
            return True
        return False

    def send_to_admin_queue(self, signal: dict) -> Optional[int]:
        chat = cfg.TELEGRAM_ADMIN_CHANNEL or cfg.TELEGRAM_ADMIN_CHAT_ID
        if not chat: return None
        result = _tg('sendMessage', {
            'chat_id': chat,
            'text': format_admin_preview(signal),
            'parse_mode': 'Markdown',
            'reply_markup': {'inline_keyboard': [[
                {'text': '✅ Approve', 'callback_data': f'approve:{signal["id"]}'},
                {'text': '❌ Reject',  'callback_data': f'reject:{signal["id"]}'},
            ]]},
        })
        return result.get('message_id') if result else None

    def send_error_alert(self, module: str, error: str) -> bool:
        chat = cfg.TELEGRAM_ADMIN_CHAT_ID
        if not chat: return False
        return bool(_tg('sendMessage', {
            'chat_id': chat,
            'text': format_error_alert(module, error),
            'parse_mode': 'Markdown',
        }))

    def send_weekly_summary(self, signals: list[dict]) -> bool:
        return bool(_tg('sendMessage', {
            'chat_id': cfg.TELEGRAM_CHANNEL_ID,
            'text': format_weekly_summary(signals),
            'parse_mode': 'Markdown',
        }))

    def test_connection(self) -> dict:
        result = _tg('getMe', {}) or {}
        if result:
            logger.info(f"Bot online: @{result.get('username')}")
        return result

    def process_callback(self, callback: dict) -> None:
        data    = callback.get('data', '')
        chat_id = callback.get('message', {}).get('chat', {}).get('id')
        msg_id  = callback.get('message', {}).get('message_id')
        if ':' not in data: return

        action, signal_id = data.split(':', 1)
        path = cfg.SIGNALS_DIR / f'{signal_id}.json'
        if not path.exists(): return
        sig = json.loads(path.read_text())

        if action == 'approve':
            ok = self.send_signal(sig)
            if ok:
                sig.update(status='published',
                           published_at=datetime.now(timezone.utc).isoformat())
                path.write_text(json.dumps(sig, indent=2))
            _tg('answerCallbackQuery', {'callback_query_id': callback['id'],
                                        'text': '✅ Published!'})
            _tg('editMessageText', {
                'chat_id': chat_id, 'message_id': msg_id,
                'text': f"✅ PUBLISHED — {sig['home_team']} vs {sig['away_team']}",
                'parse_mode': 'Markdown'})
        elif action == 'reject':
            sig.update(status='rejected',
                       rejected_at=datetime.now(timezone.utc).isoformat())
            path.write_text(json.dumps(sig, indent=2))
            _tg('answerCallbackQuery', {'callback_query_id': callback['id'],
                                        'text': '❌ Rejected'})
            _tg('editMessageText', {
                'chat_id': chat_id, 'message_id': msg_id,
                'text': f"❌ REJECTED — {sig['home_team']} vs {sig['away_team']}",
                'parse_mode': 'Markdown'})


def dispatch_pending():
    sender = TelegramSender()
    for path in sorted(cfg.SIGNALS_DIR.glob('*.json')):
        try:
            sig = json.loads(path.read_text())
            if sig.get('status') != 'pending': continue
            if cfg.PUBLISH_MODE == 'auto':
                if sender.send_signal(sig):
                    sig.update(status='published',
                               published_at=datetime.now(timezone.utc).isoformat())
                    path.write_text(json.dumps(sig, indent=2))
            else:
                msg_id = sender.send_to_admin_queue(sig)
                if msg_id:
                    sig.update(status='admin_review', admin_msg_id=msg_id)
                    path.write_text(json.dumps(sig, indent=2))
            time.sleep(1)
        except Exception as e:
            logger.error(f'Dispatch error {path.name}: {e}')
            sender.send_error_alert('bot_sender', str(e))


def poll_callbacks(duration: int = 300):
    """Poll for admin approve/reject callbacks for `duration` seconds."""
    sender = TelegramSender()
    offset_path = cfg.DATA_DIR / 'tg_offset.txt'
    offset = int(offset_path.read_text()) if offset_path.exists() else None
    import time as _time
    deadline = _time.time() + duration
    while _time.time() < deadline:
        try:
            params = {'timeout': 20, 'allowed_updates': ['callback_query']}
            if offset: params['offset'] = offset
            result = _tg('getUpdates', params)
            for upd in (result or []):
                uid = upd.get('update_id')
                if uid: offset = uid + 1
                if 'callback_query' in upd:
                    sender.process_callback(upd['callback_query'])
            if offset: offset_path.write_text(str(offset))
            _time.sleep(2)
        except KeyboardInterrupt:
            break
        except Exception as e:
            logger.error(f'Poll error: {e}')
            _time.sleep(5)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s [%(levelname)s] %(message)s')
    s = TelegramSender()
    bot = s.test_connection()
    print(f"{'✓' if bot else '✗'} Bot: @{bot.get('username', 'not connected')}")
    dispatch_pending()
