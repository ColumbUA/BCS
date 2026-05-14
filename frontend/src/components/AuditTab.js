import { useEffect, useState } from "react";
import { useAuth } from "../AuthContext";
import { cls } from "./Common";

const CAT_LABELS = {
  soldiers: "Картки",
  transfers: "Переміщення",
  documents: "Документи",
  warehouse: "Склад",
  ammo: "Боєкомплект",
  equipment: "Засоби",
  users: "Користувачі",
  backup: "Бекап",
  settings: "Реквізити",
  interactions: "Взаємодія",
  other: "Інше",
};

const METHOD_COLOR = {
  POST: "#A4C26A", PUT: "#7AB8D8", PATCH: "#7AB8D8",
  DELETE: "#E89090",
};

export default function AuditTab({ showToast }) {
  const { ax } = useAuth();
  const [items, setItems] = useState([]);
  const [cats, setCats] = useState([]);
  const [users, setUsers] = useState([]);
  const [filter, setFilter] = useState({ category: "", username: "", success: "" });
  const [limit, setLimit] = useState(200);
  const [loading, setLoading] = useState(false);

  const reload = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (filter.category) params.append("category", filter.category);
      if (filter.username) params.append("username", filter.username);
      if (filter.success !== "") params.append("success", filter.success);
      params.append("limit", String(limit));
      const r = await ax().get(`/audit-log?${params.toString()}`);
      setItems(r.data.items || []);
    } catch (e) {
      showToast(e.response?.data?.detail || "Помилка завантаження", "err");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    ax().get("/audit-log/categories").then(r => {
      setCats(r.data.categories || []);
      setUsers(r.data.usernames || []);
    }).catch(() => {});
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => { reload(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [filter, limit]);

  const fmtTime = (s) => s ? s.slice(0, 19).replace("T", " ") : "—";

  return (
    <div data-testid="audit-tab">
      <div className="bg-mil border border-mil rounded-lg p-5 mb-5"
           style={{ borderLeft: "4px solid #B8A0D6" }}>
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div>
            <div className="text-xs uppercase mb-1" style={{ color: "#7A8B6C" }}>Журнал дій (audit log)</div>
            <h2 className="text-lg font-bold">🛡 Аудит системи</h2>
            <div className="text-sm mt-1" style={{ color: "#7A8B6C" }}>
              Усі mutating-дії (POST/PUT/DELETE) логуються автоматично.
              Зберігається <b>90 днів</b>.
            </div>
          </div>
          <button className="btn-mil text-xs" onClick={reload} disabled={loading}
                  data-testid="btn-audit-reload">
            {loading ? "⏳" : "↻ Оновити"}
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-3 mt-4">
          <div>
            <div className="text-xs uppercase mb-1" style={{ color: "#7A8B6C" }}>Категорія</div>
            <select className="input-mil w-full" data-testid="audit-filter-cat"
                    value={filter.category}
                    onChange={(e) => setFilter({ ...filter, category: e.target.value })}>
              <option value="">— усі —</option>
              {cats.map(c => <option key={c} value={c}>{CAT_LABELS[c] || c}</option>)}
            </select>
          </div>
          <div>
            <div className="text-xs uppercase mb-1" style={{ color: "#7A8B6C" }}>Користувач</div>
            <select className="input-mil w-full" data-testid="audit-filter-user"
                    value={filter.username}
                    onChange={(e) => setFilter({ ...filter, username: e.target.value })}>
              <option value="">— усі —</option>
              {users.map(u => <option key={u} value={u}>{u}</option>)}
            </select>
          </div>
          <div>
            <div className="text-xs uppercase mb-1" style={{ color: "#7A8B6C" }}>Результат</div>
            <select className="input-mil w-full" data-testid="audit-filter-success"
                    value={filter.success}
                    onChange={(e) => setFilter({ ...filter, success: e.target.value })}>
              <option value="">— усі —</option>
              <option value="true">✓ Успішні</option>
              <option value="false">✕ Помилки</option>
            </select>
          </div>
          <div>
            <div className="text-xs uppercase mb-1" style={{ color: "#7A8B6C" }}>Кількість</div>
            <select className="input-mil w-full" data-testid="audit-filter-limit"
                    value={limit} onChange={(e) => setLimit(Number(e.target.value))}>
              <option value={50}>50</option>
              <option value={200}>200</option>
              <option value={500}>500</option>
              <option value={1000}>1000</option>
            </select>
          </div>
        </div>
      </div>

      {items.length === 0 ? (
        <div className="text-center py-12 bg-mil border border-dashed border-mil rounded-lg" style={{ color: "#5C6E54" }}>
          Подій не знайдено
        </div>
      ) : (
        <div className="bg-mil border border-mil rounded-lg overflow-x-auto" data-testid="audit-table">
          <table className="w-full text-xs">
            <thead className="bg-mil-deep">
              <tr style={{ color: "#7A8B6C" }}>
                <th className="text-left px-3 py-2 uppercase">Час (UTC)</th>
                <th className="text-left px-3 py-2 uppercase">Користувач</th>
                <th className="text-left px-3 py-2 uppercase">Роль</th>
                <th className="text-left px-3 py-2 uppercase">Метод</th>
                <th className="text-left px-3 py-2 uppercase">Шлях</th>
                <th className="text-left px-3 py-2 uppercase">Категорія</th>
                <th className="text-right px-3 py-2 uppercase">Статус</th>
              </tr>
            </thead>
            <tbody>
              {items.map(it => (
                <tr key={it.id} className="border-t border-mil hover:bg-mil-deep"
                    data-testid={`audit-row-${it.id}`}>
                  <td className="px-3 py-2 whitespace-nowrap" style={{ fontFamily: "JetBrains Mono", color: "#A4C26A" }}>
                    {fmtTime(it.created_at)}
                  </td>
                  <td className="px-3 py-2 font-bold">{it.username}</td>
                  <td className="px-3 py-2" style={{ color: "#7A8B6C" }}>{it.user_role}</td>
                  <td className="px-3 py-2 font-bold" style={{ color: METHOD_COLOR[it.method] || "#fff" }}>
                    {it.method}
                  </td>
                  <td className="px-3 py-2 truncate max-w-md" style={{ fontFamily: "JetBrains Mono", color: "#D8C36A" }} title={it.path}>
                    {it.path}
                  </td>
                  <td className="px-3 py-2">
                    <span className="text-xs px-2 py-0.5 rounded" style={{
                      background: "#2F3D26", color: "#A4C26A",
                    }}>
                      {CAT_LABELS[it.category] || it.category}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-right font-mono"
                      style={{ color: it.success ? "#A4C26A" : "#E89090" }}>
                    {it.status_code}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="text-xs mt-3" style={{ color: "#5C6E54" }}>
        Усього записів: <b>{items.length}</b>. TTL: 90 днів (MongoDB index).
      </div>
    </div>
  );
}
