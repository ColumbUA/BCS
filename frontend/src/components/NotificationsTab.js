import { useEffect, useState } from "react";
import { useAuth } from "../AuthContext";
import { cls } from "./Common";

export default function NotificationsTab({ showToast, onOpenSoldier }) {
  const { ax } = useAuth();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try { const r = await ax().get("/notifications/material"); setData(r.data); }
    catch (e) { showToast(e.response?.data?.detail || "Помилка", "err"); }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  if (loading) return <div className="text-center py-10" style={{ color: "#7A8B6C" }}>Завантаження…</div>;
  if (!data) return null;

  return (
    <div>
      <div className="bg-mil border border-mil rounded-lg p-5 mb-5"
           style={{ borderLeft: "4px solid #D4A06A" }}>
        <div className="flex items-start gap-3">
          <div className="text-3xl">📨</div>
          <div className="flex-1">
            <div className="text-xs uppercase tracking-wider mb-1" style={{ color: "#7A8B6C" }}>Сповіщення матеріалісту</div>
            <h2 className="text-lg font-bold text-brown">{data.recipient}</h2>
            <div className="text-sm mt-2" style={{ color: "#7A8B6C" }}>
              {data.with_issues > 0 ? (
                <>Виявлено <span className="font-bold text-brown">{data.with_issues}</span> карток з неповним пакетом документів{" "}
                  (з {data.total_soldiers} загалом). Потрібно зібрати скани.</>
              ) : (
                <span className="text-accent">✓ Усі картки укомплектовано документами!</span>
              )}
            </div>
          </div>
          <button className="btn-mil text-sm" onClick={load} data-testid="refresh-notif">↻</button>
        </div>
      </div>

      {data.issues.length === 0 ? (
        <div className="text-center py-12 bg-mil border border-dashed border-mil rounded-lg" style={{ color: "#A4C26A" }}>
          ✓ Усі обов'язкові документи завантажено
        </div>
      ) : (
        <div className="space-y-2">
          {data.issues.map((it) => (
            <div key={it.soldier_id}
                 onClick={() => onOpenSoldier && onOpenSoldier(it.soldier_id)}
                 className="bg-mil border border-mil rounded-lg p-3 flex items-start gap-3 cursor-pointer hover:border-brown transition-all"
                 data-testid={`notif-${it.soldier_id}`}>
              <div className="text-2xl">⚠</div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-bold">{it.fio}</span>
                  {it.callsign && <span className="text-blue text-sm">«{it.callsign}»</span>}
                  <span className="text-xs" style={{ color: "#7A8B6C" }}>{it.position}</span>
                </div>
                <div className="text-xs mt-1" style={{ color: "#5C6E54" }}>{it.node_path}</div>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {it.missing.map(d => (
                    <span key={d} className="badge badge-state-bad" style={{ fontSize: "10px" }}>
                      ✕ {d}
                    </span>
                  ))}
                </div>
              </div>
              <div className="text-brown text-xs">▸</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
