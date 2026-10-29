from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from listing_ledger.api import create_app


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path / "ledger.sqlite")) as c:
        yield c


def stream(client):
    response = client.post("/api/streams")
    assert response.status_code == 201
    return response.json()["stream_id"]


def event(event_id, observed_at="2026-10-20T09:00:00Z", **changes):
    value = {
        "event_id": event_id,
        "listing_id": "jacket",
        "title": "Canvas jacket",
        "observed_at": observed_at,
        "status": "active",
        "price_minor": 8000,
        "currency": "EUR",
    }
    value.update(changes)
    return value


def post(client, sid, payload):
    return client.post(f"/api/streams/{sid}/events", json=payload)


def test_exact_retry_and_timezone_canonicalization(client):
    sid = stream(client)
    first = post(client, sid, event("one", "2026-10-20T09:00:00+02:00"))
    retry = post(client, sid, event("one", "2026-10-20T07:00:00Z"))
    assert first.status_code == 201
    assert retry.status_code == 200
    assert retry.json() == {"event": first.json()["event"], "duplicate": True}


def test_conflicting_event_id_is_409_and_sequence_does_not_advance(client):
    sid = stream(client)
    post(client, sid, event("one"))
    conflict = post(client, sid, event("one", price_minor=7000))
    next_event = post(client, sid, event("two", "2026-10-20T10:00:00Z"))
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "event_conflict"
    assert next_event.json()["event"]["sequence"] == 2


def test_correction_resolution_is_receipt_cutoff_then_observed_order(client):
    sid = stream(client)
    post(client, sid, event("first", "2026-10-20T09:00:00Z"))
    post(client, sid, event("later", "2026-10-20T12:00:00Z", price_minor=6500))
    late = post(client, sid, event("late", "2026-10-20T10:00:00Z", price_minor=7500)).json()[
        "event"
    ]
    cutoff = late["sequence"]
    side = event("side", "2026-10-20T11:00:00Z", listing_id="other")
    post(client, sid, side)
    post(client, sid, event("fix1", "2026-10-20T12:00:00Z", price_minor=6200, supersedes="later"))
    correction2 = post(
        client, sid, event("fix2", "2026-10-20T12:00:00Z", price_minor=6000, supersedes="later")
    ).json()["event"]
    final_side = event("side2", "2026-10-20T11:30:00Z", listing_id="other")
    post(client, sid, final_side)
    before = client.get(
        f"/api/streams/{sid}/listings/jacket", params={"through_sequence": cutoff}
    ).json()
    after = client.get(f"/api/streams/{sid}/listings/jacket").json()
    assert before["price_minor"] == 6500
    assert before["source_event_id"] == "later"
    assert before["as_of_sequence"] == cutoff
    assert after["price_minor"] == 6000
    assert after["source_event_id"] == "fix2"
    assert after["applied_event_ids"] == ["first", "late", "fix2"]
    assert after["last_known_price_minor"] == 6000
    assert after["as_of_sequence"] == correction2["sequence"] + 1


def test_validation_missing_zero_unknown_and_naive_time(client):
    sid = stream(client)
    bad = event("bad", "2026-10-20T09:00:00")
    assert post(client, sid, bad).status_code == 422
    zero = post(client, sid, event("zero", price_minor=0))
    assert zero.status_code == 201
    unknown = post(
        client, sid, event("unknown", "2026-10-20T10:00:00Z", status="unknown", price_minor=None)
    )
    assert unknown.status_code == 201
    projection = client.get(f"/api/streams/{sid}/listings/jacket").json()
    assert projection["status"] == "unknown"
    assert projection["price_minor"] is None
    assert projection["last_known_price_minor"] == 0


def test_correction_targets_are_restricted_and_streams_isolated(client):
    sid1, sid2 = stream(client), stream(client)
    post(client, sid1, event("base"))
    assert post(client, sid1, event("chain", supersedes="missing")).status_code == 422
    post(client, sid1, event("fix", supersedes="base"))
    assert post(client, sid1, event("chain2", supersedes="fix")).status_code == 422
    assert client.get(f"/api/streams/{sid2}/events").json()["events"] == []


