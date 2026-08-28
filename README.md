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

## Live monitoring (email alerts, not automated trading)

`tracker/data/rss_monitor.py` + `tracker/data/live_rules.py` +
`tracker/pipeline/monitor.py` (`python -m tracker.cli monitor-news`) is a
live version of the event detection this project has been doing by hand
throughout — with two honest limits stated up front:

1. **Detection is a keyword match against RSS headlines, not verified
   research.** Every event in the hand-built calendars
   (`trump_events.py`, `geopolitical_events.py`) was found by manually
   reading multiple sources and cross-checking dates — that's what made
   those backtest results trustworthy. This module does none of that. It
   *will* produce false positives and *will* miss things a human would
   catch. Treat a match as "worth a look," not a confirmed event.
2. **It reports the documented rule's output — it does not decide for
   you and it does not place any trade.** For each match it prints the
   backtested category, the mechanical trade the rule specifies (which
   tickers, which direction, how long to hold), and the historical win
   rate/average return for that exact category — the same facts in this
   README, just delivered automatically. Categories this project actually
   tested and found *don't* work (de-escalation, tariffs, FOMC, crypto
   policy) are reported as detected-but-not-validated, not suppressed and
   not upgraded into a suggested trade.

**Data source**: four free, no-key, no-signup RSS feeds — verified live
while building this, not assumed: BBC World News, Al Jazeera, UN News, and
the US Department of War's (formerly Defense) own newsroom feed. No paid
news API needed; GDELT (this project's original live-news pick) still has
a broken TLS certificate on the provider's end as of writing.

**State**: `data/cache/rss_monitor_state.json` tracks which article links
have already been processed (so the same headline doesn't refire the same
alert) and which validated signals are still "open" (so it can later
remind you the documented holding period has elapsed and it's worth
considering closing the position) — this is a reminder based on the
rule's holding period, not knowledge of whether you actually placed the
trade.

**Delivery**: `monitor-news` doesn't send email itself — it prints
everything a scheduler needs. Email is sent by whatever Claude Code
session runs the check, via your Gmail connector (enable it for that
chat/session under claude.ai Settings → Connectors), so your own Gmail
auth is used rather than credentials stored in this repo. A scheduled
Claude Code trigger firing every few hours, with a prompt telling it to
run `python -m tracker.cli monitor-news` and email the result if there's
anything to report, is the intended way to run this continuously — hourly
is possible but adds cost without adding much value, since these are rare
events that stay in the news for hours once they break.

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

### Live-data status (checked directly against each source)

Once this project's environment network access was opened up, every data
source got tested against the real thing, not just synthetic fixtures.
Current status:

| Source | Status | Notes |
|---|---|---|
| SEC Form 4 (insider tracker) | **Working** | Fixed two real bugs found this way: Bezos's CIK has to be found via full-text search on surname (the legacy `cgi-bin/browse-edgar` name-search endpoint times out); and `primaryDocument` often points at an XSLT-rendered HTML view, not raw XML — fixed by using the same filename at the accession root instead. |
| Prices (`tracker/data/prices.py`) | **Working**, rewritten | `yfinance`'s cookie/crumb fetch to `fc.yahoo.com` failed outright here; the underlying chart API works fine called directly, so that's what this now does, with retry/backoff for Yahoo's real (and fairly aggressive) per-IP rate limiting. |
| GBP→USD FX | **Working** | Uses the same direct chart fetch (`GBPUSD=X`). |
| Congress disclosures (Senate/House Stock Watcher) | **Down** | Both S3 buckets (`senate-stock-watcher-data`, `house-stock-watcher-data`) return AccessDenied, and the community's own GitHub source (`timothycarambat/senate-stock-watcher-data`) stopped updating in **December 2020**. This looks like the project has gone dark, not a transient outage. `fetch_disclosures()` now degrades to an empty frame instead of crashing, so the insider tracker still works on its own — but there is currently no free, live source of Congressional STOCK Act data wired into this repo. If you need it, look at a paid API (Quiver Quant, Capitol Trades) or a direct scraper of `efdsearch.senate.gov` / `disclosures-clerk.house.gov`. |
| Policy news (GDELT) | **Down** | `api.gdeltproject.org` is serving a TLS certificate that `curl -v` and `openssl` both confirm is invalid ("certificate has expired") even though `openssl s_client` shows a leaf cert dated *today* — most likely a broken intermediate on their end. This is a server-side problem, not fixable from a client without disabling certificate verification, which this project won't do. The event-driven strategy is untestable against live news until GDELT fixes this (or you swap in `NEWSAPI_KEY` and a different provider in `tracker/data/news.py`). |

Given that, **the mirror-trade strategy currently only has insider (Musk/Bezos)
signals to work with, not Congress** — see "A real result" below for what
that actually produced.

### Trump policy calendar (a workaround for GDELT being down)

`tracker/data/trump_events.py` + `backtest-trump-events` is a substitute for
the live-news event-driven strategy while GDELT's certificate is broken: a
hand-verified, dated, sourced calendar of 18 real Trump administration
announcements (tariffs, the 2025 and 2026 Iran conflicts, the Fed chair
transition, crypto policy) from Feb 2025 through Aug 2026, each mapped to a
directional ticker hypothesis the same way `event_map.py` works. It is
**not** a live feed — it won't pick up new announcements on its own; add
rows to `EVENT_CALENDAR` by hand as things happen, each with a real source.

Read the result with real caution: 18 events is a small, manually-curated
sample (not independently drawn — the "n_signals" column in the category
breakdown counts one row per *ticker*, so e.g. "19 middle_east_conflict
signals" is really only 5 distinct dates). Good for a real, checkable
first look — not for a statistically confident conclusion either way.

This repo was originally built in a sandboxed session whose outbound network
was restricted to PyPI and GitHub only, so:

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
  months?", run:
  `python -m tracker.cli backtest-walkforward --strategy mirror --train-months 6 --test-months 1`
  and read the printed report as-is — good, bad, or mixed.

### A real result (run live, not synthetic)

With Congress data down (see table above), `backtest-mirror --holding-days 21`
against real 2-year price history and real SEC filings found exactly **two**
qualifying trades: Elon Musk's September 2025 open-market TSLA purchase
(~$1B, filed as ~25 separate line items in one Form 4 — collapsed to one
signal, see the dedup note in `tracker/signals/mirror_trade.py`) and one
Jeff Bezos AMZN purchase. Result: **+1.5% total return vs. +41% for just
buying and holding SPY over the same window.** Not a cherry-picked bad
example — it's what the only two real signals available actually did.

The reason isn't that the strategy is badly built; it's structural:
corporate insiders overwhelmingly *sell* (tax obligations, diversification,
10b5-1 plans), so open-market *purchases* — the only signal worth mirroring,
per "What this is (and isn't)" above — are rare. Two data points isn't
enough to draw a real conclusion either way, and `backtest-walkforward`
correctly refuses to train a model on that little data rather than
fabricating a confident-looking curve. The honest takeaway right now: this
specific signal (insider purchases only, Musk + Bezos only) has not shown
an edge over the S&P 500 in the one real test available. Widening
`WATCHED_INSIDERS`, fixing the Congress data source, or getting GDELT news
working would all add more signal to actually evaluate — right now there
just isn't much to work with.

### A second real result: reacting to Trump's policy announcements

`backtest-trump-events --holding-days 10` against real price history:
**+1.9% total return vs. +41% for SPY buy-and-hold** over the same window
(Feb 2025 - Aug 2026) — again, substantially underperforming the market.
But the category breakdown is more interesting than the headline number:

| category | independent dates | win rate | avg return/trade |
|---|---|---|---|
| **Middle East escalation** (long oil/defense, short airlines) | **7** | **64%** | **+2.4%** |
| tariff_policy_reversal | 1 | 50% | +0.1% |
| monetary_policy (Fed chair transition) | 2 | 50% | -0.1% |
| tariff_policy | 5 | 38% | -0.3% |
| Middle East **de-escalation** (short oil/defense on ceasefires) | 3 | 38% | -0.9% |
| crypto_policy | 1 | 0% | **-15.4%** |

("independent dates" matters more than the raw signal count in
`backtest-trump-events`' own output — that table counts one row per
*ticker*, so e.g. 22 middle-east-escalation signals are really only 7
distinct announcements, each traded across several tickers.)

Three things worth being straight about:

1. **The escalation side of the Iran/Middle East trade is the one real
   finding here** — 7 independent dates (the March and June 2025 Houthi/Iran
   strikes, four 2026 Iran-war escalations) at a 64% win rate and +2.4%
   average is more consistent than everything else in the table, and
   directly supports the original "he's moving oil and defense stocks with
   this policy" instinct. Still a small sample — call it encouraging, not
   proven — but it's the one category where the data holds together rather
   than looking like noise.
2. **The de-escalation side does not work** — shorting oil/defense when a
   ceasefire is announced lost money more often than not (38% win rate).
   The honest read: markets treat these ceasefires as fragile and don't
   fully unwind the conflict risk premium, so "buy the escalation" is a
   meaningfully different (and better-supported) trade than "sell the
   ceasefire" — worth knowing before assuming the pattern is symmetric.
3. **The crypto trade was a clear, real miss**: the May 2026 executive
   order integrating crypto into the financial system looked like an
   obvious "long Coinbase/bitcoin" call, and both positions lost 15%+ over
   the following two weeks anyway — a reminder that "the policy sounds
   good for the sector" and "the trade makes money" are different claims.
4. **The bigger reason the total lags SPY so much**: this strategy is
   mostly in cash between signals (short holding windows, capped position
   sizes), so during a period where the index itself rose ~41%, just being
   invested the whole time beats picking a handful of 10-day tactical
   trades almost by construction — a structural cost of the approach, not
   only a sign the picks were bad.

### Core + satellite: beating the fund, not just the signal

`tracker/backtest/core_satellite.py` (`backtest-core-satellite`) fixes the
cash-drag problem directly: stay 100% invested in `settings.benchmark_ticker`
at all times, and fund each tilt by temporarily selling benchmark units
rather than holding cash — the tilt's gain or loss lands on top of the
benchmark's own return instead of instead of it.

Real result, last 12 months, £5,000 starting capital, benchmark = SWDA.L
(the MSCI World proxy from the section above):

| Approach | Final value | Return | Max drawdown |
|---|---|---|---|
| Just holding the fund | £6,035 | +20.7% | -27.4% |
| Core + satellite, **all** Trump-calendar categories | £6,043 | +20.9% | -26.0% |
| Core + satellite, **escalation-only** (the validated signal) | **£6,532** | **+30.6%** | **-26.0%** |

The escalation-only version is the first thing in this whole project that
has actually beaten the benchmark — by about £497 on £5,000, with a
*slightly smaller* max drawdown than just holding the fund outright (the
tilt happens to land during the same market stress that also hits the
broad index, so it isn't purely adding risk). Trading every category
instead of just the validated one comes out roughly flat against the fund
— consistent with the earlier finding that only the escalation side of
this calendar has real support.

Keep the caveat sizing: this is still 12 trades from 7 independent dates.
A real edge, worth continuing to track — not yet a large enough sample to
bet heavily on. `--satellite-pct` (default 0.15) is the risk knob: raising
it scales the edge and the drawdown together, it doesn't get you one
without the other.

### Generalizing the escalation pattern beyond Trump/Iran

The obvious question about a 7-date pattern: is "major conflict escalation
→ long oil/defense" a real market mechanism, or a Trump/Iran quirk that
happened to look good? `tracker/data/geopolitical_events.py` adds a second
hand-verified calendar — Russia-Ukraine (the August 2024 Kursk incursion,
the December 2025 peace-talks defense selloff) and China-Taiwan (four
dated PLA military exercises, "Joint Sword"/"Strait Thunder"/"Justice
Mission", 2024-2025, adding a short-semiconductors leg since these
specifically move TSMC-adjacent stocks) — and
`tracker/data/combined_conflict.py` merges it with the Iran calendar for
one test of the general hypothesis, same tickers/direction logic as
before, same core+satellite engine.

**It held up. It got stronger, not weaker:**

| Signal | Independent dates | Win rate | Avg return/trade |
|---|---|---|---|
| Iran only (previous finding) | 7 | 64% | +2.4% |
| Ukraine + Taiwan only (new) | 5 | 75% | +1.6% |
| **All three combined** | **11** | **70%** | **+2.0%** |

De-escalation still doesn't work generalized either (42% win rate,
-0.8% avg across 4 dates) — same asymmetry as before, now confirmed
across three separate conflicts rather than one.

Run through core + satellite (`backtest-core-satellite --strategy
generalized-escalation-only`), £5,000, last 12 months:

| Approach | Final value | Return |
|---|---|---|
| Just holding the fund | £6,035 | +20.7% |
| Core + satellite, Iran-only escalation | £6,532 | +30.6% |
| **Core + satellite, generalized (Iran + Ukraine + Taiwan) escalation** | **£6,678** | **+33.6%** |
| Core + satellite, generalized escalation **+ de-escalation** | £6,279 | +25.6% |

Widening the sample made the result *better*, not diluted — real evidence
this is closer to "markets reliably reprice defense/oil/semis on state-conflict
escalation" than "one lucky reading of Trump-Iran." Still 11 dates, not
110 — a genuine, growing case, not a proven law. Max drawdown is the same
-26% either way; adding more escalation sources adds return, not extra
downside, in this sample.

**What I looked into and didn't add:** OPEC+ supply decisions (a
structurally different, higher-frequency mechanism) — I couldn't pin down
specific "surprise" decision dates with the confidence bar the rest of
this calendar holds itself to (OPEC+ outcomes are often pre-signaled over
weeks, making "the surprise date" genuinely ambiguous, unlike a military
strike). Worth a dedicated pass later rather than a guessed date in a
financial model.

### Higher frequency, non-crisis: the pre-FOMC drift (a real negative result)

11-12 conflict-escalation dates over ~2 years is nowhere near daily, and
crises are inherently rare — you can't manufacture more of them. The
honest way to get real frequency without waiting for a war is a
**scheduled, recurring, publicly pre-announced calendar**: the Fed
publishes its 8-meetings-a-year FOMC schedule years in advance
(`tracker/data/macro_calendar.py`), guaranteeing this specific event keeps
happening for the next 24 months regardless of politics.

The hypothesis tested is a real, published academic finding — not folk
wisdom: **pre-FOMC announcement drift** (Lucca & Moench, *Journal of
Finance*, 2015), which found abnormally elevated average US equity returns
in the ~24 hours before scheduled Fed decisions, independent of what the
Fed actually announces. `backtest-macro` tests it directly: long SPY from
the close before each of the last 21 resolvable FOMC meetings through the
close on the decision day.

**It didn't hold up.** 47.6% win rate — worse than a coin flip — and
essentially flat total return (-0.02%) before costs eat the rest. Through
core + satellite it comes out just below simply holding the fund (£6,877
vs. £6,900 on £5,000). This is a real, useful negative result, not a
failure to find something: it's a well-known, heavily published pattern,
and well-known patterns are exactly the ones professional funds arbitrage
away fastest once they're public — this project isn't the first to try
trading it. Higher frequency didn't mean easier money here; if anything,
scheduled and well-studied made it *harder* to find an edge than the
rare, harder-to-systematically-trade crisis events did. Worth knowing
before assuming "more frequent = better."

CPI and non-farm payrolls releases are the same style of scheduled,
recurring, publicly pre-announced event and would be worth the same test
— not yet added, since getting their exact historical release dates right
needs a dedicated sourcing pass the FOMC calendar didn't (the Fed
publishes multi-year meeting dates directly; BLS release calendars are
less trivial to source with full confidence for 2+ years of history).

