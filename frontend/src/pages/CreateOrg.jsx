import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api";

const btnPrimary =
  "rounded-md bg-teal px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-tealdeep disabled:opacity-60";

export default function CreateOrg() {
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const org = await api("/orgs", {
        method: "POST",
        body: JSON.stringify({ name, description: description || null }),
      });
      localStorage.setItem("orgId", org.id);
      navigate("/");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-dotgrid p-6">
      <form
        className="flex w-[360px] flex-col gap-3 rounded-xl border border-line bg-white p-8 shadow-lift"
        onSubmit={handleSubmit}
      >
        <h1 className="font-display text-[17px] font-bold">Create organization</h1>
        <input
          placeholder="Name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
        />
        <input
          placeholder="Description (optional)"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
        {error && <p className="text-[13px] text-danger">{error}</p>}
        <button type="submit" className={btnPrimary} disabled={busy}>
          Create organization
        </button>
        <p className="mt-1 text-center text-[13px] text-inksoft">
          <Link to="/" className="font-semibold text-teal hover:text-tealdeep">
            ← Back to boards
          </Link>
        </p>
      </form>
    </div>
  );
}
