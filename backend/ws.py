from fastapi import FastAPI, WebSocket
from fastapi.websockets import WebSocketDisconnect
import random


app = FastAPI()


rooms: dict[str, list[dict]] = {}


@app.websocket("/connect")
async def connect(websocket: WebSocket):
    await websocket.accept()

    user_id = None
    board_id = None

    try:
        while True:
            data = await websocket.receive_json()
            print(data)

            if data["type"] == "join":

                board_id = data["boardId"]

                if board_id not in rooms:
                    rooms[board_id] = []

                user_id = random.randint(1000, 9999)

                for user in rooms[board_id]:
                    await user["socket"].send_json({
                        "type": "join",
                        "userId": user_id
                    })

                rooms[board_id].append({
                    "userId": user_id,
                    "socket": websocket
                })

                users = [
                    {"id": user["userId"]}
                    for user in rooms[board_id]
                    if user["userId"] != user_id
                ]

                await websocket.send_json({
                    "type": "initial_state",
                    "users": users
                })

    except WebSocketDisconnect:
        if board_id and user_id:
            rooms[board_id] = [
                user
                for user in rooms[board_id]
                if user["userId"] != user_id
            ]
            if not rooms[board_id]:
                del rooms[board_id]
            else:
                for user in rooms[board_id]:
                    await user["socket"].send_json({
                        "type": "leave",
                        "userId": user_id
                    })
