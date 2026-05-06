import { useState, useEffect, useMemo } from "react";
import { useAuth, can } from "../AuthContext";
import { cls } from "./Common";

export default function AmmoTab({ structure, config, showToast }) {
  const { ax, user } = useAuth();
  const editable = can.edit(user);
  const [items, setItems] = useState([]);
  const [editingId, setEditingId] = useState(null);
  const [unitFilter, setUnitFilter] = useState("");
  const subunits = structure ? structure.order.map(k => structure.subunits[k].name) : [];

  const empty = { node_path: subunits[0] || "", weapon: "АК-74", ammo_type: "патрон", caliber: "5.45×39", qty: 0, unit: "шт", notes: "" };
  const [form, setForm] = useState(empty);

  const load = async () => { const r = await ax().get("/ammo"); setItems(r.data); };
  useEffect(() => { load(); }, []);

  // Auto-fill caliber when weapon changes
  const setWeapon = (w) => {
    const calMap = {
      "АК-74": "5.45×39", "АКС-74": "5.45×39", "АК-74М": "5.45×39", "АКС-74У": "5.45×39",
      "CZ BREN 2 (5.56 мм)": "5.56×45",
      "ПМ": "9×18", "Форт-12": "9×18",
      "Глок-19": "9×19",
      "ПКМ": "7.62×54R", "СВД": "7.62×54R",
      "РПК-74": "5.45×39",
      "ВСС «ВИНТОРЕЗ»": "9×39",
      "ВОГ-25": "40 мм", "ВОГ-25П": "40 мм",
      "ВОГ-17": "30 мм", "АГС-17": "30 мм",
    };
    const grenades = ["РГД-5", "Ф-1", "РГ-42", "РГО"];
    const isGren = grenades.includes(w);
    const isVog = w.startsWith("ВОГ") || w.startsWith("АГС");
    setForm({
      ...form, weapon: w,
      caliber: calMap[w] || "",
      ammo_type: isGren ? "граната" : (isVog ? "ВОГ" : "патрон"),
    });
  };

  const submit = async (e) => {
    e.preventDefault();
    try {
      if (editingId) await ax().put(`/ammo/${editingId}`, form);
      else await ax().post("/ammo", form);
      showToast(editingId ? "Оновлено" : "Додано");
      setForm({ ...empty, node_path: form.node_path });
      setEditingId(null); load();
    } catch (e2) { showToast(e2.response?.data?.detail || "Помилка", "err"); }
  };

  const remove = async (id) => {
    if (!window.confirm("Видалити запис?")) return;
    await ax().delete(`/ammo/${id}`); showToast("Видалено"); load();
  };

  const seedTypical = async () => {
    if (!window.confirm("Замінити весь облік БК типовим набором (1 БК на роту)?")) return;
    try { await ax().post("/ammo/preset/typical"); showToast("Заповнено"); load(); }
    catch (e) { showToast(e.response?.data?.detail || "Помилка", "err"); }
  };

  const filtered = unitFilter ? items.filter(i => i.node_path === unitFilter) : items;

  const totals = useMemo(() => {
    const byWeapon = {}, byUnit = {};
    items.forEach(i => {
      byWeapon[i.weapon] = (byWeapon[i.weapon] || 0) + i.qty;
      byUnit[i.node_path] = (byUnit[i.node_path] || 0) + i.qty;
    });
    return { byWeapon, byUnit, total: Object.values(byWeapon).reduce((a, b) => a + b, 0) };
  }, [items]);

  const grouped = useMemo(() => {
    const g = {};
    filtered.forEach(i => { g[i.node_path] = g[i.node_path] || []; g[i.node_path].push(i); });
    return g;
  }, [filtered]);

  return (
    <div>
      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-5">
        <div className="bg-mil border border-mil rounded p-3">
          <div className="text-2xl font-bold text-accent" style={{ fontFamily: "JetBrains Mono" }}>{totals.total.toLocaleString("uk")}</div>
          <div className="text-xs uppercase" style={{ color: "#7A8B6C" }}>Всього БК</div>
        </div>
        {["АК-74", "CZ BREN 2 (5.56 мм)", "РГД-5", "Ф-1"].map(w => (
          <div key={w} className="bg-mil border border-mil rounded p-3">
            <div className="text-2xl font-bold" style={{ fontFamily: "JetBrains Mono", color: "#7AB8D8" }}>
              {(totals.byWeapon[w] || 0).toLocaleString("uk")}
            </div>
            <div className="text-xs uppercase truncate" style={{ color: "#7A8B6C" }}>{w}</div>
          </div>
        ))}
      </div>

      {editable && (
        <div className="bg-mil border border-mil rounded-lg p-4 mb-5">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-accent font-bold tracking-wide">{editingId ? "✎ РЕДАГУВАННЯ БК" : "+ ДОДАТИ ЗАПИС БК"}</h3>
            {can.commander(user) && <button className="btn-mil text-xs" onClick={seedTypical}>Заповнити типове</button>}
          </div>
          <form onSubmit={submit} className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <Field label="Підрозділ"><select className="input-mil" value={form.node_path} onChange={(e) => setForm({ ...form, node_path: e.target.value })}>
              {subunits.map(s => <option key={s}>{s}</option>)}
            </select></Field>
            <Field label="Зброя / тип"><select className="input-mil" value={form.weapon} onChange={(e) => setWeapon(e.target.value)} data-testid="ammo-weapon">
              {config?.weapon_types.map(w => <option key={w}>{w}</option>)}
            </select></Field>
            <Field label="Тип БК"><select className="input-mil" value={form.ammo_type} onChange={(e) => setForm({ ...form, ammo_type: e.target.value })}>
              {config?.ammo_types.map(t => <option key={t}>{t}</option>)}
            </select></Field>
            <Field label="Калібр"><input className="input-mil" placeholder="5.45×39" value={form.caliber} onChange={(e) => setForm({ ...form, caliber: e.target.value })} /></Field>
            <Field label="Кількість *"><input type="number" min="0" className="input-mil" value={form.qty} onChange={(e) => setForm({ ...form, qty: parseInt(e.target.value) || 0 })} required data-testid="ammo-qty" /></Field>
            <Field label="Од."><input className="input-mil" value={form.unit} onChange={(e) => setForm({ ...form, unit: e.target.value })} /></Field>
            <div className="col-span-2"><Field label="Примітки"><input className="input-mil" placeholder="напр. на складі / в розпорядженні КВ" value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} /></Field></div>
            <div className="col-span-2 md:col-span-4 flex gap-2">
              <button type="submit" className="btn-mil btn-mil-primary" data-testid="ammo-submit">{editingId ? "Зберегти" : "Додати"}</button>
              {editingId && <button type="button" className="btn-mil" onClick={() => { setEditingId(null); setForm(empty); }}>Скасувати</button>}
            </div>
          </form>
        </div>
      )}

      <div className="flex gap-3 mb-3 items-center">
        <select className="input-mil" style={{ width: "auto" }} value={unitFilter} onChange={(e) => setUnitFilter(e.target.value)}>
          <option value="">Усі підрозділи</option>
          {subunits.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
        <div className="text-sm ml-auto" style={{ color: "#7A8B6C" }}>
          Записів: <span className="text-accent font-bold">{filtered.length}</span>
        </div>
      </div>

      {Object.keys(grouped).length === 0 ? (
        <div className="text-center py-12 bg-mil border border-dashed border-mil rounded-lg" style={{ color: "#5C6E54" }}>
          Немає записів БК
        </div>
      ) : Object.entries(grouped).map(([unit, list]) => (
        <div key={unit} className="bg-mil border border-mil rounded-lg overflow-hidden mb-3">
          <div className="px-4 py-2 border-b border-mil bg-mil-deep flex justify-between">
            <span className="font-bold text-accent">{unit}</span>
            <span className="text-xs" style={{ color: "#7A8B6C" }}>
              разом: <span className="text-accent font-bold">{list.reduce((a,b) => a + b.qty, 0).toLocaleString("uk")}</span>
            </span>
          </div>
          <div className="p-3 space-y-2">
            {list.map(a => (
              <div key={a.id} className="bg-mil-deep border border-mil rounded p-3 flex items-center gap-3">
                <div className="flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-bold">{a.weapon}</span>
                    <span className="badge badge-cat" style={{ background: a.ammo_type === "граната" ? "rgba(232,144,144,.15)" : (a.ammo_type === "ВОГ" ? "rgba(212,160,106,.15)" : "rgba(122,184,216,.15)"), color: a.ammo_type === "граната" ? "#E89090" : (a.ammo_type === "ВОГ" ? "#D4A06A" : "#7AB8D8") }}>{a.ammo_type}</span>
                    {a.caliber && <span className="text-sm" style={{ fontFamily: "JetBrains Mono", color: "#A4C26A" }}>{a.caliber}</span>}
                    <span className="text-lg font-bold" style={{ fontFamily: "JetBrains Mono", color: "#D4A06A" }}>×{a.qty.toLocaleString("uk")} {a.unit}</span>
                  </div>
                  {a.notes && <div className="text-xs mt-1" style={{ color: "#7A8B6C" }}>{a.notes}</div>}
                </div>
                {editable && <>
                  <button className="btn-mil text-xs py-1 px-2" onClick={() => { setForm({ ...a }); setEditingId(a.id); window.scrollTo({top:0, behavior:"smooth"}); }}>✎</button>
                  <button className="btn-mil btn-mil-danger text-xs py-1 px-2" onClick={() => remove(a.id)}>✕</button>
                </>}
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function Field({ label, children }) {
  return <div><label className="text-xs uppercase block mb-1" style={{ color: "#7A8B6C" }}>{label}</label>{children}</div>;
}
