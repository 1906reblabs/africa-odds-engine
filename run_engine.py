"""
scheduler/run_engine.py
========================
Master orchestrator — runs the full 4-step pipeline per cycle.
Called by GitHub Actions every 4 hours.
"""

import json
import logging
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import config as cfg
from data_sources.api_fetcher import DataAggregator, save_raw_data
from engine.signal_engine import SignalEngine
from telegram.bot_sender import TelegramSender, dispatch_pending, poll_callbacks

# ── LOGGING ───────────────────────────────────────────────────────────────────
log_path = cfg.LOGS_DIR / f'run_{datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")}.log'
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(str(log_path), encoding='utf-8'),
    ],
)
logger = logging.getLogger('abin.main')


def run():
    start = datetime.now(timezone.utc)
    sender = TelegramSender()

    logger.info('═' * 60)
    logger.info('  AFRICAN BETTING INTELLIGENCE NETWORK — ENGINE START')
    logger.info(f'  {start.strftime("%Y-%m-%d %H:%M UTC")}')
    logger.info('═' * 60)

    try:
        # ── STEP 1: Validate ──────────────────────────────────────────
        logger.info('Step 1/4: Validating config...')
        for w in cfg.validate_config():
            logger.warning(f'  CONFIG: {w}')
        active = cfg.get_active_leagues()
        logger.info(f'  Active leagues ({len(active)}): {active}')
        logger.info(f'  Publish mode: {cfg.PUBLISH_MODE}')

        if not cfg.TELEGRAM_BOT_TOKEN:
            logger.error('No BOT_TOKEN — aborting'); sys.exit(1)

        # ── STEP 2: Fetch data ────────────────────────────────────────
        logger.info('Step 2/4: Fetching odds and fixtures...')
        if active:
            data = DataAggregator().fetch_all_active()
            save_raw_data(data)
        else:
            data = []
        total_odds = sum(len(d.get('odds_events', [])) for d in data)
        logger.info(f'  Fetched: {total_odds} odds events across {len(data)} leagues')

        # ── STEP 3: Signal engine ─────────────────────────────────────
        logger.info('Step 3/4: Running signal engine...')
        sigs = SignalEngine().run()
        logger.info(f'  Queued: {len(sigs)} signal(s)')

        # ── STEP 4: Dispatch ──────────────────────────────────────────
        logger.info(f'Step 4/4: Dispatching (mode={cfg.PUBLISH_MODE})...')
        if sigs:
            dispatch_pending()
            if cfg.PUBLISH_MODE == 'admin':
                logger.info('  Polling 5 minutes for admin responses...')
                poll_callbacks(duration=280)
        else:
            logger.info('  No signals to dispatch this cycle')

        # ── DONE ──────────────────────────────────────────────────────
        elapsed = (datetime.now(timezone.utc) - start).total_seconds()
        logger.info('═' * 60)
        logger.info(f'  RUN COMPLETE in {elapsed:.1f}s — {len(sigs)} signal(s)')
        logger.info('═' * 60)

        (cfg.DATA_DIR / 'last_run.json').write_text(json.dumps({
            'run_start': start.isoformat(), 'elapsed_sec': elapsed,
            'leagues': active, 'odds_events': total_odds,
            'signals': len(sigs), 'status': 'ok',
        }, indent=2))

    except Exception as e:
        logger.error(f'FATAL: {e}\n{traceback.format_exc()}')
        try: sender.send_error_alert('run_engine', f'{type(e).__name__}: {e}')
        except Exception: pass
        (cfg.DATA_DIR / 'last_run.json').write_text(json.dumps({
            'run_start': start.isoformat(), 'status': 'error', 'error': str(e)
        }, indent=2))
        sys.exit(1)


if __name__ == '__main__':
    run()
