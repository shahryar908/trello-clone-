import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../AuthContext";

const btnPrimary =
  "rounded-md bg-teal px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-tealdeep disabled:opacity-60";
const linkCls = "font-semibold text-teal hover:text-tealdeep";

export default function Login({ mode }) {
  const isSignup = mode === "signup";
  const { login, signup } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      if (isSignup) await signup(email, password);
      else await login(email, password);
      const orgs = await api("/orgs");
      navigate(orgs.length > 0 ? "/" : "/orgs/new");
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
        <div className="mb-2">
          <span className="select-none font-display text-[32px] font-extrabold tracking-tight">
            tack<span className="text-teal">.</span>
          </span>
          <p className="text-[13px] text-inksoft">
            Boards, issues, and the people moving them.
          </p>
        </div>
        <h1 className="font-display text-[17px] font-bold">
          {isSignup ? "Create your account" : "Sign in"}
        </h1>
        <input
          type="email"
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
        <input
          type="password"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          minLength={6}
        />
        {error && <p className="text-[13px] text-danger">{error}</p>}
        <button type="submit" className={btnPrimary} disabled={busy}>
          {busy ? "..." : isSignup ? "Create account" : "Sign in"}
        </button>
        <p className="mt-1 text-center text-[13px] text-inksoft">
          {isSignup ? (
            <>
              Already have an account?{" "}
              <Link to="/login" className={linkCls}>
                Sign in
              </Link>
            </>
          ) : (
            <>
              New here?{" "}
              <Link to="/signup" className={linkCls}>
                Sign up
              </Link>
            </>
          )}
        </p>
      </form>
    </div>
  );
}
