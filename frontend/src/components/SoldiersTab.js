import { useState, useEffect } from "react";
import { useAuth, can } from "../AuthContext";
import { cls } from "./Common";
import FilePreviewModal from "./FilePreviewModal";
import TransferModal from "./TransferModal";
import { downloadAuthFile } from "../utils/download";

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
const LOCATIONS = ["ППД", "РЗ", "РВ", "Відрядження", "Відпустка", "Лікарня", "СЗЧ", "ВЛК", "Інше"];

function locColor(loc) {
  return {
    "ППД":        { bg: "rgba(164,194,106,.15)", c: "#A4C26A" },
    "РЗ":         { bg: "rgba(122,184,216,.15)", c: "#7AB8D8" },
    "РВ":         { bg: "rgba(212,160,106,.25)", c: "#D4A06A" },
    "Відрядження":{ bg: "rgba(184,160,214,.15)", c: "#B8A0D6" },
    "Відпустка":  { bg: "rgba(216,195,106,.15)", c: "#D8C36A" },
    "Лікарня":    { bg: "rgba(122,184,216,.15)", c: "#7AB8D8" },
    "СЗЧ":        { bg: "rgba(232,144,144,.2)",  c: "#E89090" },
    "ВЛК":        { bg: "rgba(212,160,106,.15)", c: "#D4A06A" },
    "Інше":       { bg: "rgba(122,139,108,.15)", c: "#7A8B6C" },
  }[loc] || { bg: "rgba(122,139,108,.15)", c: "#7A8B6C" };
}

