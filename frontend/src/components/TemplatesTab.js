import { useEffect, useState } from "react";
import { useAuth } from "../AuthContext";
import { cls } from "./Common";

const CAT_ICONS = {
  "Рапорти": "📝",
  "Накази": "📜",
  "Акти": "📋",
  "Журнали": "📚",
  "Донесення": "📊",
};

export default function TemplatesTab({ showToast }) {
  const { ax, token } = useAuth();
  const [items, setItems] = useState([]);
  const [soldiers, setSoldiers] = useState([]);
  const [selectedSoldier, setSelectedSoldier] = useState("");
  const [downloading, setDownloading] = useState("");
  const [showSettings, setShowSettings] = useState(false);

  const reload = async () => {
    const [t, s] = await Promise.all([ax().get("/templates"), ax().get("/soldiers")]);
    setItems(t.data.templates); setSoldiers(s.data);
  };
  useEffect(() => { reload(); }, []);

  const download = async (tpl) => {
    setDownloading(tpl.id);
    try {
      const url = `${process.env.REACT_APP_BACKEND_URL}/api/templates/${tpl.id}/render` +
                  (selectedSoldier ? `?soldier_id=${selectedSoldier}` : "");
      const res = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob();
      const u = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = u; a.download = `${tpl.name}.docx`;
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(u), 1000);
      showToast(`Завантажено: ${tpl.name}.docx`);
    } catch (e) { showToast(`Помилка: ${e.message}`, "err"); }
    finally { setDownloading(""); }
  };

  const grouped = items.reduce((m, t) => { (m[t.category] = m[t.category] || []).push(t); return m; }, {});
  const order = ["Рапорти", "Накази", "Акти", "Журнали", "Донесення"];

  return (
    <div>
      <div className="bg-mil border border-mil rounded-lg p-4 mb-5"
           style={{ borderLeft: "4px solid #D4A06A" }}>
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div>
            <div className="text-xs uppercase mb-1" style={{ color: "#7A8B6C" }}>
              Зразки документів — звіряйте з керівними документами вашої частини
            </div>
            <div className="text-sm">
              Автозаповнення з картки солдата (ПІБ, звання, посада, підрозділ).
            </div>
          </div>
          <div className="flex gap-2 flex-wrap items-center">
            <select className="input-mil" style={{ width: "auto" }} value={selectedSoldier}
                    onChange={(e) => setSelectedSoldier(e.target.value)} data-testid="tpl-soldier">
              <option value="">— Без автозаповнення —</option>
              {soldiers.map(s => (
                <option key={s.id} value={s.id}>
                  {s.fio} {s.callsign && `«${s.callsign}»`}
                </option>
              ))}
            </select>
            <button className="btn-mil text-sm" onClick={() => setShowSettings(true)} data-testid="btn-settings">
              ⚙ Реквізити частини
            </button>
          </div>
        </div>
      </div>

      {order.filter(c => grouped[c]).map(cat => (
        <div key={cat} className="mb-6">
          <h3 className="text-lg font-bold tracking-wide mb-3 text-accent">
            {CAT_ICONS[cat]} {cat.toUpperCase()} <span className="text-xs ml-2" style={{ color: "#7A8B6C" }}>({grouped[cat].length})</span>
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {grouped[cat].map(t => (
              <div key={t.id} className="bg-mil border border-mil rounded-lg p-4 flex flex-col gap-2"
                   data-testid={`tpl-${t.id}`}>
                <div className="font-semibold flex-1">{t.name}</div>
                {t.desc && <div className="text-xs" style={{ color: "#7A8B6C" }}>{t.desc}</div>}
                <button className="btn-mil btn-mil-primary text-xs justify-center mt-1"
                        onClick={() => download(t)} disabled={downloading === t.id}
                        data-testid={`tpl-dl-${t.id}`}>
                  {downloading === t.id ? "⏳ …" : "⬇ Завантажити .docx"}
                </button>
              </div>
            ))}
          </div>
        </div>
      ))}

      {showSettings && <SettingsModal onClose={() => setShowSettings(false)} showToast={showToast} />}
    </div>
  );
}


function SettingsModal({ onClose, showToast }) {
  const { ax, user } = useAuth();
  const editable = user?.role === "COMMANDER";
  const [form, setForm] = useState(null);

  useEffect(() => {
    ax().get("/settings").then(r => setForm(r.data));
  }, []);

  const save = async () => {
    try { await ax().put("/settings", form); showToast("✓ Збережено"); onClose(); }
    catch (e) { showToast(e.response?.data?.detail || "Помилка", "err"); }
  };

  if (!form) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4"
         style={{ background: "rgba(14,26,20,.85)", backdropFilter: "blur(6px)" }} onClick={onClose}>
      <div className="bg-mil border border-mil rounded-lg p-6 w-full max-w-2xl"
           onClick={(e) => e.stopPropagation()}>
        <div className="flex justify-between items-start mb-4">
          <div>
            <h2 className="text-xl font-bold text-accent">Реквізити військової частини</h2>
            <div className="text-xs mt-1" style={{ color: "#7A8B6C" }}>Підставляються у шапку всіх документів</div>
          </div>
          <button className="btn-mil text-xs" onClick={onClose}>✕</button>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <Field label="Повна назва частини">
            <input className="input-mil" value={form.unit_full} disabled={!editable}
                   onChange={(e) => setForm({...form, unit_full: e.target.value})}
                   placeholder="напр. Розвідувальний батальйон ____ ОМБр" />
          </Field>
          <Field label="Скорочення (в/ч)">
            <input className="input-mil" value={form.unit_short} disabled={!editable}
                   onChange={(e) => setForm({...form, unit_short: e.target.value})}
                   placeholder="напр. в/ч А1234" />
          </Field>
          <Field label="ПІБ командира частини">
            <input className="input-mil" value={form.unit_chief} disabled={!editable}
                   onChange={(e) => setForm({...form, unit_chief: e.target.value})}
                   placeholder="ПЕТРЕНКО І.І." />
          </Field>
          <Field label="Звання командира частини">
            <input className="input-mil" value={form.unit_chief_rank} disabled={!editable}
                   onChange={(e) => setForm({...form, unit_chief_rank: e.target.value})}
                   placeholder="полковник" />
          </Field>
          <Field label="Місто/н.п.">
            <input className="input-mil" value={form.city} disabled={!editable}
                   onChange={(e) => setForm({...form, city: e.target.value})} />
          </Field>
          <Field label="Назва роти">
            <input className="input-mil" value={form.company_name} disabled={!editable}
                   onChange={(e) => setForm({...form, company_name: e.target.value})} />
          </Field>
        </div>
        {editable && (
          <div className="flex gap-2 mt-5">
            <button className="btn-mil btn-mil-primary" onClick={save} data-testid="btn-settings-save">Зберегти</button>
            <button className="btn-mil" onClick={onClose}>Скасувати</button>
          </div>
        )}
        {!editable && <div className="text-xs mt-3" style={{ color: "#7A8B6C" }}>Лише командир роти може редагувати реквізити.</div>}
      </div>
    </div>
  );
}

function Field({ label, children }) {
  return <div><label className="text-xs uppercase block mb-1" style={{ color: "#7A8B6C" }}>{label}</label>{children}</div>;
}