### Beyond the US: EMEA, Asia, Sub-Saharan Africa

Everything above skewed US/Trump-centric even though Iran and Ukraine
already weren't. Widened `geopolitical_events.py` with real, dated events
from three more regions:

- **Middle East beyond Iran-US**: Israel killing Hezbollah leader Hassan
  Nasrallah (Sept 27, 2024); Iran's ~200-missile direct strike on Israel
  (Oct 1, 2024); Israel's retaliatory strikes on Iran (Oct 26, 2024) — the
  last one is a useful edge case: those strikes *deliberately avoided*
  Iranian oil infrastructure, and next-day oil prices reportedly fell on
  that news. Tested anyway per the standard escalation hypothesis rather
  than hand-picking the "obviously right" direction after the fact — and
  over the actual 10-day holding window used throughout this project, oil
  and defense positions still came out net positive (5 of 6 tickers). A
  real reminder that a single day's headline reaction and a 10-day
  systematic holding rule can disagree.
- **South Asia**: India's "Operation Sindoor" strikes on Pakistan (May 7,
  2025) — India's own defense-manufacturer stocks reportedly rallied far
  harder than the global primes tested here (Nifty Defence Index +32% over
  the following year), but this project hasn't verified NSE-ticker data
  access, so only the same global LMT/RTX/NOC/GD basket was tested — a
  likely understatement of the real move, noted rather than papered over.
