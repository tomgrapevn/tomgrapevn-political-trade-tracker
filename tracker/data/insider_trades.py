"""Corporate insider trades (SEC Form 4) for named wealthy/notable individuals.

Different legal basis and different coverage than tracker/data/disclosures.py:
Congress members file under the STOCK Act (any trade, any ticker, 45-day
window). A corporate insider — an officer, director, or 10%+ owner — instead
files a **Form 4** with the SEC within *2 business days* of a transaction,
but only for trades in the company(ies) where they hold that role. Elon
Musk's Form 4s cover Tesla; they say nothing about, say, a personal stake he
might hold in an unrelated public company (no disclosure requirement there),
and nothing about SpaceX (private, no SEC filings at all). Same for Jeff
Bezos and Amazon. Treat WATCHED_INSIDERS as "this person's trades in the
company they run," not "this person's whole portfolio."

Also worth knowing before treating any single filing as a signal: many
insider sales are pre-scheduled **Rule 10b5-1 plan** sales set up months in
advance for tax/diversification reasons, not a real-time view. Purchases
("P" transaction code, open-market buys) are rarer and a much stronger
signal than sales ("S") for exactly that reason — see mirror_trade.py's
same default for the Congressional data.

No API key needed, but the SEC requires a descriptive User-Agent identifying
you (see SEC_EDGAR_CONTACT in .env) — see
https://www.sec.gov/os/webmaster-faq#developers.

NOTE: the Form 4 XML field names below follow the SEC's long-stable
ownership-document schema. This has not been exercised against a live
filing from this environment (see README) — if a field comes back empty
where you'd expect data, diff `_parse_form4_xml` against a real filing
(e.g. https://www.sec.gov/Archives/edgar/data/1318605/... for a Tesla Form 4)
before trusting the output.
"""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from urllib.parse import quote

import pandas as pd
import requests

from tracker.config import CACHE_DIR, settings

logger = logging.getLogger(__name__)

BROWSE_EDGAR_URL = "https://www.sec.gov/cgi-bin/browse-edgar"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
ARCHIVE_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession_nodash}/{doc}"

_EXPECTED_COLUMNS = [
    "chamber",
    "member",
    "ticker",
    "transaction_type",
    "transaction_date",
    "disclosure_date",
    "amount_range",
    "owner",
    "asset_description",
]

_TRANSACTION_CODE_MAP = {
    "P": "purchase",
    "S": "sale",
}


def _headers() -> dict:
    return {"User-Agent": f"political-trade-tracker research tool ({settings.sec_edgar_contact})"}


def resolve_cik(name: str) -> str | None:
    """Look up a reporting owner's 10-digit zero-padded CIK by name via
    EDGAR's company/owner search. Returns None if no confident match."""
    cache_file = CACHE_DIR / f"cik_{re.sub(r'[^a-z0-9]', '_', name.lower())}.txt"
    if cache_file.exists():
        return cache_file.read_text().strip() or None

    params = {"action": "getcompany", "company": name, "type": "4", "owner": "include", "count": "10", "output": "atom"}
    try:
        resp = requests.get(BROWSE_EDGAR_URL, params=params, headers=_headers(), timeout=20)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        ns = {"a": "http://www.w3.org/2005/Atom"}
        for entry in root.findall("a:entry", ns):
            cik_match = re.search(r"CIK=(\d{10})", entry.findtext("a:link", "", ns) or entry.get("link", ""))
            if not cik_match:
                title = entry.findtext("a:title", "", ns) or ""
                cik_match = re.search(r"\((\d{10})\)", title)
            if cik_match:
                cik = cik_match.group(1)
                cache_file.write_text(cik)
                return cik
    except (requests.RequestException, ET.ParseError) as exc:
        logger.warning("CIK lookup failed for %r (%s)", name, exc)
    return None


