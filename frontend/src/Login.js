import { useState } from "react";
import { useAuth } from "./AuthContext";

export default function Login() {
  const { login } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [totp, setTotp] = useState("");
  const [need2fa, setNeed2fa] = useState(false);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setErr("");
    setLoading(true);
    try {
      await login(username.trim().toLowerCase(), password, totp || null);
    } catch (ex) {
      const detail = ex.response?.data?.detail || ex.message;
      const detailStr = typeof detail === "string" ? detail : JSON.stringify(detail);
      if (detailStr.includes("2FA")) setNeed2fa(true);
      setErr(detailStr);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-grid flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-6">
          <div className="inline-block px-4 py-1 rounded text-xs uppercase tracking-widest mb-3"
               style={{ background: "rgba(164,194,106,.15)", color: "#A4C26A", letterSpacing: "2px", border: "1px solid #2C4A2C" }}>
            CONFIDENTIAL
          </div>
          <h1 className="text-3xl font-bold tracking-wider mb-1">УПРАВЛІННЯ РОТОЮ</h1>
          <div className="text-sm" style={{ color: "#A4C26A", letterSpacing: "1px" }}>
            РОТА РАДІО ТА РАДІОТЕХНІЧНОЇ РОЗВІДКИ
          </div>
          <div className="text-xs mt-1" style={{ color: "#7A8B6C" }}>
            Розвідувальний батальйон • Авторизація
          </div>
        </div>

        <form onSubmit={submit} className="bg-mil border border-mil rounded-lg p-6 space-y-4">
          <div>
            <label className="text-xs uppercase tracking-wider block mb-1.5" style={{ color: "#7A8B6C" }}>Логін</label>
            <input className="input-mil" value={username} onChange={(e) => setUsername(e.target.value)}
                   placeholder="напр. kr" autoFocus required data-testid="login-username" />
          </div>
          <div>
            <label className="text-xs uppercase tracking-wider block mb-1.5" style={{ color: "#7A8B6C" }}>Пароль</label>
            <input type="password" className="input-mil" value={password} onChange={(e) => setPassword(e.target.value)}
                   placeholder="••••••••" required data-testid="login-password" />
          </div>
          {need2fa && (
            <div>
              <label className="text-xs uppercase tracking-wider block mb-1.5" style={{ color: "#D4A06A" }}>
                Код Google Authenticator
              </label>
              <input className="input-mil" value={totp} onChange={(e) => setTotp(e.target.value.replace(/\D/g, ""))}
                     placeholder="123 456" maxLength="6" inputMode="numeric"
                     style={{ fontFamily: "JetBrains Mono", letterSpacing: "4px", textAlign: "center", fontSize: "18px" }}
                     data-testid="login-totp" />
            </div>
          )}
          {err && (
            <div className="text-sm rounded p-3 border"
                 style={{ background: "rgba(232,144,144,.1)", borderColor: "#4A2C2C", color: "#E89090" }}
                 data-testid="login-err">
              {err}
            </div>
          )}
          <button type="submit" className="btn-mil btn-mil-primary w-full justify-center"
                  disabled={loading} data-testid="login-submit">
            {loading ? "Авторизація…" : "Увійти"}
          </button>
        </form>

        <div className="text-center text-xs mt-4" style={{ color: "#5C6E54" }}>
          Тестові облікові: <span style={{ color: "#A4C26A" }}>kr / kolumb2026</span>{" "}
          (командир) • <span style={{ color: "#D4A06A" }}>material / venom2026</span>{" "}
          (матеріаліст)
        </div>
      </div>
    </div>
  );
}