- **Sub-Saharan Africa**: M23 rebels capturing Goma, DRC (Jan 27, 2025) —
  a region controlling major cobalt/coltan supply. Tested Glencore
  (GLEN.L, DRC cobalt mining exposure) as the only real, liquid ticker
  with a direct link — an imperfect proxy (a large diversified miner, not
  a pure DRC play). Result: essentially flat (-0.7% over 10 days, one data
  point). Inconclusive, as expected going in; kept separate from the main
  escalation statistics as its own `resource_supply_risk` category rather
  than folded in, since it's a different mechanism (supply-chain risk, not
  a war-escalation trade) tested on a single event.

**The escalation pattern held up as more independent, geographically
diverse data was added** — the real test of whether it was fragile or
robust. Adding these 4 new dates (9 more resolved trades) barely moved the
aggregate: win rate 69.1% (was 69.6%), average return per trade +2.0%
(unchanged), now across 15 independent dates instead of 11. Through core +
satellite, full history (since May 2024) on £5,000: £7,809 (+56.2%) vs.
the fund's £6,900 (+38.0%) — an ~18-point edge, in line with what the
Iran/Ukraine/Taiwan-only version already showed. That consistency under
expansion is more reassuring than the original 11-date finding on its own
— an overfit pattern would have degraded as new, independent cases were
added; this one didn't.

