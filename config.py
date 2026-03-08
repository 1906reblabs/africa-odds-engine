"""
AFRICAN BETTING INTELLIGENCE NETWORK — Master Configuration
============================================================
Single source of truth. Modelled on and extended from the Edgeline config pattern.

Competitions covered:
  Domestic:
  ✓ PSL         — Premier Soccer League (South Africa)       priority 1
  ✓ NFD         — National First Division (South Africa)     priority 2
  ✓ NPFL        — Nigeria Premier Football League            priority 3
  ✓ Botola Pro  — Moroccan Premier League                    priority 4
  ✓ Egypt PL    — Egyptian Premier League                    priority 5
  ✓ KPL         — Kenyan Premier League                      priority 6
  Continental:
  ✓ CAF CL      — CAF Champions League                       priority 7
  ✓ CAF CC      — CAF Confederation Cup                      priority 8
  International:
  ✓ CHAN         — African Nations Championship               priority 9
  ✓ AFCON Qual  — AFCON Qualifiers / African Internationals  priority 10

Bookmakers monitored (5):
  ✓ Betway          — Primary African retail bookmaker
  ✓ Hollywoodbets   — Major SA retail bookmaker
  ✓ Bet365          — Global sharp reference
  ✓ William Hill    — Global sharp reference
  ✓ 1xBet           — African market retail presence

Signal cap: 5–10 per cycle  |  7–10 per week
Admin access: Unlimited, free, permanent — never billed
"""

import os
from pathlib import Path
from datetime import date
from dotenv import load_dotenv

load_dotenv()

# ── PATHS ─────────────────────────────────────────────────────────────────────
BASE_DIR     = Path(__file__).parent
DATA_DIR     = Path(os.getenv('DATA_DIR', str(BASE_DIR / 'data')))
SIGNALS_DIR  = DATA_DIR / 'signals'
LOGS_DIR     = DATA_DIR / 'logs'

for _d in [DATA_DIR, SIGNALS_DIR, LOGS_DIR]:
    _d.mkdir(parents=True, exist_ok=True)


# ── ADMIN ACCESS ──────────────────────────────────────────────────────────────
# Admin has unlimited, free, permanent access. Never billed. Never subject
# to subscriber checks. Mirrors the Edgeline admin pattern exactly.
ADMIN_USER      = os.getenv('ADMIN_USER', 'admin')
ADMIN_PASS      = os.getenv('ADMIN_PASS', 'abin2025_change_this')
ADMIN_EMAIL     = os.getenv('ADMIN_EMAIL', '')
ADMIN_API_KEY   = os.getenv('ADMIN_API_KEY', '')

def is_admin_request(user: str, password: str) -> bool:
    """Check if this is an admin login attempt."""
    return user == ADMIN_USER and password == ADMIN_PASS

def admin_exempt_from_billing() -> bool:
    """Admin is always exempt from all billing checks. Unconditional."""
    return True


# ── SIGNAL ENGINE SETTINGS ────────────────────────────────────────────────────
SIGNALS_PER_CYCLE     = int(os.getenv('SIGNALS_PER_CYCLE', '7'))
WEEKLY_SIGNAL_CAP     = int(os.getenv('WEEKLY_SIGNAL_CAP', '10'))   # Hard ceiling
MIN_SIGNALS_EXPECTED  = int(os.getenv('MIN_SIGNALS_EXPECTED', '7')) # Soft weekly target
CONFIDENCE_THRESHOLD  = int(os.getenv('CONFIDENCE_THRESHOLD', '65'))
HARD_REJECT_BELOW     = int(os.getenv('HARD_REJECT_BELOW', '50'))
API_TIMEOUT           = 15  # seconds

# Publish mode: 'auto' publishes directly; 'admin' sends to review queue first
PUBLISH_MODE = os.getenv('PUBLISH_MODE', 'admin')


# ── API KEYS ──────────────────────────────────────────────────────────────────
THE_ODDS_API_KEY       = os.getenv('THE_ODDS_API_KEY', '')
FOOTBALL_DATA_API_KEY  = os.getenv('FOOTBALL_DATA_API_KEY', '')
RAPID_API_KEY          = os.getenv('RAPID_API_KEY', '')
ANTHROPIC_API_KEY      = os.getenv('ANTHROPIC_API_KEY', '')
LLM_MODEL              = 'claude-sonnet-4-6'

