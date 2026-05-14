import { useEffect, useMemo, useState } from "react";
import { useAuth } from "../AuthContext";

const SEV_COLORS = {
  red: { bg: "#3D1F1F", fg: "#E89090", glow: "#E8909030", icon: "🔴" },
  yellow: { bg: "#3D331F", fg: "#D8C36A", glow: "#D8C36A30", icon: "🟡" },
  green: { bg: "#1F3D22", fg: "#A4C26A", glow: "#A4C26A30", icon: "🟢" },
};

export default function RiskHeatmap({ showToast }) {
  const { ax } = useAuth();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [riskFilter, setRiskFilter] = useState("all"); // all | red | yellow | green
  const [subunitFilter, setSubunitFilter] = useState("");

  const reload = async () => {
    setLoading(true);
    try {
      const r = await ax().get("/risk-heatmap");
      setData(r.data);
    } catch (e) {
      showToast?.(e.response?.data?.detail || "Помилка завантаження", "err");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { reload(); /* eslint-disable-next-line */ }, []);

  const filteredSoldiers = useMemo(() => {
    if (!data) return [];
    return data.soldiers.filter(s => {
      if (riskFilter !== "all" && s.risk !== riskFilter) return false;
      if (subunitFilter && s.node_path !== subunitFilter) return false;
      return true;
    });
  }, [data, riskFilter, subunitFilter]);

  if (!data) {
    return <div className="text-center py-12" style={{ color: "#7A8B6C" }}>
      {loading ? "⏳ Розрахунок ризиків…" : "Немає даних"}
    </div>;
  }

  const t = data.totals;
  const sortedSubunits = Object.entries(data.by_subunit)
    .sort((a, b) => b[1].red - a[1].red || b[1].yellow - a[1].yellow);

  return (
    <div data-testid="risk-heatmap">
      {/* HERO BAR */}
      <div className="bg-mil border border-mil rounded-lg p-5 mb-5"
           style={{ borderLeft: "4px solid #E89090" }}>
        <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
          <div>
            <div className="text-xs uppercase mb-1" style={{ color: "#7A8B6C" }}>Командир, увага!</div>
            <h2 className="text-lg font-bold">🔥 Карта ризиків особового складу</h2>
            <div className="text-xs mt-1" style={{ color: "#7A8B6C" }}>
              Оновлено: {data.generated_at?.slice(0, 19).replace("T", " ")} UTC
            </div>
          </div>
          <button className="btn-mil text-xs" onClick={reload} disabled={loading} data-testid="btn-heatmap-reload">
            {loading ? "⏳" : "↻ Перерахувати"}
          </button>
        </div>

        {/* TOTAL BAR */}
        <div className="rounded-md overflow-hidden h-10 flex shadow-inner"
             style={{ background: "#1B1F18" }}>
          {t.red > 0 && (
            <button
              className="flex items-center justify-center font-bold text-sm transition-opacity"
              style={{
                width: `${t.ratio_red}%`, background: "linear-gradient(135deg, #C84545, #8B2929)",
                color: "white", minWidth: "60px"
              }}
              onClick={() => setRiskFilter(riskFilter === "red" ? "all" : "red")}
              data-testid="bar-red"
              title={`Червоні: ${t.red} осіб (${t.ratio_red.toFixed(0)}%)`}>
              🔴 {t.red}
            </button>
          )}
          {t.yellow > 0 && (
            <button
              className="flex items-center justify-center font-bold text-sm"
              style={{
                width: `${t.ratio_yellow}%`, background: "linear-gradient(135deg, #C8A845, #8B6F29)",
                color: "white", minWidth: "60px"
              }}
              onClick={() => setRiskFilter(riskFilter === "yellow" ? "all" : "yellow")}
              data-testid="bar-yellow"
              title={`Жовті: ${t.yellow} осіб (${t.ratio_yellow.toFixed(0)}%)`}>
              🟡 {t.yellow}
            </button>
          )}
          {t.green > 0 && (
            <button
              className="flex items-center justify-center font-bold text-sm"
              style={{
                width: `${t.ratio_green}%`, background: "linear-gradient(135deg, #6FA040, #3F7029)",
                color: "white", minWidth: "60px"
              }}
              onClick={() => setRiskFilter(riskFilter === "green" ? "all" : "green")}
              data-testid="bar-green"
              title={`Зелені: ${t.green} осіб (${t.ratio_green.toFixed(0)}%)`}>
              🟢 {t.green}
            </button>
          )}
        </div>

        {/* QUICK STATS */}
        <div className="grid grid-cols-3 gap-2 mt-3 text-center text-xs" style={{ color: "#7A8B6C" }}>
          <div><b style={{ color: "#E89090" }}>{t.red}</b> потребують уваги</div>
          <div><b style={{ color: "#D8C36A" }}>{t.yellow}</b> на спостереженні</div>
          <div><b style={{ color: "#A4C26A" }}>{t.green}</b> у нормі</div>
        </div>
      </div>

      {/* BY SUBUNIT GRID */}
      <div className="mb-5">
        <div className="text-xs uppercase mb-2" style={{ color: "#7A8B6C" }}>За підрозділами</div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2"
             data-testid="heatmap-subunits">
          {sortedSubunits.map(([np, v]) => {
            const dominant = v.red > 0 ? "red" : v.yellow > 0 ? "yellow" : "green";
            const cfg = SEV_COLORS[dominant];
            const isFiltered = subunitFilter === np;
            return (
              <button key={np}
                      onClick={() => setSubunitFilter(isFiltered ? "" : np)}
                      className="text-left p-3 rounded border transition-all hover:opacity-90"
                      data-testid={`heatmap-su-${np.replace(/[^A-Za-z0-9]/g, '_').slice(0, 30)}`}
                      style={{
                        background: cfg.bg,
                        borderColor: isFiltered ? cfg.fg : "#2F3D26",
                        boxShadow: isFiltered ? `0 0 12px ${cfg.glow}` : "none",
                      }}>
                <div className="text-xs truncate" style={{ color: "#A4C26A" }} title={np}>
                  {np}
                </div>
                <div className="flex items-center justify-between mt-1">
                  <div style={{ fontFamily: "JetBrains Mono", color: cfg.fg }}>
                    {cfg.icon} <b className="text-lg">{v[dominant]}</b>/<span className="text-sm opacity-60">{v.total}</span>
                  </div>
                  <div className="text-xs opacity-60" style={{ color: "white" }}>
                    🔴{v.red} 🟡{v.yellow} 🟢{v.green}
                  </div>
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* FILTERS */}
      <div className="bg-mil border border-mil rounded-lg p-3 mb-3 flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2 flex-wrap text-xs">
          <span style={{ color: "#7A8B6C" }}>Фільтр:</span>
          {["all", "red", "yellow", "green"].map(r => (
            <button key={r}
                    onClick={() => setRiskFilter(r)}
                    className={`px-3 py-1 rounded-md transition ${riskFilter === r ? "font-bold" : "opacity-60 hover:opacity-100"}`}
                    style={{
                      background: r === "all" ? "#2F3D26" : SEV_COLORS[r]?.bg,
                      color: r === "all" ? "#A4C26A" : SEV_COLORS[r]?.fg,
                      border: riskFilter === r ? `1px solid ${r === "all" ? "#A4C26A" : SEV_COLORS[r]?.fg}` : "1px solid transparent",
                    }}
                    data-testid={`risk-filter-${r}`}>
              {r === "all" ? "Усі" : SEV_COLORS[r].icon} {r === "red" ? "Червоні" : r === "yellow" ? "Жовті" : r === "green" ? "Зелені" : ""}
            </button>
          ))}
          {subunitFilter && (
            <button onClick={() => setSubunitFilter("")}
                    className="px-2 py-1 rounded text-xs"
                    style={{ background: "#2F3D26", color: "#7A8B6C", border: "1px solid #5C6E54" }}>
              ✕ {subunitFilter.length > 40 ? subunitFilter.slice(0, 40) + "…" : subunitFilter}
            </button>
          )}
        </div>
        <div className="text-xs" style={{ color: "#7A8B6C" }}>
          Знайдено: <b>{filteredSoldiers.length}</b> з {t.total}
        </div>
      </div>

      {/* SOLDIERS LIST */}
      <div className="bg-mil border border-mil rounded-lg overflow-hidden" data-testid="heatmap-list">
        {filteredSoldiers.length === 0 ? (
          <div className="text-center py-8" style={{ color: "#7A8B6C" }}>
            🎉 Немає солдатів у цій категорії
          </div>
        ) : (
          <div className="divide-y divide-mil">
            {filteredSoldiers.slice(0, 100).map(s => {
              const cfg = SEV_COLORS[s.risk];
              return (
                <div key={s.id}
                     className="p-3 flex items-start gap-3 hover:bg-mil-deep transition"
                     data-testid={`heatmap-soldier-${s.id}`}
                     style={{ borderLeft: `4px solid ${cfg.fg}` }}>
                  <div className="text-2xl mt-1">{cfg.icon}</div>
                  <div className="flex-1 min-w-0">
                    <div className="font-bold text-sm">
                      {s.fio}
                      {s.callsign && <span className="ml-2" style={{ color: cfg.fg }}>«{s.callsign}»</span>}
                    </div>
                    <div className="text-xs mt-0.5" style={{ color: "#7A8B6C" }}>
                      {[s.rank, s.position, s.node_path].filter(Boolean).join(" • ")}
                    </div>
                    {s.labels?.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-2">
                        {s.labels.map((l, i) => (
                          <span key={i}
                                className="text-xs px-2 py-0.5 rounded"
                                style={{
                                  background: SEV_COLORS[l.severity]?.bg,
                                  color: SEV_COLORS[l.severity]?.fg,
                                  border: `1px solid ${SEV_COLORS[l.severity]?.fg}40`,
                                }}>
                            {l.label}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
            {filteredSoldiers.length > 100 && (
              <div className="p-3 text-center text-xs" style={{ color: "#7A8B6C" }}>
                Показано перші 100 з {filteredSoldiers.length}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
