"""
telegram/admin_queue.py
========================
Standalone admin approval loop.
Polls Telegram for ✅/❌ callback_query responses on queued signals.
Can be run as a separate process or imported into run_engine.py.
"""

import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import config as cfg
from telegram.bot_sender import TelegramSender, _tg

logger = logging.getLogger('abin.admin_queue')


def send_all_pending_to_review() -> int:
    """
    Send every pending signal to the admin review queue.
    Returns count of signals dispatched.
    """
    sender = TelegramSender()
    sent = 0
    for path in sorted(cfg.SIGNALS_DIR.glob('*.json')):
        try:
            sig = json.loads(path.read_text())
            if sig.get('status') != 'pending':
                continue
            msg_id = sender.send_to_admin_queue(sig)
            if msg_id:
                sig.update(status='admin_review',
                           admin_msg_id=msg_id,
                           review_sent_at=datetime.now(timezone.utc).isoformat())
                path.write_text(json.dumps(sig, indent=2))
                logger.info(f"  Queued for review: {sig['home_team']} vs {sig['away_team']}")
                sent += 1
            time.sleep(0.8)
        except Exception as e:
            logger.error(f'Error queuing {path.name}: {e}')
    return sent


def poll_for_decisions(duration_seconds: int = 300, poll_interval: int = 3) -> dict:
    """
    Poll Telegram for admin approve/reject decisions.
    Runs for `duration_seconds` then returns a summary dict.
    """
    sender = TelegramSender()
    offset_path = cfg.DATA_DIR / 'tg_offset.txt'
    offset = int(offset_path.read_text()) if offset_path.exists() else None

    approved = rejected = errors = 0
    deadline = time.time() + duration_seconds

    logger.info(f'Polling for admin decisions ({duration_seconds}s)...')

    while time.time() < deadline:
        try:
            params = {
                'timeout': min(poll_interval * 5, 20),
                'allowed_updates': ['callback_query'],
            }
            if offset:
                params['offset'] = offset

            updates = _tg('getUpdates', params) or []

            for upd in updates:
                uid = upd.get('update_id')
                if uid:
                    offset = uid + 1

                if 'callback_query' not in upd:
                    continue

                cb   = upd['callback_query']
                data = cb.get('data', '')
                if ':' not in data:
                    continue

                action, signal_id = data.split(':', 1)
                path = cfg.SIGNALS_DIR / f'{signal_id}.json'

                if not path.exists():
                    _tg('answerCallbackQuery', {
                        'callback_query_id': cb['id'],
                        'text': '⚠️ Signal not found',
                    })
                    continue

                sig     = json.loads(path.read_text())
                chat_id = cb.get('message', {}).get('chat', {}).get('id')
                msg_id  = cb.get('message', {}).get('message_id')
                admin   = cb.get('from', {}).get('username', 'admin')

                if action == 'approve':
                    ok = sender.send_signal(sig)
                    if ok:
                        sig.update(
                            status='published',
                            approved_by=admin,
                            published_at=datetime.now(timezone.utc).isoformat(),
                        )
                        path.write_text(json.dumps(sig, indent=2))
                        approved += 1
                        logger.info(f"  ✅ APPROVED by @{admin}: "
                                    f"{sig['home_team']} vs {sig['away_team']}")
                    _tg('answerCallbackQuery', {
                        'callback_query_id': cb['id'],
                        'text': '✅ Signal published to channel!',
                    })
                    _tg('editMessageReplyMarkup', {
                        'chat_id': chat_id, 'message_id': msg_id,
                        'reply_markup': {'inline_keyboard': []},
                    })

                elif action == 'reject':
                    sig.update(
                        status='rejected',
                        rejected_by=admin,
                        rejected_at=datetime.now(timezone.utc).isoformat(),
                    )
                    path.write_text(json.dumps(sig, indent=2))
                    rejected += 1
                    logger.info(f"  ❌ REJECTED by @{admin}: "
                                f"{sig['home_team']} vs {sig['away_team']}")
                    _tg('answerCallbackQuery', {
                        'callback_query_id': cb['id'],
                        'text': '❌ Signal rejected.',
                    })
                    _tg('editMessageReplyMarkup', {
                        'chat_id': chat_id, 'message_id': msg_id,
                        'reply_markup': {'inline_keyboard': []},
                    })

            if offset:
                offset_path.write_text(str(offset))

            time.sleep(poll_interval)

        except KeyboardInterrupt:
            logger.info('Poll interrupted by user')
            break
        except Exception as e:
            errors += 1
            logger.error(f'Poll error: {e}')
            time.sleep(5)

    summary = {'approved': approved, 'rejected': rejected, 'errors': errors}
    logger.info(f'Poll complete: {summary}')
    return summary


def get_pending_count() -> int:
    return sum(
        1 for f in cfg.SIGNALS_DIR.glob('*.json')
        if json.loads(f.read_text()).get('status') == 'pending'
    )


def get_awaiting_review_count() -> int:
    return sum(
        1 for f in cfg.SIGNALS_DIR.glob('*.json')
        if json.loads(f.read_text()).get('status') == 'admin_review'
    )


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s [%(levelname)s] %(message)s')
    pending = get_pending_count()
    review  = get_awaiting_review_count()
    logger.info(f'Queue status — pending: {pending}, awaiting review: {review}')
    if pending:
        n = send_all_pending_to_review()
        logger.info(f'Sent {n} signals to admin review queue')
    if pending or review:
        poll_for_decisions(duration_seconds=600)