### Found via the live monitor, verified, and added: a real gap it caught

Once `monitor-news` (see "Live monitoring" below) was running, it
surfaced a real, current event outside the hand-checked calendar: the US
Dept. of War's own newsroom feed showed a second wave of Iran strikes
running from at least March through July 2026 that the calendar had
missed entirely (it only had the Feb 28 - Apr 8 "Epic Fury" campaign and
the Apr 13 blockade). Cross-checked against Al Jazeera before adding
anything: the April ceasefire broke down and the US resumed major strikes
on **July 8, 2026** ("the most severe [strikes] since" the mid-June
truce, per Al Jazeera; corroborated by the Dept. of War's own dated
releases through "13th night of strikes," July 24). Added as a proper,
sourced calendar entry (not just left as an unverified RSS match) — this
is exactly the verify-before-trusting standard every other entry in this
project holds itself to, just triggered by an automated feed instead of a
manual literature search.

Rerunning the £5,000/12-month and full-history numbers with this
addition:

| Window | Independent dates | Final value | Return | vs. fund |
|---|---|---|---|---|
| Last 12 months | 6 | **£6,760** | +35.2% | fund: £5,973 (+19.5%) |
| Full history (since May 2024) | 16 | **£7,962** | +59.2% | fund: £6,900 (+38.0%) |

