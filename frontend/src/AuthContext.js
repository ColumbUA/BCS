import { createContext, useContext, useEffect, useState, useCallback } from "react";
import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

const AuthContext = createContext(null);

const TOKEN_KEY = "rrr_token";

export function AuthProvider({ children }) {
  const [user, setUser] = useState(undefined);   // undefined = loading, null = not logged in
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY) || "");

  const ax = useCallback(() => {
    const inst = axios.create({ baseURL: API });
    if (token) inst.defaults.headers.common["Authorization"] = `Bearer ${token}`;
    return inst;
  }, [token]);

  useEffect(() => {
    if (!token) { setUser(null); return; }
    axios.get(`${API}/auth/me`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => setUser(r.data))
      .catch(() => { localStorage.removeItem(TOKEN_KEY); setToken(""); setUser(null); });
  }, [token]);

  const login = async (username, password, totp_code) => {
    const res = await axios.post(`${API}/auth/login`, { username, password, totp_code });
    const t = res.data.access_token;
    localStorage.setItem(TOKEN_KEY, t);
    setToken(t);
    setUser(res.data.user);
    return res.data.user;
  };

  const logout = () => {
    localStorage.removeItem(TOKEN_KEY);
    setToken("");
    setUser(null);
  };

  const refreshMe = async () => {
    const r = await axios.get(`${API}/auth/me`, { headers: { Authorization: `Bearer ${token}` } });
    setUser(r.data);
    return r.data;
  };

  return (
    <AuthContext.Provider value={{ user, token, login, logout, ax, refreshMe }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}

export const ROLE_LABELS = {
  COMMANDER: "Командир роти",
  PLATOON_LEADER: "Командир взводу",
  MATERIAL: "Матеріаліст",
  VIEWER: "Перегляд",
};

export const can = {
  edit: (u) => u && ["COMMANDER", "PLATOON_LEADER", "MATERIAL"].includes(u.role),
  commander: (u) => u && u.role === "COMMANDER",
  material: (u) => u && (u.role === "MATERIAL" || u.role === "COMMANDER"),
};
