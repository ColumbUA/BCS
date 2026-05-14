import { useState, useEffect } from "react";
import { useAuth, can } from "../AuthContext";

const STATUS_OPTIONS = ["ППД", "РЗ", "РВ", "Відрядження", "Відпустка", "Лікарня", "СЗЧ", "ВЛК", "Інше"];
const STATUS_COLOR = {
  "ППД": "#A4C26A", "РЗ": "#7AB8D8", "РВ": "#D8C36A",
  "Відрядження": "#B8A0D6", "Відпустка": "#A4C26A",
  "Лікарня": "#D67676", "СЗЧ": "#E89090", "ВЛК": "#D67676",
  "Інше": "#7A8B6C",
};

/**
 * Календар локацій солдата.
 *
 * Props:
 *   soldierId: string
 *   showToast: fn
 */
export default function LocationsEditor({ soldierId, showToast }) {
  const { ax, user } = useAuth();
  const editable = can.edit(user);
  const [items, setItems] = useState([]);
  const [today, setToday] = useState("");
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState({ effective_date: "", status: "ППД", place: "", note: "" });
  const [busy, setBusy] = useState(false);

  const load = async () => {
    try {
      const r = await ax().get(`/soldiers/${soldierId}/locations`);
      setItems(r.data.items || []);
      setToday(r.data.today || "");
    } catch (e) {
      showToast?.(e.response?.data?.detail || "Помилка завантаження локацій", "err");
    }
  };

  useEffect(() => { if (soldierId) load(); /* eslint-disable-next-line */ }, [soldierId]);

  const startAdd = () => {
    setForm({ effective_date: today || new Date().toISOString().slice(0, 10), status: "ППД", place: "", note: "" });
    setAdding(true);
  };

  const submit = async () => {
    if (!form.effective_date || !form.status) {
      showToast?.("Заповніть дату та статус", "err");
      return;
    }
    setBusy(true);
    try {
      await ax().post(`/soldiers/${soldierId}/locations`, form);
      showToast?.(`✓ Запис додано на ${form.effective_date}`);
      setAdding(false);
      await load();
    } catch (e) {
      showToast?.(e.response?.data?.detail || "Помилка", "err");
    } finally {
      setBusy(false);
    }
  };

  const remove = async (id, date, status) => {
    if (!window.confirm(`Видалити запис: ${date} → ${status}?`)) return;
    try {
      await ax().delete(`/locations/${id}`);
      showToast?.("Видалено");
      await load();
    } catch (e) {
      showToast?.(e.response?.data?.detail || "Помилка", "err");
    }
  };

  // Розділяємо на минулі/поточний/майбутні
  const past = items.filter(i => i.effective_date < today);
  const current = items.filter(i => i.effective_date === today);
  const future = items.filter(i => i.effective_date > today);
  // Якщо немає запису на today — поточним вважається останній з минулих
  const effectiveCurrent = current[0] || past[past.length - 1] || null;

  const Row = ({ it, badge }) => {
    const color = STATUS_COLOR[it.status] || "#A4C26A";
    return (
      <div className="flex items-start gap-3 py-2 px-3 rounded border border-mil"
           data-testid={`loc-row-${it.id}`}
           style={{ background: "#1B1F18", borderLeft: `4px solid ${color}` }}>
        <div className="text-xs whitespace-nowrap pt-0.5" style={{ fontFamily: "JetBrains Mono", color: "#7A8B6C" }}>
          {it.effective_date}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-bold text-sm" style={{ color }}>{it.status}</span>
            {badge && <span className="text-xs px-2 py-0.5 rounded" style={{ background: "#2F3D26", color: "#A4C26A" }}>{badge}</span>}
            {it.place && <span className="text-xs" style={{ color: "#7AB8D8" }}>📍 {it.place}</span>}
          </div>
          {it.note && <div className="text-xs mt-0.5" style={{ color: "#7A8B6C" }}>{it.note}</div>}
        </div>
        {editable && (
          <button className="btn-mil btn-mil-danger text-xs" onClick={() => remove(it.id, it.effective_date, it.status)}
                  data-testid={`loc-delete-${it.id}`} title="Видалити">✕</button>
        )}
      </div>
    );
  };

  return (
    <div className="bg-mil-deep border border-mil rounded-lg p-4" data-testid="locations-editor"
         style={{ borderLeft: "3px solid #7AB8D8" }}>
      <div className="flex items-center justify-between mb-3">
        <div>
          <div className="text-xs uppercase" style={{ color: "#7A8B6C" }}>Календар локацій</div>
          <h3 className="text-sm font-bold mt-0.5">
            📅 Розташування на дату
            {effectiveCurrent && (
              <span className="ml-3 text-xs px-2 py-1 rounded"
                    style={{ background: "#1B2A1C", color: STATUS_COLOR[effectiveCurrent.status], border: `1px solid ${STATUS_COLOR[effectiveCurrent.status]}40` }}>
                СЬОГОДНІ: {effectiveCurrent.status}
              </span>
            )}
          </h3>
        </div>
        {editable && !adding && (
          <button className="btn-mil text-xs" onClick={startAdd} data-testid="btn-add-location">
            + Запланувати
          </button>
        )}
      </div>

      {adding && (
        <div className="bg-mil border border-accent rounded p-3 mb-3" data-testid="form-new-location">
          <div className="grid grid-cols-1 md:grid-cols-5 gap-2 mb-2">
            <div>
              <div className="text-xs mb-1" style={{ color: "#7A8B6C" }}>З дати</div>
              <input type="date" className="input-mil text-sm w-full" value={form.effective_date}
                     onChange={(e) => setForm({ ...form, effective_date: e.target.value })}
                     data-testid="loc-date" />
            </div>
            <div>
              <div className="text-xs mb-1" style={{ color: "#7A8B6C" }}>Статус</div>
              <select className="input-mil text-sm w-full" value={form.status}
                      onChange={(e) => setForm({ ...form, status: e.target.value })}
                      data-testid="loc-status">
                {STATUS_OPTIONS.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
            <div className="md:col-span-2">
              <div className="text-xs mb-1" style={{ color: "#7A8B6C" }}>Місце</div>
              <input className="input-mil text-sm w-full" placeholder="н.п., адреса, координати"
                     value={form.place} onChange={(e) => setForm({ ...form, place: e.target.value })}
                     data-testid="loc-place" />
            </div>
            <div className="flex items-end gap-1">
              <button className="btn-mil btn-mil-primary text-xs flex-1"
                      onClick={submit} disabled={busy} data-testid="btn-loc-save">
                {busy ? "⏳" : "Зберегти"}
              </button>
              <button className="btn-mil text-xs" onClick={() => setAdding(false)}>✕</button>
            </div>
          </div>
          <input className="input-mil text-sm w-full" placeholder="Примітка (необовʼязково)"
                 value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })}
                 data-testid="loc-note" />
        </div>
      )}

      <div className="space-y-2">
        {items.length === 0 && (
          <div className="text-center py-4 text-xs" style={{ color: "#5C6E54" }}>
            Записів локацій ще немає. Натисніть «+ Запланувати» щоб додати поточну позицію та плани на майбутнє.
          </div>
        )}

        {past.slice(-3).map(it => <Row key={it.id} it={it} />)}

        {past.length > 3 && (
          <div className="text-center text-xs py-1" style={{ color: "#5C6E54" }}>
            ↑ ще {past.length - 3} минулих записів
          </div>
        )}

        {current.map(it => <Row key={it.id} it={it} badge="СЬОГОДНІ" />)}

        {future.length > 0 && (
          <>
            <div className="text-xs mt-3 mb-1" style={{ color: "#7AB8D8" }}>
              ▼ ЗАПЛАНОВАНО ({future.length})
            </div>
            {future.map(it => <Row key={it.id} it={it} />)}
          </>
        )}
      </div>
    </div>
  );
}
