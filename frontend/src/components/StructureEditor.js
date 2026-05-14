import { useState } from "react";
import { useAuth } from "../AuthContext";

/**
 * StructureEditor — CRUD для структури роти.
 * Тільки для COMMANDER.
 *
 * Props:
 *  - structure: { subunits, order, name }
 *  - onChange:  () => Promise<void>   (перезавантажити структуру)
 *  - showToast: (msg, kind) => void
 */
export default function StructureEditor({ structure, onChange, showToast }) {
  const { ax } = useAuth();
  const [creatingSu, setCreatingSu] = useState(false);
  const [newSu, setNewSu] = useState({ key: "", name: "", type: "platoon", count: 0 });
  const [creatingSq, setCreatingSq] = useState(null); // parent_key
  const [newSq, setNewSq] = useState({ key: "", name: "", count: 0 });
  const [renaming, setRenaming] = useState(null); // {kind:'su'|'sq', parent_key, key, oldName}
  const [tmpName, setTmpName] = useState("");

  if (!structure) return null;

  const ax_ = ax();

  // ============================ ACTIONS ============================

  const createSubunit = async () => {
    if (!newSu.key.trim() || !newSu.name.trim()) {
      showToast("Заповніть ключ і назву", "err");
      return;
    }
    try {
      await ax_.post("/structure/subunits", newSu);
      showToast(`✓ Додано підрозділ «${newSu.name}»`);
      setNewSu({ key: "", name: "", type: "platoon", count: 0 });
      setCreatingSu(false);
      await onChange?.();
    } catch (e) {
      showToast(e.response?.data?.detail || "Помилка", "err");
    }
  };

  const createSquad = async (parentKey) => {
    if (!newSq.key.trim() || !newSq.name.trim()) {
      showToast("Заповніть ключ і назву", "err");
      return;
    }
    try {
      await ax_.post("/structure/squads", { ...newSq, parent_key: parentKey });
      showToast(`✓ Додано відділення «${newSq.name}»`);
      setNewSq({ key: "", name: "", count: 0 });
      setCreatingSq(null);
      await onChange?.();
    } catch (e) {
      showToast(e.response?.data?.detail || "Помилка", "err");
    }
  };

  const saveRename = async () => {
    if (!tmpName.trim() || !renaming) return;
    try {
      if (renaming.kind === "su") {
        const r = await ax_.put(`/structure/subunits/${renaming.key}`, { new_name: tmpName });
        if (r.data.cascade_count) {
          showToast(`✓ Перейменовано. Оновлено ${r.data.cascade_count} карток/засобів`);
        } else {
          showToast(`✓ Перейменовано на «${tmpName}»`);
        }
      } else {
        await ax_.put(`/structure/squads/${renaming.parent_key}/${renaming.key}`, { new_name: tmpName });
        showToast(`✓ Перейменовано відділення`);
      }
      setRenaming(null); setTmpName("");
      await onChange?.();
    } catch (e) {
      showToast(e.response?.data?.detail || "Помилка", "err");
    }
  };

  const deleteSubunit = async (key, name) => {
    if (!window.confirm(`Видалити підрозділ «${name}»?\nПов'язані картки/засоби втратять структурний зв'язок.`)) return;
    try {
      await ax_.delete(`/structure/subunits/${key}`);
      showToast(`✕ Видалено`);
      await onChange?.();
    } catch (e) {
      const msg = e.response?.data?.detail || "Помилка";
      if (msg.includes("Не можна видалити")) {
        if (window.confirm(`${msg}\n\nВсе одно видалити? (force=1)`)) {
          await ax_.delete(`/structure/subunits/${key}?force=1`);
          showToast(`✕ Видалено (force)`);
          await onChange?.();
          return;
        }
      }
      showToast(msg, "err");
    }
  };

  const deleteSquad = async (parentKey, key, name) => {
    if (!window.confirm(`Видалити відділення «${name}»?`)) return;
    try {
      await ax_.delete(`/structure/squads/${parentKey}/${key}`);
      showToast(`✕ Видалено`);
      await onChange?.();
    } catch (e) {
      const msg = e.response?.data?.detail || "Помилка";
      if (msg.includes("Не можна видалити")) {
        if (window.confirm(`${msg}\n\nВсе одно видалити?`)) {
          await ax_.delete(`/structure/squads/${parentKey}/${key}?force=1`);
          showToast(`✕ Видалено (force)`);
          await onChange?.();
          return;
        }
      }
      showToast(msg, "err");
    }
  };

  // ============================ RENDER ============================

  return (
    <div className="bg-mil border border-mil rounded-lg p-5" data-testid="structure-editor"
         style={{ borderLeft: "4px solid #D4A06A" }}>
      <div className="flex items-center justify-between mb-4">
        <div>
          <div className="text-xs uppercase mb-1" style={{ color: "#7A8B6C" }}>Редагування</div>
          <h3 className="text-base font-bold">🏗 Структура роти/батальйону</h3>
        </div>
        <button className="btn-mil btn-mil-primary text-xs"
                onClick={() => setCreatingSu(true)} data-testid="btn-add-subunit">
          + Підрозділ
        </button>
      </div>

      {creatingSu && (
        <div className="bg-mil-deep border border-accent rounded p-3 mb-3" data-testid="form-new-subunit">
          <div className="grid grid-cols-2 md:grid-cols-5 gap-2 text-sm">
            <input className="input-mil" placeholder="ключ (латиниця): vzvod_3"
                   value={newSu.key} onChange={(e) => setNewSu({ ...newSu, key: e.target.value })}
                   data-testid="new-su-key" />
            <input className="input-mil" placeholder="Назва: 3 Взвод РР"
                   value={newSu.name} onChange={(e) => setNewSu({ ...newSu, name: e.target.value })}
                   data-testid="new-su-name" />
            <select className="input-mil" value={newSu.type}
                    onChange={(e) => setNewSu({ ...newSu, type: e.target.value })}>
              <option value="hq">штаб</option>
              <option value="platoon">взвод</option>
              <option value="squad">відділення</option>
              <option value="other">інше</option>
            </select>
            <input className="input-mil" type="number" placeholder="штат"
                   value={newSu.count} onChange={(e) => setNewSu({ ...newSu, count: Number(e.target.value) })} />
            <div className="flex gap-1">
              <button className="btn-mil btn-mil-primary text-xs flex-1"
                      onClick={createSubunit} data-testid="btn-su-save">Створити</button>
              <button className="btn-mil text-xs"
                      onClick={() => { setCreatingSu(false); setNewSu({ key: "", name: "", type: "platoon", count: 0 }); }}>
                ✕
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="space-y-2">
        {structure.order.map(suKey => {
          const su = structure.subunits[suKey];
          if (!su) return null;
          const squads = Object.entries(su.squads || {}).filter(([k]) => k !== "__DIRECT__");
          return (
            <div key={suKey} className="border border-mil rounded p-3" data-testid={`su-${suKey}`}>
              {/* SUBUNIT */}
              <div className="flex items-center justify-between gap-2">
                {renaming?.kind === "su" && renaming.key === suKey ? (
                  <div className="flex-1 flex gap-2">
                    <input className="input-mil flex-1 text-sm" value={tmpName}
                           onChange={(e) => setTmpName(e.target.value)}
                           onKeyDown={(e) => e.key === "Enter" && saveRename()}
                           autoFocus />
                    <button className="btn-mil btn-mil-primary text-xs" onClick={saveRename}>✓</button>
                    <button className="btn-mil text-xs" onClick={() => setRenaming(null)}>✕</button>
                  </div>
                ) : (
                  <>
                    <div className="font-bold">
                      <span style={{ color: "#A4C26A" }}>{su.name}</span>
                      <span className="text-xs ml-2" style={{ color: "#7A8B6C" }}>
                        {su.type} • {su.count} осіб
                      </span>
                    </div>
                    <div className="flex gap-1">
                      <button className="btn-mil text-xs" title="Додати відділення"
                              onClick={() => { setCreatingSq(suKey); setNewSq({ key: "", name: "", count: 0 }); }}
                              data-testid={`btn-add-squad-${suKey}`}>+ Відділення</button>
                      <button className="btn-mil text-xs" title="Перейменувати"
                              onClick={() => { setRenaming({ kind: "su", key: suKey, oldName: su.name }); setTmpName(su.name); }}
                              data-testid={`btn-rename-su-${suKey}`}>✎</button>
                      <button className="btn-mil btn-mil-danger text-xs" title="Видалити"
                              onClick={() => deleteSubunit(suKey, su.name)}
                              data-testid={`btn-del-su-${suKey}`}>✕</button>
                    </div>
                  </>
                )}
              </div>

              {/* SQUAD CREATE */}
              {creatingSq === suKey && (
                <div className="bg-mil-deep border border-accent rounded p-2 mt-2 grid grid-cols-2 md:grid-cols-4 gap-2 text-sm"
                     data-testid={`form-new-squad-${suKey}`}>
                  <input className="input-mil text-xs" placeholder="ключ: vid_3"
                         value={newSq.key} onChange={(e) => setNewSq({ ...newSq, key: e.target.value })} />
                  <input className="input-mil text-xs" placeholder="Назва відділення"
                         value={newSq.name} onChange={(e) => setNewSq({ ...newSq, name: e.target.value })} />
                  <input className="input-mil text-xs" type="number" placeholder="штат"
                         value={newSq.count} onChange={(e) => setNewSq({ ...newSq, count: Number(e.target.value) })} />
                  <div className="flex gap-1">
                    <button className="btn-mil btn-mil-primary text-xs flex-1"
                            onClick={() => createSquad(suKey)}
                            data-testid={`btn-sq-save-${suKey}`}>Створити</button>
                    <button className="btn-mil text-xs" onClick={() => setCreatingSq(null)}>✕</button>
                  </div>
                </div>
              )}

              {/* SQUADS */}
              {squads.length > 0 && (
                <div className="mt-2 ml-4 space-y-1">
                  {squads.map(([sqKey, sq]) => (
                    <div key={sqKey} className="flex items-center justify-between text-sm border-l border-mil pl-3 py-1"
                         data-testid={`sq-${suKey}-${sqKey}`}>
                      {renaming?.kind === "sq" && renaming.key === sqKey && renaming.parent_key === suKey ? (
                        <div className="flex-1 flex gap-2">
                          <input className="input-mil flex-1 text-sm" value={tmpName}
                                 onChange={(e) => setTmpName(e.target.value)}
                                 onKeyDown={(e) => e.key === "Enter" && saveRename()}
                                 autoFocus />
                          <button className="btn-mil btn-mil-primary text-xs" onClick={saveRename}>✓</button>
                          <button className="btn-mil text-xs" onClick={() => setRenaming(null)}>✕</button>
                        </div>
                      ) : (
                        <>
                          <div>
                            <span style={{ color: "#7AB8D8" }}>↳ {sq.name || "(без назви)"}</span>
                            {sq.count > 0 && <span className="text-xs ml-2" style={{ color: "#7A8B6C" }}>{sq.count} осіб</span>}
                          </div>
                          <div className="flex gap-1">
                            <button className="btn-mil text-xs"
                                    onClick={() => { setRenaming({ kind: "sq", parent_key: suKey, key: sqKey, oldName: sq.name }); setTmpName(sq.name); }}
                                    data-testid={`btn-rename-sq-${suKey}-${sqKey}`}>✎</button>
                            <button className="btn-mil btn-mil-danger text-xs"
                                    onClick={() => deleteSquad(suKey, sqKey, sq.name)}
                                    data-testid={`btn-del-sq-${suKey}-${sqKey}`}>✕</button>
                          </div>
                        </>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>

      <div className="text-xs mt-4" style={{ color: "#5C6E54" }}>
        💡 Зміни структури автоматично перейменовують <b>node_path</b> у картках, засобах, БК.
        Видалення з прив'язками вимагає підтвердження.
      </div>
    </div>
  );
}
