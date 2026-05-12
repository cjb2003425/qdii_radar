from datetime import datetime

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch

import server

client = TestClient(server.app)


def make_quote(code: str, price: float = 1.2345, rate: float = 1.23):
    return {
        "f12": code,
        "f2": price,
        "f3": rate,
        "f17": price,
        "f18": price,
    }


# ============================================================================
# Test 1: Cached slow fields returned without blocking
# ============================================================================

def test_api_funds_uses_cached_slow_fields_without_blocking(monkeypatch):
    monkeypatch.setattr(
        server.data.funds_loader, "QDII_FUNDS", [{"code": "513100", "name": "纳指ETF"}]
    )
    monkeypatch.setattr(
        server, "fetch_quotes_for_codes", AsyncMock(return_value=[make_quote("513100")])
    )
    monkeypatch.setattr(server, "fetch_limits_for_codes", AsyncMock(return_value={}))
    monkeypatch.setattr(
        server,
        "get_cached_limit",
        lambda code: {"exists": True, "fresh": True, "value": "限额1000元"},
    )
    monkeypatch.setattr(
        server,
        "get_cached_one_year_change",
        lambda code: {
            "exists": True,
            "fresh": True,
            "available": True,
            "value": 12.34,
        },
    )

    response = client.get("/api/funds?codes=513100")

    assert response.status_code == 200
    body = response.json()
    assert body[0]["limitText"] == "限额1000元"
    assert body[0]["ytdChange"] == 12.34
    assert body[0]["ytdChangeAvailable"] is True


# ============================================================================
# Test 2: Small cold-cache requests should fill YTD synchronously
# ============================================================================

def test_api_funds_fills_ytd_synchronously_for_small_cold_cache_requests(monkeypatch):
    monkeypatch.setattr(
        server.data.funds_loader, "QDII_FUNDS", [{"code": "513100", "name": "纳指ETF"}]
    )
    monkeypatch.setattr(
        server, "fetch_quotes_for_codes", AsyncMock(return_value=[make_quote("513100")])
    )
    monkeypatch.setattr(server, "fetch_limits_for_codes", AsyncMock(return_value={}))
    monkeypatch.setattr(
        server, "get_cached_limit", lambda code: {"exists": False, "fresh": False, "value": "—"}
    )
    monkeypatch.setattr(
        server,
        "get_cached_one_year_change",
        lambda code: {"exists": False, "fresh": False, "available": False, "value": 0},
    )
    monkeypatch.setattr(
        server,
        "get_one_year_change",
        lambda code, is_exchange_traded: {"percentage_change": 12.34, "available": True},
    )
    monkeypatch.setattr(server, "schedule_history_refresh", lambda codes, flags: (_ for _ in ()).throw(AssertionError("small cold-cache requests should not schedule history refresh")))

    response = client.get("/api/funds?codes=513100")

    assert response.status_code == 200
    body = response.json()
    assert body[0]["limitText"] == "—"
    assert body[0]["ytdChange"] == 12.34
    assert body[0]["ytdChangeAvailable"] is True


# ============================================================================
# Test 3: Large missing-history requests should still use background refresh
# ============================================================================

def test_api_funds_schedules_background_refresh_for_large_missing_history_cache(monkeypatch):
    scheduled = []
    funds = [
        {"code": "513100", "name": "纳指ETF1"},
        {"code": "513101", "name": "纳指ETF2"},
        {"code": "513102", "name": "纳指ETF3"},
        {"code": "513103", "name": "纳指ETF4"},
    ]

    def fake_schedule_limit_refresh(codes):
        scheduled.append(("limit", tuple(codes)))

    def fake_schedule_history_refresh(codes, exchange_traded_flags):
        scheduled.append(("history", tuple(codes)))

    monkeypatch.setattr(server.data.funds_loader, "QDII_FUNDS", funds)
    monkeypatch.setattr(
        server,
        "fetch_quotes_for_codes",
        AsyncMock(return_value=[make_quote(f["code"]) for f in funds]),
    )
    monkeypatch.setattr(server, "fetch_limits_for_codes", AsyncMock(return_value={}))
    monkeypatch.setattr(
        server, "get_cached_limit", lambda code: {"exists": False, "fresh": False, "value": "—"}
    )
    monkeypatch.setattr(
        server,
        "get_cached_one_year_change",
        lambda code: {"exists": False, "fresh": False, "available": False, "value": 0},
    )
    monkeypatch.setattr(server, "schedule_limit_refresh", fake_schedule_limit_refresh)
    monkeypatch.setattr(server, "schedule_history_refresh", fake_schedule_history_refresh)
    monkeypatch.setattr(
        server,
        "get_one_year_change",
        lambda code, is_exchange_traded: (_ for _ in ()).throw(AssertionError("large requests should not synchronously calculate YTD")),
    )

    response = client.get("/api/funds?codes=513100,513101,513102,513103")

    assert response.status_code == 200
    body = response.json()
    assert all(item["ytdChange"] == 0 for item in body)
    assert all(item["ytdChangeAvailable"] is False for item in body)
    assert ("history", ("513100", "513101", "513102", "513103")) in scheduled