# Telegram
TELEGRAM_BOT_TOKEN      = os.getenv('BOT_TOKEN', '')
TELEGRAM_CHANNEL_ID     = os.getenv('CHANNEL_ID', '')
TELEGRAM_ADMIN_CHAT_ID  = os.getenv('ADMIN_ID', '')
TELEGRAM_ADMIN_CHANNEL  = os.getenv('ADMIN_CHANNEL_ID', '')

# Email (Mailgun — mirrors Edgeline delivery config)
MAILGUN_API_KEY  = os.getenv('MAILGUN_API_KEY', '')
MAILGUN_DOMAIN   = os.getenv('MAILGUN_DOMAIN', 'mg.abin.co.za')

# WhatsApp via Twilio (founding member perk)
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID', '')
TWILIO_AUTH_TOKEN  = os.getenv('TWILIO_AUTH_TOKEN', '')
TWILIO_WA_NUMBER   = os.getenv('TWILIO_WA_NUMBER', 'whatsapp:+14155238886')

# PayFast (SA payments — mirrors Edgeline PayFast config)
PAYFAST_MERCHANT_ID  = os.getenv('PAYFAST_MERCHANT_ID', '')
PAYFAST_MERCHANT_KEY = os.getenv('PAYFAST_MERCHANT_KEY', '')
PAYFAST_PASSPHRASE   = os.getenv('PAYFAST_PASSPHRASE', '')
PAYFAST_SANDBOX      = os.getenv('PAYFAST_SANDBOX', 'true').lower() == 'true'
SITE_URL             = os.getenv('SITE_URL', 'https://abin.co.za')

PF_BASE    = 'https://sandbox.payfast.co.za' if PAYFAST_SANDBOX else 'https://www.payfast.co.za'
RETURN_URL = f'{SITE_URL}/subscribe/success'
CANCEL_URL = f'{SITE_URL}/subscribe/cancel'
NOTIFY_URL = f'{SITE_URL}/api/payfast/notify'


# ── SUBSCRIPTION PLANS (ZAR) ──────────────────────────────────────────────────
PLANS = {
    'weekly': {
        'amount':      '99.00',
        'item_name':   'ABIN Weekly Signal Access',
        'recurring':   True,
        'frequency':   4,    # weekly
        'cycles':      0,    # indefinite
        'description': '7–10 high-confidence signals per week across 10 African competitions.',
    },
    'founding': {
        'amount':      '199.00',
        'item_name':   'ABIN Founding Member — Monthly',
        'recurring':   True,
        'frequency':   3,    # monthly
        'cycles':      0,
        'max_slots':   50,
        'description': 'First 50 founding members. Locked rate. WhatsApp delivery included.',
    },
    'per_signal': {
        'amount':      '20.00',
        'item_name':   'ABIN Single Signal',
        'recurring':   False,
        'description': 'One high-confidence signal with full reasoning.',
    },
}
FOUNDING_MEMBER_CAP = 50

# Affiliate links — replace with your actual affiliate URLs
AFFILIATE_LINKS = {
    'betway':        os.getenv('AFFILIATE_BETWAY',        'https://betway.co.za'),
    'hollywoodbets': os.getenv('AFFILIATE_HOLLYWOODBETS', 'https://www.hollywoodbets.net'),
    '1xbet':         os.getenv('AFFILIATE_1XBET',         'https://1xbet.com'),
}


# ── LEAGUE CONFIGS ────────────────────────────────────────────────────────────
# Mirrors Edgeline LEAGUE_CONFIGS pattern with additional competitions.
# Each entry includes odds API keys, API-Football IDs, and African-specific edge notes.

