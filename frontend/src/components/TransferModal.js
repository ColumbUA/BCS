import { useState, useEffect } from "react";
import { useAuth } from "../AuthContext";

const TRANSFER_TYPES = [
  { v: "in-rota",    l: "Переміщення в межах роти" },
  { v: "in-bat",     l: "Переміщення в межах батальйону" },
  { v: "in-polk",    l: "Переміщення в межах полка" },
  { v: "in-brigade", l: "Переміщення в межах бригади" },
  { v: "in-zsu",     l: "Переміщення між частинами ЗСУ" },
  { v: "discharge",  l: "Звільнення з військової служби" },
  { v: "deceased",   l: "Виключення зі списків (загибель)" },
  { v: "missing",    l: "Виключення зі списків (зник безвісти)" },
];
const STATUS_LABELS = {
  draft: "Чернетка", submitted: "Подано", approved: "Затверджено",
  executed: "Виконано", rejected: "Відхилено",
};
const STATUS_COLORS = {
  draft: "#7A8B6C", submitted: "#7AB8D8", approved: "#A4C26A",
  executed: "#A4C26A", rejected: "#E89090",
};

// Recommend doc template per transfer type
const RECOMMENDED_DOCS = {
  "in-rota": ["report_handover"],
  "in-bat": ["report_handover", "act_position_handover"],
  "in-polk": ["report_handover", "act_position_handover"],
  "in-brigade": ["report_handover", "act_position_handover"],
  "in-zsu": ["report_handover", "act_position_handover"],
  "discharge": ["report_dismissal_contract", "report_dismissal_health", "act_position_handover"],
  "deceased": ["losses_report"],
  "missing": ["losses_report"],
};

