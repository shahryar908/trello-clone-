import { useCallback, useEffect, useRef, useState } from "react";
import { WS_BASE, getToken } from "../api";

export function useBoardSocket(boardId, { onComment } = {}) {
  const [presence, setPresence] = useState([]);
  const wsRef = useRef(null);
  const onCommentRef = useRef(onComment);
  onCommentRef.current = onComment;

  useEffect(() => {
    if (!boardId) return undefined;
    let closedByUs = false;
    let retries = 0;
    let ws;

    function connect() {
      ws = new WebSocket(`${WS_BASE}/ws/boards/${boardId}?token=${getToken() || ""}`);
      wsRef.current = ws;

      ws.onopen = () => {
        retries = 0;
      };

      ws.onmessage = (event) => {
        let msg;
        try {
          msg = JSON.parse(event.data);
        } catch {
          return;
        }
        if (msg.type === "presence_changed") setPresence(msg.users);
        else if (msg.type === "comment_created") onCommentRef.current?.(msg.comment);
        else if (msg.type === "error") console.warn("WS error:", msg.detail);
      };

      ws.onclose = () => {
        if (!closedByUs && retries < 5) {
          retries += 1;
          setTimeout(connect, 2000);
        }
      };
    }

    connect();
    return () => {
      closedByUs = true;
      if (ws) ws.close();
    };
  }, [boardId]);

  const send = useCallback((msg) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(msg));
    }
  }, []);

  return { presence, send };
}
