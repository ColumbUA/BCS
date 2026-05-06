import { useEffect, useState, useMemo } from "react";
import { useAuth, can } from "../AuthContext";
import { cls } from "./Common";

const TXN_LABELS = { IN: "Прихід", OUT: "Видача", WRITEOFF: "Списання" };
const TXN_COLORS = {
  IN: { color: "#A4C26A", bg: "rgba(164,194,106,.15)", border: "#3D5A2C" },
  OUT: { color: "#7AB8D8", bg: "rgba(122,184,216,.15)", border: "#2C4A5E" },
  WRITEOFF: { color: "#E89090", bg: "rgba(232,144,144,.15)", border: "#4A2C2C" },
};

export default function WarehouseTab({ config, showToast }) {
  const { ax, user } = useAuth();
  const editable = can.edit(user);
  const [items, setItems] = useState([]);
  const [filter, setFilter] = useState("");
  const [catFilter, setCatFilter] = useState("");
  const [selectedItem, setSelectedItem] = useState(null);
  const [showAdd, setShowAdd] = useState(false);
  const [editItem, setEditItem] = useState(null);

  const reload = async () => { const r = await ax().get("/warehouse/items"); setItems(r.data); };
  useEffect(() => { reload(); }, []);

  const filtered = items.filter(i => {
    if (catFilter && i.category !== catFilter) return false;
    if (filter) {
      const f = filter.toLowerCase();
      return i.name.toLowerCase().includes(f) || (i.serial || "").toLowerCase().includes(f);
    }
    return true;
  });

  const stats = useMemo(() => {
    const total = items.reduce((a, b) => a + (b.balance || 0), 0);
    const lowStock = items.filter(i => i.below_min).length;
    const cats = {};
    items.forEach(i => { cats[i.category] = (cats[i.category] || 0) + (i.balance || 0); });
    return { total, lowStock, cats };
  }, [items]);

  return (
    <div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-5">
        <div className="bg-mil border border-mil rounded p-3">
          <div className="text-2xl font-bold text-accent" style={{ fontFamily: "JetBrains Mono" }}>{items.length}</div>
          <div className="text-xs uppercase" style={{ color: "#7A8B6C" }}>Позицій</div>
        </div>
        <div className="bg-mil border border-mil rounded p-3">
          <div className="text-2xl font-bold text-blue" style={{ fontFamily: "JetBrains Mono" }}>{stats.total.toLocaleString("uk")}</div>
          <div className="text-xs uppercase" style={{ color: "#7A8B6C" }}>На залишку</div>
        </div>
        <div className="bg-mil border border-mil rounded p-3">
          <div className="text-2xl font-bold" style={{ color: stats.lowStock ? "#E89090" : "#A4C26A", fontFamily: "JetBrains Mono" }}>{stats.lowStock}</div>
          <div className="text-xs uppercase" style={{ color: "#7A8B6C" }}>Нижче мін.</div>
        </div>
        <div className="bg-mil border border-mil rounded p-3">
          <div className="text-2xl font-bold text-purple" style={{ fontFamily: "JetBrains Mono" }}>{Object.keys(stats.cats).length}</div>
          <div className="text-xs uppercase" style={{ color: "#7A8B6C" }}>Категорій</div>
        </div>
      </div>

      <div className="flex flex-wrap gap-3 mb-4 items-center">
        <input className="input-mil flex-1 min-w-[240px]" placeholder="🔍 Пошук за назвою / SN"
               value={filter} onChange={(e) => setFilter(e.target.value)} />
        <select className="input-mil" style={{ width: "auto" }} value={catFilter} onChange={(e) => setCatFilter(e.target.value)}>
          <option value="">Усі категорії</option>
          {(config?.warehouse_categories || []).map(c => <option key={c}>{c}</option>)}
        </select>
        {editable && (
          <button className="btn-mil btn-mil-primary text-sm" onClick={() => setShowAdd(true)} data-testid="btn-wh-add">
            + Додати позицію
          </button>
        )}
        <div className="text-sm ml-auto" style={{ color: "#7A8B6C" }}>
          Показано: <span className="text-accent font-bold">{filtered.length}</span> / {items.length}
        </div>
      </div>

      {filtered.length === 0 ? (
        <div className="text-center py-12 bg-mil border border-dashed border-mil rounded-lg" style={{ color: "#5C6E54" }}>
          Складських позицій ще немає. {editable && "Додайте першу через '+ Додати позицію'"}
        </div>
      ) : (
        <div className="bg-mil border border-mil rounded-lg overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-mil-deep">
              <tr style={{ color: "#7A8B6C" }}>
                <th className="text-left px-3 py-2 uppercase text-xs">Найменування</th>
                <th className="text-left px-3 py-2 uppercase text-xs">Категорія</th>
                <th className="text-left px-3 py-2 uppercase text-xs">SN/Інв.№</th>
                <th className="text-right px-3 py-2 uppercase text-xs">Залишок</th>
                <th className="text-right px-3 py-2 uppercase text-xs">Мін.</th>
                <th className="px-3 py-2"></th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(it => (
                <tr key={it.id} className={cls("border-t border-mil hover:bg-mil-deep cursor-pointer",
                                                it.below_min && "bg-red-900/10")}
                    onClick={() => setSelectedItem(it.id)} data-testid={`wh-item-${it.id}`}>
                  <td className="px-3 py-2 font-semibold">{it.name}</td>
                  <td className="px-3 py-2"><span className="badge badge-cat">{it.category}</span></td>
                  <td className="px-3 py-2 text-xs" style={{ color: "#7A8B6C", fontFamily: "JetBrains Mono" }}>{it.serial || "—"}</td>
                  <td className="px-3 py-2 text-right font-bold" style={{ fontFamily: "JetBrains Mono", color: it.below_min ? "#E89090" : "#A4C26A" }}>
                    {it.balance.toLocaleString("uk")} {it.unit}
                  </td>
                  <td className="px-3 py-2 text-right text-xs" style={{ color: "#7A8B6C" }}>{it.min_balance || "—"}</td>
                  <td className="px-3 py-2 text-right">
                    {editable && (
                      <button className="btn-mil text-xs py-1 px-2" onClick={(e) => { e.stopPropagation(); setEditItem(it); }}>✎</button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showAdd && <ItemModal config={config} onClose={() => setShowAdd(false)} onSaved={() => { setShowAdd(false); reload(); }} showToast={showToast} />}
      {editItem && <ItemModal config={config} item={editItem} onClose={() => setEditItem(null)} onSaved={() => { setEditItem(null); reload(); }} showToast={showToast} />}
      {selectedItem && <ItemDetailModal itemId={selectedItem} onClose={() => { setSelectedItem(null); reload(); }} showToast={showToast} />}
    </div>
  );
}


function ItemModal({ item, config, onClose, onSaved, showToast }) {
  const { ax } = useAuth();
  const [form, setForm] = useState(item || { name: "", category: "Майно (речове)", unit: "шт", serial: "", notes: "", min_balance: 0 });
  const submit = async (e) => {
    e.preventDefault();
    try {
      if (item) await ax().put(`/warehouse/items/${item.id}`, form);
      else await ax().post("/warehouse/items", form);
      showToast(item ? "✓ Оновлено" : "✓ Додано");
      onSaved();
    } catch (e2) { showToast(e2.response?.data?.detail || "Помилка", "err"); }
  };
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4"
         style={{ background: "rgba(14,26,20,.85)", backdropFilter: "blur(6px)" }} onClick={onClose}>
      <form className="bg-mil border border-mil rounded-lg p-6 w-full max-w-2xl"
            onSubmit={submit} onClick={(e) => e.stopPropagation()}>
        <h2 className="text-xl font-bold text-accent mb-4">
          {item ? "✎ Редагувати позицію" : "+ Додати складську позицію"}
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div className="md:col-span-2">
            <Field label="Найменування *">
              <input className="input-mil" required value={form.name} onChange={(e) => setForm({...form, name: e.target.value})}
                     placeholder="напр. Бронежилет 6Б45" data-testid="wh-name" />
            </Field>
          </div>
          <Field label="Категорія">
            <select className="input-mil" value={form.category} onChange={(e) => setForm({...form, category: e.target.value})}>
              {(config?.warehouse_categories || []).map(c => <option key={c}>{c}</option>)}
            </select>
          </Field>
          <Field label="Одиниця">
            <input className="input-mil" value={form.unit} onChange={(e) => setForm({...form, unit: e.target.value})} placeholder="шт / кг / л" />
          </Field>
          <Field label="Серійний / Інв.№">
            <input className="input-mil" value={form.serial} onChange={(e) => setForm({...form, serial: e.target.value})} />
          </Field>
          <Field label="Мін. залишок (для алерту)">
            <input type="number" min="0" className="input-mil" value={form.min_balance} onChange={(e) => setForm({...form, min_balance: parseInt(e.target.value) || 0})} />
          </Field>
          <div className="md:col-span-2">
            <Field label="Примітки">
              <input className="input-mil" value={form.notes} onChange={(e) => setForm({...form, notes: e.target.value})} />
            </Field>
          </div>
        </div>
        <div className="flex gap-2 mt-5">
          <button type="submit" className="btn-mil btn-mil-primary" data-testid="wh-submit">{item ? "Зберегти" : "Додати"}</button>
          <button type="button" className="btn-mil" onClick={onClose}>Скасувати</button>
        </div>
      </form>
    </div>
  );
}


function ItemDetailModal({ itemId, onClose, showToast }) {
  const { ax, user } = useAuth();
  const editable = can.edit(user);
  const isCommander = user?.role === "COMMANDER";
  const [item, setItem] = useState(null);
  const [txns, setTxns] = useState([]);
  const [showTxn, setShowTxn] = useState(null);

  const load = async () => {
    const [items, t] = await Promise.all([ax().get("/warehouse/items"), ax().get(`/warehouse/items/${itemId}/txns`)]);
    setItem(items.data.find(i => i.id === itemId));
    setTxns(t.data);
  };
  useEffect(() => { load(); }, [itemId]);

  const removeTxn = async (id) => {
    if (!window.confirm("Видалити транзакцію? Залишок буде перерахований.")) return;
    await ax().delete(`/warehouse/txns/${id}`); showToast("Видалено"); load();
  };

  const removeItem = async () => {
    if (!window.confirm(`Видалити позицію '${item.name}' разом з усіма транзакціями?`)) return;
    await ax().delete(`/warehouse/items/${itemId}`); showToast("Видалено"); onClose();
  };

  if (!item) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4"
         style={{ background: "rgba(14,26,20,.85)", backdropFilter: "blur(6px)" }} onClick={onClose}>
      <div className="bg-mil border border-mil rounded-lg w-full max-w-3xl max-h-[90vh] overflow-y-auto"
           onClick={(e) => e.stopPropagation()}>
        <div className="sticky top-0 bg-mil border-b border-mil p-5 z-10 flex justify-between items-start">
          <div>
            <div className="text-xs uppercase" style={{ color: "#7A8B6C" }}>Складська позиція</div>
            <h2 className="text-xl font-bold text-accent">{item.name}</h2>
            <div className="flex gap-2 mt-1">
              <span className="badge badge-cat">{item.category}</span>
              {item.serial && <span className="text-xs" style={{ color: "#7A8B6C", fontFamily: "JetBrains Mono" }}>SN: {item.serial}</span>}
            </div>
          </div>
          <div className="flex gap-2">
            {isCommander && (
              <button className="btn-mil btn-mil-danger text-xs" onClick={removeItem} data-testid="wh-delete-item">✕ Позицію</button>
            )}
            <button className="btn-mil text-xs" onClick={onClose}>✕</button>
          </div>
        </div>

        <div className="p-5">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-5">
            <Stat label="Залишок" value={`${item.balance} ${item.unit}`} color={item.below_min ? "#E89090" : "#A4C26A"} />
            <Stat label="Прихід" value={txns.filter(t => t.type === "IN").reduce((a, b) => a + b.qty, 0)} color="#A4C26A" />
            <Stat label="Видача" value={txns.filter(t => t.type === "OUT").reduce((a, b) => a + b.qty, 0)} color="#7AB8D8" />
            <Stat label="Списано" value={txns.filter(t => t.type === "WRITEOFF").reduce((a, b) => a + b.qty, 0)} color="#E89090" />
          </div>

          {editable && (
            <div className="flex gap-2 mb-4 flex-wrap">
              <button className="btn-mil text-sm" onClick={() => setShowTxn("IN")} data-testid="wh-btn-in"
                      style={{ borderColor: "#3D5A2C", color: "#A4C26A" }}>+ Прихід</button>
              <button className="btn-mil text-sm" onClick={() => setShowTxn("OUT")} data-testid="wh-btn-out"
                      style={{ borderColor: "#2C4A5E", color: "#7AB8D8" }}>↗ Видача</button>
              <button className="btn-mil text-sm" onClick={() => setShowTxn("WRITEOFF")} data-testid="wh-btn-writeoff"
                      style={{ borderColor: "#4A2C2C", color: "#E89090" }}>✕ Списання</button>
            </div>
          )}

          <h3 className="text-sm uppercase tracking-wider mb-2" style={{ color: "#7A8B6C" }}>Журнал операцій</h3>
          {txns.length === 0 ? (
            <div className="text-center py-8 border border-dashed border-mil rounded text-sm" style={{ color: "#5C6E54" }}>
              Операцій ще немає
            </div>
          ) : (
            <div className="space-y-2">
              {txns.slice().reverse().map(t => {
                const c = TXN_COLORS[t.type];
                return (
                  <div key={t.id} className="bg-mil-deep border border-mil rounded p-3 flex items-center gap-3">
                    <div className="badge" style={{ background: c.bg, color: c.color, border: `1px solid ${c.border}`, fontSize: "10px" }}>
                      {TXN_LABELS[t.type]}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-bold" style={{ fontFamily: "JetBrains Mono", color: c.color }}>
                          {t.type === "IN" ? "+" : "−"}{t.qty} {item.unit}
                        </span>
                        {t.counterparty && <span className="text-sm">{t.type === "IN" ? "від" : "→"} {t.counterparty}</span>}
                        {t.doc_ref && <span className="text-xs" style={{ color: "#7A8B6C" }}>· {t.doc_ref}</span>}
                      </div>
                      <div className="text-xs mt-0.5" style={{ color: "#7A8B6C" }}>
                        {t.created_at?.slice(0, 16).replace("T", " ")} · {t.created_by}
                        {t.reason && ` · ${t.reason}`}
                        {t.notes && ` · ${t.notes}`}
                      </div>
                    </div>
                    {isCommander && (
                      <button className="btn-mil btn-mil-danger text-xs py-1 px-2" onClick={() => removeTxn(t.id)}>✕</button>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {showTxn && (
          <TxnModal type={showTxn} itemId={itemId} unit={item.unit} balance={item.balance}
                    onClose={() => setShowTxn(null)} onSaved={() => { setShowTxn(null); load(); }} showToast={showToast} />
        )}
      </div>
    </div>
  );
}


function TxnModal({ type, itemId, unit, balance, onClose, onSaved, showToast }) {
  const { ax } = useAuth();
  const [form, setForm] = useState({ qty: 1, counterparty: "", doc_ref: "", reason: "", notes: "", date: new Date().toISOString().slice(0, 10) });
  const submit = async (e) => {
    e.preventDefault();
    try {
      await ax().post("/warehouse/txns", { ...form, item_id: itemId, type });
      showToast(`✓ ${TXN_LABELS[type]} записано`);
      onSaved();
    } catch (e2) { showToast(e2.response?.data?.detail || "Помилка", "err"); }
  };
  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4"
         style={{ background: "rgba(14,26,20,.9)" }} onClick={onClose}>
      <form className="bg-mil border border-mil rounded-lg p-6 w-full max-w-md"
            onSubmit={submit} onClick={(e) => e.stopPropagation()}>
        <h3 className="text-lg font-bold mb-3" style={{ color: TXN_COLORS[type].color }}>
          {TXN_LABELS[type]}
          <span className="text-xs ml-3" style={{ color: "#7A8B6C" }}>Залишок: {balance} {unit}</span>
        </h3>
        <div className="space-y-3">
          <Field label={`Кількість, ${unit} *`}>
            <input type="number" min="1" max={type === "IN" ? undefined : balance} className="input-mil" required
                   value={form.qty} onChange={(e) => setForm({...form, qty: parseInt(e.target.value) || 1})}
                   data-testid="wh-txn-qty" />
          </Field>
          <Field label={type === "IN" ? "Постачальник / від кого" : "Кому видано"}>
            <input className="input-mil" value={form.counterparty} onChange={(e) => setForm({...form, counterparty: e.target.value})} />
          </Field>
          <Field label="№ документа (накладна / акт / розписка)">
            <input className="input-mil" value={form.doc_ref} onChange={(e) => setForm({...form, doc_ref: e.target.value})} />
          </Field>
          {type === "WRITEOFF" && (
            <Field label="Причина списання">
              <input className="input-mil" value={form.reason} onChange={(e) => setForm({...form, reason: e.target.value})}
                     placeholder="Зношення / втрата / пошкодження" />
            </Field>
          )}
          <Field label="Дата">
            <input type="date" className="input-mil" value={form.date} onChange={(e) => setForm({...form, date: e.target.value})} />
          </Field>
        </div>
        <div className="flex gap-2 mt-5">
          <button type="submit" className="btn-mil btn-mil-primary" data-testid="wh-txn-submit">Зберегти</button>
          <button type="button" className="btn-mil" onClick={onClose}>Скасувати</button>
        </div>
      </form>
    </div>
  );
}

function Field({ label, children }) {
  return <div><label className="text-xs uppercase block mb-1" style={{ color: "#7A8B6C" }}>{label}</label>{children}</div>;
}
function Stat({ label, value, color }) {
  return (
    <div className="bg-mil-deep border border-mil rounded p-2.5">
      <div className="text-xl font-bold" style={{ color, fontFamily: "JetBrains Mono" }}>{value}</div>
      <div className="text-xs uppercase" style={{ color: "#7A8B6C" }}>{label}</div>
    </div>
  );
}