# ============================================================================
# Test 4: Background refresh scheduled for stale cache
# ============================================================================

def test_api_funds_schedules_background_refresh_for_stale_cache(monkeypatch):
    scheduled = []

    def fake_schedule_limit_refresh(codes):
        scheduled.append(("limit", tuple(codes)))

    def fake_schedule_history_refresh(codes, exchange_traded_flags):
        scheduled.append(("history", tuple(codes)))

    monkeypatch.setattr(
        server.data.funds_loader, "QDII_FUNDS", [{"code": "513100", "name": "纳指ETF"}]
    )
    monkeypatch.setattr(
        server, "fetch_quotes_for_codes", AsyncMock(return_value=[make_quote("513100")])
    )
    monkeypatch.setattr(server, "fetch_limits_for_codes", AsyncMock(return_value={}))
    # stale = exists but not fresh
    monkeypatch.setattr(
        server,
        "get_cached_limit",
        lambda code: {"exists": True, "fresh": False, "value": "限额1000元"},
    )
    monkeypatch.setattr(
        server,
        "get_cached_one_year_change",
        lambda code: {
            "exists": True,
            "fresh": False,
            "available": True,
            "value": 12.34,
        },
    )
    monkeypatch.setattr(server, "schedule_limit_refresh", fake_schedule_limit_refresh)
    monkeypatch.setattr(server, "schedule_history_refresh", fake_schedule_history_refresh)

    response = client.get("/api/funds?codes=513100")

    assert response.status_code == 200
    assert ("limit", ("513100",)) in scheduled
    assert ("history", ("513100",)) in scheduled


# ============================================================================
# Test 5: In-flight dedupe for limit refresh scheduling
# ============================================================================

def test_schedule_limit_refresh_skips_code_already_inflight(monkeypatch):
    # Ensure the in-flight set exists on the server module
    if not hasattr(server, "limit_refresh_inflight"):
        monkeypatch.setattr(server, "limit_refresh_inflight", set())

    server.limit_refresh_inflight.add("513100")
    try:
        scheduled = []

        def fake_schedule_limit_refresh(codes):
            # Only schedule codes not already in-flight
            codes_to_schedule = [c for c in codes if c not in server.limit_refresh_inflight]
            if codes_to_schedule:
                scheduled.append(("limit", tuple(codes_to_schedule)))

        monkeypatch.setattr(
            server.data.funds_loader, "QDII_FUNDS", [{"code": "513100", "name": "纳指ETF"}]
        )
        monkeypatch.setattr(
            server, "fetch_quotes_for_codes", AsyncMock(return_value=[make_quote("513100")])
        )
        monkeypatch.setattr(server, "fetch_limits_for_codes", AsyncMock(return_value={}))
        monkeypatch.setattr(
            server,
            "get_cached_limit",
            lambda code: {"exists": False, "fresh": False, "value": "—"},
        )
        monkeypatch.setattr(
            server,
            "get_cached_one_year_change",
            lambda code: {"exists": False, "fresh": False, "available": False, "value": 0},
        )
        monkeypatch.setattr(server, "schedule_limit_refresh", fake_schedule_limit_refresh)
        monkeypatch.setattr(
            server, "schedule_history_refresh", lambda codes, flags: None
        )

        response = client.get("/api/funds?codes=513100")

        assert response.status_code == 200
        # Because 513100 is already in-flight, no new scheduling should happen
        assert scheduled == []
    finally:
        server.limit_refresh_inflight.discard("513100")


# ============================================================================
# Test 6: In-flight dedupe for history refresh scheduling
# ============================================================================

