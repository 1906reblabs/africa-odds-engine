"""
engine/signal_engine.py
========================
Orchestrates the full signal pipeline:
  1. Load raw data (or use demo data)
  2. For each fixture × market, run Poisson + ValueDetector
  3. Rank by confidence, apply weekly cap
  4. Write approved signals to SIGNALS_DIR for distribution
"""

import json
import logging
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
import config as cfg
from models.poisson_model import PoissonModel
from models.value_detector import ValueDetector, calculate_consensus

logger = logging.getLogger('abin.engine')
poisson  = PoissonModel()
detector = ValueDetector()


# ── WEEKLY CAP ────────────────────────────────────────────────────────────────

def _weekly_count() -> int:
    path = cfg.DATA_DIR / 'weekly_counts.json'
    if not path.exists(): return 0
    today  = datetime.now(timezone.utc)
    monday = today - timedelta(days=today.weekday())
    return json.loads(path.read_text()).get(monday.strftime('%Y-W%V'), 0)

def _inc_weekly():
    path  = cfg.DATA_DIR / 'weekly_counts.json'
    data  = json.loads(path.read_text()) if path.exists() else {}
    today = datetime.now(timezone.utc)
    week  = (today - timedelta(days=today.weekday())).strftime('%Y-W%V')
    data[week] = data.get(week, 0) + 1
    path.write_text(json.dumps(data, indent=2))


# ── SIGNAL BUILDER ────────────────────────────────────────────────────────────

def _build_signal(event, market, outcome, model_prob, market_odds,
                   score, league_key, league_name, pois) -> dict:
    commence = event.get('commence_time', '')
    try:
        utc = datetime.fromisoformat(commence.replace('Z', '+00:00'))
        sast = (utc + timedelta(hours=2)).strftime('%H:%M SAST, %d %b %Y')
    except Exception:
        sast = commence

    home, away = event.get('home_team', '?'), event.get('away_team', '?')
    hxg, axg   = pois.get('home_xg', 0), pois.get('away_xg', 0)

    insight = (
        f"Model projects {hxg:.2f}–{axg:.2f} xG. "
        f"Over 2.5: {pois.get('over_2_5', 0):.0%}. "
        f"BTTS: {pois.get('btts_yes', 0):.0%}."
    )
    if score['edge'] >= cfg.MED_VALUE_EDGE:
        insight += f" Edge vs market: {score['edge_pct']}."

    return {
        'id':            str(uuid.uuid4())[:12],
        'league':        league_key,
        'league_name':   league_name,
        'home_team':     home,
        'away_team':     away,
        'kick_off':      sast,
        'kick_off_utc':  commence,
        'market':        market,
        'outcome':       outcome,
        'odds':          round(market_odds, 2),
        'confidence':    score['total'],
        'edge':          score['edge_pct'],
        'kelly':         score['kelly_fraction'],
        'recommendation': score['recommendation'],
        'model_insight': insight,
        'components':    score['components'],
        'poisson':       {k: v for k, v in pois.items()
                         if isinstance(v, (int, float))},
        'status':        'pending',
        'created_utc':   datetime.now(timezone.utc).isoformat(),
        'result':        None,
    }


# ── MAIN ENGINE ───────────────────────────────────────────────────────────────

class SignalEngine:

    def process_event(self, event: dict, league_key: str, league_name: str,
                       home_form: list = None, away_form: list = None) -> list[dict]:
        bms = event.get('bookmakers', [])
        if not bms: return []

        default_form = [{'scored': 1.2, 'conceded': 1.1}] * 5
        hf = home_form or default_form
        af = away_form or default_form

        pois = poisson.predict_from_form(hf, af, league_key)
        completeness = 0.85 if home_form and away_form else \
                       0.72 if home_form or away_form else 0.60

        candidates = []

        for outcome_name, model_key in [
            ('Home', 'home_win'), ('Draw', 'draw'), ('Away', 'away_win')
        ]:
            con = calculate_consensus(bms, 'h2h', outcome_name)
            if con['best_odds'] <= 1.0: continue
            s = detector.score(pois[model_key], con['best_odds'], bms,
                               'h2h', outcome_name, data_completeness=completeness)
            if s['total'] >= cfg.HARD_REJECT_BELOW:
                candidates.append(_build_signal(
                    event, 'Match Winner', outcome_name, pois[model_key],
                    con['best_odds'], s, league_key, league_name, pois))

        for label, model_key, market_name in [
            ('Over',  'over_2_5',  'Goals Over 2.5'),
            ('Under', 'under_2_5', 'Goals Under 2.5'),
        ]:
            con = calculate_consensus(bms, 'totals', label)
            if con['best_odds'] <= 1.0: continue
            s = detector.score(pois[model_key], con['best_odds'], bms,
                               'totals', label, data_completeness=completeness)
            if s['total'] >= cfg.HARD_REJECT_BELOW:
                candidates.append(_build_signal(
                    event, market_name, f'{label} 2.5', pois[model_key],
                    con['best_odds'], s, league_key, league_name, pois))

        return candidates

    def run(self) -> list[dict]:
        raw = cfg.DATA_DIR / 'raw_data.json'
        if not raw.exists():
            logger.warning('No raw data — run ingestion first')
            return []

        weekly_used = _weekly_count()
        remaining   = cfg.WEEKLY_SIGNAL_CAP - weekly_used
        if remaining <= 0:
            logger.info(f'Weekly cap reached ({weekly_used}/{cfg.WEEKLY_SIGNAL_CAP})')
            return []

        all_data = json.loads(raw.read_text())
        candidates = []

        for ld in all_data:
            for event in ld.get('odds_events', []):
                try:
                    sigs = self.process_event(
                        event, ld['league'], ld.get('league_name', ld['league']))
                    candidates.extend(sigs)
                except Exception as e:
                    logger.error(f"Error on event {event.get('id','?')}: {e}")

        candidates.sort(key=lambda x: x['confidence'], reverse=True)
        qualified = [c for c in candidates if c['confidence'] >= cfg.CONFIDENCE_THRESHOLD]
        selected  = qualified[:min(cfg.SIGNALS_PER_CYCLE, remaining)]

        for sig in selected:
            path = cfg.SIGNALS_DIR / f"{sig['id']}.json"
            path.write_text(json.dumps(sig, indent=2))
            logger.info(f"  QUEUED [{sig['confidence']:>3}] "
                        f"{sig['home_team']} vs {sig['away_team']} "
                        f"— {sig['market']} {sig['outcome']} @ {sig['odds']}")

        (cfg.DATA_DIR / 'last_run.json').write_text(json.dumps({
            'run_at': datetime.now(timezone.utc).isoformat(),
            'processed': len(candidates), 'qualified': len(qualified),
            'saved': len(selected), 'weekly_used': weekly_used + len(selected),
        }, indent=2))

        logger.info(f'Engine complete: {len(selected)} signals queued')
        return selected


