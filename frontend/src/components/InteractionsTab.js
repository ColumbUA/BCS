import { useState, useMemo } from "react";
import { useAuth, can } from "../AuthContext";
import { cls } from "./Common";

export default function InteractionsTab({ interactions, structure, channels, onChange, showToast }) {
  const { ax, user } = useAuth();
  const editable = can.edit(user);
  const subunits = structure ? structure.order.map(k => structure.subunits[k].name) : [];
  const externalNodes = ["Командир батальйону", "Старший начальник", "Сусіди"];
  const allOptions = [...externalNodes, ...subunits];

  const empty = { source: subunits[0] || "", target: subunits[1] || "",
                  channel: "радіо УКХ", freq: "", callsign: "", purpose: "" };
  const [form, setForm] = useState(empty);
  const [editingId, setEditingId] = useState(null);

  const submit = async (e) => {
    e.preventDefault();
    if (form.source === form.target) { showToast("Джерело ≠ адресат", "err"); return; }
    try {
      if (editingId) await ax().put(`/interactions/${editingId}`, form);
      else await ax().post("/interactions", form);
      showToast(editingId ? "Оновлено" : "Додано");
      setForm({ ...empty, source: form.source, target: form.target, channel: form.channel });
      setEditingId(null); onChange();
    } catch (e2) { showToast(e2.response?.data?.detail || "Помилка", "err"); }
  };

  const remove = async (id) => {
    if (!window.confirm("Видалити?")) return;
    await ax().delete(`/interactions/${id}`); showToast("Видалено"); onChange();
  };

  const seedTypical = async () => {
    if (!window.confirm("Замінити всі зв'язки типовим набором?")) return;
    try { await ax().post("/interactions/preset/typical"); showToast("Заповнено"); onChange(); }
    catch (e) { showToast(e.response?.data?.detail || "Помилка", "err"); }
  };

  const grouped = useMemo(() => {
    const g = {};
    interactions.forEach(i => { g[i.source] = g[i.source] || []; g[i.source].push(i); });
    return g;
  }, [interactions]);

  const channelColor = {
    "радіо УКХ": "#7AB8D8", "радіо КХ": "#A4C26A", "ЗАЗ (захищений)": "#E89090",
    "цифровий канал": "#B8A0D6", "дротовий": "#D8C36A", "посильний": "#7A8B6C", "L-band/SAT": "#D4A06A",
  };

  return (
    <div>
      {editable && (
        <div className="bg-mil border border-mil rounded-lg p-4 mb-5">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-accent font-bold tracking-wide">{editingId ? "✎ РЕДАГУВАННЯ" : "+ ДОДАТИ КАНАЛ"}</h3>
            {can.commander(user) && <button className="btn-mil text-xs" onClick={seedTypical}>Заповнити типове</button>}
          </div>
          <form onSubmit={submit} className="grid grid-cols-2 md:grid-cols-3 gap-3">
            <Field label="Джерело"><select className="input-mil" value={form.source} onChange={(e) => setForm({ ...form, source: e.target.value })}>{allOptions.map(n => <option key={n}>{n}</option>)}</select></Field>
            <Field label="Адресат"><select className="input-mil" value={form.target} onChange={(e) => setForm({ ...form, target: e.target.value })}>{allOptions.map(n => <option key={n}>{n}</option>)}</select></Field>
            <Field label="Канал"><select className="input-mil" value={form.channel} onChange={(e) => setForm({ ...form, channel: e.target.value })}>{channels.map(c => <option key={c}>{c}</option>)}</select></Field>
            <Field label="Частота / RC"><input className="input-mil" placeholder="RC-12 / 145.500 МГц" value={form.freq} onChange={(e) => setForm({ ...form, freq: e.target.value })} /></Field>
            <Field label="Позивний"><input className="input-mil" placeholder="КОЛУМБ" value={form.callsign} onChange={(e) => setForm({ ...form, callsign: e.target.value })} /></Field>
            <Field label="Призначення"><input className="input-mil" placeholder="Постановка задач" value={form.purpose} onChange={(e) => setForm({ ...form, purpose: e.target.value })} /></Field>
            <div className="col-span-2 md:col-span-3 flex gap-2">
              <button type="submit" className="btn-mil btn-mil-primary">{editingId ? "Зберегти" : "Додати"}</button>
              {editingId && <button type="button" className="btn-mil" onClick={() => { setEditingId(null); setForm(empty); }}>Скасувати</button>}
            </div>
          </form>
        </div>
      )}

      <div className="space-y-3">
        {Object.keys(grouped).length === 0 ? (
          <div className="text-center py-12 bg-mil border border-dashed border-mil rounded-lg" style={{ color: "#5C6E54" }}>
            Зв'язків ще не додано
          </div>
        ) : Object.entries(grouped).map(([src, items]) => (
          <div key={src} className="bg-mil border border-mil rounded-lg overflow-hidden">
            <div className="px-4 py-2 border-b border-mil bg-mil-deep">
              <span className="text-xs uppercase" style={{ color: "#7A8B6C" }}>Від:</span>{" "}
              <span className="font-bold text-accent">{src}</span>
            </div>
            <div className="p-3 space-y-2">
              {items.map((i) => (
                <div key={i.id} className="bg-mil-deep border border-mil rounded p-3 flex items-start gap-3">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-accent">→</span>
                      <span className="font-bold">{i.target}</span>
                      <span className="badge" style={{ background: `${channelColor[i.channel] || "#5C6E54"}30`, color: channelColor[i.channel] || "#7A8B6C", border: `1px solid ${channelColor[i.channel] || "#5C6E54"}` }}>{i.channel}</span>
                      {i.freq && <span className="text-sm" style={{ fontFamily: "JetBrains Mono", color: "#D4A06A" }}>{i.freq}</span>}
                      {i.callsign && <span className="text-sm" style={{ color: "#7AB8D8" }}>«{i.callsign}»</span>}
                    </div>
                    {i.purpose && <div className="text-xs mt-1" style={{ color: "#7A8B6C" }}>{i.purpose}</div>}
                  </div>
                  {editable && <>
                    <button className="btn-mil text-xs py-1 px-2" onClick={() => { setForm({ ...i }); setEditingId(i.id); }}>✎</button>
                    <button className="btn-mil btn-mil-danger text-xs py-1 px-2" onClick={() => remove(i.id)}>✕</button>
                  </>}
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function Field({ label, children }) {
  return <div><label className="text-xs uppercase block mb-1" style={{ color: "#7A8B6C" }}>{label}</label>{children}</div>;
}
