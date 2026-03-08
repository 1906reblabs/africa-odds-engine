"""
tests/test_engine.py
=====================
35-test offline suite. No API keys required.
"""

import json
import sys
import types
import uuid
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# ── Mock httpx before any import that needs it ───────────────────────────────
if 'httpx' not in sys.modules:
    _mock = types.ModuleType('httpx')
    class _FakeClient:
        def __enter__(self): return self
        def __exit__(self, *a): pass
    _mock.Client = _FakeClient
    _mock.RequestError = Exception
    sys.modules['httpx'] = _mock


class TestPoissonModel(unittest.TestCase):

    def setUp(self):
        from models.poisson_model import PoissonModel
        self.m = PoissonModel()

    def test_1x2_sums_to_one(self):
        r = self.m.predict(1.2, 1.0, 1.1, 1.0, 'psl')
        self.assertAlmostEqual(r['home_win'] + r['draw'] + r['away_win'], 1.0, places=3)

    def test_ou_sums_to_one(self):
        r = self.m.predict(1.2, 1.0, 1.1, 1.0, 'psl')
        self.assertAlmostEqual(r['over_2_5'] + r['under_2_5'], 1.0, places=3)

    def test_btts_sums_to_one(self):
        r = self.m.predict(1.2, 1.0, 1.1, 1.0, 'psl')
        self.assertAlmostEqual(r['btts_yes'] + r['btts_no'], 1.0, places=3)

    def test_btts_bounds(self):
        r = self.m.predict(1.5, 0.8, 1.2, 0.9, 'psl')
        self.assertGreaterEqual(r['btts_yes'], 0.0)
        self.assertLessEqual(r['btts_yes'], 1.0)

    def test_strong_home_wins_more(self):
        strong = self.m.predict(1.8, 0.7, 0.8, 1.4, 'psl')
        weak   = self.m.predict(0.8, 1.4, 1.8, 0.7, 'psl')
        self.assertGreater(strong['home_win'], weak['home_win'])

    def test_high_attack_more_goals(self):
        hi = self.m.predict(1.8, 1.0, 1.7, 1.0, 'psl')
        lo = self.m.predict(0.7, 1.0, 0.7, 1.0, 'psl')
        self.assertGreater(hi['over_2_5'], lo['over_2_5'])

    def test_xg_in_range(self):
        r = self.m.predict(1.2, 1.0, 1.1, 1.0, 'psl')
        self.assertGreater(r['home_xg'], 0.0)
        self.assertLess(r['home_xg'], 5.0)

    def test_all_leagues(self):
        import config as cfg
        for lg in cfg.LEAGUE_CONFIGS:
            r = self.m.predict(1.2, 1.0, 1.1, 1.0, lg)
            t = r['home_win'] + r['draw'] + r['away_win']
            self.assertAlmostEqual(t, 1.0, places=2, msg=f'{lg} probs must sum to 1')

    def test_predict_from_form(self):
        hf = [{'scored': 2, 'conceded': 0}] * 5
        af = [{'scored': 1, 'conceded': 2}] * 5
        r  = self.m.predict_from_form(hf, af, 'psl')
        self.assertIn('home_win', r)
        self.assertGreater(r['home_win'], r['away_win'])

    def test_over_15_greater_than_over_25(self):
        r = self.m.predict(1.2, 1.0, 1.1, 1.0, 'psl')
        self.assertGreater(r['over_1_5'], r['over_2_5'])

    def test_over_25_greater_than_over_35(self):
        r = self.m.predict(1.2, 1.0, 1.1, 1.0, 'psl')
        self.assertGreater(r['over_2_5'], r['over_3_5'])


