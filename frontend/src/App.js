import { useEffect, useState, useMemo } from "react";
import axios from "axios";
import "@/App.css";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const cls = (...x) => x.filter(Boolean).join(" ");

function App() {
  const [tab, setTab] = useState("structure");
  const [structure, setStructure] = useState(null);
  const [equipment, setEquipment] = useState([]);
  const [interactions, setInteractions] = useState([]);
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState(null);
  const [downloading, setDownloading] = useState(null);

  const showToast = (msg, kind = "ok") => {
    setToast({ msg, kind });
    setTimeout(() => setToast(null), 2500);
  };

  const downloadFile = async (urlPath, filename, key) => {
    setDownloading(key);
    try {
      const res = await fetch(`${API}${urlPath}`, { credentials: "omit" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      showToast(`Завантажено: ${filename}`);
    } catch (e) {
      console.error(e);
      showToast(`Помилка завантаження: ${e.message}`, "err");
    } finally {
      setDownloading(null);
    }
  };

  const reload = async () => {
    const [s, e, i, c] = await Promise.all([
      axios.get(`${API}/structure`),
      axios.get(`${API}/equipment`),
      axios.get(`${API}/interactions`),
      axios.get(`${API}/config`),
    ]);
    setStructure(s.data);
    setEquipment(e.data);
    setInteractions(i.data);
    setConfig(c.data);
    setLoading(false);
  };

  useEffect(() => {
    reload().catch((err) => {
      console.error(err);
      showToast("Не вдалося завантажити дані", "err");
      setLoading(false);
    });
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen bg-grid flex items-center justify-center">
        <div className="text-accent text-xl">Завантаження…</div>
      </div>
    );
  }

  const subunitNames = structure ? structure.order.map(k => structure.subunits[k].name) : [];

  return (
    <div className="min-h-screen bg-grid">
      {/* Header */}
      <header className="border-b border-mil sticky top-0 z-30 glass">
        <div className="max-w-[1400px] mx-auto px-6 py-4 flex items-center justify-between gap-6 flex-wrap">
          <div>
            <h1 className="text-2xl font-bold tracking-wider" style={{ letterSpacing: "1.5px" }}>
              УПРАВЛІННЯ РОТОЮ <span className="text-accent">РРР</span>
            </h1>
            <div className="text-sm" style={{ color: "#7A8B6C" }}>
              Розвідувальний батальйон • {structure?.name} • {structure?.total_personnel} осіб
            </div>
          </div>
          <div className="flex items-center gap-3 flex-wrap">
            <button className="btn-mil" disabled={downloading === "org"}
              onClick={() => downloadFile("/export/orgstructure.xml", "Управління ротою РРР - Організаційна структура.xml", "org")}
              data-testid="dl-org">
              {downloading === "org" ? "⏳" : "⬇"} Орг. структура (.xml)
            </button>
            <button className="btn-mil" disabled={downloading === "cmd"}
              onClick={() => downloadFile("/export/command.xml", "Управління ротою РРР - Бойове управління.xml", "cmd")}
              data-testid="dl-cmd">
              {downloading === "cmd" ? "⏳" : "⬇"} Бойове управління (.xml)
            </button>
            <button className="btn-mil" disabled={downloading === "int"}
              onClick={() => downloadFile("/export/interactions.xml", "Управління ротою РРР - Матриця взаємодії.xml", "int")}
              data-testid="dl-int">
              {downloading === "int" ? "⏳" : "⬇"} Матриця взаємодії (.xml)
            </button>
            <button className="btn-mil btn-mil-primary" disabled={downloading === "zip"}
              onClick={() => downloadFile("/export/full-package.zip", "Управління ротою РРР - пакет.zip", "zip")}
              data-testid="dl-zip">
              {downloading === "zip" ? "⏳ Підготовка…" : "⬇ ZIP-пакет"}
            </button>
            <a className="btn-mil" href="/files/rota-rrr-deploy.zip"
               download="rota-rrr-deploy.zip" data-testid="dl-deploy"
               title="Повний пакет для розгортання на власному сервері (Docker Compose)">
              🚀 Deploy-пакет
            </a>
          </div>
        </div>

        <div className="max-w-[1400px] mx-auto px-6 flex gap-2 border-t border-mil">
          <div className={cls("tab-mil", tab === "structure" && "active")} onClick={() => setTab("structure")} data-testid="tab-structure">
            Структура та засоби
          </div>
          <div className={cls("tab-mil", tab === "interactions" && "active")} onClick={() => setTab("interactions")} data-testid="tab-interactions">
            Матриця взаємодії
          </div>
          <div className={cls("tab-mil", tab === "summary" && "active")} onClick={() => setTab("summary")} data-testid="tab-summary">
            Зведення
          </div>
        </div>
      </header>

      {/* Toast */}
      {toast && (
        <div className={cls(
          "fixed top-24 right-6 z-50 px-4 py-3 rounded-lg shadow-lg border",
          toast.kind === "ok" ? "bg-mil border-accent text-accent" : "bg-mil border-red-500 text-red-300"
        )}>
          {toast.msg}
        </div>
      )}

      <main className="max-w-[1400px] mx-auto px-6 py-6">
        {tab === "structure" && (
          <StructureTab
            structure={structure}
            equipment={equipment}
            config={config}
            onChange={reload}
            showToast={showToast}
          />
        )}
        {tab === "interactions" && (
          <InteractionsTab
            interactions={interactions}
            subunits={subunitNames}
            channels={config?.interaction_channels || []}
            onChange={reload}
            showToast={showToast}
          />
        )}
        {tab === "summary" && (
          <SummaryTab equipment={equipment} interactions={interactions} structure={structure} />
        )}
      </main>
    </div>
  );
}


/* ================== STRUCTURE TAB ================== */
function StructureTab({ structure, equipment, config, onChange, showToast }) {
  const [selectedNode, setSelectedNode] = useState(null);
  const [expanded, setExpanded] = useState({});

  const toggle = (k) => setExpanded((e) => ({ ...e, [k]: !e[k] }));

  // Build tree
  const tree = useMemo(() => {
    if (!structure) return [];
    return structure.order.map((key) => {
      const sub = structure.subunits[key];
      const squads = Object.entries(sub.squads).map(([sk, sq]) => ({
        key: sk,
        name: sq.name,
        positions: sq.positions,
      }));
      return { key, sub, squads };
    });
  }, [structure]);

  const eqByPath = useMemo(() => {
    const m = {};
    equipment.forEach((e) => {
      m[e.node_path] = m[e.node_path] || [];
      m[e.node_path].push(e);
    });
    return m;
  }, [equipment]);

  const seedTypical = async () => {
    if (!window.confirm("Це замінить всі ШТАТНІ засоби типовим набором для роти РРР. Продовжити?")) return;
    await axios.post(`${API}/equipment/preset/typical`);
    showToast("Типові засоби заповнено");
    onChange();
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[420px_1fr] gap-6">
      {/* TREE */}
      <div className="bg-mil border border-mil rounded-lg p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-accent font-bold tracking-wide">СТРУКТУРА РОТИ</h3>
          <button className="btn-mil text-xs" onClick={seedTypical} data-testid="btn-seed-typical">
            Заповнити типове
          </button>
        </div>
        <div className="text-xs mb-3" style={{ color: "#7A8B6C" }}>
          Натисніть на підрозділ або відділення, щоб додати/редагувати засоби
        </div>

        <NodeRow
          label={structure.name}
          count={structure.total_personnel}
          type="company"
          path={structure.name}
          selected={selectedNode === structure.name}
          onClick={() => setSelectedNode(structure.name)}
          eqCount={eqByPath[structure.name]?.length || 0}
        />

        <div className="ml-3 mt-1 space-y-1">
          {tree.map(({ key, sub, squads }) => {
            const subPath = sub.name;
            const exp = expanded[key];
            const hasSquads = squads.some((s) => s.key !== "__DIRECT__");
            return (
              <div key={key}>
                <NodeRow
                  label={sub.name}
                  count={sub.count}
                  type={sub.type}
                  path={subPath}
                  selected={selectedNode === subPath}
                  onClick={() => setSelectedNode(subPath)}
                  eqCount={eqByPath[subPath]?.length || 0}
                  expandable={hasSquads}
                  expanded={exp}
                  onToggle={() => toggle(key)}
                />
                {exp && hasSquads && (
                  <div className="ml-5 mt-1 space-y-1">
                    {squads.filter((s) => s.key !== "__DIRECT__").map((sq) => {
                      const sqPath = `${subPath}/${sq.name}`;
                      return (
                        <NodeRow
                          key={sq.key}
                          label={sq.name}
                          count={sq.positions.length}
                          type="squad"
                          path={sqPath}
                          selected={selectedNode === sqPath}
                          onClick={() => setSelectedNode(sqPath)}
                          eqCount={eqByPath[sqPath]?.length || 0}
                        />
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* EQUIPMENT EDITOR */}
      <div className="bg-mil border border-mil rounded-lg p-4">
        {!selectedNode ? (
          <div className="text-center py-20" style={{ color: "#7A8B6C" }}>
            <div className="text-5xl mb-4 opacity-30">📦</div>
            <div className="text-lg">Оберіть підрозділ для редагування засобів</div>
          </div>
        ) : (
          <EquipmentEditor
            nodePath={selectedNode}
            structure={structure}
            equipment={eqByPath[selectedNode] || []}
            allEquipment={equipment}
            config={config}
            onChange={onChange}
            showToast={showToast}
          />
        )}
      </div>
    </div>
  );
}


function NodeRow({ label, count, type, path, selected, onClick, eqCount, expandable, expanded, onToggle }) {
  const colors = {
    company: { bg: "rgba(61,90,44,.4)", border: "#A4C26A" },
    hq: { bg: "rgba(91,58,41,.4)", border: "#D4A06A" },
    platoon: { bg: "rgba(44,74,94,.4)", border: "#7AB8D8" },
    group: { bg: "rgba(74,61,92,.4)", border: "#B8A0D6" },
    workshop: { bg: "rgba(92,74,44,.4)", border: "#D8C36A" },
    squad: { bg: "rgba(31,46,34,.6)", border: "#8FAA76" },
    unit: { bg: "rgba(31,46,34,.6)", border: "#8FAA76" },
  };
  const c = colors[type] || colors.unit;
  return (
    <div
      data-testid={`node-${path}`}
      onClick={onClick}
      className={cls("group flex items-center gap-2 px-2.5 py-2 rounded cursor-pointer text-sm border transition-all", selected ? "ring-1" : "")}
      style={{
        background: selected ? c.bg : "transparent",
        borderColor: selected ? c.border : "transparent",
        boxShadow: selected ? `inset 3px 0 0 ${c.border}` : undefined,
      }}
    >
      {expandable ? (
        <button
          className="text-xs w-4 text-center"
          style={{ color: c.border }}
          onClick={(e) => { e.stopPropagation(); onToggle(); }}
          data-testid={`expand-${path}`}
        >
          {expanded ? "▾" : "▸"}
        </button>
      ) : <div className="w-4" />}
      <div className="flex-1 truncate">{label}</div>
      <div className="text-xs px-1.5 py-0.5 rounded" style={{ background: c.bg, color: c.border, border: `1px solid ${c.border}` }}>
        {count}
      </div>
      {eqCount > 0 && (
        <div className="text-xs px-1.5 py-0.5 rounded badge-cat">📦 {eqCount}</div>
      )}
    </div>
  );
}


/* ================== EQUIPMENT EDITOR ================== */
function EquipmentEditor({ nodePath, structure, equipment, allEquipment, config, onChange, showToast }) {
  const [form, setForm] = useState({
    category: "Засіб зв'язку",
    name: "",
    type: "штатний",
    qty: 1,
    state: "справний",
    serial: "",
    notes: "",
  });
  const [editingId, setEditingId] = useState(null);

  // Aggregate equipment from all child paths if this is a parent (subunit with squads)
  const childEquipment = useMemo(() => {
    return allEquipment.filter(e => e.node_path !== nodePath && e.node_path.startsWith(nodePath + "/"));
  }, [allEquipment, nodePath]);

  const reset = () => {
    setForm({ category: "Засіб зв'язку", name: "", type: "штатний", qty: 1, state: "справний", serial: "", notes: "" });
    setEditingId(null);
  };

  const submit = async (ev) => {
    ev.preventDefault();
    if (!form.name.trim()) { showToast("Введіть назву засобу", "err"); return; }
    try {
      if (editingId) {
        await axios.put(`${API}/equipment/${editingId}`, form);
        showToast("Засіб оновлено");
      } else {
        await axios.post(`${API}/equipment`, { ...form, node_path: nodePath });
        showToast("Засіб додано");
      }
      reset();
      onChange();
    } catch (e) {
      showToast(e.response?.data?.detail || "Помилка", "err");
    }
  };

  const remove = async (id) => {
    if (!window.confirm("Видалити засіб?")) return;
    await axios.delete(`${API}/equipment/${id}`);
    showToast("Видалено");
    onChange();
  };

  const startEdit = (e) => {
    setForm({
      category: e.category, name: e.name, type: e.type, qty: e.qty,
      state: e.state, serial: e.serial || "", notes: e.notes || "",
    });
    setEditingId(e.id);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const stateBadge = (s) => {
    if (s === "справний") return "badge-state-ok";
    if (s === "потребує ремонту" || s === "у польоті/виконанні") return "badge-state-warn";
    return "badge-state-bad";
  };

  return (
    <div>
      <div className="mb-4">
        <div className="text-xs uppercase tracking-wider mb-1" style={{ color: "#7A8B6C" }}>Підрозділ</div>
        <h2 className="text-xl font-bold text-accent">{nodePath}</h2>
      </div>

      {/* Add/Edit form */}
      <form onSubmit={submit} className="bg-mil-deep border border-mil rounded-lg p-4 mb-5">
        <div className="text-sm font-semibold mb-3 text-brown">
          {editingId ? "✎ Редагування засобу" : "+ Додати засіб / транспорт / зв'язок / ОВТ"}
        </div>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          <div>
            <label className="text-xs uppercase tracking-wider block mb-1" style={{ color: "#7A8B6C" }}>Категорія</label>
            <select className="input-mil" value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} data-testid="eq-category">
              {config?.equipment_categories.map((c) => <option key={c}>{c}</option>)}
            </select>
          </div>
          <div className="md:col-span-2">
            <label className="text-xs uppercase tracking-wider block mb-1" style={{ color: "#7A8B6C" }}>Назва *</label>
            <input className="input-mil" placeholder="напр. Р-187П1 АКВЕДУК" value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })} data-testid="eq-name" required />
          </div>
          <div>
            <label className="text-xs uppercase tracking-wider block mb-1" style={{ color: "#7A8B6C" }}>Тип</label>
            <div className="flex gap-2">
              {["штатний", "позаштатний"].map((t) => (
                <button type="button" key={t} onClick={() => setForm({ ...form, type: t })}
                  className={cls("flex-1 py-2 px-3 rounded text-xs font-bold uppercase tracking-wider border transition-all",
                    form.type === t
                      ? (t === "штатний" ? "badge-shtatny border-accent" : "badge-pozashtatny border-brown")
                      : "border-mil text-gray-500 hover:text-gray-300"
                  )}
                  data-testid={`eq-type-${t}`}>
                  {t}
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="text-xs uppercase tracking-wider block mb-1" style={{ color: "#7A8B6C" }}>Кількість</label>
            <input type="number" min="1" className="input-mil" value={form.qty}
              onChange={(e) => setForm({ ...form, qty: parseInt(e.target.value) || 1 })} data-testid="eq-qty" />
          </div>
          <div>
            <label className="text-xs uppercase tracking-wider block mb-1" style={{ color: "#7A8B6C" }}>Стан</label>
            <select className="input-mil" value={form.state} onChange={(e) => setForm({ ...form, state: e.target.value })} data-testid="eq-state">
              {config?.equipment_states.map((s) => <option key={s}>{s}</option>)}
            </select>
          </div>
          <div>
            <label className="text-xs uppercase tracking-wider block mb-1" style={{ color: "#7A8B6C" }}>Серійний / №</label>
            <input className="input-mil" value={form.serial} onChange={(e) => setForm({ ...form, serial: e.target.value })} data-testid="eq-serial" />
          </div>
          <div className="col-span-2 md:col-span-3">
            <label className="text-xs uppercase tracking-wider block mb-1" style={{ color: "#7A8B6C" }}>Примітки</label>
            <input className="input-mil" placeholder="Дислокація, відповідальний, тощо" value={form.notes}
              onChange={(e) => setForm({ ...form, notes: e.target.value })} data-testid="eq-notes" />
          </div>
        </div>
        <div className="flex gap-2 mt-4">
          <button type="submit" className="btn-mil btn-mil-primary" data-testid="btn-eq-submit">
            {editingId ? "Зберегти зміни" : "Додати засіб"}
          </button>
          {editingId && (
            <button type="button" className="btn-mil" onClick={reset}>Скасувати</button>
          )}
        </div>
      </form>

      {/* List */}
      <div className="mb-2 flex items-center justify-between">
        <h4 className="font-semibold tracking-wide">
          ЗАСОБИ ({equipment.length})
          {childEquipment.length > 0 && <span className="text-xs ml-2" style={{ color: "#7A8B6C" }}>+ у відділеннях: {childEquipment.length}</span>}
        </h4>
      </div>

      {equipment.length === 0 && childEquipment.length === 0 && (
        <div className="text-center py-10 border border-dashed border-mil rounded" style={{ color: "#5C6E54" }}>
          Засобів ще не додано. Додайте перший вище ⬆
        </div>
      )}

      {equipment.length > 0 && (
        <div className="space-y-2 mb-4">
          {equipment.map((e) => (
            <div key={e.id} className="bg-mil-deep border border-mil rounded p-3 flex items-start gap-3" data-testid={`eq-${e.id}`}>
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
                    {e.notes && <span>{e.notes}</span>}
                  </div>
                )}
              </div>
              <button className="btn-mil text-xs py-1 px-2" onClick={() => startEdit(e)} data-testid={`edit-${e.id}`}>✎</button>
              <button className="btn-mil btn-mil-danger text-xs py-1 px-2" onClick={() => remove(e.id)} data-testid={`del-${e.id}`}>✕</button>
            </div>
          ))}
        </div>
      )}

      {childEquipment.length > 0 && (
        <div className="mt-6">
          <div className="text-xs uppercase tracking-wider mb-2" style={{ color: "#7A8B6C" }}>
            Засоби у відділеннях підрозділу
          </div>
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


/* ================== INTERACTIONS TAB ================== */
function InteractionsTab({ interactions, subunits, channels, onChange, showToast }) {
  const [form, setForm] = useState({
    source: subunits[0] || "", target: subunits[1] || "",
    channel: "радіо УКХ", freq: "", callsign: "", purpose: "",
  });
  const [editingId, setEditingId] = useState(null);

  // External source option (e.g. КБ)
  const externalNodes = ["Командир батальйону", "Старший начальник", "Сусіди"];
  const allSourceOptions = [...externalNodes, ...subunits];

  const submit = async (ev) => {
    ev.preventDefault();
    if (form.source === form.target) { showToast("Джерело та адресат мають відрізнятися", "err"); return; }
    try {
      if (editingId) {
        await axios.put(`${API}/interactions/${editingId}`, form);
        showToast("Зв'язок оновлено");
      } else {
        await axios.post(`${API}/interactions`, form);
        showToast("Зв'язок додано");
      }
      setEditingId(null);
      setForm({ ...form, freq: "", callsign: "", purpose: "" });
      onChange();
    } catch (e) {
      showToast(e.response?.data?.detail || "Помилка", "err");
    }
  };

  const remove = async (id) => {
    if (!window.confirm("Видалити зв'язок?")) return;
    await axios.delete(`${API}/interactions/${id}`);
    showToast("Видалено");
    onChange();
  };

  const seedTypical = async () => {
    if (!window.confirm("Це замінить всі зв'язки типовим набором. Продовжити?")) return;
    await axios.post(`${API}/interactions/preset/typical`);
    showToast("Типову матрицю заповнено");
    onChange();
  };

  const startEdit = (i) => {
    setForm({ source: i.source, target: i.target, channel: i.channel, freq: i.freq, callsign: i.callsign, purpose: i.purpose });
    setEditingId(i.id);
  };

  // Build matrix grouped by source
  const grouped = useMemo(() => {
    const g = {};
    interactions.forEach((i) => {
      g[i.source] = g[i.source] || [];
      g[i.source].push(i);
    });
    return g;
  }, [interactions]);

  const channelColor = {
    "радіо УКХ": "#7AB8D8",
    "радіо КХ": "#A4C26A",
    "ЗАЗ (захищений)": "#E89090",
    "цифровий канал": "#B8A0D6",
    "дротовий": "#D8C36A",
    "посильний": "#7A8B6C",
    "L-band/SAT": "#D4A06A",
  };

  return (
    <div>
      {/* FORM */}
      <div className="bg-mil border border-mil rounded-lg p-4 mb-5">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-accent font-bold tracking-wide">
            {editingId ? "✎ РЕДАГУВАННЯ ЗВ'ЯЗКУ" : "+ ДОДАТИ КАНАЛ ВЗАЄМОДІЇ"}
          </h3>
          <button className="btn-mil text-xs" onClick={seedTypical} data-testid="btn-int-seed">
            Заповнити типове
          </button>
        </div>
        <form onSubmit={submit} className="grid grid-cols-2 md:grid-cols-3 gap-3">
          <div>
            <label className="text-xs uppercase tracking-wider block mb-1" style={{ color: "#7A8B6C" }}>Джерело</label>
            <select className="input-mil" value={form.source} onChange={(e) => setForm({ ...form, source: e.target.value })} data-testid="int-source">
              {allSourceOptions.map((n) => <option key={n}>{n}</option>)}
            </select>
          </div>
          <div>
            <label className="text-xs uppercase tracking-wider block mb-1" style={{ color: "#7A8B6C" }}>Адресат</label>
            <select className="input-mil" value={form.target} onChange={(e) => setForm({ ...form, target: e.target.value })} data-testid="int-target">
              {allSourceOptions.map((n) => <option key={n}>{n}</option>)}
            </select>
          </div>
          <div>
            <label className="text-xs uppercase tracking-wider block mb-1" style={{ color: "#7A8B6C" }}>Канал</label>
            <select className="input-mil" value={form.channel} onChange={(e) => setForm({ ...form, channel: e.target.value })} data-testid="int-channel">
              {channels.map((c) => <option key={c}>{c}</option>)}
            </select>
          </div>
          <div>
            <label className="text-xs uppercase tracking-wider block mb-1" style={{ color: "#7A8B6C" }}>Частота / RC</label>
            <input className="input-mil" placeholder="напр. RC-12 / 145.500 МГц" value={form.freq}
              onChange={(e) => setForm({ ...form, freq: e.target.value })} data-testid="int-freq" />
          </div>
          <div>
            <label className="text-xs uppercase tracking-wider block mb-1" style={{ color: "#7A8B6C" }}>Позивний</label>
            <input className="input-mil" placeholder="напр. КОЛУМБ" value={form.callsign}
              onChange={(e) => setForm({ ...form, callsign: e.target.value })} data-testid="int-callsign" />
          </div>
          <div>
            <label className="text-xs uppercase tracking-wider block mb-1" style={{ color: "#7A8B6C" }}>Призначення</label>
            <input className="input-mil" placeholder="напр. Постановка задач" value={form.purpose}
              onChange={(e) => setForm({ ...form, purpose: e.target.value })} data-testid="int-purpose" />
          </div>
          <div className="col-span-2 md:col-span-3 flex gap-2">
            <button type="submit" className="btn-mil btn-mil-primary" data-testid="btn-int-submit">
              {editingId ? "Зберегти" : "Додати зв'язок"}
            </button>
            {editingId && (
              <button type="button" className="btn-mil" onClick={() => { setEditingId(null); setForm({ ...form, freq: "", callsign: "", purpose: "" }); }}>
                Скасувати
              </button>
            )}
          </div>
        </form>
      </div>

      {/* List grouped by source */}
      <div className="space-y-3">
        {Object.keys(grouped).length === 0 ? (
          <div className="text-center py-12 bg-mil border border-dashed border-mil rounded-lg" style={{ color: "#5C6E54" }}>
            Зв'язків ще не додано. Натисніть «Заповнити типове» для швидкого старту.
          </div>
        ) : (
          Object.entries(grouped).map(([src, items]) => (
            <div key={src} className="bg-mil border border-mil rounded-lg overflow-hidden">
              <div className="px-4 py-2 border-b border-mil bg-mil-deep">
                <span className="text-xs uppercase tracking-wider" style={{ color: "#7A8B6C" }}>Від:</span>{" "}
                <span className="font-bold text-accent">{src}</span>
              </div>
              <div className="p-3 space-y-2">
                {items.map((i) => (
                  <div key={i.id} className="bg-mil-deep border border-mil rounded p-3 flex items-start gap-3" data-testid={`int-${i.id}`}>
                    <div className="flex-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-accent">→</span>
                        <span className="font-bold">{i.target}</span>
                        <span className="badge" style={{ background: `${channelColor[i.channel] || "#5C6E54"}30`, color: channelColor[i.channel] || "#7A8B6C", border: `1px solid ${channelColor[i.channel] || "#5C6E54"}` }}>
                          {i.channel}
                        </span>
                        {i.freq && <span className="text-sm" style={{ fontFamily: "JetBrains Mono", color: "#D4A06A" }}>{i.freq}</span>}
                        {i.callsign && <span className="text-sm" style={{ color: "#7AB8D8" }}>«{i.callsign}»</span>}
                      </div>
                      {i.purpose && <div className="text-xs mt-1" style={{ color: "#7A8B6C" }}>{i.purpose}</div>}
                    </div>
                    <button className="btn-mil text-xs py-1 px-2" onClick={() => startEdit(i)} data-testid={`int-edit-${i.id}`}>✎</button>
                    <button className="btn-mil btn-mil-danger text-xs py-1 px-2" onClick={() => remove(i.id)} data-testid={`int-del-${i.id}`}>✕</button>
                  </div>
                ))}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}


/* ================== SUMMARY TAB ================== */
function SummaryTab({ equipment, interactions, structure }) {
  const sumByCat = {};
  const sumByType = { штатний: 0, позаштатний: 0 };
  equipment.forEach((e) => {
    sumByCat[e.category] = (sumByCat[e.category] || 0) + (e.qty || 1);
    sumByType[e.type] = (sumByType[e.type] || 0) + (e.qty || 1);
  });
  const total = sumByType.штатний + sumByType.позаштатний;

  // Top units by equipment count
  const byUnit = {};
  equipment.forEach((e) => {
    const k = e.node_path.split("/")[0];
    byUnit[k] = (byUnit[k] || 0) + (e.qty || 1);
  });
  const topUnits = Object.entries(byUnit).sort((a, b) => b[1] - a[1]);

  return (
    <div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <Stat value={structure.total_personnel} label="Особовий склад" color="#A4C26A" />
        <Stat value={total} label="Засобів усього" color="#7AB8D8" />
        <Stat value={sumByType.штатний} label="Штатних" color="#A4C26A" />
        <Stat value={sumByType.позаштатний} label="Позаштатних" color="#D4A06A" />
        <Stat value={interactions.length} label="Каналів взаємодії" color="#B8A0D6" />
        <Stat value={Object.keys(byUnit).length} label="Підрозділів з засобами" color="#D8C36A" />
        <Stat value={Object.keys(sumByCat).length} label="Категорій засобів" color="#7AB8D8" />
        <Stat value={equipment.length} label="Записів засобів" color="#A4C26A" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-mil border border-mil rounded-lg p-5">
          <h3 className="text-accent font-bold tracking-wide mb-4">ЗА КАТЕГОРІЯМИ</h3>
          {Object.entries(sumByCat).sort((a, b) => b[1] - a[1]).map(([cat, n]) => (
            <div key={cat} className="mb-3 last:mb-0">
              <div className="flex justify-between text-sm mb-1">
                <span>{cat}</span>
                <span className="text-accent font-bold">{n}</span>
              </div>
              <div className="h-2 bg-mil-deep rounded overflow-hidden">
                <div className="h-full" style={{ width: `${total ? (n / total) * 100 : 0}%`, background: "linear-gradient(90deg, #3D5A2C, #A4C26A)" }}></div>
              </div>
            </div>
          ))}
          {!Object.keys(sumByCat).length && <div className="text-sm" style={{ color: "#7A8B6C" }}>Поки немає даних</div>}
        </div>

        <div className="bg-mil border border-mil rounded-lg p-5">
          <h3 className="text-accent font-bold tracking-wide mb-4">ЗА ПІДРОЗДІЛАМИ</h3>
          {topUnits.map(([u, n]) => (
            <div key={u} className="mb-3 last:mb-0">
              <div className="flex justify-between text-sm mb-1">
                <span className="truncate pr-2">{u}</span>
                <span className="text-blue font-bold">{n}</span>
              </div>
              <div className="h-2 bg-mil-deep rounded overflow-hidden">
                <div className="h-full" style={{ width: `${topUnits[0] ? (n / topUnits[0][1]) * 100 : 0}%`, background: "linear-gradient(90deg, #2C4A5E, #7AB8D8)" }}></div>
              </div>
            </div>
          ))}
          {!topUnits.length && <div className="text-sm" style={{ color: "#7A8B6C" }}>Поки немає даних</div>}
        </div>
      </div>
    </div>
  );
}

function Stat({ value, label, color }) {
  return (
    <div className="bg-mil border border-mil rounded-lg p-4">
      <div className="text-3xl font-bold" style={{ color, fontFamily: "JetBrains Mono" }}>{value}</div>
      <div className="text-xs uppercase tracking-wider mt-1" style={{ color: "#7A8B6C" }}>{label}</div>
    </div>
  );
}

export default App;
