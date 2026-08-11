import { useEffect, useState } from "react";
import { useNavigate, useOutletContext, useParams } from "react-router-dom";
import { api } from "../api";

const btnPrimary =
  "rounded-md bg-teal px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-tealdeep";
const btnGhost =
  "rounded-md px-2 py-1 text-sm font-medium text-inksoft hover:bg-tray hover:text-ink";
const metaLabel =
  "min-w-[92px] text-xs font-semibold uppercase tracking-[0.06em] text-inksoft";

export default function IssueModal() {
  const { boardId, issueId } = useParams();
  const navigate = useNavigate();
  const { send, lastComment, refresh, labels } = useOutletContext();

  const [issue, setIssue] = useState(null);
  const [comments, setComments] = useState([]);
  const [title, setTitle] = useState("");
  const [editingTitle, setEditingTitle] = useState(false);
  const [description, setDescription] = useState("");
  const [body, setBody] = useState("");
  const [showLabelPicker, setShowLabelPicker] = useState(false);
  const [newLabelName, setNewLabelName] = useState("");
  const [newLabelColor, setNewLabelColor] = useState("#ef4444");
  const [error, setError] = useState("");

  useEffect(() => {
    api(`/issues/${issueId}`)
      .then((data) => {
        setIssue(data);
        setTitle(data.title);
        setDescription(data.description || "");
      })
      .catch((err) => setError(err.message));
    api(`/issues/${issueId}/comments`)
      .then(setComments)
      .catch((err) => setError(err.message));
  }, [issueId]);

  // realtime comments arrive via the board's WebSocket (no local echo —
  // the sender's own comment comes back in the broadcast too)
  useEffect(() => {
    if (lastComment && lastComment.issue_id === Number(issueId)) {
      setComments((prev) =>
        prev.some((c) => c.id === lastComment.id) ? prev : [...prev, lastComment]
      );
    }
  }, [lastComment, issueId]);

  function close() {
    navigate(`/boards/${boardId}`);
  }

  useEffect(() => {
    function onKey(e) {
      if (e.key === "Escape") close();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  async function patch(fields) {
    try {
      const updated = await api(`/issues/${issueId}`, {
        method: "PATCH",
        body: JSON.stringify(fields),
      });
      setIssue((prev) => ({ ...prev, ...updated, labels: prev.labels }));
      refresh();
    } catch (err) {
      setError(err.message);
    }
  }

  async function refetchIssue() {
    const data = await api(`/issues/${issueId}`);
    setIssue(data);
    refresh();
  }

  async function attachLabel(labelId) {
    try {
      await api(`/issues/${issueId}/labels`, {
        method: "POST",
        body: JSON.stringify({ label_id: labelId }),
      });
      await refetchIssue();
    } catch (err) {
      setError(err.message);
    }
  }

  async function detachLabel(labelId) {
    try {
      await api(`/issues/${issueId}/labels/${labelId}`, { method: "DELETE" });
      await refetchIssue();
    } catch (err) {
      setError(err.message);
    }
  }

  async function createLabel(e) {
    e.preventDefault();
    try {
      const label = await api(`/boards/${boardId}/labels`, {
        method: "POST",
        body: JSON.stringify({ name: newLabelName, color: newLabelColor }),
      });
      setNewLabelName("");
      refresh();
      await attachLabel(label.id);
    } catch (err) {
      setError(err.message);
    }
  }

  async function deleteIssue() {
    if (!confirm("Delete this issue?")) return;
    try {
      await api(`/issues/${issueId}`, { method: "DELETE" });
      refresh();
      close();
    } catch (err) {
      setError(err.message);
    }
  }

  function sendComment(e) {
    e.preventDefault();
    const text = body.trim();
    if (!text) return;
    send({ type: "comment_create", issue_id: Number(issueId), body: text });
    setBody("");
  }

  const backdropCls =
    "fixed inset-0 z-10 flex items-start justify-center bg-ink/35 px-4 pb-4 pt-[8vh] backdrop-blur-[2px]";
  const modalCls =
    "animate-pop flex max-h-[84vh] w-[600px] max-w-full flex-col gap-4 overflow-y-auto rounded-2xl border border-line bg-white p-6 shadow-modal";

  if (!issue) {
    return (
      <div className={backdropCls} onClick={close}>
        <div className={modalCls} onClick={(e) => e.stopPropagation()}>
          {error ? (
            <p className="text-[13px] text-danger">{error}</p>
          ) : (
            <p className="text-inksoft">Loading…</p>
          )}
        </div>
      </div>
    );
  }

  const attachedIds = issue.labels.map((l) => l.id);
  const attachable = labels.filter((l) => !attachedIds.includes(l.id));

  return (
    <div className={backdropCls} onClick={close}>
      <div className={modalCls} onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start justify-between gap-2.5">
          <div className="flex flex-1 flex-col gap-0.5">
            <span className="font-mono text-[11.5px] text-inksoft">#{issue.id}</span>
            {editingTitle ? (
              <input
                autoFocus
                className="font-display text-[17px] font-bold"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                onBlur={() => {
                  setEditingTitle(false);
                  if (title.trim() && title !== issue.title) patch({ title: title.trim() });
                }}
                onKeyDown={(e) => e.key === "Enter" && e.target.blur()}
              />
            ) : (
              <h2
                className="cursor-text font-display text-[19px] font-bold"
                onClick={() => setEditingTitle(true)}
                title="Click to edit"
              >
                {issue.title}
              </h2>
            )}
          </div>
          <button className={btnGhost} onClick={close}>
            ×
          </button>
        </div>

        <div className="flex items-center gap-3">
          <label className={metaLabel}>Due date</label>
          <input
            type="date"
            value={issue.due_date || ""}
            onChange={(e) => patch({ due_date: e.target.value || null })}
          />
        </div>

        <div className="flex items-center gap-3">
          <label className={metaLabel}>Labels</label>
          <div className="flex flex-wrap items-center gap-1.5">
            {issue.labels.map((l) => (
              <span
                key={l.id}
                className="inline-flex items-center gap-1.5 rounded-full px-3 py-[3px] text-xs font-semibold text-white"
                style={{ background: l.color }}
              >
                {l.name}
                <button
                  className="cursor-pointer text-white/85"
                  onClick={() => detachLabel(l.id)}
                >
                  ×
                </button>
              </span>
            ))}
            <button
              className={btnGhost}
              onClick={() => setShowLabelPicker(!showLabelPicker)}
            >
              + add label
            </button>
          </div>
        </div>

        {showLabelPicker && (
          <div className="flex flex-wrap items-center gap-2 rounded-lg border border-line bg-paper p-3">
            {attachable.map((l) => (
              <button
                key={l.id}
                className="inline-flex items-center rounded-full px-3 py-[3px] text-xs font-semibold text-white"
                style={{ background: l.color }}
                onClick={() => attachLabel(l.id)}
              >
                {l.name}
              </button>
            ))}
            <form className="flex items-center gap-1.5" onSubmit={createLabel}>
              <input
                placeholder="New label"
                value={newLabelName}
                onChange={(e) => setNewLabelName(e.target.value)}
                required
              />
              <input
                type="color"
                className="h-9 w-10 p-[3px]"
                value={newLabelColor}
                onChange={(e) => setNewLabelColor(e.target.value)}
              />
              <button type="submit" className={btnPrimary}>
                Create
              </button>
            </form>
          </div>
        )}

        <div className="flex flex-col gap-1.5">
          <label className={metaLabel}>Description</label>
          <textarea
            placeholder="Add a description…"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            onBlur={() => {
              if ((issue.description || "") !== description)
                patch({ description: description || null });
            }}
            rows={4}
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <label className={metaLabel}>Comments</label>
          <ul className="mb-2 flex flex-col gap-2">
            {comments.map((c) => (
              <li
                key={c.id}
                className="rounded-md border border-linesoft bg-paper px-3 py-2 text-sm"
              >
                <span className="font-bold text-teal">{c.author.email}:</span> {c.body}
                <span className="mt-1 block font-mono text-[11px] text-inksoft">
                  {new Date(c.created_at).toLocaleString()}
                </span>
              </li>
            ))}
            {comments.length === 0 && (
              <li className="text-inksoft">No comments yet — write the first one below.</li>
            )}
          </ul>
          <form className="flex gap-2" onSubmit={sendComment}>
            <input
              className="flex-1"
              placeholder="Write a comment…"
              value={body}
              onChange={(e) => setBody(e.target.value)}
            />
            <button type="submit" className={btnPrimary}>
              Send
            </button>
          </form>
        </div>

        {error && <p className="text-[13px] text-danger">{error}</p>}

        <div className="flex justify-end border-t border-linesoft pt-3.5">
          <button
            className="rounded-md border border-line px-4 py-2 text-sm font-semibold text-danger transition-colors hover:border-[#e5b5b3] hover:bg-[#faeceb]"
            onClick={deleteIssue}
          >
            Delete issue
          </button>
        </div>
      </div>
    </div>
  );
}