def _parse_form4_xml(xml_bytes: bytes, insider_name: str) -> list[dict]:
    root = ET.fromstring(xml_bytes)
    issuer_ticker = (root.findtext(".//issuerTradingSymbol") or "").strip().upper()
    rows = []
    for txn in root.findall(".//nonDerivativeTable/nonDerivativeTransaction"):
        code = (txn.findtext(".//transactionCoding/transactionCode") or "").strip().upper()
        if code not in _TRANSACTION_CODE_MAP:
            continue
        txn_date = txn.findtext(".//transactionDate/value")
        shares = txn.findtext(".//transactionAmounts/transactionShares/value")
        price = txn.findtext(".//transactionAmounts/transactionPricePerShare/value")
        if not txn_date or not shares:
            continue
        try:
            amount = float(shares) * float(price or 0)
        except ValueError:
            amount = float("nan")
        rows.append(
            {
                "chamber": "insider",
                "member": insider_name,
                "ticker": issuer_ticker,
                "transaction_type": _TRANSACTION_CODE_MAP[code],
                "transaction_date": txn_date,
                "amount_range": f"${amount:,.0f} - ${amount:,.0f}" if amount == amount else pd.NA,
                "owner": "self",
                "asset_description": f"{issuer_ticker} common stock (Form 4)",
            }
        )
    return rows


def fetch_insider_trades(names: list[str] | None = None, max_filings_per_person: int = 40) -> pd.DataFrame:
    """Fetch and parse recent Form 4 filings for each name in `names`
    (defaults to settings.watched_insiders). One row per non-derivative
    (i.e. common-stock) transaction."""
    names = names if names is not None else settings.watched_insiders
    all_rows: list[dict] = []

    for name in names:
        cik = resolve_cik(name)
        if cik is None:
            logger.warning("Could not resolve a CIK for %r — skipping.", name)
            continue

        try:
            resp = requests.get(SUBMISSIONS_URL.format(cik=int(cik)), headers=_headers(), timeout=20)
            resp.raise_for_status()
            submissions = resp.json()
        except (requests.RequestException, ValueError) as exc:
            logger.warning("Submissions fetch failed for %s (CIK %s): %s", name, cik, exc)
            continue

        recent = submissions.get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
        accessions = recent.get("accessionNumber", [])
        docs = recent.get("primaryDocument", [])
        filing_dates = recent.get("filingDate", [])

        n_seen = 0
        for form, accession, doc, filing_date in zip(forms, accessions, docs, filing_dates):
            if form != "4" or n_seen >= max_filings_per_person:
                continue
            n_seen += 1
            accession_nodash = accession.replace("-", "")
            url = ARCHIVE_URL.format(cik=int(cik), accession_nodash=accession_nodash, doc=doc)
            try:
                doc_resp = requests.get(url, headers=_headers(), timeout=20)
                doc_resp.raise_for_status()
                rows = _parse_form4_xml(doc_resp.content, name)
            except (requests.RequestException, ET.ParseError) as exc:
                logger.warning("Form 4 fetch/parse failed for %s at %s: %s", name, url, exc)
                continue
            for row in rows:
                row["disclosure_date"] = filing_date
            all_rows.extend(rows)

    if not all_rows:
        return pd.DataFrame(columns=_EXPECTED_COLUMNS + ["disclosure_lag_days"])

    df = pd.DataFrame(all_rows)
    df["transaction_date"] = pd.to_datetime(df["transaction_date"], errors="coerce")
    df["disclosure_date"] = pd.to_datetime(df["disclosure_date"], errors="coerce")
    df["ticker"] = df["ticker"].astype(str).str.upper().str.strip()
    df = df.dropna(subset=["transaction_date", "disclosure_date", "ticker"])
    df["disclosure_lag_days"] = (df["disclosure_date"] - df["transaction_date"]).dt.days
    return df[_EXPECTED_COLUMNS + ["disclosure_lag_days"]].reset_index(drop=True)
