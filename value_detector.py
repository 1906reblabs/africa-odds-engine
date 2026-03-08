"""
models/value_detector.py
=========================
Edge calculation, drift detection, bookmaker consensus, and Kelly staking.
Uses the RUBRIC_WEIGHTS from config.py — matching Edgeline confidence rubric.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
import config as cfg


def implied_prob(odds: float) -> float:
    return 1.0 / odds if odds > 1.0 else 1.0

def remove_margin(probs: list[float]) -> list[float]:
    total = sum(probs) or 1.0
    return [p / total for p in probs]

def calculate_edge(model_prob: float, market_odds: float) -> float:
    """Edge = model_prob × market_odds − 1. Positive = value."""
    return model_prob * market_odds - 1.0

def kelly_fraction(edge: float, odds: float, fraction: float = 0.25) -> float:
    """Quarter-Kelly stake as fraction of bankroll."""
    if odds <= 1.0 or edge <= 0: return 0.0
    b = odds - 1.0
    p = (edge + 1.0) / odds
    q = 1.0 - p
    return max(0.0, (b * p - q) / b * fraction)


def detect_drift(open_odds: float, current_odds: float) -> dict:
    if open_odds <= 1.0 or current_odds <= 1.0:
        return {'pct_change': 0.0, 'direction': 'stable',
                'is_significant': False, 'is_strong': False}
    pct = (current_odds - open_odds) / open_odds * 100
    direction = 'shortened' if current_odds < open_odds else \
                'drifted'   if current_odds > open_odds else 'stable'
    return {
        'open_odds': round(open_odds, 3), 'current_odds': round(current_odds, 3),
        'pct_change': round(pct, 2), 'direction': direction,
        'is_significant': abs(pct) >= cfg.SIGNIFICANT_DRIFT_PCT,
        'is_strong':      abs(pct) >= cfg.STRONG_DRIFT_PCT,
    }


def calculate_consensus(bookmakers: list[dict], market_key: str,
                         outcome_name: str) -> dict:
    """Average odds and disagreement score across bookmakers."""
    all_odds = []
    best_odds, best_book = 0.0, ''
    for bm in bookmakers:
        for mkt in bm.get('markets', []):
            if mkt.get('key') != market_key: continue
            for oc in mkt.get('outcomes', []):
                if oc.get('name', '').lower() == outcome_name.lower():
                    p = oc.get('price', 0)
                    if p > 1.0:
                        all_odds.append(p)
                        if p > best_odds:
                            best_odds, best_book = p, bm.get('key', '')
    if not all_odds:
        return {'consensus': 0.0, 'variance': 0.0, 'cv': 0.0,
                'disagreement': False, 'count': 0, 'best_odds': 0.0, 'best_book': ''}
    avg = sum(all_odds) / len(all_odds)
    var = sum((o - avg) ** 2 for o in all_odds) / len(all_odds)
    cv  = (var ** 0.5) / avg if avg > 0 else 0
    return {
        'consensus':    round(avg, 3),
        'variance':     round(var, 4),
        'cv':           round(cv, 4),
        'disagreement': cv > 0.05,
        'count':        len(all_odds),
        'min_odds':     min(all_odds),
        'max_odds':     max(all_odds),
        'best_odds':    best_odds,
        'best_book':    best_book,
    }


def retail_vs_sharp(bookmakers: list[dict], market_key: str,
                     outcome_name: str) -> dict:
    """Compare retail vs sharp book odds. Retail longer = value opportunity."""
    sharp_keys  = cfg.get_sharp_books()
    retail_keys = cfg.get_retail_books()
    sharp, retail = [], []
    for bm in bookmakers:
        bm_key = bm.get('key', '')
        for mkt in bm.get('markets', []):
            if mkt.get('key') != market_key: continue
            for oc in mkt.get('outcomes', []):
                if oc.get('name', '').lower() == outcome_name.lower():
                    p = oc.get('price', 0)
                    if p > 1.0:
                        if bm_key in sharp_keys:  sharp.append(p)
                        elif bm_key in retail_keys: retail.append(p)
    if not sharp or not retail: return {'has_divergence': False}
    sa = sum(sharp)  / len(sharp)
    ra = sum(retail) / len(retail)
    div = (ra - sa) / sa * 100 if sa > 0 else 0
    return {'sharp_avg': round(sa, 3), 'retail_avg': round(ra, 3),
            'divergence_pct': round(div, 2),
            'has_divergence': div >= 3.0, 'retail_has_value': div >= 5.0}


class ValueDetector:
    """
    Score a single bet candidate on a 0–100 confidence scale.
    Uses RUBRIC_WEIGHTS from config.py — matching the Edgeline pattern.
    """

    W = cfg.RUBRIC_WEIGHTS   # alias

    def score(self, model_prob: float, market_odds: float,
              bookmakers: list[dict], market_key: str, outcome_name: str,
              open_odds: float = None, data_completeness: float = 0.8) -> dict:

        comp = {}

        # 1. Data quality
        comp['data_quality'] = int(data_completeness * self.W['data_quality'])

        # 2. Market edge
        edge = calculate_edge(model_prob, market_odds)
        if edge >= cfg.HIGH_VALUE_EDGE:
            comp['market_edge'] = self.W['market_edge']
        elif edge >= cfg.MED_VALUE_EDGE:
            comp['market_edge'] = int(self.W['market_edge'] * 0.75)
        elif edge >= cfg.MIN_VALUE_EDGE:
            comp['market_edge'] = int(self.W['market_edge'] * 0.45)
        else:
            comp['market_edge'] = 0

        # 3. Drift confirmation
        if open_odds:
            d = detect_drift(open_odds, market_odds)
            if d['direction'] == 'shortened' and d['is_strong']:
                comp['drift_confirmation'] = self.W['drift_confirmation']
            elif d['direction'] == 'shortened' and d['is_significant']:
                comp['drift_confirmation'] = int(self.W['drift_confirmation'] * 0.6)
            elif d['direction'] == 'stable':
                comp['drift_confirmation'] = int(self.W['drift_confirmation'] * 0.3)
            else:
                comp['drift_confirmation'] = 0
        else:
            comp['drift_confirmation'] = int(self.W['drift_confirmation'] * 0.4)

        # 4. Bookmaker agreement
        con = calculate_consensus(bookmakers, market_key, outcome_name)
        if con['disagreement']:
            comp['bookmaker_agreement'] = self.W['bookmaker_agreement']
        elif con['count'] >= 3:
            comp['bookmaker_agreement'] = int(self.W['bookmaker_agreement'] * 0.5)
        elif con['count'] < 2:
            comp['bookmaker_agreement'] = int(self.W['bookmaker_agreement'] * 0.3)
        else:
            comp['bookmaker_agreement'] = int(self.W['bookmaker_agreement'] * 0.7)

        # 5. Model alignment
        fair = 1.0 / con['consensus'] if con.get('consensus', 0) > 0 else 0
        if fair > 0:
            gap = abs(model_prob - fair) / fair
            if model_prob > fair and gap >= 0.10:
                comp['model_alignment'] = self.W['model_alignment']
            elif model_prob > fair:
                comp['model_alignment'] = int(self.W['model_alignment'] * 0.6)
            else:
                comp['model_alignment'] = int(self.W['model_alignment'] * 0.2)
        else:
            comp['model_alignment'] = int(self.W['model_alignment'] * 0.3)

        total = sum(comp.values())
        if total >= 80:      rec = '🔥 STRONG BUY'
        elif total >= cfg.CONFIDENCE_THRESHOLD: rec = '✅ BUY'
        elif total >= 55:    rec = '⚠️ MARGINAL'
        else:                rec = '❌ PASS'

        return {
            'total': total, 'components': comp,
            'edge': round(edge, 4), 'edge_pct': f'{edge*100:.1f}%',
            'kelly_fraction': round(kelly_fraction(edge, market_odds), 4),
            'recommendation': rec,
            'model_prob': round(model_prob, 4),
            'market_odds': round(market_odds, 3),
            'consensus': con,
        }
