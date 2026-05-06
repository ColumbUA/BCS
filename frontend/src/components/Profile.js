import { useState, useEffect } from "react";
import { useAuth } from "../AuthContext";
import { cls } from "./Common";

export default function Profile({ onClose, showToast }) {
  const { user, ax, refreshMe, logout } = useAuth();
  const [pwd, setPwd] = useState({ old: "", neu: "" });
  const [qr, setQr] = useState(null);
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);

  const setup2fa = async () => {
    setBusy(true);
    try {
      const r = await ax().post("/auth/2fa/setup");
      setQr(r.data);
    } catch (e) { showToast("Помилка: " + (e.response?.data?.detail || e.message), "err"); }
    finally { setBusy(false); }
  };

  const verify2fa = async () => {
    setBusy(true);
    try {
      await ax().post("/auth/2fa/verify", { code });
      showToast("✓ 2FA увімкнено");
      setQr(null); setCode("");
      await refreshMe();
    } catch (e) { showToast("Помилка: " + (e.response?.data?.detail || e.message), "err"); }
    finally { setBusy(false); }
  };

  const disable2fa = async () => {
    if (!window.confirm("Вимкнути 2FA?")) return;
    await ax().post("/auth/2fa/disable");
    showToast("2FA вимкнено");
    await refreshMe();
  };

  const changePwd = async (e) => {
    e.preventDefault();
    if (pwd.neu.length < 6) { showToast("Пароль ≥6 символів", "err"); return; }
    try {
      await ax().post("/auth/change-password", { old_password: pwd.old, new_password: pwd.neu });
      showToast("✓ Пароль змінено");
      setPwd({ old: "", neu: "" });
    } catch (e) { showToast(e.response?.data?.detail || "Помилка", "err"); }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4"
         style={{ background: "rgba(14,26,20,.85)", backdropFilter: "blur(6px)" }}
         onClick={onClose}>
      <div className="bg-mil border border-mil rounded-lg p-6 w-full max-w-2xl max-h-[90vh] overflow-y-auto"
           onClick={(e) => e.stopPropagation()}>
        <div className="flex justify-between items-start mb-4">
          <div>
            <h2 className="text-xl font-bold text-accent">Профіль</h2>
            <div className="text-sm" style={{ color: "#7A8B6C" }}>{user?.name}</div>
            <div className="text-xs mt-1" style={{ color: "#A4C26A" }}>
              {user?.role} {user?.platoon && `• ${user.platoon}`}
            </div>
          </div>
          <button className="btn-mil text-xs" onClick={onClose}>✕</button>
        </div>

        {/* 2FA */}
        <div className="bg-mil-deep border border-mil rounded-lg p-4 mb-4">
          <h3 className="text-sm font-bold mb-3 text-brown">🔐 Двофакторна аутентифікація (Google Authenticator)</h3>
          {user?.totp_enabled ? (
            <div>
              <div className="text-sm mb-3 text-accent">✓ 2FA увімкнено. При кожному вході потрібен 6-значний код.</div>
              <button className="btn-mil btn-mil-danger" onClick={disable2fa}>Вимкнути 2FA</button>
            </div>
          ) : qr ? (
            <div>
              <div className="text-xs mb-2" style={{ color: "#7A8B6C" }}>
                1. Відскануйте QR-код у Google Authenticator / Authy / Microsoft Authenticator
              </div>
              <div className="flex gap-4 items-center mb-3">
                <img src={qr.qr_data_uri} alt="QR" className="rounded bg-white p-2" style={{ width: 180 }} />
                <div className="text-xs">
                  <div style={{ color: "#7A8B6C" }}>Або введіть вручну:</div>
                  <div style={{ fontFamily: "JetBrains Mono", color: "#A4C26A", wordBreak: "break-all" }}>
                    {qr.secret}
                  </div>
                </div>
              </div>
              <div className="text-xs mb-2" style={{ color: "#7A8B6C" }}>2. Введіть 6-значний код з додатка для активації:</div>
              <div className="flex gap-2">
                <input className="input-mil" value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
                       maxLength="6" placeholder="123 456"
                       style={{ fontFamily: "JetBrains Mono", letterSpacing: "4px", textAlign: "center" }} />
                <button className="btn-mil btn-mil-primary" onClick={verify2fa} disabled={busy || code.length !== 6}>
                  Активувати
                </button>
              </div>
            </div>
          ) : (
            <button className="btn-mil btn-mil-primary" onClick={setup2fa} disabled={busy}>
              Увімкнути 2FA
            </button>
          )}
        </div>

        {/* Change password */}
        <form onSubmit={changePwd} className="bg-mil-deep border border-mil rounded-lg p-4 mb-4">
          <h3 className="text-sm font-bold mb-3 text-brown">🔑 Змінити пароль</h3>
          <div className="grid grid-cols-2 gap-3">
            <input type="password" className="input-mil" placeholder="Старий пароль" required
                   value={pwd.old} onChange={(e) => setPwd({ ...pwd, old: e.target.value })} />
            <input type="password" className="input-mil" placeholder="Новий пароль (≥6)" required
                   value={pwd.neu} onChange={(e) => setPwd({ ...pwd, neu: e.target.value })} />
          </div>
          <button type="submit" className="btn-mil btn-mil-primary mt-3">Зберегти</button>
        </form>

        <button className="btn-mil btn-mil-danger w-full justify-center" onClick={() => { logout(); onClose(); }}>
          Вийти із системи
        </button>
      </div>
    </div>
  );
}
