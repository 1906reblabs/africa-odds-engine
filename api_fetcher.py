"""
data_sources/api_fetcher.py
============================
Three-source data aggregator with automatic fallback:
  1. The Odds API   — live odds from 5 bookmakers
  2. API-Football   — fixtures, form, xG, lineups (RapidAPI)
  3. football-data.org — official results and standings

Falls back automatically if any source fails.
"""

import json
import logging
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
import config as cfg

logger = logging.getLogger('abin.fetcher')

# ── HTTP CLIENT (lazy import to avoid hard dependency in tests) ────────────────

def _get(url: str, params: dict = None, headers: dict = None,
         retries: int = 3) -> Optional[dict]:
    """Simple HTTP GET with retry. Returns parsed JSON or None."""
    try:
        import httpx
    except ImportError:
        logger.error('httpx not installed — run: pip install httpx')
        return None

    last_err = None
    for attempt in range(1, retries + 1):
        try:
            with httpx.Client(timeout=cfg.API_TIMEOUT, follow_redirects=True) as client:
                r = client.get(url, params=params or {}, headers=headers or {})
                if r.status_code == 429:
                    wait = int(r.headers.get('Retry-After', 60))
                    logger.warning(f'Rate limited — waiting {wait}s')
                    time.sleep(wait)
                    continue
                if r.status_code in (404, 422):
                    logger.debug(f'Resource not found: {url}')
                    return None
                r.raise_for_status()
                return r.json()
        except Exception as e:
            last_err = e
            if attempt < retries:
                time.sleep(2 ** attempt)
    logger.error(f'GET failed after {retries} attempts: {last_err}  url={url}')
    return None


# ── THE ODDS API ──────────────────────────────────────────────────────────────

class OddsAPIClient:
    BASE = 'https://api.the-odds-api.com/v4'

    def __init__(self, api_key: str = ''):
        self.api_key = api_key or cfg.THE_ODDS_API_KEY
        self._remaining = '?'

    def fetch_odds(self, sport_key: str, regions: str = 'uk,eu',
                   markets: str = 'h2h,totals') -> list[dict]:
        if not self.api_key:
            logger.warning('No Odds API key — skipping')
            return []
        import httpx
        try:
            import httpx
            with httpx.Client(timeout=cfg.API_TIMEOUT) as client:
                r = client.get(f'{self.BASE}/sports/{sport_key}/odds', params={
                    'apiKey': self.api_key, 'regions': regions,
                    'markets': markets, 'oddsFormat': 'decimal', 'dateFormat': 'iso',
                })
                self._remaining = r.headers.get('x-requests-remaining', '?')
                if r.status_code in (404, 422):
                    return []
                r.raise_for_status()
                return r.json()
        except Exception as e:
            logger.warning(f'Odds API error ({sport_key}): {e}')
            return []


# ── API-FOOTBALL (RAPIDAPI) ───────────────────────────────────────────────────

class APIFootballClient:
    BASE = 'https://api-football-v1.p.rapidapi.com/v3'

    def __init__(self, api_key: str = ''):
        key = api_key or cfg.RAPID_API_KEY
        self._headers = {
            'x-rapidapi-host': 'api-football-v1.p.rapidapi.com',
            'x-rapidapi-key':  key,
        } if key else {}
        self._enabled = bool(key)

    def get_fixtures(self, league_id: int, season: int, next_n: int = 20) -> list[dict]:
        if not self._enabled: return []
        data = _get(f'{self.BASE}/fixtures', {'league': league_id, 'season': season,
                                               'next': next_n, 'status': 'NS'},
                    self._headers)
        return (data or {}).get('response', [])

    def get_team_statistics(self, team_id: int, league_id: int, season: int) -> dict:
        if not self._enabled: return {}
        data = _get(f'{self.BASE}/teams/statistics',
                    {'team': team_id, 'league': league_id, 'season': season},
                    self._headers)
        return (data or {}).get('response', {})

    def get_standings(self, league_id: int, season: int) -> list[dict]:
        if not self._enabled: return []
        data = _get(f'{self.BASE}/standings',
                    {'league': league_id, 'season': season}, self._headers)
        resp = (data or {}).get('response', [])
        if resp:
            return resp[0].get('league', {}).get('standings', [[]])[0]
        return []

    def get_head_to_head(self, team1: int, team2: int, last: int = 10) -> list[dict]:
        if not self._enabled: return []
        data = _get(f'{self.BASE}/fixtures/headtohead',
                    {'h2h': f'{team1}-{team2}', 'last': last}, self._headers)
        return (data or {}).get('response', [])


