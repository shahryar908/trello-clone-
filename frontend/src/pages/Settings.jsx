import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";

const btnPrimary =
  "rounded-md bg-teal px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-tealdeep";

export default function Settings() {
  const { orgId } = useParams();
  const [orgName, setOrgName] = useState("");
  const [myRole, setMyRole] = useState(null);
  const [members, setMembers] = useState([]);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("member");
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");

  useEffect(() => {
    api("/orgs")
      .then((orgs) => {
        const org = orgs.find((o) => o.id === Number(orgId));
        if (org) {
          setOrgName(org.name);
          setMyRole(org.role);
        }
      })
      .catch((err) => setError(err.message));
    api(`/orgs/${orgId}/members`)
      .then(setMembers)
      .catch((err) => setError(err.message));
  }, [orgId]);

  async function addMember(e) {
    e.preventDefault();
    setError("");
    setOk("");
    try {
      const member = await api(`/orgs/${orgId}/members`, {
        method: "POST",
        body: JSON.stringify({ email, role }),
      });
      setMembers([...members, member]);
      setOk(`Added ${member.email} as ${member.role}`);
      setEmail("");
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="mx-auto max-w-[1400px] px-7 py-5">
      <header className="mb-6 flex items-center justify-between gap-4">
        <h1 className="font-display text-[19px] font-bold">{orgName} — Settings</h1>
        <Link to="/" className="font-semibold text-teal hover:text-tealdeep">
          Back to boards
        </Link>
      </header>

      <section className="max-w-[520px] rounded-xl border border-line bg-white p-6 shadow-card">
        <h2 className="mb-3.5 font-display text-[15px] font-bold">Members</h2>
        <ul className="mb-5">
          {members.map((m) => (
            <li
              key={m.user_id}
              className="flex items-center justify-between border-b border-linesoft py-2.5 text-sm"
            >
              <span>{m.email}</span>
              <span className="rounded bg-tray px-2 py-0.5 font-mono text-[11.5px] text-inksoft">
                {m.role}
              </span>
            </li>
          ))}
        </ul>

        {myRole === "admin" && (
          <form className="flex gap-2" onSubmit={addMember}>
            <input
              type="email"
              placeholder="teammate@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="flex-1"
            />
            <select value={role} onChange={(e) => setRole(e.target.value)}>
              <option value="member">member</option>
              <option value="admin">admin</option>
            </select>
            <button type="submit" className={btnPrimary}>
              Add member
            </button>
          </form>
        )}
        {error && <p className="my-2 text-[13px] text-danger">{error}</p>}
        {ok && <p className="my-2 text-[13px] text-teal">{ok}</p>}
      </section>
    </div>
  );
}