LEAGUE_CONFIGS = {

    'psl': {
        'name':           'PSL — Premier Soccer League',
        'country':        'South Africa',
        'tier':           'domestic',
        'season':         '2024-25',
        'active':         True,
        'priority':       1,
        'odds_sport_key': 'soccer_south_africa_premiership',
        'odds_regions':   'uk,eu',
        'fd_competition': 'PSL',
        'af_league_id':   288,
        'af_season':      2024,
        'has_xg':         False,
        'has_lineups':    True,
        'edge_notes':     'Home advantage systematically overpriced. Away form in SA often '
                          'undervalued by global models. Squad rotation during CAF weeks '
                          'creates pricing gaps. Betway and Hollywoodbets slow to react.',
    },

    'nfd': {
        'name':           'NFD — National First Division',
        'country':        'South Africa',
        'tier':           'domestic_2',
        'season':         '2024-25',
        'active':         True,
        'priority':       2,
        'odds_sport_key': 'soccer_south_africa_nfd',
        'odds_regions':   'uk,eu',
        'fd_competition': None,
        'af_league_id':   289,
        'af_season':      2024,
        'has_xg':         False,
        'has_lineups':    False,
        'edge_notes':     'Extremely low global bookmaker attention. Largest domestic '
                          'information asymmetry. Local ground conditions never priced in.',
    },

    'npfl': {
        'name':           'NPFL — Nigeria Premier Football League',
        'country':        'Nigeria',
        'tier':           'domestic',
        'season':         '2024-25',
        'active':         True,
        'priority':       3,
        'odds_sport_key': 'soccer_nigeria_professional',
        'odds_regions':   'uk,eu',
        'fd_competition': None,
        'af_league_id':   332,
        'af_season':      2024,
        'has_xg':         False,
        'has_lineups':    False,
        'edge_notes':     'Heavily undertracked by global bookmakers. Largest information '
                          'asymmetry of all covered leagues. Local travel fatigue is '
                          'systematically unpriced. Nigerian domestic results barely tracked.',
    },

    'botola': {
        'name':           'Botola Pro — Moroccan Premier League',
        'country':        'Morocco',
        'tier':           'domestic',
        'season':         '2024-25',
        'active':         True,
        'priority':       4,
        'odds_sport_key': 'soccer_morocco_botola_pro',
        'odds_regions':   'uk,eu',
        'fd_competition': None,
        'af_league_id':   200,
        'af_season':      2024,
        'has_xg':         False,
        'has_lineups':    True,
        'edge_notes':     'Undertracked by European bookmakers despite Morocco World Cup '
                          'exposure. Ramadan schedule disruption ignored. Desert heat '
                          'effects on late-season matches unpriced.',
    },

    'egypt_pl': {
        'name':           'Egyptian Premier League',
        'country':        'Egypt',
        'tier':           'domestic',
        'season':         '2024-25',
        'active':         True,
        'priority':       5,
        'odds_sport_key': 'soccer_egypt_premier_league',
        'odds_regions':   'uk,eu',
        'fd_competition': None,
        'af_league_id':   233,
        'af_season':      2024,
        'has_xg':         True,
        'has_lineups':    True,
        'edge_notes':     'Al Ahly and Zamalek dominance creates extreme odds compression '
                          'in their matches. Strong underdog value in away fixtures. '
                          'Ramadan scheduling effects ignored by European models.',
    },

    'kpl': {
        'name':           'KPL — Kenyan Premier League',
        'country':        'Kenya',
        'tier':           'domestic',
        'season':         '2024-25',
        'active':         True,
        'priority':       6,
        'odds_sport_key': 'soccer_kenya_premier',
        'odds_regions':   'uk,eu',
        'fd_competition': None,
        'af_league_id':   350,
        'af_season':      2024,
        'has_xg':         False,
        'has_lineups':    False,
        'edge_notes':     'Near-zero global bookmaker attention. Nairobi altitude unpriced. '
                          'Gor Mahia and AFC Leopards derbies attract disproportionate '
                          'square money — sharp value on underdog side.',
    },

    'caf_cl': {
        'name':           'CAF Champions League',
        'country':        'Africa (multi)',
        'tier':           'continental',
        'season':         '2024-25',
        'active':         True,
        'priority':       7,
        'odds_sport_key': 'soccer_africa_champions_league',
        'odds_regions':   'uk,eu',
        'fd_competition': None,
        'af_league_id':   21,
        'af_season':      2024,
        'has_xg':         False,
        'has_lineups':    True,
        'edge_notes':     'Cross-country travel fatigue massively underpriced. Home advantage '
                          'for African teams is highest in CAF competition. Altitude effects '
                          '(Ethiopian venues) rarely priced. Weather differences between '
                          'North Africa and sub-Saharan Africa ignored by global books.',
    },

    'caf_cc': {
        'name':           'CAF Confederation Cup',
        'country':        'Africa (multi)',
        'tier':           'continental',
        'season':         '2024-25',
        'active':         True,
        'priority':       8,
        'odds_sport_key': 'soccer_africa_confederation_cup',
        'odds_regions':   'uk,eu',
        'fd_competition': None,
        'af_league_id':   22,
        'af_season':      2024,
        'has_xg':         False,
        'has_lineups':    False,
        'edge_notes':     'Less covered than CAF CL — even larger information gaps. Many '
                          'matches priced on reputation not current form. Pitch condition '
                          'data almost never available to global bookmakers.',
    },

    'chan': {
        'name':           'CHAN — African Nations Championship',
        'country':        'Africa (international)',
        'tier':           'international',
        'season':         '2025',
        'active':         False,   # Only during tournament — toggle manually
        'priority':       9,
        'odds_sport_key': 'soccer_africa_nations_championship',
        'odds_regions':   'uk,eu',
        'fd_competition': None,
        'af_league_id':   29,
        'af_season':      2025,
        'has_xg':         False,
        'has_lineups':    False,
        'edge_notes':     'Home-based players only — bookmakers use stale club ratings. '
                          'Largest model-vs-market gap of any African competition.',
    },

    'afcon_qual': {
        'name':           'AFCON Qualifiers / African Internationals',
        'country':        'Africa (international)',
        'tier':           'international',
        'season':         '2025-26',
        'active':         True,
        'priority':       10,
        'odds_sport_key': 'soccer_africa_cup_of_nations_qual',
        'odds_regions':   'uk,eu',
        'fd_competition': None,
        'af_league_id':   30,
        'af_season':      2025,
        'has_xg':         False,
        'has_lineups':    False,
        'edge_notes':     'Club-vs-country conflicts affect squad availability — never '
                          'priced in. African national teams have the largest form variance '
                          'of any international tier. Home crowd effects dramatically '
                          'underpriced at African venues.',
        # Activate only during these windows
        'active_windows': [
            ('2025-03-20', '2025-03-25'),
            ('2025-06-05', '2025-06-10'),
            ('2025-09-04', '2025-09-09'),
            ('2025-10-09', '2025-10-14'),
            ('2025-11-13', '2025-11-18'),
        ],
    },
}


