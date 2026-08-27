# Political Trade Tracker

A research pipeline that tracks **publicly disclosed Congressional stock
trades**, **corporate-insider trades of named individuals** (e.g. Musk,
Bezos, via SEC Form 4), and **policy/geopolitical news events**, backtests
signal strategies built on top of them, and includes a **paper-trading-only**
execution stub so you can see the signals reach a (simulated) brokerage
account. A daily pipeline (`daily-run`) reacts to just the last 24 hours of
news/disclosures, sized against a GBP starting capital — see "Daily
automation" below.

This is a research and backtesting tool. It does not place real trades. Read
"What this can and can't see" and "Realistic expectations" below before
acting on anything it outputs.

## What this is (and isn't)

**Tracks:** trades disclosed by members of **Congress** under the STOCK
Act — Senators and Representatives are required to file a Periodic
Transaction Report (PTR) within 45 days of any trade over $1,000. Two
community projects, [Senate Stock Watcher](https://senatestockwatcher.com)
and [House Stock Watcher](https://housestockwatcher.com), parse those
filings into structured JSON and publish it for free. That's
`tracker/data/disclosures.py`.

**Does not track the President's or Vice President's individual trades in
real time.** This is a real, structural limitation, not an oversight: the
President and VP file an annual OGE Form 278 financial disclosure with
*asset value ranges*, not the 45-day, transaction-level PTR that Congress
files. There is no public feed of "here's a stock the President bought
yesterday." If you want to track people connected to the administration,
populate `WATCHLIST` in `.env` with the names of specific members of
Congress you care about (allied committee members, family members who hold
office, etc.) — the tracker filters disclosures to that list.

**Tracks named individuals' insider trades** (`WATCHED_INSIDERS` in `.env`,
default Elon Musk / Jeff Bezos) via **SEC Form 4** filings
(`tracker/data/insider_trades.py`) — a different legal mechanism than the
STOCK Act: an officer/director/10%+ owner must file within *2 business
days* of a trade, but only for the company(ies) where they hold that role.
Musk's filings cover Tesla; Bezos's cover Amazon. Neither covers a private
company (SpaceX, Blue Origin) or any stake outside that one company —
this is not a view into their whole net worth or portfolio, just their
disclosed trading in the company they run. Many insider *sales* are
pre-scheduled Rule 10b5-1 plan sales (tax/diversification, not a market
call), so — same choice as the Congress tracker — `mirror_trade.py`
defaults to signaling only on open-market *purchases*.

**Tracks policy/news events** via free-text search against
[GDELT](https://www.gdeltproject.org) (no API key needed), matched against a
hand-authored keyword → affected-tickers hypothesis table in
`tracker/data/event_map.py` (e.g. "Iran" → long energy/defense, short
airlines). This table is a starting hypothesis, not a fact — the backtest
is what tells you whether a given entry actually held up.

## Daily automation (24h news window, fixed time)

`python -m tracker.cli daily-run` is the "trade at the same time every day"
entry point: it looks at only the last `--window-hours` (default 24) of
policy news and newly-disclosed Congress/insider trades, generates signals
from just that window, converts your GBP capital to USD
(`tracker/data/fx.py`), sizes positions, and submits to the paper broker
(dry run unless `--confirm`).

**Wiring it to actually fire at 7am UK time** is a scheduler's job, not this
script's — point a daily cron (or a Claude Code Routine, `create_trigger`)
at `python -m tracker.cli daily-run --confirm`. One real gotcha: cron runs
in UTC, and the UK isn't — it's BST (UTC+1) in summer, GMT (UTC+0) in
winter. A cron fixed at `0 6 * * *` hits 7am UK time during BST but 6am once
the clocks go back in late October, and vice versa for a cron fixed at
`0 7 * * *`. Either update the cron expression at each DST change, or use a
scheduler that already understands IANA time zones (`Europe/London`)
instead of raw UTC crons.

## Realistic expectations

Read this before funding anything.

- **The 45-day disclosure lag is a real cost.** By the time a Congressional
  trade is public, the market has often already moved. Some published
  studies (and this repo's own backtest, once you run it) find mirror
  strategies barely beat a plain S&P 500 buy-and-hold after that lag and
  after transaction costs — some find they don't beat it at all. Don't
  assume an edge exists; measure it with `backtest-mirror` and look at the
  benchmark comparison row.
- **The event-driven keyword map is a hypothesis you have to falsify.**
  `tracker/data/event_map.py` encodes plausible-sounding trades
  ("Iran headlines → long oil"). Some of those relationships are real and
  well documented; others are folk wisdom that doesn't survive contact with
  data. Run `backtest-events` and look at `category_hit_rates` before
  trusting any single row.
- **A backtest is not a guarantee.** Overfitting, regime change, and a
  small sample size (2 years is not that many independent events) all mean
  a backtest that looks good can still lose money going forward.
- **This repo deliberately does not "search for a winning pathway."**
  It would be easy to tune the holding period, article-count threshold, or
  model hyperparameters against a fixed historical window until one
  combination shows a great curve — that measures how well you can fit
  noise, not whether there's a real edge, and reporting that curve as if it
  were reliable would be actively misleading right before you fund an
  account. `tracker/backtest/walkforward.py` (`backtest-walkforward` in the
  CLI) is the honest version: it trains only on data before each test
  block, predicts on the next unseen month, and reports whatever comes out
  — including "the model doesn't beat taking every signal" or "neither
  beats the S&P 500," if that's what the data says.
- **Turning a small account into "millions" is not a realistic target for
  this or any strategy.** No prediction engine in this repo — or
  elsewhere — can promise that, and anyone selling that promise is selling
  something else. Use this to make better-informed, smaller, well-sized
  bets; size every position so a string of losses doesn't wipe you out.

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt   # includes pytest
pip install -e .
cp .env.example .env
# fill in: WATCHLIST (Congress members), WATCHED_INSIDERS (default Musk/Bezos),
# SEC_EDGAR_CONTACT (a real email — SEC requires this in the User-Agent),
# INITIAL_CAPITAL_GBP, and optionally Alpaca paper keys.
```

### Note on this repository's own dev environment

This repo was built and tested in a sandboxed session whose outbound network
was restricted to PyPI and GitHub only — Senate/House Stock Watcher,
yfinance, GDELT, and SEC EDGAR (`www.sec.gov` / `data.sec.gov`) were all
unreachable from there (confirmed directly, including via a raw-fetch tool
that normally has broader reach than a sandboxed shell — this wasn't a
`curl`-specific block). So:

- `tests/` runs entirely against **synthetic, seeded fixture data**
  (`tests/conftest.py`) — it validates the pipeline's *logic* (no
  look-ahead, correct P&L math, correct feature engineering, no negative
  equity, no live trading endpoint reachable) without needing live data.
  `pip install -e . && pytest -q` runs it anywhere.
- The live data paths (`fetch-data`, `backtest-mirror`, `backtest-events`,
  `backtest-walkforward`, `train-*`, `daily-run`) are real implementations
  against real free sources, but they've only been exercised here via the
  synthetic fixtures, not against live data. **Run
  `python -m tracker.cli fetch-data` yourself somewhere with normal internet
  access first**, and sanity-check the row counts it prints, before
  trusting a live backtest report. In particular, `tracker/data/insider_trades.py`'s
  Form 4 XML field paths follow the SEC's documented schema from training
  knowledge, not a verified live sample — diff its output against one real
  filing before trusting it (see the module docstring for a sample URL
  pattern).
- To get a real answer to "would this have made money over the last 12
  months?", run (with normal internet access):
  `python -m tracker.cli backtest-walkforward --strategy mirror --train-months 6 --test-months 1`
  and read the printed report as-is — good, bad, or mixed.

## Usage

```bash
# Warm the local cache: Congress disclosures, insider (Form 4) trades,
# prices for every ticker involved, policy news, and the GBPUSD rate.
python -m tracker.cli fetch-data

# Backtest "buy what they disclosed buying, N days after it's public"
# (blends Congress + insider (Musk/Bezos/...) disclosures).
python -m tracker.cli backtest-mirror --holding-days 21
# -> reports/backtest_mirror.md: equity curve stats (in USD, capital
#    converted from INITIAL_CAPITAL_GBP), benchmark comparison, per-member
#    win rate/avg return breakdown, recent trade log.

# Backtest "react to policy news via the event_map hypothesis table"
python -m tracker.cli backtest-events --holding-days 10 --min-article-count 3
# -> reports/backtest_events.md: same shape, broken down by event category.

# THE HONEST 12-MONTH TEST: walk the model forward month by month, training
# only on data before each test block, and compare the model-filtered
# out-of-sample curve against taking every signal and against buy-and-hold.
python -m tracker.cli backtest-walkforward --strategy mirror --train-months 6 --test-months 1
python -m tracker.cli backtest-walkforward --strategy events --train-months 6 --test-months 1

# Train + chronologically evaluate a classifier predicting whether a given
# disclosed trade / news event will turn out profitable, over the whole
# history at once (use backtest-walkforward instead for an out-of-sample
# read). Reports whether it beats a naive majority-class baseline — treat
# "it doesn't beat baseline" as a real, useful answer, not a bug to fix.
python -m tracker.cli train-mirror --model-type gbm
python -m tracker.cli train-events --model-type logreg

# The daily "trade at a fixed time" entry point — last 24h of news +
# newly-disclosed trades only. See "Daily automation" above for scheduling.
python -m tracker.cli daily-run
python -m tracker.cli daily-run --confirm

# Size the latest signals against your Alpaca *paper* account and print
# what would be submitted (dry run by default; --confirm actually submits
# to the paper endpoint — never a live one, see below).
python -m tracker.cli paper-trade --strategy mirror
python -m tracker.cli paper-trade --strategy mirror --confirm
```

## Paper trading only — no live execution path

`tracker/execution/paper_broker.py` talks to
[Alpaca](https://alpaca.markets)'s free **paper trading** API (simulated
money, real market data). `PaperBrokerClient.__post_init__` calls
`_assert_paper_endpoint`, which raises `LiveTradingBlockedError` for any
`base_url` that isn't `paper-api.alpaca.markets` — there is no config value
or flag anywhere in this repo that routes an order to a real-money
endpoint. If you eventually want to trade with real capital, that's a
decision you make directly in your own brokerage account, informed by (not
delegated to) what the backtests here show you.

## How the backtest works (and where it simplifies)

`tracker/backtest/engine.py`:

1. **`resolve_trades`** — for each signal, entry price = first close *on or
   after* the signal date (never before — that would be look-ahead), exit
   price = close `holding_days` trading days later. Returns are reduced by
   a flat round-trip transaction cost (`TRANSACTION_COST_BPS`, default 5bps
   each way).
2. **`simulate_portfolio`** — walks trades through a real trading calendar
   against a starting capital (`INITIAL_CAPITAL_USD`) and a max-position-size
   rule (`MAX_POSITION_PCT` of current equity per position); a ticker
   already held is skipped until its position closes (no averaging in).

Stated simplifications: no margin/borrow cost modeling for short
positions (a short's P&L is just the sign-flipped long P&L), no slippage
beyond the flat transaction-cost assumption, and open-position
mark-to-market between entry and exit is a linear accrual of the trade's
already-known outcome rather than a true daily repricing. Good enough to
compare strategies and get directionally right performance numbers; not a
substitute for a production-grade broker simulator.

## Repository layout

```
tracker/
  config.py              Settings from .env
  cli.py                 python -m tracker.cli ...
  data/
    disclosures.py        Senate/House Stock Watcher fetch + normalize
    insider_trades.py      SEC Form 4 fetch + normalize (Musk/Bezos/... watchlist)
    fx.py                   GBP -> USD conversion (with offline fallback)
    prices.py               yfinance historical OHLCV + forward-return helper
    news.py                  GDELT policy-news search + daily aggregation
    event_map.py              keyword -> ticker/direction hypothesis table
  signals/
    mirror_trade.py        disclosures (Congress + insider) -> signal rows
    event_driven.py        daily news events -> signal rows via event_map
  backtest/
    engine.py               trade resolution + portfolio simulation
    metrics.py                CAGR / Sharpe / max drawdown / win rate
    walkforward.py             rolling train/test folds, no cherry-picking
  models/
    features.py              signal rows -> ML feature frames
    prediction_engine.py       chronological train/test split + evaluation
  execution/
    paper_broker.py          Alpaca paper-trading client (paper-only, guarded)
  pipeline/
    daily.py                24h-window signal generation + paper execution
  reporting.py              Markdown report rendering
tests/                     Synthetic-fixture tests (see "Setup" above)
```

## Legal / ethical notes

- Congressional trade disclosure data is public by law (STOCK Act) and this
  is exactly the use case community projects like Senate/House Stock
  Watcher, Capitol Trades, and Quiver Quant already serve commercially —
  there's nothing novel-risk here.
- SEC Form 4 insider-trade data is likewise public by law (Securities
  Exchange Act §16(a)) and is the same data OpenInsider and similar trackers
  are built on.
- GDELT is an open, free research dataset explicitly built for this kind of
  querying.
- This is not investment advice, and the authors/maintainers of this repo
  are not registered investment advisors. You are responsible for your own
  trading decisions and for complying with any regulations that apply to
  you (including insider-trading law, which does **not** cover trading on
  information that is already publicly disclosed, but does cover acting on
  material non-public information from any other source).
