import {
  DndContext,
  PointerSensor,
  closestCorners,
  useDroppable,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import {
  SortableContext,
  arrayMove,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { useCallback, useEffect, useRef, useState } from "react";
import { Link, Outlet, useNavigate, useParams } from "react-router-dom";
import { api } from "../api";
import { useBoardSocket } from "../hooks/useBoardSocket";

const linkCls = "font-semibold text-teal hover:text-tealdeep";
const btnPrimary =
  "rounded-md bg-teal px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-tealdeep";
const btnGhost =
  "rounded-md px-2 py-1 text-sm font-medium text-inksoft hover:bg-tray hover:text-ink";

function IssueCard({ issue, labels, onOpen }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: issue.id });
  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.4 : 1,
  };
  const issueLabels = labels.filter((l) => (issue.label_ids || []).includes(l.id));

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...attributes}
      {...listeners}
      className="relative cursor-grab overflow-hidden rounded-md border border-line bg-white py-2.5 pl-[15px] pr-3 shadow-card transition hover:-translate-y-px hover:shadow-lift active:cursor-grabbing"
      onClick={onOpen}
    >
      {issueLabels.length > 0 && (
        <span className="absolute inset-y-0 left-0 flex w-[5px] flex-col">
          {issueLabels.map((l) => (
            <span
              key={l.id}
              className="flex-1"
              style={{ background: l.color }}
              title={l.name}
            />
          ))}
        </span>
      )}
      <div className="text-sm font-medium leading-snug">{issue.title}</div>
      <div className="mt-1.5 flex items-center justify-between">
        <span className="font-mono text-[11.5px] text-inksoft">#{issue.id}</span>
        {issue.due_date && (
          <span className="font-mono text-[11.5px] text-amber">{issue.due_date}</span>
        )}
      </div>
    </div>
  );
}

function SectionColumn({ section, labels, onOpenIssue, onAddIssue, onRename, onDelete }) {
  const { setNodeRef } = useDroppable({ id: `section-${section.id}` });
  const [adding, setAdding] = useState(false);
  const [title, setTitle] = useState("");

  function submitIssue(e) {
    e.preventDefault();
    onAddIssue(section.id, title);
    setTitle("");
    setAdding(false);
  }

  return (
    <div className="flex max-h-full w-[280px] shrink-0 flex-col gap-2.5 rounded-[10px] border border-line bg-tray p-3">
      <div className="flex items-center justify-between px-0.5">
        <span
          className="flex cursor-default items-center gap-2 font-mono text-xs font-medium uppercase tracking-[0.08em] text-inksoft"
          onDoubleClick={() => {
            const next = prompt("Rename section", section.title);
            if (next && next.trim()) onRename(section.id, next.trim());
          }}
          title="Double-click to rename"
        >
          {section.title}
          <span className="rounded-full border border-line bg-white px-[7px] font-mono text-[11.5px] leading-[17px] text-inksoft">
            {section.issues.length}
          </span>
        </span>
        <button className={btnGhost} onClick={() => onDelete(section.id)} title="Delete section">
          ×
        </button>
      </div>

      <SortableContext
        items={section.issues.map((i) => i.id)}
        strategy={verticalListSortingStrategy}
      >
        <div ref={setNodeRef} className="flex min-h-[30px] flex-col gap-2 overflow-y-auto p-px">
          {section.issues.map((issue) => (
            <IssueCard
              key={issue.id}
              issue={issue}
              labels={labels}
              onOpen={() => onOpenIssue(issue.id)}
            />
          ))}
        </div>
      </SortableContext>

      {adding ? (
        <form className="flex flex-col gap-2" onSubmit={submitIssue}>
          <input
            autoFocus
            placeholder="Issue title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            required
          />
          <div className="flex gap-2">
            <button type="submit" className={btnPrimary}>
              Add
            </button>
            <button type="button" className={btnGhost} onClick={() => setAdding(false)}>
              Cancel
            </button>
          </div>
        </form>
      ) : (
        <button
          className="rounded-md px-2 py-1.5 text-left text-sm font-medium text-inksoft transition-colors hover:bg-tealwash hover:text-teal"
          onClick={() => setAdding(true)}
        >
          + Add issue
        </button>
      )}
    </div>
  );
}