# ── FOOTBALL-DATA.ORG ─────────────────────────────────────────────────────────

class FootballDataClient:
    BASE = 'https://api.football-data.org/v4'

    def __init__(self, api_key: str = ''):
        key = api_key or cfg.FOOTBALL_DATA_API_KEY
        self._headers = {'X-Auth-Token': key} if key else {}
        self._enabled = bool(key)

    def get_matches(self, competition: str) -> list[dict]:
        if not self._enabled or not competition: return []
        today = datetime.now(timezone.utc)
        data = _get(f'{self.BASE}/competitions/{competition}/matches',
                    {'dateFrom': today.strftime('%Y-%m-%d'),
                     'dateTo': (today + timedelta(days=7)).strftime('%Y-%m-%d'),
                     'status': 'SCHEDULED'},
                    self._headers)
        return (data or {}).get('matches', [])


# ── UNIFIED DATA AGGREGATOR ───────────────────────────────────────────────────

class DataAggregator:
    """Combines all three sources. Falls back silently if any source fails."""

    def __init__(self):
        self.odds = OddsAPIClient()
        self.af   = APIFootballClient()
        self.fd   = FootballDataClient()

    def fetch_league(self, league_key: str) -> dict:
        lcfg = cfg.LEAGUE_CONFIGS.get(league_key, {})
        if not lcfg:
            return {'league': league_key, 'fixtures': [], 'odds_events': []}

        logger.info(f'  → {lcfg["name"]}')

        fixtures    = []
        odds_events = []
        standings   = []

        if lcfg.get('af_league_id') and cfg.RAPID_API_KEY:
            fixtures  = self.af.get_fixtures(lcfg['af_league_id'], lcfg.get('af_season', 2024))
            standings = self.af.get_standings(lcfg['af_league_id'], lcfg.get('af_season', 2024))

        if lcfg.get('fd_competition') and cfg.FOOTBALL_DATA_API_KEY and not fixtures:
            # Fallback to football-data.org if API-Football failed or returned nothing
            matches   = self.fd.get_matches(lcfg['fd_competition'])
            fixtures  = matches  # different schema but engine handles both

        if lcfg.get('odds_sport_key') and cfg.THE_ODDS_API_KEY:
            odds_events = self.odds.fetch_odds(
                lcfg['odds_sport_key'], lcfg.get('odds_regions', 'uk,eu'))

        return {
            'league':      league_key,
            'league_name': lcfg['name'],
            'country':     lcfg['country'],
            'fixtures':    fixtures,
            'odds_events': odds_events,
            'standings':   standings,
            'edge_notes':  lcfg.get('edge_notes', ''),
            'fetched_at':  datetime.now(timezone.utc).isoformat(),
        }

    def fetch_all_active(self) -> list[dict]:
        active = cfg.get_active_leagues()
        logger.info(f'Fetching {len(active)} active leagues: {active}')
        results = []
        for key in active:
            try:
                data = self.fetch_league(key)
                results.append(data)
                time.sleep(0.4)
            except Exception as e:
                logger.error(f'Failed fetching {key}: {e}')
        return results


def save_raw_data(data: list[dict], filename: str = 'raw_data.json') -> Path:
    path = cfg.DATA_DIR / filename
    path.write_text(json.dumps(data, indent=2, default=str))
    return path

def load_raw_data(filename: str = 'raw_data.json') -> list[dict]:
    path = cfg.DATA_DIR / filename
    return json.loads(path.read_text()) if path.exists() else []


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s [%(levelname)s] %(message)s')
    agg  = DataAggregator()
    data = agg.fetch_all_active()
    save_raw_data(data)
    print(f'✓ {sum(len(d["odds_events"]) for d in data)} odds events across '
          f'{len(data)} leagues')