export default function TransferModal({ soldier, onClose, onChanged, showToast }) {
  const { ax, user } = useAuth();
  const [transfers, setTransfers] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [busy, setBusy] = useState(false);

  const reload = async () => {
    const r = await ax().get(`/soldiers/${soldier.id}/transfers`);
    setTransfers(r.data);
  };
  useEffect(() => { reload(); }, [soldier.id]);

  const execute = async (t) => {
    if (!window.confirm(`Виконати переміщення?\n\n${TRANSFER_TYPES.find(x => x.v === t.transfer_type)?.l}\n${t.from_node_path} → ${t.to_node_path}\n\nКартка солдата буде оновлена.`)) return;
    setBusy(true);
    try {
      await ax().post(`/transfers/${t.id}/execute`);
      showToast("✓ Переміщення виконано");
      reload(); onChanged && onChanged();
    } catch (e) { showToast(e.response?.data?.detail || "Помилка", "err"); }
    finally { setBusy(false); }
  };

  const remove = async (t) => {
    if (!window.confirm("Видалити запис переміщення?")) return;
    await ax().delete(`/transfers/${t.id}`); showToast("Видалено"); reload();
  };

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4"
         style={{ background: "rgba(14,26,20,.85)", backdropFilter: "blur(6px)" }} onClick={onClose}>
      <div className="bg-mil border border-mil rounded-lg w-full max-w-3xl max-h-[92vh] overflow-y-auto"
           onClick={(e) => e.stopPropagation()}>
        <div className="sticky top-0 bg-mil border-b border-mil p-5 flex justify-between items-start">
          <div>
            <div className="text-xs uppercase" style={{ color: "#7A8B6C" }}>Переміщення військовослужбовця</div>
            <h2 className="text-xl font-bold text-accent">🔄 {soldier.fio}</h2>
            <div className="text-xs mt-1" style={{ color: "#7A8B6C" }}>{soldier.node_path}</div>
          </div>
          <div className="flex gap-2">
            <button className="btn-mil btn-mil-primary text-sm" onClick={() => setShowForm(true)} data-testid="btn-new-transfer">
              + Нове
            </button>
            <button className="btn-mil text-xs" onClick={onClose}>✕</button>
          </div>
        </div>

        <div className="p-5">
          {transfers.length === 0 ? (
            <div className="text-center py-10 border border-dashed border-mil rounded" style={{ color: "#5C6E54" }}>
              Переміщень ще не було
            </div>
          ) : (
            <div className="space-y-2">
              {transfers.map(t => {
                const type = TRANSFER_TYPES.find(x => x.v === t.transfer_type);
                return (
                  <div key={t.id} className="bg-mil-deep border border-mil rounded p-3"
                       data-testid={`tr-${t.id}`}>
                    <div className="flex items-start gap-3">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap mb-1">
                          <span className="font-semibold">{type?.l || t.transfer_type}</span>
                          <span className="badge"
                            style={{ background: `${STATUS_COLORS[t.status]}30`, color: STATUS_COLORS[t.status],
                                     border: `1px solid ${STATUS_COLORS[t.status]}`, fontSize: "10px" }}>
                            {STATUS_LABELS[t.status]}
                          </span>
                          {t.order_number && <span className="text-xs" style={{ color: "#D4A06A" }}>наказ № {t.order_number}</span>}
                        </div>
                        <div className="text-sm" style={{ color: "#E8F0D8" }}>
                          <span style={{ color: "#7A8B6C" }}>{t.from_node_path || "—"}</span>
                          <span className="text-accent mx-2">→</span>
                          <span>{t.to_node_path}</span>
                        </div>
                        {t.new_position && <div className="text-xs mt-1"><span style={{ color: "#7A8B6C" }}>Нова посада:</span> {t.new_position}</div>}
                        {t.reason && <div className="text-xs" style={{ color: "#7A8B6C" }}>{t.reason}</div>}
                        <div className="text-xs mt-1" style={{ color: "#5C6E54" }}>
                          {t.effective_date && `від ${t.effective_date} • `}
                          {t.created_at?.slice(0, 10)} • {t.created_by}
                          {t.executed_at && ` • виконано ${t.executed_at.slice(0, 10)}`}
                        </div>
                      </div>
                      <div className="flex flex-col gap-1">
                        {t.status !== "executed" && (
                          <button className="btn-mil btn-mil-primary text-xs py-1 px-2"
                                  onClick={() => execute(t)} disabled={busy}>
                            ▶ Виконати
                          </button>
                        )}
                        {user?.role === "COMMANDER" && (
                          <button className="btn-mil btn-mil-danger text-xs py-1 px-2" onClick={() => remove(t)}>✕</button>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {showForm && (
          <TransferForm soldier={soldier}
            onClose={() => setShowForm(false)}
            onCreated={() => { setShowForm(false); reload(); onChanged && onChanged(); }}
            showToast={showToast} />
        )}
      </div>
    </div>
  );
}


function TransferForm({ soldier, onClose, onCreated, showToast }) {
  const { ax, token } = useAuth();
  const [form, setForm] = useState({
    soldier_id: soldier.id,
    transfer_type: "in-rota",
    from_node_path: soldier.node_path || "",
    to_node_path: "",
    new_position: "",
    reason: "",
    effective_date: "",
    order_number: "",
    status: "draft",
    notes: "",
  });
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    if (!form.to_node_path.trim()) { showToast("Вкажіть куди", "err"); return; }
    setBusy(true);
    try {
      const r = await ax().post("/transfers", form);
      showToast("✓ Створено. Можна сформувати супровідні документи.");
      // Suggest generating doc
      const recs = RECOMMENDED_DOCS[form.transfer_type] || [];
      if (recs.length && window.confirm(`Згенерувати супровідний документ?\n\nРекомендовано: ${recs[0]}\n(збережеться у картці)`)) {
        const url = `${process.env.REACT_APP_BACKEND_URL}/api/templates/${recs[0]}/render?soldier_id=${soldier.id}&save_to_card=1`;
        const res = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
        if (res.ok) {
          const blob = await res.blob();
          const u = URL.createObjectURL(blob);
          const a = document.createElement("a"); a.href = u; a.download = `Документ_до_переміщення.docx`;
          document.body.appendChild(a); a.click(); a.remove();
          setTimeout(() => URL.revokeObjectURL(u), 1000);
          showToast("✓ Документ згенеровано і збережено у картці");
        }
      }
      onCreated();
    } catch (e) { showToast(e.response?.data?.detail || "Помилка", "err"); }
    finally { setBusy(false); }
  };

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center p-4"
         style={{ background: "rgba(14,26,20,.9)" }} onClick={onClose}>
      <form className="bg-mil border border-mil rounded-lg w-full max-w-2xl p-6 max-h-[92vh] overflow-y-auto"
            onSubmit={submit} onClick={(e) => e.stopPropagation()}>
        <h2 className="text-xl font-bold text-accent mb-4">+ Створення переміщення</h2>
        <div className="space-y-3">
          <Field label="Тип переміщення *">
            <select className="input-mil" value={form.transfer_type}
                    onChange={(e) => setForm({...form, transfer_type: e.target.value})}
                    data-testid="tr-type">
              {TRANSFER_TYPES.map(t => <option key={t.v} value={t.v}>{t.l}</option>)}
            </select>
          </Field>
          <Field label="Звідки">
            <input className="input-mil" value={form.from_node_path}
                   onChange={(e) => setForm({...form, from_node_path: e.target.value})} />
          </Field>
          <Field label="Куди *">
            <input className="input-mil" required value={form.to_node_path}
                   onChange={(e) => setForm({...form, to_node_path: e.target.value})}
                   placeholder={form.transfer_type === "in-rota"
                                ? "напр. 1 Взвод радіорозвідки / 2 Відділення"
                                : "напр. в/ч А1234 (47 ОМБр) / м.Київ / запас"}
                   data-testid="tr-to" />
          </Field>
          {form.transfer_type === "in-rota" && (
            <Field label="Нова посада (опц.)">
              <input className="input-mil" value={form.new_position}
                     onChange={(e) => setForm({...form, new_position: e.target.value})}
                     placeholder="Якщо змінюється" />
            </Field>
          )}
          <div className="grid grid-cols-2 gap-3">
            <Field label="Дата набуття чинності">
              <input type="date" className="input-mil" value={form.effective_date}
                     onChange={(e) => setForm({...form, effective_date: e.target.value})} />
            </Field>
            <Field label="№ наказу">
              <input className="input-mil" value={form.order_number}
                     onChange={(e) => setForm({...form, order_number: e.target.value})}
                     placeholder="напр. 123-К" />
            </Field>
          </div>
          <Field label="Підстава / причина">
            <input className="input-mil" value={form.reason}
                   onChange={(e) => setForm({...form, reason: e.target.value})}
                   placeholder="напр. рапорт від __.__, ВЛК, посилення підрозділу" />
          </Field>
          <Field label="Статус">
            <select className="input-mil" value={form.status}
                    onChange={(e) => setForm({...form, status: e.target.value})}>
              <option value="draft">Чернетка</option>
              <option value="submitted">Подано (на розгляді)</option>
              <option value="approved">Затверджено</option>
              <option value="executed">Виконано</option>
            </select>
          </Field>
          <Field label="Примітки">
            <textarea rows="2" className="input-mil" value={form.notes}
                      onChange={(e) => setForm({...form, notes: e.target.value})} />
          </Field>
        </div>
        <div className="flex gap-2 mt-5">
          <button type="submit" className="btn-mil btn-mil-primary" disabled={busy} data-testid="tr-submit">
            {busy ? "…" : "Створити + сформувати документ"}
          </button>
          <button type="button" className="btn-mil" onClick={onClose}>Скасувати</button>
        </div>
        <div className="text-xs mt-3" style={{ color: "#7A8B6C" }}>
          ℹ Після створення можна одразу згенерувати супровідний документ (рапорт/клопотання/наказ),
          який буде збережено у картці військового.
        </div>
      </form>
    </div>
  );
}

function Field({ label, children }) {
  return <div><label className="text-xs uppercase block mb-1" style={{ color: "#7A8B6C" }}>{label}</label>{children}</div>;
}
