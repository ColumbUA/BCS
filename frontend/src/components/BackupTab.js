import { useEffect, useState } from "react";
import { useAuth } from "../AuthContext";
import { cls } from "./Common";
import { downloadAuthFile } from "../utils/download";

export default function BackupTab({ showToast }) {
  const { ax, token } = useAuth();
  const [backups, setBackups] = useState([]);
  const [running, setRunning] = useState(false);
  const [jobStatus, setJobStatus] = useState("");   // queued | running | done | error
  const [jobMsg, setJobMsg] = useState("");
  const [downloading, setDownloading] = useState("");

  const reload = async () => {
    const r = await ax().get("/admin/backup/list");
    setBackups(r.data.backups);
  };
  useEffect(() => { reload(); }, []);

  // Polling job статусу
  const pollJob = async (jobId) => {
    let tries = 0;
    while (tries < 120) {   // макс 2 хв (120 × 1с)
      await new Promise(r => setTimeout(r, 1000));
      try {
        const r = await ax().get(`/admin/backup/job/${jobId}`);
        const j = r.data;
        setJobStatus(j.status);
        if (j.status === "done") {
          const sz = j.result?.size ? `${(j.result.size/1024/1024).toFixed(1)} MB` : "";
          const fb = j.fallback ? " ⚠ fallback (JSON dump)" : "";
          setJobMsg(`✓ ${j.result?.name || "OK"} ${sz}${fb}`);
          showToast(`✓ Бекап створено: ${j.result?.name} ${sz}${fb}`);
          await reload();
          return;
        }
        if (j.status === "error") {
          setJobMsg(`✕ ${j.error || "Помилка"}`);
          showToast(`✕ Бекап не виконано: ${j.error}`, "err");
          return;
        }
      } catch (e) {
        // продовжуємо poll
      }
      tries++;
    }
    setJobMsg("⏱ Таймаут polling (>2 хв) — перевірте журнал бекапів");
  };

  const runNow = async () => {
    setRunning(true);
    setJobStatus("queued");
    setJobMsg("Поставлено в чергу…");
    try {
      const r = await ax().post("/admin/backup/run");
      const jobId = r.data.job_id;
      if (r.data.message) {
        setJobMsg(r.data.message);
        showToast(r.data.message);
      }
      await pollJob(jobId);
    } catch (e) {
      showToast(e.response?.data?.detail || "Помилка", "err");
      setJobMsg("✕ Не вдалось запустити");
    } finally {
      setRunning(false);
    }
  };

  const download = async (name) => {
    setDownloading(name);
    try {
      await downloadAuthFile(
        `${process.env.REACT_APP_BACKEND_URL}/api/admin/backup/download/${encodeURIComponent(name)}`,
        name,
        token,
      );
      showToast(`✓ Завантажено: ${name}`);
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
            {running ? "⏳ Створення… (у фоні)" : "🚀 Зробити бекап зараз"}
          </button>
        </div>
        {running && (
          <div className="mt-3 text-xs flex items-center gap-2"
               style={{ color: "#7AB8D8" }}
               data-testid="backup-job-progress">
            <span className="inline-block w-2 h-2 rounded-full" style={{
              background: jobStatus === "running" ? "#A4C26A" : "#7AB8D8",
              animation: "pulse 1.2s infinite"
            }} />
            <span>Статус задачі: <b>{jobStatus || "…"}</b> {jobMsg && `— ${jobMsg}`}</span>
          </div>
        )}
        {!running && jobMsg && (
          <div className="mt-3 text-xs" style={{ color: jobStatus === "error" ? "#D67676" : "#A4C26A" }}
               data-testid="backup-job-result">
            {jobMsg}
          </div>
        )}
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
