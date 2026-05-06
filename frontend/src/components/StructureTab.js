import { useState, useMemo } from "react";
import { useAuth, can } from "../AuthContext";
import { cls, NodeRow } from "./Common";

export default function StructureTab({ structure, equipment, config, onChange, showToast }) {
  const { ax, user } = useAuth();
  const [selectedNode, setSelectedNode] = useState(null);
  const [expanded, setExpanded] = useState({});

  const toggle = (k) => setExpanded((e) => ({ ...e, [k]: !e[k] }));

  const tree = useMemo(() => {
    if (!structure) return [];
    return structure.order.map((key) => ({
      key,
      sub: structure.subunits[key],
      squads: Object.entries(structure.subunits[key].squads).map(([sk, sq]) => ({ key: sk, ...sq })),
    }));
  }, [structure]);

  const eqByPath = useMemo(() => {
    const m = {};
    equipment.forEach((e) => { m[e.node_path] = m[e.node_path] || []; m[e.node_path].push(e); });
    return m;
  }, [equipment]);

  const seedTypical = async () => {
    if (!window.confirm("Це замінить усі ШТАТНІ засоби типовим набором. Продовжити?")) return;
    try { await ax().post("/equipment/preset/typical"); showToast("Типове заповнено"); onChange(); }
    catch (e) { showToast(e.response?.data?.detail || "Помилка", "err"); }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[420px_1fr] gap-6">
      <div className="bg-mil border border-mil rounded-lg p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-accent font-bold tracking-wide">СТРУКТУРА РОТИ</h3>
          {can.commander(user) && (
            <button className="btn-mil text-xs" onClick={seedTypical}>Заповнити типове</button>
          )}
        </div>
        <div className="text-xs mb-3" style={{ color: "#7A8B6C" }}>
          Натисніть на підрозділ або відділення, щоб додати/редагувати засоби
        </div>

        <NodeRow label={structure.name} count={structure.total_personnel} type="company"
                 path={structure.name} selected={selectedNode === structure.name}
                 onClick={() => setSelectedNode(structure.name)} eqCount={eqByPath[structure.name]?.length || 0} />

        <div className="ml-3 mt-1 space-y-1">
          {tree.map(({ key, sub, squads }) => {
            const exp = expanded[key];
            const hasSquads = squads.some((s) => s.key !== "__DIRECT__");
            return (
              <div key={key}>
                <NodeRow label={sub.name} count={sub.count} type={sub.type}
                  path={sub.name} selected={selectedNode === sub.name}
                  onClick={() => setSelectedNode(sub.name)}
                  eqCount={eqByPath[sub.name]?.length || 0}
                  expandable={hasSquads} expanded={exp} onToggle={() => toggle(key)} />
                {exp && hasSquads && (
                  <div className="ml-5 mt-1 space-y-1">
                    {squads.filter((s) => s.key !== "__DIRECT__").map((sq) => {
                      const sqPath = `${sub.name}/${sq.name}`;
                      return (
                        <NodeRow key={sq.key} label={sq.name} count={sq.positions.length} type="squad"
                          path={sqPath} selected={selectedNode === sqPath}
                          onClick={() => setSelectedNode(sqPath)}
                          eqCount={eqByPath[sqPath]?.length || 0} />
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      <div className="bg-mil border border-mil rounded-lg p-4">
        {!selectedNode ? (
          <div className="text-center py-20" style={{ color: "#7A8B6C" }}>
            <div className="text-5xl mb-4 opacity-30">📦</div>
            <div className="text-lg">Оберіть підрозділ для редагування засобів</div>
          </div>
        ) : (
          <EquipmentEditor nodePath={selectedNode} equipment={eqByPath[selectedNode] || []}
            allEquipment={equipment} config={config} onChange={onChange} showToast={showToast} />
        )}
      </div>
    </div>
  );
}


function EquipmentEditor({ nodePath, equipment, allEquipment, config, onChange, showToast }) {
  const { ax, user } = useAuth();
  const editable = can.edit(user);
  const empty = { category: "Засіб зв'язку", name: "", type: "штатний", qty: 1, state: "справний", serial: "", notes: "" };
  const [form, setForm] = useState(empty);
  const [editingId, setEditingId] = useState(null);

  const childEquipment = useMemo(() =>
    allEquipment.filter(e => e.node_path !== nodePath && e.node_path.startsWith(nodePath + "/")),
    [allEquipment, nodePath]);

  const reset = () => { setForm(empty); setEditingId(null); };

  const submit = async (ev) => {
    ev.preventDefault();
    if (!form.name.trim()) { showToast("Введіть назву", "err"); return; }
    try {
      if (editingId) await ax().put(`/equipment/${editingId}`, form);
      else await ax().post("/equipment", { ...form, node_path: nodePath });
      showToast(editingId ? "Оновлено" : "Додано");
      reset(); onChange();
    } catch (e) { showToast(e.response?.data?.detail || "Помилка", "err"); }
  };

  const remove = async (id) => {
    if (!window.confirm("Видалити?")) return;
    await ax().delete(`/equipment/${id}`); showToast("Видалено"); onChange();
  };

  const startEdit = (e) => {
    setForm({ category: e.category, name: e.name, type: e.type, qty: e.qty, state: e.state, serial: e.serial || "", notes: e.notes || "" });
    setEditingId(e.id);
  };

  const stateBadge = (s) =>
    s === "справний" ? "badge-state-ok"
    : (s === "потребує ремонту" || s === "у польоті/виконанні") ? "badge-state-warn"
    : "badge-state-bad";

  return (
    <div>
      <div className="mb-4">
        <div className="text-xs uppercase tracking-wider mb-1" style={{ color: "#7A8B6C" }}>Підрозділ</div>
        <h2 className="text-xl font-bold text-accent">{nodePath}</h2>
      </div>

      {editable && (
        <form onSubmit={submit} className="bg-mil-deep border border-mil rounded-lg p-4 mb-5">
          <div className="text-sm font-semibold mb-3 text-brown">
            {editingId ? "✎ Редагування" : "+ Додати засіб / транспорт / зв'язок / ОВТ"}
          </div>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            <div>
              <label className="text-xs uppercase block mb-1" style={{ color: "#7A8B6C" }}>Категорія</label>
              <select className="input-mil" value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>
                {config?.equipment_categories.map((c) => <option key={c}>{c}</option>)}
              </select>
            </div>
            <div className="md:col-span-2">
              <label className="text-xs uppercase block mb-1" style={{ color: "#7A8B6C" }}>Назва *</label>
              <input className="input-mil" placeholder="напр. CZ BREN 2 (5.56 мм) або Р-187П1" value={form.name}
                     onChange={(e) => setForm({ ...form, name: e.target.value })} required data-testid="eq-name" />
            </div>
            <div>
              <label className="text-xs uppercase block mb-1" style={{ color: "#7A8B6C" }}>Тип</label>
              <div className="flex gap-2">
                {["штатний", "позаштатний"].map((t) => (
                  <button type="button" key={t} onClick={() => setForm({ ...form, type: t })}
                    className={cls("flex-1 py-2 px-3 rounded text-xs font-bold uppercase tracking-wider border",
                      form.type === t
                        ? (t === "штатний" ? "badge-shtatny border-accent" : "badge-pozashtatny border-brown")
                        : "border-mil text-gray-500")}>
                    {t}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <label className="text-xs uppercase block mb-1" style={{ color: "#7A8B6C" }}>Кількість</label>
              <input type="number" min="1" className="input-mil" value={form.qty}
                     onChange={(e) => setForm({ ...form, qty: parseInt(e.target.value) || 1 })} />
            </div>
            <div>
              <label className="text-xs uppercase block mb-1" style={{ color: "#7A8B6C" }}>Стан</label>
              <select className="input-mil" value={form.state} onChange={(e) => setForm({ ...form, state: e.target.value })}>
                {config?.equipment_states.map((s) => <option key={s}>{s}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs uppercase block mb-1" style={{ color: "#7A8B6C" }}>Серійний / №</label>
              <input className="input-mil" value={form.serial} onChange={(e) => setForm({ ...form, serial: e.target.value })} />
            </div>
            <div className="col-span-2 md:col-span-3">
              <label className="text-xs uppercase block mb-1" style={{ color: "#7A8B6C" }}>Примітки</label>
              <input className="input-mil" placeholder="Дислокація, відповідальний…" value={form.notes}
                     onChange={(e) => setForm({ ...form, notes: e.target.value })} />
            </div>
          </div>
          <div className="flex gap-2 mt-4">
            <button type="submit" className="btn-mil btn-mil-primary">{editingId ? "Зберегти" : "Додати"}</button>
            {editingId && <button type="button" className="btn-mil" onClick={reset}>Скасувати</button>}
          </div>
        </form>
      )}

      <h4 className="font-semibold tracking-wide mb-2">
        ЗАСОБИ ({equipment.length})
        {childEquipment.length > 0 && <span className="text-xs ml-2" style={{ color: "#7A8B6C" }}>+ у відділеннях: {childEquipment.length}</span>}
      </h4>

      {equipment.length === 0 && childEquipment.length === 0 && (
        <div className="text-center py-10 border border-dashed border-mil rounded" style={{ color: "#5C6E54" }}>
          Засобів ще не додано
        </div>
      )}

      {equipment.length > 0 && (
        <div className="space-y-2 mb-4">
          {equipment.map((e) => (
            <div key={e.id} className="bg-mil-deep border border-mil rounded p-3 flex items-start gap-3">
              <div className="flex-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-bold">{e.name}</span>
                  <span className="badge badge-cat">{e.category}</span>
                  <span className={cls("badge", e.type === "штатний" ? "badge-shtatny" : "badge-pozashtatny")}>{e.type}</span>
                  <span className={cls("badge", stateBadge(e.state))}>{e.state}</span>
                  <span className="text-sm" style={{ color: "#7A8B6C" }}>× {e.qty}</span>
                </div>
                {(e.serial || e.notes) && (
                  <div className="text-xs mt-1" style={{ color: "#7A8B6C" }}>
                    {e.serial && <span className="mr-3">SN: {e.serial}</span>}
                    {e.notes}
                  </div>
                )}
              </div>
              {editable && <>
                <button className="btn-mil text-xs py-1 px-2" onClick={() => startEdit(e)}>✎</button>
                <button className="btn-mil btn-mil-danger text-xs py-1 px-2" onClick={() => remove(e.id)}>✕</button>
              </>}
            </div>
          ))}
        </div>
      )}

      {childEquipment.length > 0 && (
        <div>
          <div className="text-xs uppercase mb-2" style={{ color: "#7A8B6C" }}>У відділеннях підрозділу</div>
          <div className="space-y-1.5">
            {childEquipment.map((e) => (
              <div key={e.id} className="bg-mil-deep/50 border border-mil/50 rounded px-3 py-1.5 text-xs flex items-center gap-2">
                <span style={{ color: "#7A8B6C" }}>{e.node_path.replace(nodePath + "/", "")}</span>
                <span className="text-accent">›</span>
                <span className="font-semibold">{e.name}</span>
                <span className="badge badge-cat" style={{ fontSize: "9px" }}>{e.category}</span>
                <span className={cls("badge", e.type === "штатний" ? "badge-shtatny" : "badge-pozashtatny")} style={{ fontSize: "9px" }}>{e.type}</span>
                <span style={{ color: "#7A8B6C" }}>× {e.qty}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
