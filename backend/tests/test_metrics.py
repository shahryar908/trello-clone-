"""Instrumentation.

Metrics live in a process-wide registry, so they carry over between tests.
Every test here reads a value before and after and asserts on the *delta* —
never on an absolute number.
"""

from prometheus_client import REGISTRY

from app import ws as ws_module


def read(name: str, labels: dict | None = None) -> float:
    return REGISTRY.get_sample_value(name, labels or {}) or 0.0


def test_requests_are_counted_by_status(client):
    before_ok = read(
        "tack_http_requests_total", {"method": "GET", "path": "/health", "status": "200"}
    )

    client.get("/health")
    client.get("/health")

    after_ok = read(
        "tack_http_requests_total", {"method": "GET", "path": "/health", "status": "200"}
    )
    assert after_ok - before_ok == 2


def test_failures_are_counted_separately_from_successes(client):
    labels = {"method": "GET", "path": "/orgs", "status": "401"}
    before = read("tack_http_requests_total", labels)

    client.get("/orgs")  # no token

    assert read("tack_http_requests_total", labels) - before == 1


def test_the_route_template_is_the_label_not_the_url(client, workspace):
    """The cardinality guard: /boards/1 and /boards/2 are ONE time series."""
    labels = {"method": "GET", "path": "/boards/{board_id}", "status": "200"}
    before = read("tack_http_requests_total", labels)

    h = workspace.owner.headers
    other = client.post(f"/orgs/{workspace.org_id}/boards", json={"title": "Two"}, headers=h).json()
    client.get(f"/boards/{workspace.board_id}", headers=h)
    client.get(f"/boards/{other['id']}", headers=h)

    # both requests landed on the same series, keyed by the template
    assert read("tack_http_requests_total", labels) - before == 2
    # and no series was created for the literal path
    assert (
        REGISTRY.get_sample_value(
            "tack_http_requests_total",
            {"method": "GET", "path": f"/boards/{workspace.board_id}", "status": "200"},
        )
        is None
    )


def test_unmatched_routes_do_not_mint_a_series_per_url(client):
    """A scanner hitting random paths must not be able to fill up Prometheus."""
    before = read(
        "tack_http_requests_total",
        {"method": "GET", "path": "__unmatched__", "status": "404"},
    )

    client.get("/wp-admin")
    client.get("/.env")

    after = read(
        "tack_http_requests_total",
        {"method": "GET", "path": "__unmatched__", "status": "404"},
    )
    assert after - before == 2


def test_latency_is_observed(client):
    labels = {"method": "GET", "path": "/health"}
    before = read("tack_http_request_duration_seconds_count", labels)
    client.get("/health")
    assert read("tack_http_request_duration_seconds_count", labels) - before == 1


def test_signups_are_counted(client, make_user):
    before = read("tack_signups_total")
    make_user("counted@example.com")
    assert read("tack_signups_total") - before == 1


def test_a_rejected_signup_is_not_counted(client, make_user):
    make_user("taken@example.com")
    before = read("tack_signups_total")

    duplicate = client.post(
        "/auth/signup", json={"email": "taken@example.com", "password": "whatever12"}
    )

    assert duplicate.status_code == 409
    assert read("tack_signups_total") - before == 0


def test_comments_created_over_the_socket_are_counted(client, workspace):
    before = read("tack_comments_created_total")
    url = f"/ws/boards/{workspace.board_id}?token={workspace.owner.token}"

    with client.websocket_connect(url) as sock:
        sock.receive_json()  # presence
        sock.send_json({"type": "comment_create", "issue_id": workspace.issue_id, "body": "hi"})
        sock.receive_json()

    assert read("tack_comments_created_total") - before == 1


def test_connection_gauges_track_the_rooms(client):
    manager = ws_module.ConnectionManager()

    class FakeSocket:
        async def accept(self):
            pass

    import anyio

    laptop, phone, other_board = FakeSocket(), FakeSocket(), FakeSocket()

    async def scenario():
        await manager.connect(1, 7, laptop)
        await manager.connect(1, 7, phone)
        await manager.connect(2, 8, other_board)

    anyio.run(scenario)

    assert read("tack_websocket_connections") == 3
    assert read("tack_websocket_rooms") == 2

    manager.disconnect(1, 7, phone)
    assert read("tack_websocket_connections") == 2
    assert read("tack_websocket_rooms") == 2, "user is still on board 1 from the laptop"

    manager.disconnect(1, 7, laptop)
    manager.disconnect(2, 8, other_board)
    assert read("tack_websocket_connections") == 0
    assert read("tack_websocket_rooms") == 0


def test_a_stale_disconnect_cannot_push_the_gauge_negative(client):
    manager = ws_module.ConnectionManager()
    manager.disconnect(99, 99, object())
    assert read("tack_websocket_connections") >= 0