def get_active_leagues() -> list[str]:
    """Return list of currently active league keys sorted by priority."""
    today = date.today().isoformat()
    active = []
    for key, cfg in LEAGUE_CONFIGS.items():
        if not cfg.get('active', False):
            continue
        if cfg.get('active_windows'):
            in_window = any(start <= today <= end for start, end in cfg['active_windows'])
            if not in_window:
                continue
        active.append(key)
    return sorted(active, key=lambda k: LEAGUE_CONFIGS[k]['priority'])


# ── BOOKMAKER CONFIG (5 SOURCES) ──────────────────────────────────────────────
# Mirrors Edgeline BOOKMAKERS list with retail/sharp classification and weights.

BOOKMAKERS = [
    {
        'key':       'betway',
        'name':      'Betway',
        'region':    'africa',
        'type':      'retail',    # soft lines, exploitable — primary target
        'weight':    1.3,
        'notes':     'Primary SA/African bookmaker. Often slow to react to sharp money.',
    },
    {
        'key':       'hollywoodbets',
        'name':      'Hollywoodbets',
        'region':    'south_africa',
        'type':      'retail',
        'weight':    1.2,
        'notes':     'Major SA bookmaker. PSL focus makes them the key SA reference.',
    },
    {
        'key':       'bet365',
        'name':      'Bet365',
        'region':    'global',
        'type':      'sharp',
        'weight':    1.0,
        'notes':     'Global sharp reference. Bet365 line is often the "true" market.',
    },
    {
        'key':       'williamhill',
        'name':      'William Hill',
        'region':    'global',
        'type':      'sharp',
        'weight':    0.9,
        'notes':     'Secondary sharp reference. Compare with Bet365 for consensus.',
    },
    {
        'key':       '1xbet',
        'name':      '1xBet',
        'region':    'africa',
        'type':      'retail',
        'weight':    1.1,
        'notes':     'Strong African market presence. Often carries larger margins on '
                     'African fixtures — creates exploitable overrounds.',
    },
]