# ── DEMO DATA ─────────────────────────────────────────────────────────────────

def _demo_event(home, away, league, ho=2.10, dr=3.30, ao=3.50,
                ov=2.05, un=1.80) -> dict:
    kick = (datetime.now(timezone.utc) + timedelta(hours=26)).isoformat()
    return {
        'id': f'demo-{uuid.uuid4().hex[:8]}',
        'commence_time': kick,
        'home_team': home, 'away_team': away,
        'bookmakers': [
            {'key': 'betway', 'markets': [
                {'key': 'h2h', 'outcomes': [
                    {'name': 'Home', 'price': ho},
                    {'name': 'Draw', 'price': dr},
                    {'name': 'Away', 'price': ao},
                ]},
                {'key': 'totals', 'outcomes': [
                    {'name': 'Over', 'price': ov},
                    {'name': 'Under', 'price': un},
                ]},
            ]},
            {'key': 'bet365', 'markets': [
                {'key': 'h2h', 'outcomes': [
                    {'name': 'Home', 'price': round(ho - 0.05, 2)},
                    {'name': 'Draw', 'price': round(dr - 0.05, 2)},
                    {'name': 'Away', 'price': round(ao + 0.10, 2)},
                ]},
                {'key': 'totals', 'outcomes': [
                    {'name': 'Over',  'price': round(ov + 0.05, 2)},
                    {'name': 'Under', 'price': round(un - 0.05, 2)},
                ]},
            ]},
            {'key': 'hollywoodbets', 'markets': [
                {'key': 'h2h', 'outcomes': [
                    {'name': 'Home', 'price': round(ho + 0.08, 2)},
                    {'name': 'Draw', 'price': round(dr + 0.05, 2)},
                    {'name': 'Away', 'price': round(ao - 0.05, 2)},
                ]},
            ]},
        ],
    }


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s [%(levelname)s] %(message)s')
    engine = SignalEngine()
    demo_fixtures = [
        ('Mamelodi Sundowns', 'Orlando Pirates',   'psl',      1.75, 3.50, 5.00, 1.95, 1.85),
        ('Kaizer Chiefs',     'SuperSport United', 'psl',      2.20, 3.20, 3.40, 2.10, 1.75),
        ('Al Ahly',           'Zamalek',           'egypt_pl', 1.90, 3.40, 4.20, 2.20, 1.70),
        ('Wydad AC',          'Raja CA',           'botola',   2.00, 3.20, 3.80, 2.05, 1.80),
        ('TP Mazembe',        'Petro Luanda',      'caf_cl',   2.30, 3.10, 3.20, 2.15, 1.72),
        ('Enyimba FC',        'Rivers United',     'npfl',     2.40, 3.00, 2.90, 2.00, 1.78),
        ('Gor Mahia',         'AFC Leopards',      'kpl',      2.10, 3.25, 3.60, 2.12, 1.76),
    ]
    all_sigs = []
    for home, away, lg, ho, dr, ao, ov, un in demo_fixtures:
        event = _demo_event(home, away, lg, ho, dr, ao, ov, un)
        ln    = cfg.LEAGUE_CONFIGS.get(lg, {}).get('name', lg)
        hf    = [{'scored': 1.6, 'conceded': 0.8}] * 5
        af_   = [{'scored': 1.1, 'conceded': 1.3}] * 5
        all_sigs.extend(engine.process_event(event, lg, ln, hf, af_))

    all_sigs.sort(key=lambda x: x['confidence'], reverse=True)
    print(f'\n📊 {len(all_sigs)} signal candidates:\n')
    for s in all_sigs[:12]:
        e = '🔥' if s['confidence'] >= 80 else '✅' if s['confidence'] >= 65 else '⚠️'
        print(f"  {e} [{s['confidence']:>3}] {s['home_team'][:20]:<20} "
              f"vs {s['away_team'][:20]:<20}  "
              f"{s['market']:.<20} {s['outcome']:>8} @ {s['odds']:4.2f}  "
              f"edge: {s['edge']}")
