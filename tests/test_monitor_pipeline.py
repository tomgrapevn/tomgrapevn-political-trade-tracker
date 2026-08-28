import pandas as pd
import pytest

from tracker.data.rss_monitor import Article
from tracker.pipeline import monitor as monitor_module


@pytest.fixture(autouse=True)
def isolated_state(tmp_path, monkeypatch):
    state_file = tmp_path / "rss_monitor_state.json"
    monkeypatch.setattr("tracker.data.rss_monitor._STATE_FILE", state_file)
    yield state_file


def _escalation_article(link="https://example.com/iran-strikes"):
    return Article(
        source="test_feed",
        title="Iran strikes Israel with ballistic missiles",
        link=link,
        description="Overnight barrage escalates conflict",
        published=None,
    )


def test_run_monitor_check_generates_validated_alert_and_opens_a_position(monkeypatch):
    monkeypatch.setattr(monitor_module, "fetch_all_feeds", lambda: [_escalation_article()])

    result = monitor_module.run_monitor_check()

    assert result.n_articles_fetched == 1
    assert len(result.new_alerts) == 1
    assert result.new_alerts[0].rule.validated
    assert result.exit_reminders == []

    state = monitor_module.load_state()
    assert len(state["open_signals"]) == 1
    assert state["open_signals"][0]["category"] == "middle_east_escalation"


def test_run_monitor_check_dedupes_the_same_article_across_runs(monkeypatch):
    monkeypatch.setattr(monitor_module, "fetch_all_feeds", lambda: [_escalation_article()])

    first = monitor_module.run_monitor_check()
    second = monitor_module.run_monitor_check()

    assert len(first.new_alerts) == 1
    assert len(second.new_alerts) == 0
    assert second.n_articles_new == 0


def test_run_monitor_check_only_fires_once_per_category_per_run(monkeypatch):
    articles = [
        _escalation_article(link="https://example.com/a1"),
        _escalation_article(link="https://example.com/a2"),
    ]
    monkeypatch.setattr(monitor_module, "fetch_all_feeds", lambda: articles)

    result = monitor_module.run_monitor_check()

    assert len(result.new_alerts) == 1  # same category, second headline suppressed


def test_exit_reminder_fires_once_holding_period_has_elapsed(monkeypatch):
    monkeypatch.setattr(monitor_module, "fetch_all_feeds", lambda: [])
    past_date = (pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=1)).isoformat()
    state = {
        "seen_links": [],
        "open_signals": [
            {
                "category": "middle_east_escalation",
                "fired_at": past_date,
                "exit_date": past_date,
                "tickers_long": ["XLE"],
                "tickers_short": ["JETS"],
            }
        ],
    }
    monkeypatch.setattr(monitor_module, "load_state", lambda: state)
    saved = {}
    monkeypatch.setattr(monitor_module, "save_state", lambda s: saved.update(s))

    result = monitor_module.run_monitor_check()

    assert len(result.exit_reminders) == 1
    assert "XLE" in result.exit_reminders[0].note
    assert saved["open_signals"] == []  # closed position removed from state


def test_format_email_body_includes_disclaimer_and_sections(monkeypatch):
    monkeypatch.setattr(monitor_module, "fetch_all_feeds", lambda: [_escalation_article()])
    result = monitor_module.run_monitor_check()
    body = monitor_module.format_email_body(result)
    assert "Not financial advice" in body
    assert "POSSIBLE TRADE SIGNAL" in body
    assert "XLE" in body


def test_format_email_body_handles_nothing_to_report():
    empty_result = monitor_module.MonitorResult(
        checked_at=pd.Timestamp.now(tz="UTC").to_pydatetime(), n_articles_fetched=5, n_articles_new=0
    )
    body = monitor_module.format_email_body(empty_result)
    assert "Not financial advice" in body
    assert "POSSIBLE TRADE SIGNAL" not in body