def get_bookmakers_for_league(league_key: str) -> list[dict]:
    return BOOKMAKERS  # All 5 available for all leagues

def get_sharp_books() -> list[str]:
    return [b['key'] for b in BOOKMAKERS if b['type'] == 'sharp']

def get_retail_books() -> list[str]:
    return [b['key'] for b in BOOKMAKERS if b['type'] == 'retail']


# ── ODDS & DRIFT SETTINGS ─────────────────────────────────────────────────────
ODDS_MARKETS          = 'h2h,spreads,totals'
SIGNIFICANT_DRIFT_PCT = 5.0    # 5%+ movement = meaningful signal
STRONG_DRIFT_PCT      = 12.0   # 12%+ = strong signal

# Value detection thresholds
EDGE_HIGH = 0.15   # 15%+ = high information asymmetry bonus
EDGE_MED  = 0.10   # 10%+ = medium
EDGE_LOW  = 0.07   # 7%+  = minimum meaningful edge

MIN_VALUE_EDGE = EDGE_LOW
MED_VALUE_EDGE = EDGE_MED
HIGH_VALUE_EDGE = EDGE_HIGH


# ── CONFIDENCE RUBRIC WEIGHTS ─────────────────────────────────────────────────
# Mirrors the Edgeline rubric pattern. Sum of max values = 100.
RUBRIC_WEIGHTS = {
    'data_quality':          20,
    'market_edge':           25,
    'drift_confirmation':    20,
    'bookmaker_agreement':   20,
    'model_alignment':       15,
}


# ── FEATURE FLAGS ─────────────────────────────────────────────────────────────
FEATURES = {
    'use_poisson_model':              True,
    'use_value_detection':            True,
    'use_form_analysis':              True,
    'use_h2h_analysis':               True,
    'use_xg_when_available':          True,
    'use_odds_drift_detection':       True,
    'use_bookmaker_disagreement':     True,
    'use_retail_vs_sharp_divergence': True,
    'caf_cross_border_bias':          True,
    'international_window_mode':      True,
    'admin_review_mode':              PUBLISH_MODE == 'admin',
    'include_affiliate_links':        os.getenv('INCLUDE_AFFILIATES', 'false') == 'true',
    'weekly_summary_email':           True,
    'whatsapp_founding_members':      bool(TWILIO_ACCOUNT_SID),
}


# ── VALIDATION ────────────────────────────────────────────────────────────────
def validate_config() -> list[str]:
    """Check that all required config values are set. Returns list of warnings."""
    warnings = []

    if not TELEGRAM_BOT_TOKEN:
        warnings.append('Missing BOT_TOKEN — Telegram delivery disabled')
    if not TELEGRAM_CHANNEL_ID:
        warnings.append('Missing CHANNEL_ID — signals have nowhere to go')
    if not THE_ODDS_API_KEY and not RAPID_API_KEY:
        warnings.append('Missing both THE_ODDS_API_KEY and RAPID_API_KEY — no live odds')
    if not get_active_leagues():
        warnings.append('No active leagues — engine will produce nothing')
    if ADMIN_PASS in ('abin2025', 'abin2025_change_this'):
        warnings.append('SECURITY: Change ADMIN_PASS from default before going live!')
    if PAYFAST_SANDBOX:
        warnings.append('PAYFAST_SANDBOX=true — no real payments will process')

    return warnings


if __name__ == '__main__':
    print('AFRICAN BETTING INTELLIGENCE NETWORK — Config Validator')
    print('=' * 56)
    print(f'Active leagues:    {get_active_leagues()}')
    print(f'Bookmakers:        {[b["key"] for b in BOOKMAKERS]}')
    print(f'Signal cap:        {MIN_SIGNALS_EXPECTED}–{WEEKLY_SIGNAL_CAP}/week')
    print(f'Confidence gate:   {CONFIDENCE_THRESHOLD}')
    print(f'Publish mode:      {PUBLISH_MODE}')
    print(f'PayFast sandbox:   {PAYFAST_SANDBOX}')
    print(f'Admin free access: Yes (permanent, unconditional)')
    print()
    ws = validate_config()
    if ws:
        print('⚠  Warnings:')
        for w in ws:
            print(f'   → {w}')
    else:
        print('✓  All configuration checks passed')
