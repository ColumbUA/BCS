import { useState, useEffect } from "react";
import { useAuth, can } from "../AuthContext";
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

export default function SoldiersTab({ structure, showToast, forceOpenId, clearOpenId }) {
  const { ax, user } = useAuth();
  const [soldiers, setSoldiers] = useState([]);
  const [filter, setFilter] = useState("");
  const [unitFilter, setUnitFilter] = useState("");
  const [selected, setSelected] = useState(null);
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
    if (filter) {
      const f = filter.toLowerCase();
      return s.fio.toLowerCase().includes(f) || (s.callsign || "").toLowerCase().includes(f) || (s.position || "").toLowerCase().includes(f);
    }
    return true;
  });

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
          Карток ще немає. Командир може створити їх з БЧС однією кнопкою.
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
                  <div className={cls("badge", complete ? "badge-state-ok" : "badge-state-warn")} title="Документи">
                    📄 {c.has}/{c.total}
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
    </div>
  );
}


function SoldierDetail({ id, onClose, showToast }) {
  const { ax, user } = useAuth();
  const editable = can.edit(user);
  const [s, setS] = useState(null);
  const [form, setForm] = useState(null);
  const [files, setFiles] = useState([]);
  const [uploading, setUploading] = useState("");

  const load = async () => {
    const [r, f] = await Promise.all([ax().get(`/soldiers/${id}`), ax().get(`/soldiers/${id}/documents`)]);
    setS(r.data); setForm(r.data); setFiles(f.data);
  };

  useEffect(() => { load(); }, [id]);

  const save = async () => {
    try {
      const payload = { ...form };
      delete payload.id; delete payload.documents; delete payload.created_at; delete payload.updated_at;
      await ax().put(`/soldiers/${id}`, payload);
      showToast("✓ Збережено");
      load();
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
    const r = await ax().get(`/documents/${fileId}`, { responseType: "blob" });
    const url = URL.createObjectURL(r.data);
    const a = document.createElement("a"); a.href = url; a.download = filename; a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
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
          <button className="btn-mil text-xs" onClick={onClose}>✕</button>
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