def test_persistence_and_concurrent_duplicate_submission(tmp_path):
    db = tmp_path / "persist.sqlite"
    app = create_app(db)
    with TestClient(app) as client:
        sid = stream(client)
        payload = event("same", title="Mājas mētelis <script>")
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(
            pool.map(lambda _: post(TestClient(create_app(db)), sid, payload).status_code, range(8))
        )
    assert results.count(201) == 1
    assert results.count(200) == 7
    with TestClient(create_app(db)) as restarted:
        records = restarted.get(f"/api/streams/{sid}/events").json()["events"]
        assert len(records) == 1
        assert records[0]["title"] == "Mājas mētelis <script>"


def test_unknown_references_and_health(client):
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/api/streams/missing/events").status_code == 404
    assert client.post("/api/streams/missing/events", json=event("x")).status_code == 404


def test_event_schema_rejects_money_coercion_and_bad_ids(client):
    sid = stream(client)
    for payload in [
        event("bad id"),
        event("float", price_minor=1.5),
        event("bool", price_minor=True),
        event("string", price_minor="8"),
        event("extra", extra="x"),
    ]:
        assert post(client, sid, payload).status_code == 422


def test_demo_route_preserves_retry_attempt_but_only_saves_six_events(client):
    demo = client.post("/api/demo")
    assert demo.status_code == 201
    body = demo.json()
    assert len(body["attempts"]) == 6
    assert len(body["events"]) == 5
    assert body["attempts"][3]["duplicate"] is True
    assert body["attempts"][3]["sequence"] == body["attempts"][1]["sequence"]


def test_listing_projection_before_first_observation_and_sql_shaped_id(client):
    sid = stream(client)
    assert client.get(f"/api/streams/{sid}/listings/not-yet").status_code == 404
    assert post(client, sid, event("x' OR 1=1 --")).status_code == 422


def test_api_requires_timezone_aware_iso_timestamp_strings(client):
    sid = stream(client)
    for index, value in enumerate([0, 1730000000, "1730000000"]):
        response = post(client, sid, event(f"bad-time-{index}", value))
        assert response.status_code == 422
    accepted = post(client, sid, event("aware", "2026-10-20T09:00:00+02:00"))
    assert accepted.status_code == 201
    assert accepted.json()["event"]["observed_at"] == "2026-10-20T07:00:00Z"


def test_price_minor_has_browser_exact_technical_bound(client):
    sid = stream(client)
    for index, price in enumerate([True, 1.5, "8", 1_000_000_000_001, 9_007_199_254_740_993]):
        assert post(client, sid, event(f"bad-price-{index}", price_minor=price)).status_code == 422
    assert post(client, sid, event("zero-price", price_minor=0)).status_code == 201
    assert post(client, sid, event("max-price", price_minor=1_000_000_000_000)).status_code == 201


def test_store_closes_connections_after_success_and_error_rollback(tmp_path, monkeypatch):
    import sqlite3

    from listing_ledger.models import Event as LedgerEvent
    from listing_ledger.store import LedgerStore

    store = LedgerStore(tmp_path / "connections.sqlite")
    real_connect = sqlite3.connect
    connections = []

    def tracked_connect(*args, **kwargs):
        connection = real_connect(*args, **kwargs)
        connections.append(connection)
        return connection

    monkeypatch.setattr("listing_ledger.store.sqlite3.connect", tracked_connect)
    sid = store.create_stream()
    base = LedgerEvent.model_validate(event("base"))
    store.add_event(sid, base)
    with pytest.raises(ValueError, match="supersedes must reference"):
        store.add_event(sid, LedgerEvent.model_validate(event("retry", supersedes="missing")))
    valid = store.add_event(sid, LedgerEvent.model_validate(event("retry")))[0]
    assert valid.sequence == 2
    assert len(connections) >= 4
    for connection in connections:
        with pytest.raises(sqlite3.ProgrammingError, match="closed"):
            connection.execute("SELECT 1")