class TestValueDetector(unittest.TestCase):

    def setUp(self):
        from models.value_detector import ValueDetector
        self.d = ValueDetector()

    def _bm(self, odds, mkt='h2h', oc='Home'):
        return [
            {'key': 'betway',  'markets': [{'key': mkt, 'outcomes': [{'name': oc, 'price': odds}]}]},
            {'key': 'bet365',  'markets': [{'key': mkt, 'outcomes': [{'name': oc, 'price': round(odds - 0.05, 2)}]}]},
        ]

    def test_positive_edge_scores_above_50(self):
        r = self.d.score(0.45, 3.00, self._bm(3.00), 'h2h', 'Home', data_completeness=0.9)
        self.assertGreater(r['edge'], 0)
        self.assertGreater(r['total'], 50)

    def test_negative_edge(self):
        r = self.d.score(0.30, 1.50, self._bm(1.50), 'h2h', 'Home', data_completeness=0.9)
        self.assertLess(r['edge'], 0)

    def test_total_in_range(self):
        r = self.d.score(0.50, 2.00, self._bm(2.00), 'h2h', 'Home')
        self.assertGreaterEqual(r['total'], 0)
        self.assertLessEqual(r['total'], 100)

    def test_components_within_max(self):
        import config as cfg
        r = self.d.score(0.50, 2.50, self._bm(2.50), 'h2h', 'Home')
        for k, v in r['components'].items():
            self.assertLessEqual(v, cfg.RUBRIC_WEIGHTS.get(k, 100),
                                 msg=f'Component {k} exceeds max')

    def test_kelly_positive_iff_edge_positive(self):
        from models.value_detector import kelly_fraction
        self.assertGreater(kelly_fraction(0.20, 2.50), 0)
        self.assertEqual(kelly_fraction(-0.05, 2.50), 0.0)

    def test_edge_formula(self):
        from models.value_detector import calculate_edge
        self.assertAlmostEqual(calculate_edge(0.50, 2.20), 0.10, places=4)

    def test_remove_margin(self):
        from models.value_detector import remove_margin
        fair = remove_margin([0.5, 0.3, 0.3])
        self.assertAlmostEqual(sum(fair), 1.0, places=5)

    def test_drift_shortened(self):
        from models.value_detector import detect_drift
        d = detect_drift(2.50, 2.10)
        self.assertEqual(d['direction'], 'shortened')
        self.assertTrue(d['is_strong'])

    def test_drift_stable(self):
        from models.value_detector import detect_drift
        d = detect_drift(2.00, 2.00)
        self.assertEqual(d['direction'], 'stable')
        self.assertFalse(d['is_significant'])

    def test_drift_drifted(self):
        from models.value_detector import detect_drift
        d = detect_drift(2.00, 2.30)
        self.assertEqual(d['direction'], 'drifted')

    def test_open_odds_drift_improves_score(self):
        bms = self._bm(2.90)
        # Signal strengthens when odds shortened (sharp money in)
        with_drift    = self.d.score(0.42, 2.90, bms, 'h2h', 'Home', open_odds=3.30)
        without_drift = self.d.score(0.42, 2.90, bms, 'h2h', 'Home', open_odds=None)
        self.assertGreaterEqual(with_drift['total'], without_drift['total'])


class TestSignalEngine(unittest.TestCase):

    def setUp(self):
        from engine.signal_engine import SignalEngine, _demo_event
        self.engine = SignalEngine()
        self.demo   = _demo_event

    def test_returns_list(self):
        e = self.demo('A', 'B', 'psl')
        self.assertIsInstance(self.engine.process_event(e, 'psl', 'PSL'), list)

    def test_required_fields(self):
        e = self.demo('Al Ahly', 'Zamalek', 'egypt_pl', 1.90, 3.40, 4.20, 2.20, 1.70)
        sigs = self.engine.process_event(e, 'egypt_pl', 'Egyptian PL')
        required = ['id', 'league', 'home_team', 'away_team', 'market',
                    'outcome', 'odds', 'confidence', 'status', 'created_utc']
        for s in sigs:
            for f in required:
                self.assertIn(f, s, f'Signal missing: {f}')

    def test_confidence_in_range(self):
        e = self.demo('Wydad', 'Raja', 'botola')
        for s in self.engine.process_event(e, 'botola', 'Botola Pro'):
            self.assertGreaterEqual(s['confidence'], 0)
            self.assertLessEqual(s['confidence'], 100)

    def test_above_hard_reject(self):
        import config as cfg
        e = self.demo('Mazembe', 'Petro', 'caf_cl', 2.30, 3.10, 3.20, 2.15, 1.72)
        for s in self.engine.process_event(e, 'caf_cl', 'CAF CL'):
            self.assertGreaterEqual(s['confidence'], cfg.HARD_REJECT_BELOW)

    def test_status_pending(self):
        e = self.demo('Chiefs', 'SuperSport', 'psl')
        for s in self.engine.process_event(e, 'psl', 'PSL'):
            self.assertEqual(s['status'], 'pending')

    def test_seven_league_smoke(self):
        fixtures = [
            ('Sundowns',  'Pirates',     'psl',      1.75, 3.50, 5.00, 1.95, 1.85),
            ('Al Ahly',   'Zamalek',     'egypt_pl', 1.90, 3.40, 4.20, 2.20, 1.70),
            ('Wydad',     'Raja',        'botola',   2.00, 3.20, 3.80, 2.05, 1.80),
            ('Mazembe',   'Petro',       'caf_cl',   2.30, 3.10, 3.20, 2.15, 1.72),
            ('Enyimba',   'Rivers Utd',  'npfl',     2.40, 3.00, 2.90, 2.00, 1.78),
            ('Gor Mahia', 'AFC Leopards','kpl',      2.10, 3.25, 3.60, 2.12, 1.76),
            ('WAC',       'Al Ahly',     'caf_cc',   2.50, 3.10, 2.90, 2.10, 1.75),
        ]
        import config as cfg
        total = 0
        for home, away, lg, ho, dr, ao, ov, un in fixtures:
            e  = self.demo(home, away, lg, ho, dr, ao, ov, un)
            ln = cfg.LEAGUE_CONFIGS.get(lg, {}).get('name', lg)
            total += len(self.engine.process_event(e, lg, ln))
        self.assertGreater(total, 0)


