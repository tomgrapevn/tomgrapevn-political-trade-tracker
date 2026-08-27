import xml.etree.ElementTree as ET

from tracker.data.insider_trades import _parse_form4_xml, fetch_insider_trades, resolve_cik

_SAMPLE_FORM4_XML = b"""<?xml version="1.0"?>
<ownershipDocument>
  <issuer>
    <issuerTradingSymbol>TSLA</issuerTradingSymbol>
  </issuer>
  <nonDerivativeTable>
    <nonDerivativeTransaction>
      <transactionDate><value>2024-03-01</value></transactionDate>
      <transactionCoding>
        <transactionCode>P</transactionCode>
      </transactionCoding>
      <transactionAmounts>
        <transactionShares><value>1000</value></transactionShares>
        <transactionPricePerShare><value>180.50</value></transactionPricePerShare>
      </transactionAmounts>
    </nonDerivativeTransaction>
    <nonDerivativeTransaction>
      <transactionDate><value>2024-03-05</value></transactionDate>
      <transactionCoding>
        <transactionCode>A</transactionCode>
      </transactionCoding>
      <transactionAmounts>
        <transactionShares><value>500</value></transactionShares>
        <transactionPricePerShare><value>0</value></transactionPricePerShare>
      </transactionAmounts>
    </nonDerivativeTransaction>
    <nonDerivativeTransaction>
      <transactionDate><value>2024-03-10</value></transactionDate>
      <transactionCoding>
        <transactionCode>S</transactionCode>
      </transactionCoding>
      <transactionAmounts>
        <transactionShares><value>200</value></transactionShares>
        <transactionPricePerShare><value>190.00</value></transactionPricePerShare>
      </transactionAmounts>
    </nonDerivativeTransaction>
  </nonDerivativeTable>
</ownershipDocument>
"""


def test_parse_form4_xml_keeps_only_purchase_and_sale_codes():
    rows = _parse_form4_xml(_SAMPLE_FORM4_XML, "Elon Musk")
    codes_seen = {r["transaction_type"] for r in rows}
    assert codes_seen == {"purchase", "sale"}
    assert len(rows) == 2  # the 'A' (award) row must be dropped


def test_parse_form4_xml_computes_dollar_amount_and_ticker():
    rows = _parse_form4_xml(_SAMPLE_FORM4_XML, "Elon Musk")
    purchase = next(r for r in rows if r["transaction_type"] == "purchase")
    assert purchase["ticker"] == "TSLA"
    assert purchase["member"] == "Elon Musk"
    assert purchase["amount_range"] == f"${1000 * 180.50:,.0f} - ${1000 * 180.50:,.0f}"


def test_parse_form4_xml_handles_missing_price_without_crashing():
    xml = _SAMPLE_FORM4_XML.replace(b"<value>180.50</value>", b"<value></value>")
    # empty value -> falsy string -> price defaults to 0 in the amount calc
    rows = _parse_form4_xml(xml, "Elon Musk")
    assert any(r["transaction_type"] == "purchase" for r in rows)


def test_resolve_cik_degrades_gracefully_without_network():
    # This sandbox's network is restricted, so this exercises the real
    # failure path — resolve_cik must return None, never raise.
    result = resolve_cik("A Name Extremely Unlikely To Be Cached Anywhere xyz123")
    assert result is None


def test_fetch_insider_trades_returns_empty_frame_with_expected_columns_when_unreachable():
    df = fetch_insider_trades(["A Name Extremely Unlikely To Be Cached Anywhere xyz123"])
    assert list(df.columns) == [
        "chamber",
        "member",
        "ticker",
        "transaction_type",
        "transaction_date",
        "disclosure_date",
        "amount_range",
        "owner",
        "asset_description",
        "disclosure_lag_days",
    ]
    assert df.empty
