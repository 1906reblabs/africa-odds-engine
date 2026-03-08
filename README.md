# African Betting Intelligence Network (ABIN)

**Automated African football signal engine. 10 competitions · 5 bookmakers · Zero server cost.**

---

## What it does

Runs every 4 hours via GitHub Actions. Each cycle:

1. **Fetches** live odds from 5 bookmakers + fixtures from 3 APIs
2. **Models** each match with Poisson goal prediction
3. **Detects** value via edge calculation, drift, and bookmaker disagreement
4. **Queues** top 7–10 signals per week (confidence ≥65/100)
5. **Publishes** to a private Telegram channel (auto or admin approval)

## Competitions (10)

| Competition | Country | Priority |
|---|---|---|
| PSL — Premier Soccer League | South Africa | 1 |
| NFD — National First Division | South Africa | 2 |
| NPFL — Nigeria Premier Football League | Nigeria | 3 |
| Botola Pro | Morocco | 4 |
| Egyptian Premier League | Egypt | 5 |
| KPL — Kenyan Premier League | Kenya | 6 |
| CAF Champions League | Africa | 7 |
| CAF Confederation Cup | Africa | 8 |
| CHAN — African Nations Championship | Africa | 9 |
| AFCON Qualifiers | Africa | 10 |

## Quick Deploy (30 minutes)

1. Fork this repo
2. Create a Telegram bot via [@BotFather](https://t.me/botfather)
3. Create 2 private Telegram channels (main + admin review)
4. Get free API keys:
   - [the-odds-api.com](https://the-odds-api.com) — odds data
   - [rapidapi.com](https://rapidapi.com) → API-Football — fixtures
5. Add GitHub Secrets (Settings → Secrets → Actions):
   ```
   BOT_TOKEN, CHANNEL_ID, ADMIN_ID, THE_ODDS_API_KEY, RAPID_API_KEY, PUBLISH_MODE
   ```
6. Enable GitHub Actions → Run workflow manually to test

## Repository Structure

```
africa-odds-engine/
├── config.py                    # Master config (leagues, bookmakers, thresholds)
├── data_sources/
│   └── api_fetcher.py           # Multi-source aggregator (3 APIs, auto-fallback)
├── models/
│   ├── poisson_model.py         # Poisson goal prediction (African-calibrated)
│   └── value_detector.py        # Edge, Kelly, drift, bookmaker consensus
├── engine/
│   └── signal_engine.py         # Full pipeline: model → score → queue
├── telegram/
│   ├── bot_sender.py            # Formatted delivery + admin callbacks
│   └── admin_queue.py           # Approve/reject polling loop
├── scheduler/
│   ├── run_engine.py            # Master orchestrator (called by GitHub Actions)
│   └── weekly_summary.py        # Thursday audit email
├── tests/
│   └── test_engine.py           # 43 offline tests (no API keys needed)
├── web/
│   └── index.html               # GitHub Pages dashboard
├── .github/workflows/
│   └── scheduler.yml            # Cron: every 4h + weekly jobs
├── .env.example                 # Environment variable template
└── requirements.txt
```

## Confidence Rubric (0–100)

| Component | Max | Description |
|---|---|---|
| Data quality | 20 | API coverage, completeness |
| Market edge | 25 | Model prob vs implied prob |
| Drift confirmation | 20 | Odds movement direction |
| Bookmaker agreement | 20 | Consensus across 5 books |
| Model alignment | 15 | Model vs fair market |

- **≥80** → 🔥 Strong Buy
- **≥65** → ✅ Buy (published)
- **50–64** → ⚠️ Marginal (held)
- **<50** → ❌ Hard reject

## Publish Modes

**`PUBLISH_MODE=admin`** (recommended): Signals go to your admin Telegram channel with ✅/❌ inline buttons. You review and approve. Approved signals post to the main channel.

**`PUBLISH_MODE=auto`**: Signals post directly to the main channel after passing the confidence threshold.

## Running Cost

| Service | Cost |
|---|---|
| GitHub (repo + Actions) | R0 |
| The Odds API | R0 (free tier) |
| API-Football | R0 (free tier) |
| Mailgun | R0 (free tier) |
| Telegram | R0 |
| **Total** | **R0/month** |

## Tests

```bash
pip install -r requirements.txt
python3 tests/test_engine.py
# → 43 tests, all offline, no API keys needed
```

## Admin Access

Admin has permanent, unconditional free access. See `config.py`:

```python
def admin_exempt_from_billing() -> bool:
    return True  # Unconditional. Admin never pays.
```