export default function Board() {
  const { boardId } = useParams();
  const navigate = useNavigate();
  const [board, setBoard] = useState(null);
  const [error, setError] = useState("");
  const [lastComment, setLastComment] = useState(null);
  const [addingSection, setAddingSection] = useState(false);
  const [sectionTitle, setSectionTitle] = useState("");
  const draggingRef = useRef(false);

  const onComment = useCallback((c) => setLastComment(c), []);
  const { presence, send } = useBoardSocket(Number(boardId), { onComment });

  const refresh = useCallback(() => {
    api(`/boards/${boardId}`)
      .then(setBoard)
      .catch((err) => setError(err.message));
  }, [boardId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } })
  );

  function findSection(issueId) {
    return board.sections.find((s) => s.issues.some((i) => i.id === issueId));
  }

  function sectionByOverId(overId) {
    if (typeof overId === "string" && overId.startsWith("section-")) {
      return board.sections.find((s) => s.id === Number(overId.slice(8)));
    }
    return findSection(overId);
  }

  function handleDragStart() {
    draggingRef.current = true;
  }

  // moving between columns: update local state as the card hovers a new column
  function handleDragOver({ active, over }) {
    if (!over) return;
    const from = findSection(active.id);
    const to = sectionByOverId(over.id);
    if (!from || !to || from.id === to.id) return;
    setBoard((prev) => {
      const sections = prev.sections.map((s) => ({ ...s, issues: [...s.issues] }));
      const fromS = sections.find((s) => s.id === from.id);
      const toS = sections.find((s) => s.id === to.id);
      const idx = fromS.issues.findIndex((i) => i.id === active.id);
      if (idx === -1) return prev;
      const [moved] = fromS.issues.splice(idx, 1);
      const overIdx = toS.issues.findIndex((i) => i.id === over.id);
      if (overIdx === -1) toS.issues.push(moved);
      else toS.issues.splice(overIdx, 0, moved);
      return { ...prev, sections };
    });
  }

  function handleDragEnd({ active, over }) {
    setTimeout(() => {
      draggingRef.current = false;
    }, 0);
    if (!over) {
      refresh();
      return;
    }
    const section = findSection(active.id);
    if (!section) {
      refresh();
      return;
    }

    let issues = section.issues;
    const fromIdx = issues.findIndex((i) => i.id === active.id);
    const overIdx = issues.findIndex((i) => i.id === over.id);
    if (overIdx !== -1 && overIdx !== fromIdx) {
      issues = arrayMove(issues, fromIdx, overIdx);
    }

    // midpoint rule — must match backend spec
    const idx = issues.findIndex((i) => i.id === active.id);
    const prevIssue = issues[idx - 1];
    const nextIssue = issues[idx + 1];
    let position;
    if (!prevIssue && !nextIssue) position = 1.0;
    else if (!prevIssue) position = nextIssue.position / 2;
    else if (!nextIssue) position = prevIssue.position + 1;
    else position = (prevIssue.position + nextIssue.position) / 2;

    setBoard((prev) => ({
      ...prev,
      sections: prev.sections.map((s) =>
        s.id === section.id
          ? {
              ...s,
              issues: issues.map((i) =>
                i.id === active.id ? { ...i, position, section_id: section.id } : i
              ),
            }
          : s
      ),
    }));

    api(`/issues/${active.id}/move`, {
      method: "PATCH",
      body: JSON.stringify({ section_id: section.id, position }),
    }).catch(() => refresh());
  }

  function openIssue(issueId) {
    if (draggingRef.current) return;
    navigate(`/boards/${boardId}/issues/${issueId}`);
  }

  async function addSection(e) {
    e.preventDefault();
    try {
      await api(`/boards/${boardId}/sections`, {
        method: "POST",
        body: JSON.stringify({ title: sectionTitle }),
      });
      setSectionTitle("");
      setAddingSection(false);
      refresh();
    } catch (err) {
      setError(err.message);
    }
  }

  async function addIssue(sectionId, title) {
    try {
      await api(`/sections/${sectionId}/issues`, {
        method: "POST",
        body: JSON.stringify({ title }),
      });
      refresh();
    } catch (err) {
      setError(err.message);
    }
  }

  async function renameSection(sectionId, title) {
    try {
      await api(`/sections/${sectionId}`, {
        method: "PATCH",
        body: JSON.stringify({ title }),
      });
      refresh();
    } catch (err) {
      setError(err.message);
    }
  }

  async function deleteSection(sectionId) {
    if (!confirm("Delete this section and all its issues?")) return;
    try {
      await api(`/sections/${sectionId}`, { method: "DELETE" });
      refresh();
    } catch (err) {
      setError(err.message);
    }
  }

  async function renameBoard() {
    const next = prompt("Rename board", board.title);
    if (!next || !next.trim() || next.trim() === board.title) return;
    try {
      await api(`/boards/${boardId}`, {
        method: "PATCH",
        body: JSON.stringify({ title: next.trim() }),
      });
      refresh();
    } catch (err) {
      setError(err.message);
    }
  }

  async function deleteBoard() {
    if (!confirm("Delete this board and everything on it?")) return;
    try {
      await api(`/boards/${boardId}`, { method: "DELETE" });
      navigate("/");
    } catch (err) {
      setError(err.message); // e.g. 403 when not an org admin
    }
  }

  if (!board) {
    return (
      <div className="px-7 py-5">
        {error ? (
          <p className="text-[13px] text-danger">{error}</p>
        ) : (
          <p className="text-inksoft">Loading…</p>
        )}
      </div>
    );
  }

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-dotgrid px-7 py-5">
      <header className="mb-6 flex items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <Link to="/" className={linkCls}>
            ← Boards
          </Link>
          <h1
            className="font-display text-[19px] font-bold"
            onDoubleClick={renameBoard}
            title="Double-click to rename"
          >
            {board.title}
          </h1>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex">
            {presence.map((u) => (
              <span
                key={u.id}
                className="-ml-1.5 inline-flex h-[30px] w-[30px] items-center justify-center rounded-full border-2 border-paper bg-teal text-xs font-bold text-white first:ml-0"
                title={u.email}
              >
                {u.email[0].toUpperCase()}
              </span>
            ))}
          </div>
          <Link to={`/orgs/${board.organization_id}/settings`} className={linkCls}>
            Settings
          </Link>
          <button className={btnGhost} onClick={deleteBoard}>
            Delete board
          </button>
        </div>
      </header>

      {error && <p className="my-2 text-[13px] text-danger">{error}</p>}

      <DndContext
        sensors={sensors}
        collisionDetection={closestCorners}
        onDragStart={handleDragStart}
        onDragOver={handleDragOver}
        onDragEnd={handleDragEnd}
      >
        <div className="flex flex-1 items-start gap-4 overflow-x-auto px-0.5 pb-4 pt-1">
          {board.sections.map((section) => (
            <SectionColumn
              key={section.id}
              section={section}
              labels={board.labels}
              onOpenIssue={openIssue}
              onAddIssue={addIssue}
              onRename={renameSection}
              onDelete={deleteSection}
            />
          ))}

          {addingSection ? (
            <form
              className="flex w-[280px] shrink-0 flex-col gap-2 rounded-[10px] border border-line bg-tray p-3"
              onSubmit={addSection}
            >
              <input
                autoFocus
                placeholder="Section title"
                value={sectionTitle}
                onChange={(e) => setSectionTitle(e.target.value)}
                required
              />
              <div className="flex gap-2">
                <button type="submit" className={btnPrimary}>
                  Add
                </button>
                <button
                  type="button"
                  className={btnGhost}
                  onClick={() => setAddingSection(false)}
                >
                  Cancel
                </button>
              </div>
            </form>
          ) : (
            <button
              className="w-[280px] shrink-0 rounded-[10px] border border-dashed border-line p-4 text-center font-medium text-inksoft transition-colors hover:border-teal hover:bg-tealwash hover:text-teal"
              onClick={() => setAddingSection(true)}
            >
              + Add section
            </button>
          )}
        </div>
      </DndContext>

      <Outlet
        context={{
          send,
          lastComment,
          refresh,
          labels: board.labels,
          boardId: Number(boardId),
        }}
      />
    </div>
  );
}
