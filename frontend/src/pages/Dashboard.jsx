import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../AuthContext";

const linkCls = "font-semibold text-teal hover:text-tealdeep";
const btnPrimary =
  "rounded-md bg-teal px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-tealdeep";
const btnGhost =
  "rounded-md px-2 py-1 text-sm font-medium text-inksoft hover:bg-tray hover:text-ink";

export default function Dashboard() {
  const { email, logout } = useAuth();
  const navigate = useNavigate();
  const [orgs, setOrgs] = useState([]);
  const [orgId, setOrgId] = useState(null);
  const [boards, setBoards] = useState([]);
  const [creating, setCreating] = useState(false);
  const [title, setTitle] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    api("/orgs")
      .then((data) => {
        setOrgs(data);
        if (data.length === 0) {
          navigate("/orgs/new");
          return;
        }
        const saved = Number(localStorage.getItem("orgId"));
        setOrgId(data.some((o) => o.id === saved) ? saved : data[0].id);
      })
      .catch((err) => setError(err.message));
  }, [navigate]);

  useEffect(() => {
    if (!orgId) return;
    localStorage.setItem("orgId", orgId);
    api(`/orgs/${orgId}/boards`)
      .then(setBoards)
      .catch((err) => setError(err.message));
  }, [orgId]);

  async function createBoard(e) {
    e.preventDefault();
    try {
      const board = await api(`/orgs/${orgId}/boards`, {
        method: "POST",
        body: JSON.stringify({ title }),
      });
      setBoards([...boards, board]);
      setTitle("");
      setCreating(false);
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="mx-auto max-w-[1400px] px-7 py-5">
      <header className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <Link
            to="/"
            className="select-none font-display text-xl font-extrabold tracking-tight text-ink"
          >
            tack<span className="text-teal">.</span>
          </Link>
          <select
            value={orgId ?? ""}
            onChange={(e) => {
              const value = e.target.value;
              if (value === "new") navigate("/orgs/new");
              else setOrgId(Number(value));
            }}
            className="min-w-[170px] font-semibold"
          >
            {orgs.map((o) => (
              <option key={o.id} value={o.id}>
                {o.name}
              </option>
            ))}
            <option value="new">+ New organization</option>
          </select>
        </div>
        <div className="flex items-center gap-4">
          {orgId && (
            <Link to={`/orgs/${orgId}/settings`} className={linkCls}>
              Settings
            </Link>
          )}
          <span className="text-[13px] text-inksoft">{email}</span>
          <button
            className={btnGhost}
            onClick={() => {
              logout();
              navigate("/login");
            }}
          >
            Logout
          </button>
        </div>
      </header>

      {error && <p className="my-2 text-[13px] text-danger">{error}</p>}

      <div className="mb-4 flex items-baseline gap-2.5">
        <h1 className="font-display text-2xl font-bold">Boards</h1>
        <span className="font-mono text-[11.5px] text-inksoft">{boards.length}</span>
      </div>

      <div className="grid grid-cols-[repeat(auto-fill,minmax(200px,1fr))] gap-4">
        {boards.map((b) => (
          <Link
            key={b.id}
            to={`/boards/${b.id}`}
            className="flex min-h-[92px] items-center justify-center rounded-lg border border-line bg-white p-5 text-center font-display text-[15px] font-bold text-ink shadow-stack transition hover:-translate-y-0.5 hover:shadow-lift"
          >
            {b.title}
          </Link>
        ))}
        {creating ? (
          <form
            className="flex min-h-[92px] flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-line p-4"
            onSubmit={createBoard}
          >
            <input
              autoFocus
              placeholder="Board title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              required
              className="w-full"
            />
            <div className="flex gap-2">
              <button type="submit" className={btnPrimary}>
                Create
              </button>
              <button type="button" className={btnGhost} onClick={() => setCreating(false)}>
                Cancel
              </button>
            </div>
          </form>
        ) : (
          <button
            className="flex min-h-[92px] flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-line font-medium text-inksoft transition-colors hover:border-teal hover:bg-tealwash hover:text-teal"
            onClick={() => setCreating(true)}
          >
            + New board
          </button>
        )}
      </div>
    </div>
  );
}