export default function SoldiersTab({ structure, showToast, forceOpenId, clearOpenId }) {
  const { ax, token, user } = useAuth();
  const editable = can.edit(user);
  const [soldiers, setSoldiers] = useState([]);
  const [filter, setFilter] = useState("");
  const [unitFilter, setUnitFilter] = useState("");
  const [locFilter, setLocFilter] = useState("");
  const [selected, setSelected] = useState(null);
  const [showCreate, setShowCreate] = useState(false);
  const [loading, setLoading] = useState(true);

  const reload = async () => {
    setLoading(true);
    try { const r = await ax().get("/soldiers"); setSoldiers(r.data); }
    finally { setLoading(false); }
  };

  useEffect(() => { reload(); }, []);
  useEffect(() => {
    if (forceOpenId) { setSelected(forceOpenId); clearOpenId && clearOpenId(); }
  }, [forceOpenId]);

  const seedFromBchs = async () => {
    if (!window.confirm("Створити картки для всіх осіб з БЧС? Існуючі залишаться без змін.")) return;
    try {
      const r = await ax().post("/soldiers/seed-from-bchs");
      showToast(`Створено ${r.data.inserted} карток`); reload();
    } catch (e) { showToast(e.response?.data?.detail || "Помилка", "err"); }
  };

  const subunits = structure ? structure.order.map(k => structure.subunits[k].name) : [];
  const filtered = soldiers.filter(s => {
    if (unitFilter && !s.node_path?.startsWith(unitFilter)) return false;
    if (locFilter && (s.location_status || "ППД") !== locFilter) return false;
    if (filter) {
      const f = filter.toLowerCase();
      return s.fio.toLowerCase().includes(f) || (s.callsign || "").toLowerCase().includes(f) || (s.position || "").toLowerCase().includes(f);
    }
    return true;
  });

  const downloadBchs = async (fmt) => {
    try {
      const { filename } = await downloadAuthFile(
        `${process.env.REACT_APP_BACKEND_URL}/api/export/bchs.${fmt}`,
        `БЧС.${fmt}`,
        token,
      );
      showToast(`✓ Завантажено: ${filename}`);
    } catch (e) { showToast(`Помилка: ${e.message}`, "err"); }
  };

  const docCompleteness = (s) => {
    const docs = s.documents || {};
    const required = [...REQUIRED];
    if (s.has_driver_license) required.push("driver_license");
    const has = required.filter(t => docs[t]).length;
    return { has, total: required.length };
  };

  if (loading) return <div className="text-center py-10" style={{ color: "#7A8B6C" }}>Завантаження…</div>;

  return (
    <div>
      <div className="flex flex-wrap gap-3 mb-4 items-center">
        <input className="input-mil flex-1 min-w-[240px]" placeholder="🔍 Пошук за ПІБ / позивним / посадою"
               value={filter} onChange={(e) => setFilter(e.target.value)} />
        <select className="input-mil" style={{ width: "auto" }} value={unitFilter} onChange={(e) => setUnitFilter(e.target.value)}>
          <option value="">Усі підрозділи</option>
          {subunits.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
        <select className="input-mil" style={{ width: "auto" }} value={locFilter} onChange={(e) => setLocFilter(e.target.value)} data-testid="loc-filter">
          <option value="">📍 Усі стани</option>
          {LOCATIONS.map(l => <option key={l} value={l}>{l}</option>)}
        </select>
        <button className="btn-mil text-sm" onClick={() => downloadBchs("xlsx")} data-testid="dl-bchs-xlsx">⬇ БЧС .xlsx</button>
        <button className="btn-mil text-sm" onClick={() => downloadBchs("csv")} data-testid="dl-bchs-csv">⬇ БЧС .csv</button>
        {editable && (
          <button className="btn-mil btn-mil-primary text-sm" onClick={() => setShowCreate(true)} data-testid="btn-add-soldier">
            + Додати картку
          </button>
        )}
        {can.commander(user) && (
          <button className="btn-mil text-sm" onClick={seedFromBchs} data-testid="seed-soldiers">
            Створити картки з БЧС
          </button>
        )}
        <div className="text-sm ml-auto" style={{ color: "#7A8B6C" }}>
          Показано: <span className="text-accent font-bold">{filtered.length}</span> / {soldiers.length}
        </div>
      </div>

      {filtered.length === 0 ? (
        <div className="text-center py-12 bg-mil border border-dashed border-mil rounded-lg" style={{ color: "#5C6E54" }}>
          Карток ще немає. {editable && "Натисніть «+ Додати картку» або «Створити картки з БЧС»."}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {filtered.map(s => {
            const c = docCompleteness(s);
            const complete = c.has === c.total;
            return (
              <div key={s.id} onClick={() => setSelected(s.id)}
                   className="bg-mil border border-mil rounded-lg p-3 cursor-pointer hover:border-accent transition-all"
                   data-testid={`sold-${s.id}`}>
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1 min-w-0">
                    <div className="font-bold truncate">{s.fio}</div>
                    {s.callsign && <div className="text-xs text-blue">«{s.callsign}»</div>}
                    <div className="text-xs mt-1" style={{ color: "#7A8B6C" }}>{s.position}</div>
                    <div className="text-xs truncate" style={{ color: "#5C6E54" }}>{s.node_path}</div>
                  </div>
                  <div className="flex flex-col items-end gap-1">
                    <div className={cls("badge", complete ? "badge-state-ok" : "badge-state-warn")} title="Документи">
                      📄 {c.has}/{c.total}
                    </div>
                    <div className="badge" style={{ background: locColor(s.location_status).bg, color: locColor(s.location_status).c,
                                                    border: `1px solid ${locColor(s.location_status).c}`, fontSize: "9px" }}
                         title={s.location_place || s.location_status || "ППД"}>
                      📍 {s.location_status || "ППД"}
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {selected && (
        <SoldierDetail id={selected} onClose={() => { setSelected(null); reload(); }} showToast={showToast} />
      )}
      {showCreate && (
        <CreateSoldierModal
          subunits={subunits}
          onClose={() => setShowCreate(false)}
          onCreated={(newId) => { setShowCreate(false); reload(); setSelected(newId); }}
          showToast={showToast}
        />
      )}
    </div>
  );
}


function CreateSoldierModal({ subunits, onClose, onCreated, showToast }) {
  const { ax } = useAuth();
  const [form, setForm] = useState({
    fio: "", callsign: "", rank: "солдат", position: "", node_path: subunits[0] || "",
    birth_date: "", mobilized_at: "", bzvp_passed_at: "", ktz_passed_at: "",
    blood_group: "", has_driver_license: false, notes: "",
    education: [], certificates: [],
  });
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    if (!form.fio.trim()) { showToast("Вкажіть ПІБ", "err"); return; }
    setBusy(true);
    try {
      const r = await ax().post("/soldiers", form);
      showToast(`✓ Картку створено: ${r.data.fio}`);
      onCreated(r.data.id);
    } catch (e) { showToast(e.response?.data?.detail || "Помилка", "err"); }
    finally { setBusy(false); }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4"
         style={{ background: "rgba(14,26,20,.85)", backdropFilter: "blur(6px)" }} onClick={onClose}>
      <form className="bg-mil border border-mil rounded-lg w-full max-w-2xl p-6"
            onSubmit={submit} onClick={(e) => e.stopPropagation()}>
        <div className="flex justify-between items-start mb-4">
          <div>
            <div className="text-xs uppercase tracking-wider" style={{ color: "#7A8B6C" }}>Нова картка</div>
            <h2 className="text-xl font-bold text-accent">+ Додати картку військовослужбовця</h2>
            <div className="text-xs mt-1" style={{ color: "#7A8B6C" }}>
              Після створення можна буде завантажити документи у детальній формі
            </div>
          </div>
          <button type="button" className="btn-mil text-xs" onClick={onClose}>✕</button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div className="md:col-span-2">
            <Field label="ПІБ *">
              <input className="input-mil" required value={form.fio}
                     onChange={(e) => setForm({...form, fio: e.target.value})}
                     placeholder="ПЕТРЕНКО Іван Іванович" data-testid="new-fio" autoFocus />
            </Field>
          </div>
          <Field label="Позивний">
            <input className="input-mil" value={form.callsign}
                   onChange={(e) => setForm({...form, callsign: e.target.value})}
                   placeholder="напр. ВЕДМІДЬ" data-testid="new-callsign" />
          </Field>
          <Field label="Звання">
            <input className="input-mil" value={form.rank}
                   onChange={(e) => setForm({...form, rank: e.target.value})}
                   placeholder="солдат / молодший сержант / лейтенант" data-testid="new-rank" />
          </Field>
          <Field label="Посада">
            <input className="input-mil" value={form.position}
                   onChange={(e) => setForm({...form, position: e.target.value})}
                   placeholder="Розвідник-оператор" data-testid="new-position" />
          </Field>
          <Field label="Підрозділ *">
            <select className="input-mil" required value={form.node_path}
                    onChange={(e) => setForm({...form, node_path: e.target.value})} data-testid="new-node">
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
          <div className="md:col-span-2">
            <Field label="Примітки">
              <input className="input-mil" value={form.notes}
                     onChange={(e) => setForm({...form, notes: e.target.value})}
                     placeholder="довільний текст" />
            </Field>
          </div>
        </div>

        <div className="flex gap-2 mt-5">
          <button type="submit" className="btn-mil btn-mil-primary" disabled={busy} data-testid="new-submit">
            {busy ? "Створення…" : "Створити та відкрити"}
          </button>
          <button type="button" className="btn-mil" onClick={onClose}>Скасувати</button>
        </div>

        <div className="text-xs mt-4" style={{ color: "#5C6E54" }}>
          ℹ Після створення відкриється детальна картка, де можна додати освіту,
          сертифікати та завантажити скани документів (паспорт/ІПН/диплом/ВП/військовий квиток).
        </div>
      </form>
    </div>
  );
}


function Field({ label, children }) {
  return <div><label className="text-xs uppercase block mb-1" style={{ color: "#7A8B6C" }}>{label}</label>{children}</div>;
}


function SoldierDetail({ id, onClose, showToast }) {
  const { ax, user, token } = useAuth();
  const editable = can.edit(user);
  const isCommander = user?.role === "COMMANDER";
  const [s, setS] = useState(null);
  const [form, setForm] = useState(null);
  const [files, setFiles] = useState([]);
  const [uploading, setUploading] = useState("");
  const [showTransfer, setShowTransfer] = useState(false);
  const [previewFile, setPreviewFile] = useState(null);
  const [pdfBusy, setPdfBusy] = useState(false);

  const load = async () => {
    const [r, f] = await Promise.all([ax().get(`/soldiers/${id}`), ax().get(`/soldiers/${id}/documents`)]);
    setS(r.data); setForm(r.data); setFiles(f.data);
  };

  useEffect(() => { load(); }, [id]);

  const exportPdf = async () => {
    setPdfBusy(true);
    try {
      const { filename } = await downloadAuthFile(
        `${process.env.REACT_APP_BACKEND_URL}/api/soldiers/${id}/export.pdf`,
        `Особова_картка_${s?.fio || "soldier"}.pdf`,
        token,
      );
      showToast(`✓ PDF: ${filename}`);
    } catch (e) {
      showToast(`Помилка PDF: ${e.message}`, "err");
    } finally {
      setPdfBusy(false);
    }
  };

  const save = async () => {
    try {
      const payload = { ...form };
      delete payload.id; delete payload.documents; delete payload.created_at; delete payload.updated_at;
      await ax().put(`/soldiers/${id}`, payload);
      showToast("✓ Збережено");
      load();
    } catch (e) { showToast(e.response?.data?.detail || "Помилка", "err"); }
  };

  const removeSoldier = async () => {
    if (!window.confirm(`Видалити картку «${s.fio}»?\n\nРАЗОМ З УСІМА ДОКУМЕНТАМИ. Дію неможливо скасувати.`)) return;
    try {
      await ax().delete(`/soldiers/${id}`);
      showToast(`✓ Картку «${s.fio}» видалено`);
      onClose();
    } catch (e) { showToast(e.response?.data?.detail || "Помилка", "err"); }
  };

  const upload = async (docType, file) => {
    setUploading(docType);
    try {
      const fd = new FormData();
      fd.append("doc_type", docType);
      fd.append("file", file);
      await ax().post(`/soldiers/${id}/documents`, fd, { headers: { "Content-Type": "multipart/form-data" } });
      showToast("✓ Завантажено");
      load();
    } catch (e) { showToast(e.response?.data?.detail || "Помилка", "err"); }
    finally { setUploading(""); }
  };

  const removeDoc = async (fileId) => {
    if (!window.confirm("Видалити документ?")) return;
    await ax().delete(`/documents/${fileId}`);
    showToast("Видалено"); load();
  };

  const downloadDoc = async (fileId, filename) => {
    try {
      await downloadAuthFile(
        `${process.env.REACT_APP_BACKEND_URL}/api/documents/${fileId}`,
        filename,
        token,
      );
    } catch (e) {
      showToast(`Помилка: ${e.message}`, "err");
    }
  };

  if (!s || !form) return null;

  const required = ["passport", "ipn", "military_id"];
  if (form.has_driver_license) required.push("driver_license");
  const optional = ["diploma", "certificate", "other"];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4"
         style={{ background: "rgba(14,26,20,.85)", backdropFilter: "blur(6px)" }}
         onClick={onClose}>
      <div className="bg-mil border border-mil rounded-lg w-full max-w-4xl max-h-[92vh] overflow-y-auto"
           onClick={(e) => e.stopPropagation()}>
        {/* header */}
        <div className="sticky top-0 bg-mil border-b border-mil p-5 z-10 flex justify-between items-start">
          <div>
            <div className="text-xs uppercase tracking-wider" style={{ color: "#7A8B6C" }}>Картка військовослужбовця</div>
            <h2 className="text-xl font-bold text-accent">{s.fio}</h2>
            <div className="text-sm" style={{ color: "#7A8B6C" }}>
              {s.position} {s.callsign && <span className="text-blue">• «{s.callsign}»</span>} • {s.node_path}
            </div>
          </div>
          <div className="flex gap-2">
            <button className="btn-mil text-xs" onClick={exportPdf} disabled={pdfBusy}
                    data-testid="btn-export-pdf">
              {pdfBusy ? "⏳ PDF…" : "📄 PDF"}
            </button>
            {isCommander && (
              <button className="btn-mil btn-mil-danger text-xs" onClick={removeSoldier} data-testid="btn-delete-soldier">
                ✕ Видалити картку
              </button>
            )}
            <button className="btn-mil text-xs" onClick={onClose}>✕</button>
          </div>
        </div>

        <div className="p-5 space-y-5">
          {/* Особисті дані */}
          <Section title="📋 Особисті дані">
            <Grid>
              <Field2 label="ПІБ"><input className="input-mil" value={form.fio} disabled={!editable} onChange={(e) => setForm({...form, fio: e.target.value})} /></Field2>
              <Field2 label="Позивний"><input className="input-mil" value={form.callsign} disabled={!editable} onChange={(e) => setForm({...form, callsign: e.target.value})} /></Field2>
              <Field2 label="Звання"><input className="input-mil" value={form.rank} disabled={!editable} onChange={(e) => setForm({...form, rank: e.target.value})} /></Field2>
              <Field2 label="Посада"><input className="input-mil" value={form.position} disabled={!editable} onChange={(e) => setForm({...form, position: e.target.value})} /></Field2>
              <Field2 label="Підрозділ"><input className="input-mil" value={form.node_path} disabled={!editable} onChange={(e) => setForm({...form, node_path: e.target.value})} /></Field2>
              <Field2 label="Дата народження"><input type="date" className="input-mil" value={form.birth_date} disabled={!editable} onChange={(e) => setForm({...form, birth_date: e.target.value})} /></Field2>
              <Field2 label="Група крові"><input className="input-mil" placeholder="O(I) Rh+" value={form.blood_group} disabled={!editable} onChange={(e) => setForm({...form, blood_group: e.target.value})} /></Field2>
              <Field2 label="Має водійське посвідчення?">
                <label className="flex items-center gap-2 mt-2">
                  <input type="checkbox" checked={form.has_driver_license} disabled={!editable}
                         onChange={(e) => setForm({...form, has_driver_license: e.target.checked})} />
                  <span className="text-sm">Так (тоді ВП обов'язково)</span>
                </label>
              </Field2>
            </Grid>
          </Section>

          {/* Служба */}
          <Section title="⚔️ Служба та підготовка">
            <Grid>
              <Field2 label="Дата мобілізації"><input type="date" className="input-mil" value={form.mobilized_at} disabled={!editable} onChange={(e) => setForm({...form, mobilized_at: e.target.value})} data-testid="fld-mobilized" /></Field2>
              <Field2 label="БЗВП пройдено"><input type="date" className="input-mil" value={form.bzvp_passed_at} disabled={!editable} onChange={(e) => setForm({...form, bzvp_passed_at: e.target.value})} data-testid="fld-bzvp" /></Field2>
              <Field2 label="КТЗ пройдено"><input type="date" className="input-mil" value={form.ktz_passed_at} disabled={!editable} onChange={(e) => setForm({...form, ktz_passed_at: e.target.value})} data-testid="fld-ktz" /></Field2>
            </Grid>
          </Section>

          {/* Місцезнаходження */}
          <Section title="📍 Місцезнаходження"
                   actions={editable && (
                     <button type="button" className="btn-mil btn-mil-primary text-xs"
                             onClick={() => setShowTransfer(true)} data-testid="btn-transfer">
                       🔄 Перемістити
                     </button>
                   )}>
            <Grid>
              <Field2 label="Стан">
                <select className="input-mil" value={form.location_status || "ППД"} disabled={!editable}
                        onChange={(e) => setForm({...form, location_status: e.target.value,
                                                  location_updated_at: new Date().toISOString().slice(0,10)})}
                        data-testid="fld-loc-status">
                  {LOCATIONS.map(l => <option key={l} value={l}>{l}</option>)}
                </select>
              </Field2>
              <Field2 label="Місце (н.п./адреса/координати)">
                <input className="input-mil" value={form.location_place || ""} disabled={!editable}
                       placeholder="напр. м.Покровськ / 50.123, 36.456"
                       onChange={(e) => setForm({...form, location_place: e.target.value})} />
              </Field2>
            </Grid>
            {form.location_updated_at && (
              <div className="text-xs mt-2" style={{ color: "#7A8B6C" }}>
                Оновлено: {form.location_updated_at}
              </div>
            )}
          </Section>

          {/* Освіта */}
          <Section title="🎓 Освіта" actions={editable && <button className="btn-mil text-xs" onClick={() => setForm({...form, education: [...(form.education||[]), {degree:"", institution:"", year:"", specialty:""}]})}>+ Додати</button>}>
            {(form.education || []).length === 0 && <div className="text-xs" style={{ color: "#7A8B6C" }}>Не вказано</div>}
            {(form.education || []).map((ed, i) => (
              <div key={i} className="grid grid-cols-1 md:grid-cols-4 gap-2 mb-2">
                <input className="input-mil" placeholder="Ступінь" value={ed.degree} disabled={!editable} onChange={(e) => updArr(form, setForm, "education", i, {degree: e.target.value})} />
                <input className="input-mil" placeholder="Заклад" value={ed.institution} disabled={!editable} onChange={(e) => updArr(form, setForm, "education", i, {institution: e.target.value})} />
                <input className="input-mil" placeholder="Рік" value={ed.year} disabled={!editable} onChange={(e) => updArr(form, setForm, "education", i, {year: e.target.value})} />
                <div className="flex gap-1">
                  <input className="input-mil flex-1" placeholder="Спеціальність" value={ed.specialty} disabled={!editable} onChange={(e) => updArr(form, setForm, "education", i, {specialty: e.target.value})} />
                  {editable && <button className="btn-mil btn-mil-danger text-xs px-2" onClick={() => setForm({...form, education: form.education.filter((_,j) => j !== i)})}>✕</button>}
                </div>
              </div>
            ))}
          </Section>

          {/* Сертифікати */}
          <Section title="🏅 Сертифікати" actions={editable && <button className="btn-mil text-xs" onClick={() => setForm({...form, certificates: [...(form.certificates||[]), {name:"", issued_at:"", issuer:""}]})}>+ Додати</button>}>
            {(form.certificates || []).length === 0 && <div className="text-xs" style={{ color: "#7A8B6C" }}>Не вказано</div>}
            {(form.certificates || []).map((cert, i) => (
              <div key={i} className="grid grid-cols-1 md:grid-cols-3 gap-2 mb-2">
                <input className="input-mil" placeholder="Назва" value={cert.name} disabled={!editable} onChange={(e) => updArr(form, setForm, "certificates", i, {name: e.target.value})} />
                <input type="date" className="input-mil" value={cert.issued_at} disabled={!editable} onChange={(e) => updArr(form, setForm, "certificates", i, {issued_at: e.target.value})} />
                <div className="flex gap-1">
                  <input className="input-mil flex-1" placeholder="Видавник" value={cert.issuer} disabled={!editable} onChange={(e) => updArr(form, setForm, "certificates", i, {issuer: e.target.value})} />
                  {editable && <button className="btn-mil btn-mil-danger text-xs px-2" onClick={() => setForm({...form, certificates: form.certificates.filter((_,j) => j !== i)})}>✕</button>}
                </div>
              </div>
            ))}
          </Section>

          {/* Документи */}
          <Section title="📎 Копії документів">
            <div className="space-y-2">
              {[...required, ...optional].map(t => {
                const fileId = (s.documents || {})[t];
                const meta = files.find(f => f.id === fileId);
                const isReq = required.includes(t);
                return (
                  <div key={t} className="bg-mil-deep border border-mil rounded p-2.5 flex items-center gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-semibold text-sm">{DOC_LABELS[t]}</span>
                        {isReq && <span className="badge badge-state-warn" style={{ fontSize: "9px" }}>обов'язково</span>}
                      </div>
                      {meta && (
                        <div className="text-xs mt-1" style={{ color: "#7A8B6C" }}>
                          {meta.filename} · {(meta.size/1024).toFixed(0)} KB
                        </div>
                      )}
                    </div>
                    {meta ? (
                      <>
                        <button className="btn-mil text-xs py-1 px-2"
                                onClick={() => setPreviewFile({id: fileId, name: meta.filename, mime: meta.mime})}
                                title="Перегляд" data-testid={`prev-${fileId}`}>👁</button>
                        <button className="btn-mil text-xs py-1 px-2" onClick={() => downloadDoc(fileId, meta.filename)}>⬇</button>
                        {editable && <button className="btn-mil btn-mil-danger text-xs py-1 px-2" onClick={() => removeDoc(fileId)}>✕</button>}
                      </>
                    ) : editable && (
                      <label className="btn-mil text-xs cursor-pointer" data-testid={`upload-${t}`}>
                        {uploading === t ? "⏳" : "+ Файл"}
                        <input type="file" className="hidden" accept="image/*,application/pdf"
                               onChange={(e) => e.target.files[0] && upload(t, e.target.files[0])} />
                      </label>
                    )}
                  </div>
                );
              })}
            </div>
          </Section>

          {/* Згенеровані документи на військового */}
          {(() => {
            const generated = files.filter(f => f.source === "generated" || f.type === "generated");
            if (generated.length === 0) return null;
            return (
              <Section title="📑 Документи на військового (згенеровані)">
                <div className="text-xs mb-3" style={{ color: "#7A8B6C" }}>
                  Шаблони з вкладки «📄 Документи» автоматично зберігаються тут. Діловод проставляє статус та дати.
                </div>
                <div className="space-y-2">
                  {generated.map(g => (
                    <GeneratedDocRow key={g.id} doc={g} editable={editable}
                                     onPreview={() => setPreviewFile({id: g.id, name: g.filename, mime: g.mime})}
                                     onChanged={load} onDownload={downloadDoc} onRemove={removeDoc}
                                     showToast={showToast} />
                  ))}
                </div>
              </Section>
            );
          })()}

          <Section title="📝 Примітки">
            <textarea className="input-mil" rows="3" value={form.notes} disabled={!editable}
                      onChange={(e) => setForm({...form, notes: e.target.value})} />
          </Section>

          {editable && (
            <div className="flex gap-2 sticky bottom-0 bg-mil pt-3 pb-1 border-t border-mil">
              <button className="btn-mil btn-mil-primary" onClick={save} data-testid="btn-save-soldier">Зберегти зміни</button>
              <button className="btn-mil" onClick={onClose}>Закрити</button>
            </div>
          )}
        </div>
      </div>
      {showTransfer && (
        <TransferModal soldier={s} onClose={() => setShowTransfer(false)}
                       onChanged={load} showToast={showToast} />
      )}
      {previewFile && (
        <FilePreviewModal fileId={previewFile.id} filename={previewFile.name}
                          mime={previewFile.mime} onClose={() => setPreviewFile(null)} />
      )}
    </div>
  );
}


function GeneratedDocRow({ doc, editable, onPreview, onChanged, onDownload, onRemove, showToast }) {
  const { ax } = useAuth();
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({
    status: doc.status || "draft",
    status_at: doc.status_at || "",
    doc_notes: doc.doc_notes || "",
  });

  const STATUS_COLORS = {
    draft: { bg: "rgba(122,139,108,.2)", c: "#7A8B6C" },
    signed: { bg: "rgba(122,184,216,.2)", c: "#7AB8D8" },
    executed: { bg: "rgba(164,194,106,.2)", c: "#A4C26A" },
  };
  const STATUS_LABELS = { draft: "Чернетка", signed: "Підписано", executed: "Виконано" };
  const c = STATUS_COLORS[doc.status || "draft"];

  const save = async () => {
    try {
      await ax().put(`/documents/${doc.id}/status`, form);
      showToast("✓ Статус оновлено");
      setEditing(false); onChanged && onChanged();
    } catch (e) { showToast(e.response?.data?.detail || "Помилка", "err"); }
  };

  return (
    <div className="bg-mil-deep border border-mil rounded p-3" data-testid={`gen-${doc.id}`}>
      <div className="flex items-start gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-semibold text-sm">{doc.template_name || doc.filename}</span>
            <span className="badge" style={{ background: c.bg, color: c.c, border: `1px solid ${c.c}`, fontSize: "10px" }}>
              {STATUS_LABELS[doc.status || "draft"]}
            </span>
            {doc.status_at && <span className="text-xs" style={{ color: "#7A8B6C" }}>· {doc.status_at}</span>}
          </div>
          <div className="text-xs mt-1" style={{ color: "#5C6E54" }}>
            {doc.filename} · {(doc.size/1024).toFixed(0)} KB · згенерував {doc.uploaded_by} ({doc.uploaded_at?.slice(0,10)})
          </div>
          {doc.doc_notes && <div className="text-xs mt-1" style={{ color: "#7A8B6C" }}>📝 {doc.doc_notes}</div>}
        </div>
        <div className="flex gap-1">
          <button className="btn-mil text-xs py-1 px-2" onClick={onPreview} title="Перегляд">👁</button>
          <button className="btn-mil text-xs py-1 px-2" onClick={() => onDownload(doc.id, doc.filename)}>⬇</button>
          {editable && <button className="btn-mil text-xs py-1 px-2" onClick={() => setEditing(!editing)} title="Статус">⚙</button>}
          {editable && <button className="btn-mil btn-mil-danger text-xs py-1 px-2" onClick={() => onRemove(doc.id)}>✕</button>}
        </div>
      </div>
      {editing && (
        <div className="mt-3 pt-3 border-t border-mil grid grid-cols-1 md:grid-cols-3 gap-2">
          <select className="input-mil" value={form.status} onChange={(e) => setForm({...form, status: e.target.value})}>
            <option value="draft">Чернетка</option>
            <option value="signed">Підписано</option>
            <option value="executed">Виконано</option>
          </select>
          <input type="date" className="input-mil" value={form.status_at}
                 onChange={(e) => setForm({...form, status_at: e.target.value})} placeholder="Дата" />
          <input className="input-mil" placeholder="Примітка (наказ №...)"
                 value={form.doc_notes} onChange={(e) => setForm({...form, doc_notes: e.target.value})} />
          <div className="md:col-span-3 flex gap-2 mt-1">
            <button className="btn-mil btn-mil-primary text-xs" onClick={save}>Зберегти</button>
            <button className="btn-mil text-xs" onClick={() => setEditing(false)}>Скасувати</button>
          </div>
        </div>
      )}
    </div>
  );
}

function Section({ title, actions, children }) {
  return (
    <div className="bg-mil-deep border border-mil rounded-lg p-4">
      <div className="flex justify-between items-center mb-3">
        <h3 className="text-sm font-bold text-brown">{title}</h3>
        {actions}
      </div>
      {children}
    </div>
  );
}
function Grid({ children }) { return <div className="grid grid-cols-1 md:grid-cols-2 gap-3">{children}</div>; }
function Field2({ label, children }) { return <div><label className="text-xs uppercase block mb-1" style={{ color: "#7A8B6C" }}>{label}</label>{children}</div>; }
function updArr(form, setForm, key, idx, patch) {
  const arr = [...(form[key] || [])];
  arr[idx] = { ...arr[idx], ...patch };
  setForm({ ...form, [key]: arr });
}