class TestConfig(unittest.TestCase):

    def test_active_leagues_list(self):
        import config as cfg
        self.assertIsInstance(cfg.get_active_leagues(), list)

    def test_league_required_keys(self):
        import config as cfg
        for key, lc in cfg.LEAGUE_CONFIGS.items():
            for f in ['name', 'country', 'tier', 'active', 'priority', 'af_league_id']:
                self.assertIn(f, lc, f'{key} missing {f}')

    def test_bookmaker_required_keys(self):
        import config as cfg
        for bm in cfg.BOOKMAKERS:
            for f in ['key', 'name', 'type', 'weight']:
                self.assertIn(f, bm)

    def test_rubric_weights_sum_100(self):
        import config as cfg
        self.assertEqual(sum(cfg.RUBRIC_WEIGHTS.values()), 100)

    def test_admin_exempt(self):
        import config as cfg
        self.assertTrue(cfg.admin_exempt_from_billing())

    def test_is_admin_request(self):
        import config as cfg
        self.assertTrue(cfg.is_admin_request(cfg.ADMIN_USER, cfg.ADMIN_PASS))
        self.assertFalse(cfg.is_admin_request('admin', 'wrongpass'))

    def test_signal_caps_sane(self):
        import config as cfg
        self.assertGreater(cfg.SIGNALS_PER_CYCLE, 0)
        self.assertGreater(cfg.WEEKLY_SIGNAL_CAP, 0)
        self.assertLess(cfg.HARD_REJECT_BELOW, cfg.CONFIDENCE_THRESHOLD)

    def test_validate_returns_list(self):
        import config as cfg
        self.assertIsInstance(cfg.validate_config(), list)

    def test_sharp_books(self):
        import config as cfg
        sharp = cfg.get_sharp_books()
        self.assertIsInstance(sharp, list)
        self.assertGreater(len(sharp), 0)

    def test_retail_books(self):
        import config as cfg
        retail = cfg.get_retail_books()
        self.assertIn('betway', retail)


class TestFormatters(unittest.TestCase):

    def _sig(self):
        return {
            'id': 'test123', 'league': 'psl',
            'league_name': 'PSL — Premier Soccer League',
            'home_team': 'Mamelodi Sundowns', 'away_team': 'Orlando Pirates',
            'kick_off': '19:30 SAST, 15 Mar 2025',
            'market': 'Goals Over 2.5', 'outcome': 'Over 2.5',
            'odds': 2.10, 'confidence': 78, 'edge': '12.5%',
            'kelly': 0.045, 'recommendation': '✅ BUY',
            'model_insight': 'Model projects 1.65–1.22 xG.',
            'status': 'pending', 'result': None, 'poisson': {}, 'components': {},
        }

    def test_format_signal_is_string(self):
        from telegram.bot_sender import format_signal
        self.assertIsInstance(format_signal(self._sig()), str)

    def test_format_signal_contains_teams(self):
        from telegram.bot_sender import format_signal
        t = format_signal(self._sig())
        self.assertIn('Mamelodi Sundowns', t)
        self.assertIn('Orlando Pirates', t)

    def test_format_signal_contains_odds(self):
        from telegram.bot_sender import format_signal
        t = format_signal(self._sig())
        self.assertIn('2.1', t)

    def test_format_admin_preview(self):
        from telegram.bot_sender import format_admin_preview
        t = format_admin_preview(self._sig())
        self.assertIn('PENDING REVIEW', t)
        self.assertIn('test123', t)

    def test_format_error_alert(self):
        from telegram.bot_sender import format_error_alert
        t = format_error_alert('ingestion', 'timeout')
        self.assertIn('SYSTEM ERROR', t)
        self.assertIn('ingestion', t)


# ── RUNNER ────────────────────────────────────────────────────────────────────

def run_all():
    loader = unittest.TestLoader()
    suite  = unittest.TestSuite()
    for cls in [TestPoissonModel, TestValueDetector, TestSignalEngine,
                TestConfig, TestFormatters]:
        suite.addTests(loader.loadTestsFromTestCase(cls))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print('\n' + '═' * 58)
    print(f'Tests run: {result.testsRun}  |  Failures: {len(result.failures)}'
          f'  |  Errors: {len(result.errors)}')
    print(f'Status: {"✓ ALL PASSED" if result.wasSuccessful() else "✗ FAILURES FOUND"}')
    print('═' * 58)
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(run_all())
