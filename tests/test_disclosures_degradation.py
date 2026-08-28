import requests

from tracker.data import disclosures


def test_fetch_disclosures_degrades_to_empty_frame_when_both_sources_down(monkeypatch, tmp_path):
    monkeypatch.setattr(disclosures, "_CACHE_FILE", tmp_path / "no_cache_here.parquet")

    def always_fails(url):
        raise requests.RequestException("simulated outage")

    monkeypatch.setattr(disclosures, "_fetch_json", always_fails)

    df = disclosures.fetch_disclosures(use_cache=True, force_refresh=True)

    assert df.empty
    assert list(df.columns) == disclosures._EXPECTED_COLUMNS + ["disclosure_lag_days"]


def test_fetch_disclosures_uses_whichever_source_succeeds(monkeypatch, tmp_path):
    monkeypatch.setattr(disclosures, "_CACHE_FILE", tmp_path / "no_cache_here.parquet")

    senate_row = [
        {
            "senator": "Sen. Alpha",
            "ticker": "AAPL",
            "transaction_date": "01/02/2025",
            "type": "Purchase",
            "amount": "$1,001 - $15,000",
            "asset_description": "Apple Inc",
            "owner": "self",
            "disclosure_date": "02/01/2025",
        }
    ]

    def fake_fetch(url):
        if url == disclosures.SENATE_URL:
            return senate_row
        raise requests.RequestException("house is down")

    monkeypatch.setattr(disclosures, "_fetch_json", fake_fetch)

    df = disclosures.fetch_disclosures(use_cache=True, force_refresh=True)

    assert not df.empty
    assert (df["chamber"] == "senate").all()