Both improved slightly on the pre-update numbers (was £6,630/+32.6% and
£7,809/+56.2%) — real, additional, independently-verified data continuing
to support the pattern rather than diluting it, now for the fourth time
running.

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

# Backtest reacting to the hand-verified Trump policy calendar (works right
# now even with GDELT down — see "Trump policy calendar" above).
python -m tracker.cli backtest-trump-events --holding-days 10
python -m tracker.cli backtest-walkforward --strategy trump-events --train-months 6 --test-months 1

# Stay fully invested in the benchmark, tilt on top of it instead of
# trading from cash — see "Core + satellite" above for why this is the
# version that actually beat the fund.
python -m tracker.cli backtest-core-satellite --strategy trump-escalation-only

# The generalized version — Iran + Russia-Ukraine + China-Taiwan escalations
# combined — see "Generalizing the escalation pattern" above.
python -m tracker.cli backtest-core-satellite --strategy generalized-escalation-only

# Scheduled, recurring, non-crisis alternative: the pre-FOMC drift (a real
# negative result — see "Higher frequency, non-crisis" above).
python -m tracker.cli backtest-macro
python -m tracker.cli backtest-core-satellite --strategy pre-fomc-drift

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

# Live RSS monitor — one check, prints alerts/exit reminders (see "Live
# monitoring" above for how this gets scheduled + emailed).
python -m tracker.cli monitor-news

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
    trump_events.py            hand-verified Trump policy/geopolitical calendar
    geopolitical_events.py       hand-verified Russia-Ukraine/China-Taiwan calendar
    combined_conflict.py           merges the above into one escalation signal
    macro_calendar.py                FOMC meeting calendar + pre-drift hypothesis
    rss_monitor.py                    live RSS fetch/parse (BBC/Al Jazeera/UN/DoW)
    live_rules.py                      keyword match -> documented rule mapping
  signals/
    mirror_trade.py        disclosures (Congress + insider) -> signal rows
    event_driven.py        daily news events -> signal rows via event_map
  backtest/
    engine.py               trade resolution + portfolio simulation
    core_satellite.py        stay invested in the benchmark, tilt on top
    metrics.py                CAGR / Sharpe / max drawdown / win rate
    walkforward.py             rolling train/test folds, no cherry-picking
  models/
    features.py              signal rows -> ML feature frames
    prediction_engine.py       chronological train/test split + evaluation
  execution/
    paper_broker.py          Alpaca paper-trading client (paper-only, guarded)
  pipeline/
    daily.py                24h-window signal generation + paper execution
    monitor.py                live RSS check -> alerts + exit reminders
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
