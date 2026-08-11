from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlmodel import Session, select

from .auth import decode_token
from .database import engine
from .models import Board, Comment, Issue, Membership, User

router = APIRouter()


class ConnectionManager:
    """In-memory rooms: board_id -> {user_id: websocket}. Doubles as presence data."""

    def __init__(self) -> None:
        self.rooms: dict[int, dict[int, WebSocket]] = {}

    async def connect(self, board_id: int, user_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        room = self.rooms.setdefault(board_id, {})
        old = room.get(user_id)
        room[user_id] = websocket
        if old is not None:  # a reconnect replaces the previous socket
            try:
                await old.close()
            except Exception:
                pass

    def disconnect(self, board_id: int, user_id: int, websocket: WebSocket) -> None:
        room = self.rooms.get(board_id)
        if room and room.get(user_id) is websocket:
            del room[user_id]
            if not room:
                del self.rooms[board_id]

    async def broadcast(self, board_id: int, message: dict) -> None:
        for ws in list(self.rooms.get(board_id, {}).values()):
            try:
                await ws.send_json(message)
            except Exception:
                pass


manager = ConnectionManager()


def presence_message(board_id: int, session: Session) -> dict:
    user_ids = list(manager.rooms.get(board_id, {}).keys())
    users = []
    if user_ids:
        for u in session.exec(select(User).where(User.id.in_(user_ids))):
            users.append({"id": u.id, "email": u.email})
    return {"type": "presence_changed", "users": users}


async def handle_message(
    websocket: WebSocket, board_id: int, user_id: int, message: object
) -> None:
    if not isinstance(message, dict) or message.get("type") != "comment_create":
        await websocket.send_json({"type": "error", "detail": "Unknown message type"})
        return
    issue_id = message.get("issue_id")
    body = (message.get("body") or "").strip()
    if not body:
        await websocket.send_json({"type": "error", "detail": "Comment body cannot be empty"})
        return
    with Session(engine) as session:
        issue = session.get(Issue, issue_id) if isinstance(issue_id, int) else None
        if issue is None or issue.board_id != board_id:
            await websocket.send_json({"type": "error", "detail": "Issue not found on this board"})
            return
        author = session.get(User, user_id)
        comment = Comment(body=body, issue_id=issue.id, user_id=user_id)
        session.add(comment)
        session.commit()
        session.refresh(comment)
        payload = {
            "type": "comment_created",
            "comment": {
                "id": comment.id,
                "issue_id": comment.issue_id,
                "body": comment.body,
                "created_at": comment.created_at.isoformat(),
                "author": {"id": author.id, "email": author.email},
            },
        }
    await manager.broadcast(board_id, payload)


@router.websocket("/ws/boards/{board_id}")
async def board_ws(websocket: WebSocket, board_id: int, token: str = ""):
    # Browsers can't set headers on a WebSocket, hence the token query param.
    try:
        user_id = decode_token(token)
    except Exception:
        await websocket.close(code=4401)
        return

    with Session(engine) as session:
        user = session.get(User, user_id)
        board = session.get(Board, board_id)
        membership = None
        if user is not None and board is not None:
            membership = session.exec(
                select(Membership).where(
                    Membership.org_id == board.organization_id,
                    Membership.user_id == user.id,
                )
            ).first()
        if user is None or board is None or membership is None:
            await websocket.close(code=4403)
            return
        await manager.connect(board_id, user_id, websocket)
        await manager.broadcast(board_id, presence_message(board_id, session))

    try:
        while True:
            try:
                message = await websocket.receive_json()
            except WebSocketDisconnect:
                raise
            except Exception:
                # bad JSON never closes the connection — reply with an error instead
                await websocket.send_json({"type": "error", "detail": "Invalid JSON"})
                continue
            await handle_message(websocket, board_id, user_id, message)
    except WebSocketDisconnect:
        manager.disconnect(board_id, user_id, websocket)
        with Session(engine) as session:
            await manager.broadcast(board_id, presence_message(board_id, session))
