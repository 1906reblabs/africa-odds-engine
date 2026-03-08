"""
models/poisson_model.py
========================
Dixon-Coles style Poisson goal prediction, calibrated for African leagues.

Outputs per fixture:
  · Expected goals (home / away)
  · 1X2 outcome probabilities
  · Over/Under 1.5, 2.5, 3.5
  · Both Teams to Score
"""

import math
from functools import lru_cache
from typing import Optional

# Home advantage (goals above neutral venue), calibrated per league
HOME_ADVANTAGE = {
    'psl':        0.38,
    'nfd':        0.35,
    'npfl':       0.42,   # Nigerian home support very strong
    'botola':     0.40,
    'egypt_pl':   0.32,
    'kpl':        0.45,   # Altitude + crowd
    'caf_cl':     0.35,
    'caf_cc':     0.33,
    'chan':        0.36,
    'afcon_qual': 0.38,
    'default':    0.36,
}

# Average goals per game per league (both teams combined)
LEAGUE_AVG_GOALS = {
    'psl':        2.45,
    'nfd':        2.30,
    'npfl':       2.20,
    'botola':     2.35,
    'egypt_pl':   2.55,
    'kpl':        2.10,
    'caf_cl':     2.40,
    'caf_cc':     2.35,
    'chan':        2.25,
    'afcon_qual': 2.25,
    'default':    2.35,
}


@lru_cache(maxsize=1024)
def _poisson(lam: float, k: int) -> float:
    if lam <= 0: return 1.0 if k == 0 else 0.0
    return math.exp(-lam) * (lam ** k) / math.factorial(k)


def _score_matrix(hl: float, al: float, mx: int = 8) -> list[list[float]]:
    return [[_poisson(hl, h) * _poisson(al, a)
             for a in range(mx + 1)] for h in range(mx + 1)]


def outcome_probs(hl: float, al: float) -> dict:
    m = _score_matrix(hl, al)
    n = len(m)
    hw = sum(m[h][a] for h in range(n) for a in range(h))
    aw = sum(m[h][a] for h in range(n) for a in range(h + 1, n))
    d  = sum(m[h][h] for h in range(n))
    t  = hw + d + aw or 1.0
    return {'home_win': hw/t, 'draw': d/t, 'away_win': aw/t}


def over_under(hl: float, al: float, line: float = 2.5) -> dict:
    m = _score_matrix(hl, al, mx=10)
    n = len(m)
    ov = sum(m[h][a] for h in range(n) for a in range(n) if h + a > line)
    return {'over': ov, 'under': 1.0 - ov, 'line': line}


def btts(hl: float, al: float) -> dict:
    p0h = _poisson(hl, 0)
    p0a = _poisson(al, 0)
    yes = 1.0 - p0h - p0a + p0h * p0a
    return {'yes': max(0.0, yes), 'no': 1.0 - max(0.0, yes)}


class PoissonModel:

    def predict(self, home_attack: float, home_defence: float,
                away_attack: float, away_defence: float,
                league: str = 'default', avg_goals: float = None) -> dict:
        """
        Predict match probabilities from attack/defence ratings.

        Ratings are normalised: 1.0 = league average.
        """
        adv = HOME_ADVANTAGE.get(league, HOME_ADVANTAGE['default'])
        avg = avg_goals or LEAGUE_AVG_GOALS.get(league, LEAGUE_AVG_GOALS['default'])
        half = avg / 2

        home_xg = max(0.1, min(home_attack * away_defence * half * (1 + adv / avg), 5.0))
        away_xg = max(0.1, min(away_attack * home_defence * half, 5.0))

        oc   = outcome_probs(home_xg, away_xg)
        ou25 = over_under(home_xg, away_xg, 2.5)
        ou15 = over_under(home_xg, away_xg, 1.5)
        ou35 = over_under(home_xg, away_xg, 3.5)
        bt   = btts(home_xg, away_xg)

        return {
            'home_xg':   round(home_xg, 3),
            'away_xg':   round(away_xg, 3),
            'total_xg':  round(home_xg + away_xg, 3),
            'home_win':  round(oc['home_win'],  4),
            'draw':      round(oc['draw'],       4),
            'away_win':  round(oc['away_win'],  4),
            'over_1_5':  round(ou15['over'],    4),
            'over_2_5':  round(ou25['over'],    4),
            'under_2_5': round(ou25['under'],   4),
            'over_3_5':  round(ou35['over'],    4),
            'btts_yes':  round(bt['yes'],        4),
            'btts_no':   round(bt['no'],         4),
        }

    def predict_from_form(self, home_form: list[dict], away_form: list[dict],
                           league: str = 'default') -> dict:
        """
        Estimate from recent form. Each entry: {'scored': float, 'conceded': float}.
        """
        avg = LEAGUE_AVG_GOALS.get(league, LEAGUE_AVG_GOALS['default']) / 2
        def _avg(lst, key):
            return sum(g[key] for g in lst) / len(lst) if lst else avg

        ha = _avg(home_form, 'scored')   / avg
        hd = _avg(home_form, 'conceded') / avg
        aa = _avg(away_form, 'scored')   / avg
        ad = _avg(away_form, 'conceded') / avg
        return self.predict(ha, hd, aa, ad, league)


if __name__ == '__main__':
    m = PoissonModel()
    r = m.predict(1.45, 0.70, 1.20, 0.90, 'psl')
    print('Mamelodi Sundowns vs Orlando Pirates')
    print(f"  xG: {r['home_xg']} – {r['away_xg']}")
    print(f"  1X2: {r['home_win']:.1%} / {r['draw']:.1%} / {r['away_win']:.1%}")
    print(f"  Over 2.5: {r['over_2_5']:.1%}  BTTS: {r['btts_yes']:.1%}")
