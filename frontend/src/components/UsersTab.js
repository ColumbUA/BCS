import { useEffect, useState } from "react";
import { useAuth, ROLE_LABELS } from "../AuthContext";
import { cls } from "./Common";

const DOC_LABELS = {
  passport: "Паспорт",
  ipn: "ІПН (РНОКПП)",
  diploma: "Диплом / атестат",
  driver_license: "Водійське посвідчення",
  military_id: "Військовий квиток / офіцерське",
  certificate: "Сертифікат",
  other: "Інше",
};
const REQUIRED = ["passport", "ipn", "military_id"];

export default function UsersTab({ structure, showToast }) {
  const { ax, user } = useAuth();
  const [users, setUsers] = useState([]);
  const [showRegister, setShowRegister] = useState(false);
  const [editingUser, setEditingUser] = useState(null);

  const reload = async () => {
    try { const r = await ax().get("/users"); setUsers(r.data); }
    catch (e) { showToast(e.response?.data?.detail || "Помилка", "err"); }
  };
  useEffect(() => { reload(); }, []);

  const remove = async (u) => {
    if (!window.confirm(`Видалити користувача «${u.username}»?\n\nПов'язана картка солдата (якщо є) теж буде видалена.`)) return;
    try { await ax().delete(`/users/${u.id}`); showToast(`✓ ${u.username} видалено`); reload(); }
    catch (e) { showToast(e.response?.data?.detail || "Помилка", "err"); }
  };

  const roleColor = {
    COMMANDER: "#A4C26A",
    PLATOON_LEADER: "#7AB8D8",
    MATERIAL: "#D4A06A",
    VIEWER: "#7A8B6C",
  };

  return (
    <div>
      <div className="bg-mil border border-mil rounded-lg p-4 mb-5"
           style={{ borderLeft: "4px solid #A4C26A" }}>
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div>
            <div className="text-xs uppercase mb-1" style={{ color: "#7A8B6C" }}>Адміністрування доступу</div>
            <div className="text-sm">
              Реєстрація нових користувачів з повним пакетом документів та автостворенням картки.
            </div>
          </div>
          <button className="btn-mil btn-mil-primary text-sm" onClick={() => setShowRegister(true)} data-testid="btn-register">
            + Зареєструвати користувача
          </button>
        </div>
      </div>

      <div className="bg-mil border border-mil rounded-lg overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-mil-deep">
            <tr style={{ color: "#7A8B6C" }}>
              <th className="text-left px-3 py-2 uppercase text-xs">Логін</th>
              <th className="text-left px-3 py-2 uppercase text-xs">ПІБ / Призначення</th>
              <th className="text-left px-3 py-2 uppercase text-xs">Роль</th>
              <th className="text-left px-3 py-2 uppercase text-xs">Взвод</th>
              <th className="text-center px-3 py-2 uppercase text-xs">2FA</th>
              <th className="text-center px-3 py-2 uppercase text-xs">Картка</th>
              <th className="px-3 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {users.map(u => (
              <tr key={u.id} className="border-t border-mil hover:bg-mil-deep" data-testid={`user-${u.username}`}>
                <td className="px-3 py-2 font-bold" style={{ fontFamily: "JetBrains Mono" }}>{u.username}</td>
                <td className="px-3 py-2">{u.name || "—"}</td>
                <td className="px-3 py-2">
                  <span className="badge" style={{ background: `${roleColor[u.role]}30`, color: roleColor[u.role], border: `1px solid ${roleColor[u.role]}` }}>
                    {ROLE_LABELS[u.role] || u.role}
                  </span>
                </td>
                <td className="px-3 py-2 text-xs" style={{ color: "#7A8B6C" }}>{u.platoon || "—"}</td>
                <td className="px-3 py-2 text-center">{u.totp_enabled ? "🔐" : "—"}</td>
                <td className="px-3 py-2 text-center">{u.soldier_id ? "✓" : "—"}</td>
                <td className="px-3 py-2 text-right whitespace-nowrap">
                  <button className="btn-mil text-xs py-1 px-2 mr-1" onClick={() => setEditingUser(u)}>✎</button>
                  {u.username !== "admin" && u.id !== user?.id && (
                    <button className="btn-mil btn-mil-danger text-xs py-1 px-2" onClick={() => remove(u)}>✕</button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {showRegister && (
        <RegisterUserModal structure={structure}
          onClose={() => setShowRegister(false)}
          onCreated={() => { setShowRegister(false); reload(); }}
          showToast={showToast} />
      )}
      {editingUser && (
        <EditUserModal u={editingUser}
          onClose={() => setEditingUser(null)}
          onSaved={() => { setEditingUser(null); reload(); }}
          showToast={showToast} />
      )}
    </div>
  );
}


function RegisterUserModal({ structure, onClose, onCreated, showToast }) {
  const { ax } = useAuth();
  const subunits = structure ? structure.order.map(k => structure.subunits[k].name) : [];
  const [form, setForm] = useState({
    username: "", password: "", name: "", role: "VIEWER", platoon: "",
    create_soldier_card: true,
    fio: "", callsign: "", rank: "солдат", position: "",
    node_path: subunits[0] || "",
    birth_date: "", mobilized_at: "", bzvp_passed_at: "", ktz_passed_at: "",
    blood_group: "", has_driver_license: false, notes: "",
  });
  const [busy, setBusy] = useState(false);
  const [createdSoldierId, setCreatedSoldierId] = useState(null);

  const genPassword = () => {
    const chars = "abcdefghijklmnpqrstuvwxyz23456789";
    const p = Array.from({length: 10}, () => chars[Math.floor(Math.random()*chars.length)]).join("");
    setForm({...form, password: p});
  };

  const submit = async (e) => {
    e.preventDefault();
    if (!form.username.trim() || form.password.length < 6) {
      showToast("Введіть логін і пароль (≥6)", "err"); return;
    }
    setBusy(true);
    try {
      const r = await ax().post("/users/register", form);
      showToast(`✓ Зареєстровано: ${r.data.username}`);
      if (r.data.soldier_id) {
        setCreatedSoldierId(r.data.soldier_id);
      } else {
        onCreated();
      }
    } catch (e) { showToast(e.response?.data?.detail || "Помилка", "err"); }
    finally { setBusy(false); }
  };

  // Якщо картку створено — переходимо до завантаження документів
  if (createdSoldierId) {
    return <UploadDocsStep soldierId={createdSoldierId} username={form.username} password={form.password}
                           onClose={() => { setCreatedSoldierId(null); onCreated(); }} showToast={showToast} />;
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4"
         style={{ background: "rgba(14,26,20,.85)", backdropFilter: "blur(6px)" }} onClick={onClose}>
      <form className="bg-mil border border-mil rounded-lg w-full max-w-3xl max-h-[92vh] overflow-y-auto p-6"
            onSubmit={submit} onClick={(e) => e.stopPropagation()}>
        <div className="flex justify-between items-start mb-4">
          <div>
            <div className="text-xs uppercase tracking-wider" style={{ color: "#7A8B6C" }}>Адміністрування</div>
            <h2 className="text-xl font-bold text-accent">+ Зареєструвати користувача</h2>
            <div className="text-xs mt-1" style={{ color: "#7A8B6C" }}>
              Створює обліковий запис у системі + картку військовослужбовця (опц.)
            </div>
          </div>
          <button type="button" className="btn-mil text-xs" onClick={onClose}>✕</button>
        </div>

        <Section title="🔐 Обліковий запис">
          <Grid>
            <Field label="Логін * (англ. або цифри)">
              <input className="input-mil" required value={form.username}
                     onChange={(e) => setForm({...form, username: e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, "")})}
                     placeholder="напр. malvina, kv3" data-testid="reg-username" />
            </Field>
            <Field label="Пароль * (≥6)">
              <div className="flex gap-2">
                <input className="input-mil flex-1" required type="text" value={form.password} minLength="6"
                       onChange={(e) => setForm({...form, password: e.target.value})}
                       data-testid="reg-password" />
                <button type="button" className="btn-mil text-xs" onClick={genPassword}>🎲 Згенерувати</button>
              </div>
            </Field>
            <Field label="Роль *">
              <select className="input-mil" value={form.role} onChange={(e) => setForm({...form, role: e.target.value})} data-testid="reg-role">
                <option value="VIEWER">Перегляд (read-only)</option>
                <option value="MATERIAL">Матеріаліст / діловод</option>
                <option value="PLATOON_LEADER">Командир взводу</option>
                <option value="COMMANDER">Командир роти (повний)</option>
              </select>
            </Field>
            <Field label="Взвод (для КВ)">
              <select className="input-mil" value={form.platoon} onChange={(e) => setForm({...form, platoon: e.target.value})}>
                <option value="">—</option>
                {subunits.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
            </Field>
          </Grid>
        </Section>

        <Section title="👤 Особисті дані військовослужбовця">
          <label className="flex items-center gap-2 mb-3 text-sm">
            <input type="checkbox" checked={form.create_soldier_card}
                   onChange={(e) => setForm({...form, create_soldier_card: e.target.checked})} />
            <span>Створити пов'язану картку військовослужбовця (рекомендовано)</span>
          </label>
          {form.create_soldier_card && (
            <Grid>
              <div className="md:col-span-2">
                <Field label="ПІБ *">
                  <input className="input-mil" required={form.create_soldier_card} value={form.fio}
                         onChange={(e) => setForm({...form, fio: e.target.value, name: form.name || e.target.value})}
                         placeholder="ПЕТРЕНКО Іван Іванович" data-testid="reg-fio" />
                </Field>
              </div>
              <Field label="Позивний">
                <input className="input-mil" value={form.callsign}
                       onChange={(e) => setForm({...form, callsign: e.target.value})}
                       placeholder="МАЛЬВІНА" />
              </Field>
              <Field label="Звання">
                <input className="input-mil" value={form.rank}
                       onChange={(e) => setForm({...form, rank: e.target.value})} />
              </Field>
              <Field label="Посада">
                <input className="input-mil" value={form.position}
                       onChange={(e) => setForm({...form, position: e.target.value})}
                       placeholder="діловод / бухгалтер" />
              </Field>
              <Field label="Підрозділ">
                <select className="input-mil" value={form.node_path}
                        onChange={(e) => setForm({...form, node_path: e.target.value})}>
                  {subunits.map(s => <option key={s} value={s}>{s}</option>)}
                </select>
              </Field>
              <Field label="Дата народження">
                <input type="date" className="input-mil" value={form.birth_date}
                       onChange={(e) => setForm({...form, birth_date: e.target.value})} />
              </Field>
              <Field label="Дата мобілізації">
                <input type="date" className="input-mil" value={form.mobilized_at}
                       onChange={(e) => setForm({...form, mobilized_at: e.target.value})} />
              </Field>
              <Field label="БЗВП пройдено">
                <input type="date" className="input-mil" value={form.bzvp_passed_at}
                       onChange={(e) => setForm({...form, bzvp_passed_at: e.target.value})} />
              </Field>
              <Field label="КТЗ пройдено">
                <input type="date" className="input-mil" value={form.ktz_passed_at}
                       onChange={(e) => setForm({...form, ktz_passed_at: e.target.value})} />
              </Field>
              <Field label="Група крові">
                <input className="input-mil" placeholder="O(I) Rh+" value={form.blood_group}
                       onChange={(e) => setForm({...form, blood_group: e.target.value})} />
              </Field>
              <div>
                <label className="text-xs uppercase block mb-1" style={{ color: "#7A8B6C" }}>Водійське посвідчення</label>
                <label className="flex items-center gap-2 mt-2">
                  <input type="checkbox" checked={form.has_driver_license}
                         onChange={(e) => setForm({...form, has_driver_license: e.target.checked})} />
                  <span className="text-sm">Має ВП</span>
                </label>
              </div>
            </Grid>
          )}
        </Section>

        <div className="flex gap-2 mt-5">
          <button type="submit" className="btn-mil btn-mil-primary" disabled={busy} data-testid="reg-submit">
            {busy ? "Створення…" : "Зареєструвати → завантажити документи"}
          </button>
          <button type="button" className="btn-mil" onClick={onClose}>Скасувати</button>
        </div>
        <div className="text-xs mt-3" style={{ color: "#5C6E54" }}>
          ℹ Після створення відкриється форма завантаження документів: паспорт, ІПН, диплом, ВП, ВК
        </div>
      </form>
    </div>
  );
}


function UploadDocsStep({ soldierId, username, password, onClose, showToast }) {
  const { ax } = useAuth();
  const [files, setFiles] = useState({});
  const [uploading, setUploading] = useState("");
  const [uploaded, setUploaded] = useState({});

  const upload = async (docType, file) => {
    setUploading(docType);
    try {
      const fd = new FormData();
      fd.append("doc_type", docType);
      fd.append("file", file);
      const r = await ax().post(`/soldiers/${soldierId}/documents`, fd,
        { headers: { "Content-Type": "multipart/form-data" } });
      setUploaded({ ...uploaded, [docType]: r.data.filename });
      showToast(`✓ ${DOC_LABELS[docType]}: ${r.data.filename}`);
    } catch (e) { showToast(e.response?.data?.detail || "Помилка", "err"); }
    finally { setUploading(""); }
  };

  const all = ["passport", "ipn", "diploma", "driver_license", "military_id", "certificate"];
  const missingRequired = REQUIRED.filter(t => !uploaded[t]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4"
         style={{ background: "rgba(14,26,20,.85)", backdropFilter: "blur(6px)" }}>
      <div className="bg-mil border border-mil rounded-lg w-full max-w-2xl max-h-[92vh] overflow-y-auto p-6">
        <div className="mb-4">
          <div className="text-xs uppercase tracking-wider" style={{ color: "#7A8B6C" }}>Крок 2 з 2</div>
          <h2 className="text-xl font-bold text-accent">📎 Завантажити документи</h2>
          <div className="bg-mil-deep border border-mil rounded p-3 mt-3">
            <div className="text-xs" style={{ color: "#7A8B6C" }}>Збережіть креденшіали користувача:</div>
            <div className="font-mono mt-1" style={{ fontFamily: "JetBrains Mono", color: "#A4C26A" }}>
              {username} / {password}
            </div>
          </div>
        </div>

        <div className="space-y-2">
          {all.map(t => {
            const f = uploaded[t];
            const isReq = REQUIRED.includes(t);
            return (
              <div key={t} className="bg-mil-deep border border-mil rounded p-3 flex items-center gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-semibold text-sm">{DOC_LABELS[t]}</span>
                    {isReq && <span className="badge badge-state-warn" style={{ fontSize: "9px" }}>обов'язково</span>}
                    {f && <span className="badge badge-state-ok" style={{ fontSize: "9px" }}>✓ {f}</span>}
                  </div>
                </div>
                <label className="btn-mil text-xs cursor-pointer" data-testid={`reg-upload-${t}`}>
                  {uploading === t ? "⏳ …" : (f ? "Замінити" : "+ Файл")}
                  <input type="file" className="hidden" accept="image/*,application/pdf"
                         onChange={(e) => e.target.files[0] && upload(t, e.target.files[0])} />
                </label>
              </div>
            );
          })}
        </div>

        {missingRequired.length > 0 && (
          <div className="text-xs mt-3 rounded p-2"
               style={{ background: "rgba(212,160,106,.1)", color: "#D4A06A" }}>
            ⚠ Бракує обов'язкових: {missingRequired.map(t => DOC_LABELS[t]).join(", ")}.
            Можна завантажити пізніше через картку.
          </div>
        )}

        <div className="flex gap-2 mt-5">
          <button className="btn-mil btn-mil-primary" onClick={onClose} data-testid="reg-done">
            Готово ({Object.keys(uploaded).length} завантажено)
          </button>
        </div>
      </div>
    </div>
  );
}


function EditUserModal({ u, onClose, onSaved, showToast }) {
  const { ax } = useAuth();
  const [form, setForm] = useState({ name: u.name || "", role: u.role, platoon: u.platoon || "", new_password: "" });
  const submit = async (e) => {
    e.preventDefault();
    try {
      const payload = { ...form };
      if (!payload.new_password) delete payload.new_password;
      await ax().put(`/users/${u.id}`, payload);
      showToast("✓ Збережено"); onSaved();
    } catch (e) { showToast(e.response?.data?.detail || "Помилка", "err"); }
  };
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4"
         style={{ background: "rgba(14,26,20,.85)" }} onClick={onClose}>
      <form className="bg-mil border border-mil rounded-lg w-full max-w-lg p-6"
            onSubmit={submit} onClick={(e) => e.stopPropagation()}>
        <h2 className="text-xl font-bold text-accent mb-4">✎ Редагування {u.username}</h2>
        <div className="space-y-3">
          <Field label="Ім'я / призначення">
            <input className="input-mil" value={form.name} onChange={(e) => setForm({...form, name: e.target.value})} />
          </Field>
          <Field label="Роль">
            <select className="input-mil" value={form.role} onChange={(e) => setForm({...form, role: e.target.value})}>
              <option value="VIEWER">Перегляд</option>
              <option value="MATERIAL">Матеріаліст</option>
              <option value="PLATOON_LEADER">Командир взводу</option>
              <option value="COMMANDER">Командир роти</option>
            </select>
          </Field>
          <Field label="Взвод">
            <input className="input-mil" value={form.platoon} onChange={(e) => setForm({...form, platoon: e.target.value})} />
          </Field>
          <Field label="Скинути пароль (опц.)">
            <input className="input-mil" type="text" placeholder="залишіть порожнім щоб не міняти" value={form.new_password}
                   onChange={(e) => setForm({...form, new_password: e.target.value})} />
          </Field>
        </div>
        <div className="flex gap-2 mt-5">
          <button type="submit" className="btn-mil btn-mil-primary">Зберегти</button>
          <button type="button" className="btn-mil" onClick={onClose}>Скасувати</button>
        </div>
      </form>
    </div>
  );
}


function Section({ title, children }) {
  return (
    <div className="bg-mil-deep border border-mil rounded-lg p-4 mb-4">
      <h3 className="text-sm font-bold mb-3 text-brown">{title}</h3>
      {children}
    </div>
  );
}
function Grid({ children }) { return <div className="grid grid-cols-1 md:grid-cols-2 gap-3">{children}</div>; }
function Field({ label, children }) { return <div><label className="text-xs uppercase block mb-1" style={{ color: "#7A8B6C" }}>{label}</label>{children}</div>; }
