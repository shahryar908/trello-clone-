"""WebSocket rooms.

The ConnectionManager tests below are a regression suite for a real production
bug: rooms stored ONE socket per user, so opening the board on a second device
silently evicted the first. Comments only appeared after a refresh. The fix was
to store a set of sockets per user, and these tests are what keeps it fixed.
"""

import anyio
import pytest
from starlette.websockets import WebSocketDisconnect

from app.ws import ConnectionManager


class FakeSocket:
    """Just enough WebSocket for the manager: it accepts and it records."""

    def __init__(self, fails: bool = False) -> None:
        self.sent: list[dict] = []
        self.fails = fails

    async def accept(self) -> None:
        pass

    async def send_json(self, message: dict) -> None:
        if self.fails:
            raise RuntimeError("socket is already closed")
        self.sent.append(message)


# --- ConnectionManager, in isolation ---------------------------------------


def test_both_devices_of_one_user_receive_a_broadcast():
    manager = ConnectionManager()
    laptop, phone = FakeSocket(), FakeSocket()
    message = {"type": "comment_created", "comment": {"id": 1}}

    async def scenario():
        await manager.connect(board_id=1, user_id=7, websocket=laptop)
        await manager.connect(board_id=1, user_id=7, websocket=phone)
        await manager.broadcast(1, message)

    anyio.run(scenario)

    # the bug: the phone connecting replaced the laptop, so laptop.sent was empty
    assert laptop.sent == [message]
    assert phone.sent == [message]


def test_a_user_stays_present_until_their_last_socket_leaves():
    manager = ConnectionManager()
    laptop, phone = FakeSocket(), FakeSocket()

    async def scenario():
        await manager.connect(1, 7, laptop)
        await manager.connect(1, 7, phone)

    anyio.run(scenario)

    manager.disconnect(1, 7, phone)
    assert list(manager.rooms[1].keys()) == [7], "closing one tab must not sign the user out"

    manager.disconnect(1, 7, laptop)
    assert manager.rooms == {}, "the empty board should be cleaned up entirely"


def test_disconnecting_an_unknown_socket_is_harmless():
    # reconnect loops fire disconnect for sockets the manager has already dropped
    manager = ConnectionManager()
    manager.disconnect(1, 7, FakeSocket())
    assert manager.rooms == {}


def test_broadcasts_do_not_leak_between_boards():
    manager = ConnectionManager()
    on_board_1, on_board_2 = FakeSocket(), FakeSocket()

    async def scenario():
        await manager.connect(1, 7, on_board_1)
        await manager.connect(2, 8, on_board_2)
        await manager.broadcast(1, {"type": "comment_created"})

    anyio.run(scenario)

    assert len(on_board_1.sent) == 1
    assert on_board_2.sent == []


def test_one_dead_socket_does_not_stop_the_rest_of_the_broadcast():
    manager = ConnectionManager()
    dead, alive = FakeSocket(fails=True), FakeSocket()

    async def scenario():
        await manager.connect(1, 7, dead)
        await manager.connect(1, 8, alive)
        await manager.broadcast(1, {"type": "comment_created"})

    anyio.run(scenario)

    assert alive.sent == [{"type": "comment_created"}]


# --- the real endpoint ------------------------------------------------------


def test_connecting_without_a_valid_token_is_refused(client, workspace):
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(f"/ws/boards/{workspace.board_id}?token=nonsense") as sock:
            sock.receive_json()
    assert exc.value.code == 4401


def test_a_non_member_cannot_join_a_board_room(client, workspace, make_user):
    outsider = make_user("outsider@example.com")
    url = f"/ws/boards/{workspace.board_id}?token={outsider.token}"

    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(url) as sock:
            sock.receive_json()
    assert exc.value.code == 4403


def test_joining_announces_presence(client, workspace):
    url = f"/ws/boards/{workspace.board_id}?token={workspace.owner.token}"
    with client.websocket_connect(url) as sock:
        message = sock.receive_json()

    assert message["type"] == "presence_changed"
    assert [u["email"] for u in message["users"]] == [workspace.owner.email]


def test_a_comment_sent_over_the_socket_is_broadcast_and_persisted(client, workspace):
    url = f"/ws/boards/{workspace.board_id}?token={workspace.owner.token}"

    with client.websocket_connect(url) as sock:
        sock.receive_json()  # presence
        sock.send_json(
            {"type": "comment_create", "issue_id": workspace.issue_id, "body": "ship it"}
        )
        broadcast = sock.receive_json()

    assert broadcast["type"] == "comment_created"
    assert broadcast["comment"]["body"] == "ship it"
    assert broadcast["comment"]["author"]["email"] == workspace.owner.email

    # and it really hit the database, not just the socket
    stored = client.get(
        f"/issues/{workspace.issue_id}/comments", headers=workspace.owner.headers
    ).json()
    assert [c["body"] for c in stored] == ["ship it"]


def test_bad_input_returns_an_error_without_closing_the_socket(client, workspace):
    url = f"/ws/boards/{workspace.board_id}?token={workspace.owner.token}"

    with client.websocket_connect(url) as sock:
        sock.receive_json()  # presence

        sock.send_json({"type": "comment_create", "issue_id": workspace.issue_id, "body": "   "})
        assert sock.receive_json()["type"] == "error"

        sock.send_json({"type": "something_else"})
        assert sock.receive_json()["type"] == "error"

        sock.send_json({"type": "comment_create", "issue_id": 99999, "body": "hi"})
        assert sock.receive_json()["type"] == "error"

        # still usable after three rejections
        sock.send_json({"type": "comment_create", "issue_id": workspace.issue_id, "body": "ok"})
        assert sock.receive_json()["type"] == "comment_created"