def test_schedule_history_refresh_skips_code_already_inflight(monkeypatch):
    if not hasattr(server, "history_refresh_inflight"):
        monkeypatch.setattr(server, "history_refresh_inflight", set())

    server.history_refresh_inflight.add("513100")
    try:
        scheduled = []

        def fake_schedule_history_refresh(codes, exchange_traded_flags):
            codes_to_schedule = [c for c in codes if c not in server.history_refresh_inflight]
            if codes_to_schedule:
                scheduled.append(("history", tuple(codes_to_schedule)))

        monkeypatch.setattr(
            server.data.funds_loader, "QDII_FUNDS", [{"code": "513100", "name": "纳指ETF"}]
        )
        monkeypatch.setattr(
            server, "fetch_quotes_for_codes", AsyncMock(return_value=[make_quote("513100")])
        )
        monkeypatch.setattr(server, "fetch_limits_for_codes", AsyncMock(return_value={}))
        monkeypatch.setattr(
            server,
            "get_cached_limit",
            lambda code: {"exists": False, "fresh": False, "value": "—"},
        )
        monkeypatch.setattr(
            server,
            "get_cached_one_year_change",
            lambda code: {"exists": False, "fresh": False, "available": False, "value": 0},
        )
        monkeypatch.setattr(server, "schedule_limit_refresh", lambda codes: None)
        monkeypatch.setattr(server, "schedule_history_refresh", fake_schedule_history_refresh)

        response = client.get("/api/funds?codes=513100")

        assert response.status_code == 200
        assert scheduled == []
    finally:
        server.history_refresh_inflight.discard("513100")


# ============================================================================
# Test 7: YTD historical NAV should use first NAV of current year as base
# ============================================================================

def test_fetch_historical_nav_eastmoney_uses_first_nav_of_current_year_as_base(monkeypatch):
    current_year = datetime.now().year
    df = pd.DataFrame(
        [
            {"净值日期": f"{current_year - 1}-12-31", "累计净值": 90.0},
            {"净值日期": f"{current_year}-01-03", "累计净值": 100.0},
            {"净值日期": f"{current_year}-03-10", "累计净值": 110.0},
            {"净值日期": f"{current_year}-05-10", "累计净值": 120.0},
        ]
    )
    fake_ak = MagicMock()
    fake_ak.fund_open_fund_info_em.return_value = df
    monkeypatch.setattr(server, "ak", fake_ak)

    result = server.fetch_historical_nav_eastmoney("513100")

    assert result is not None
    assert result["nav_1_year_ago"] == 100.0
    assert result["percentage_change"] == 20.0
    assert result["days_found"] == 3


# ============================================================================
# Test 8: Exchange-traded funds should also use cumulative NAV YTD path
# ============================================================================

def test_get_one_year_change_uses_nav_ytd_for_exchange_traded_funds(monkeypatch):
    fake_session = MagicMock()

    monkeypatch.setattr(server, "get_historical_cache", lambda session, code: None)
    monkeypatch.setattr(
        server,
        "fetch_historical_nav_eastmoney",
        lambda code: {"nav_1_year_ago": 100.0, "percentage_change": 12.34, "days_found": 5},
    )

    def fail_if_called(*args, **kwargs):
        raise AssertionError("fetch_historical_etf_price should not be called for YTD calculation")

    monkeypatch.setattr(server, "fetch_historical_etf_price", fail_if_called)
    monkeypatch.setattr(server, "set_historical_cache", lambda *args, **kwargs: None)

    with patch("notifications.models.get_db", return_value=fake_session):
        result = server.get_one_year_change("513100", True)

    assert result == {"percentage_change": 12.34, "available": True}
    fake_session.close.assert_called_once()


# ============================================================================
# Test 9: Historical cache with mismatched semantic should be ignored
# ============================================================================

def test_get_historical_cache_ignores_semantic_mismatch():
    cached = MagicMock()
    cached.cached_at = datetime.utcnow()
    cached.metric_semantic = "one_year_v1"
    cached.percentage_change = -24.48
    cached.days_calculated = 243

    fake_query = MagicMock()
    fake_query.filter_by.return_value.first.return_value = cached

    fake_session = MagicMock()
    fake_session.query.return_value = fake_query

    result = server.get_historical_cache(fake_session, "161130")

    assert result is None
