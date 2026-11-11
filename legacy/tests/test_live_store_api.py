import asyncio
import importlib

import pandas as pd
import pytest

import live


def snap(ltp, tt="10:58"):
    return {"market": {"totals": {"tradeTime": tt}}, "session": {"date": "2026-11-11", "isOpen": True},
            "quotes": {"AAA": {"symbol": "AAA", "ltp": ltp, "volume": 10}, "BBB": {"symbol": "BBB", "ltp": 5, "volume": 1}},
            "tradeTime": tt}


def test_feed_publishes_only_changes_to_matching_subscribers():
    async def go():
        feed = live.LiveFeed()
        await feed.apply(snap(10))                       # first snapshot primes state, publishes nothing
        a, all_ = feed.subscribe({"AAA"}), feed.subscribe(None)
        changed = await feed.apply(snap(11, "10:59"))
        assert changed == {"AAA"}
        ev = a.queue.get_nowait()
        assert ev["event"] == "quote" and ev["data"]["ltp"] == 11 and "receivedMs" in ev["data"]["_meta"]
        kinds = sorted(all_.queue.get_nowait()["event"] for _ in range(all_.queue.qsize()))
        assert kinds == ["market", "quote"]
        assert await feed.apply(snap(11, "10:59")) == set()   # identical tick: nothing
        feed.unsubscribe(a)
        assert a not in feed._subs
    asyncio.run(go())


def test_slow_subscriber_drops_oldest():
    async def go():
        sub = live.Subscriber(None, asyncio.Queue(2))
        for i in range(3):
            sub.offer({"id": i})
        assert sub.dropped == 1 and sub.queue.get_nowait()["id"] == 1
    asyncio.run(go())


@pytest.fixture
def tmp_store(tmp_path, monkeypatch):
    import store
    monkeypatch.setattr(store, "DB", str(tmp_path / "m.sqlite"))
    return store


def test_append_eod_never_overwrites_page_bars(tmp_store):
    st = tmp_store
    with st.connect() as con:
        con.execute("INSERT INTO bars VALUES ('AAA','2026-11-11',1,2,0.5,1.5,100,5,'page')")
    q = {"AAA": {"ltp": 9, "close": 9, "open": 9, "high": 9, "low": 9, "volume": 50},
         "BBB": {"ltp": 3, "close": 3, "open": 3, "high": 3, "low": 3, "volume": 10},
         "CCC": {"ltp": 3, "volume": 0}}
    n = st.append_eod({"session": {"date": "2026-11-11", "tradingDay": True}, "quotes": q})
    assert n == 2
    assert st.bars("AAA")["close"].iloc[-1] == 1.5 and st.bars("BBB")["close"].iloc[-1] == 3
    assert st.bars("CCC").empty


def test_minute_bars_from_cumulative_volume(tmp_store):
    st = tmp_store
    t0 = int(pd.Timestamp("2026-11-11 10:01", tz="Asia/Dhaka").timestamp() * 1000)
    st.record_ticks([{"symbol": "AAA", "ltp": 10, "volume": 100}], t0, "x")
    st.record_ticks([{"symbol": "AAA", "ltp": 11, "volume": 160}], t0 + 20_000, "x")
    st.record_ticks([{"symbol": "AAA", "ltp": 9, "volume": 200}], t0 + 70_000, "x")
    m = st.minute_bars("AAA", "2026-11-11")
    assert list(m["volume"]) == [160, 40] and list(m["high"]) == [11, 9] and m["close"].iloc[0] == 11


# ----------------------------------------------------------------- API contract (no network: lifespan not started)
@pytest.fixture
def client(monkeypatch):
    from fastapi.testclient import TestClient
    api = importlib.import_module("api")
    feed = live.LiveFeed()
    asyncio.run(feed.apply(snap(10)))
    api.S.feed = feed
    api.app.state.feed = feed
    return TestClient(api.app)


def test_health_and_request_id(client):
    r = client.get("/api/v1/health", headers={"X-Request-ID": "abc123"})
    assert r.status_code == 200 and r.headers["x-request-id"] == "abc123" and "server-timing" in r.headers


def test_quotes_envelope(client):
    r = client.get("/api/v1/quotes?symbols=aaa,ZZZ")
    body = r.json()
    assert r.status_code == 200 and [q["symbol"] for q in body["data"]] == ["AAA"]
    assert body["meta"]["requestId"] and body["meta"]["disclaimer"]


def test_errors_are_problem_json(client):
    r = client.get("/api/v1/stocks/bad%20sym")
    assert r.status_code == 422 and r.headers["content-type"].startswith("application/problem+json")
    assert r.json()["requestId"]
    r = client.get("/api/v1/quotes?symbols=bad!")
    assert r.status_code == 400 and r.json()["title"] == "Bad request"
