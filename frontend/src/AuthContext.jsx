import { createContext, useContext, useState } from "react";
import { api } from "./api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem("token"));
  const [email, setEmail] = useState(() => localStorage.getItem("email"));

  async function login(emailValue, password) {
    const data = await api("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email: emailValue, password }),
    });
    localStorage.setItem("token", data.access_token);
    localStorage.setItem("email", emailValue);
    setToken(data.access_token);
    setEmail(emailValue);
  }

  async function signup(emailValue, password) {
    await api("/auth/signup", {
      method: "POST",
      body: JSON.stringify({ email: emailValue, password }),
    });
    await login(emailValue, password);
  }

  function logout() {
    localStorage.removeItem("token");
    localStorage.removeItem("email");
    setToken(null);
    setEmail(null);
  }

  return (
    <AuthContext.Provider value={{ token, email, login, signup, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
