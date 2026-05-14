import { useEffect, useState } from "react";
import { useAuth } from "../AuthContext";
import { cls } from "./Common";

export default function BackupTab({ showToast }) {
  const { ax, token } = useAuth();
  const [backups, setBackups] = useState([]);
  const [running, setRunning] = useState(false);
  const [downloading, setDownloading] = useState("");

  const reload = async () => {
    const r = await ax().get("/admin/backup/list");
    setBackups(r.data.backups);
  };
  useEffect(() => { reload(); }, []);

  const runNow = async () => {
    setRunning(true);
    try {
      const r = await ax().post("/admin/backup/run");
      showToast(`✓ Бекап створено: ${r.data.name} (${(r.data.size/1024/1024).toFixed(1)} MB)`);
      reload();
    } catch (e) { showToast(e.response?.data?.detail || "Помилка", "err"); }
    finally { setRunning(false); }
  };

  const download = async (name) => {
    setDownloading(name);
    try {
      const url = `${process.env.REACT_APP_BACKEND_URL}/api/admin/backup/download/${encodeURIComponent(name)}`;
      const res = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob();
      const u = URL.createObjectURL(blob);
      const a = document.createElement("a"); a.href = u; a.download = name;
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(u), 1000);
      showToast(`Завантажено: ${name}`);
    } catch (e) { showToast(`Помилка: ${e.message}`, "err"); }
    finally { setDownloading(""); }
  };

  const remove = async (name) => {
    if (!window.confirm(`Видалити бекап «${name}»?`)) return;
    try {
      await ax().delete(`/admin/backup/${encodeURIComponent(name)}`);
      showToast(`Видалено: ${name}`);
      reload();
    } catch (e) { showToast(e.response?.data?.detail || "Помилка", "err"); }
  };

  const fmtSize = (b) => b > 1024*1024 ? `${(b/1024/1024).toFixed(1)} MB` : `${(b/1024).toFixed(0)} KB`;
  const fmtDate = (s) => s ? s.slice(0, 19).replace("T", " ") : "—";

  return (
    <div>
      <div className="bg-mil border border-mil rounded-lg p-5 mb-5"
           style={{ borderLeft: "4px solid #7AB8D8" }}>
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div>
            <div className="text-xs uppercase mb-1" style={{ color: "#7A8B6C" }}>Резервне копіювання</div>
            <h2 className="text-lg font-bold">🛡 Бекап БД та документів</h2>
            <div className="text-sm mt-1" style={{ color: "#7A8B6C" }}>
              Автоматично щодня о <b>02:00 UTC</b>. Зберігається останніх 10 бекапів.<br/>
              Кожен бекап = MongoDB dump + усі завантажені документи + структура БЧС.
            </div>
          </div>
          <button className="btn-mil btn-mil-primary" onClick={runNow} disabled={running} data-testid="btn-backup-now">
            {running ? "⏳ Створення… (може зайняти 30-60 сек)" : "🚀 Зробити бекап зараз"}
          </button>
        </div>
      </div>

      {backups.length === 0 ? (
        <div className="text-center py-12 bg-mil border border-dashed border-mil rounded-lg" style={{ color: "#5C6E54" }}>
          Бекапів ще немає. Натисніть «🚀 Зробити бекап зараз» для першого.
        </div>
      ) : (
        <div className="bg-mil border border-mil rounded-lg overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-mil-deep">
              <tr style={{ color: "#7A8B6C" }}>
                <th className="text-left px-3 py-2 uppercase text-xs">Файл</th>
                <th className="text-left px-3 py-2 uppercase text-xs">Створено</th>
                <th className="text-right px-3 py-2 uppercase text-xs">Розмір</th>
                <th className="px-3 py-2 w-32"></th>
              </tr>
            </thead>
            <tbody>
              {backups.map(b => (
                <tr key={b.name} className="border-t border-mil">
                  <td className="px-3 py-2 font-mono text-xs" style={{ fontFamily: "JetBrains Mono", color: "#A4C26A" }}>
                    {b.name}
                  </td>
                  <td className="px-3 py-2 text-xs" style={{ color: "#7A8B6C" }}>{fmtDate(b.created_at)}</td>
                  <td className="px-3 py-2 text-right" style={{ fontFamily: "JetBrains Mono", color: "#7AB8D8" }}>
                    {fmtSize(b.size)}
                  </td>
                  <td className="px-3 py-2 text-right whitespace-nowrap">
                    <button className="btn-mil text-xs py-1 px-2 mr-1"
                            onClick={() => download(b.name)}
                            disabled={downloading === b.name}
                            data-testid={`bk-dl-${b.name}`}>
                      {downloading === b.name ? "⏳" : "⬇"}
                    </button>
                    <button className="btn-mil btn-mil-danger text-xs py-1 px-2"
                            onClick={() => remove(b.name)} data-testid={`bk-rm-${b.name}`}>✕</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="text-xs mt-4" style={{ color: "#5C6E54" }}>
        💡 Відновлення з бекапу: розпакуйте архів і виконайте на сервері<br/>
        <code style={{ fontFamily: "JetBrains Mono", color: "#A4C26A" }}>mongorestore --drop mongo/</code> + скопіюйте папку <code style={{ fontFamily: "JetBrains Mono", color: "#A4C26A" }}>storage/</code> у /app/storage.<br/>
        Або зверніться до адміна.
      </div>
    </div>
  );
}
