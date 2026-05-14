import { useEffect, useState } from "react";
import axios from "axios";
import "@/App.css";
import { AuthProvider, useAuth, API, ROLE_LABELS, can } from "./AuthContext";
import Login from "./Login";
import Profile from "./components/Profile";
import StructureTab from "./components/StructureTab";
import InteractionsTab from "./components/InteractionsTab";
import SoldiersTab from "./components/SoldiersTab";
import AmmoTab from "./components/AmmoTab";
import NotificationsTab from "./components/NotificationsTab";
import TemplatesTab from "./components/TemplatesTab";
import WarehouseTab from "./components/WarehouseTab";
import UsersTab from "./components/UsersTab";
import { cls, Stat } from "./components/Common";

function AppShell() {
  const { user, token, logout, ax } = useAuth();
  const [tab, setTab] = useState("structure");
  const [structure, setStructure] = useState(null);
  const [equipment, setEquipment] = useState([]);
  const [interactions, setInteractions] = useState([]);
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState(null);
  const [downloading, setDownloading] = useState(null);
  const [showProfile, setShowProfile] = useState(false);
  const [openSoldierId, setOpenSoldierId] = useState(null);

  const showToast = (msg, kind = "ok") => {
    if (window.__toastTimer) clearTimeout(window.__toastTimer);
    setToast({ msg, kind });
    window.__toastTimer = setTimeout(() => setToast(null), 2500);
  };

  const reload = async () => {
    const inst = ax();
    const [s, e, i, c] = await Promise.all([
      inst.get("/structure"),
      inst.get("/equipment"),
      inst.get("/interactions"),
      inst.get("/config"),
    ]);
    setStructure(s.data); setEquipment(e.data);
    setInteractions(i.data); setConfig(c.data);
    setLoading(false);
  };

  useEffect(() => {
    if (user && token) reload().catch((err) => { console.error(err); showToast("Не вдалося завантажити дані", "err"); setLoading(false); });
  }, [user, token]);

  const downloadFile = async (urlPath, filename, key) => {
    setDownloading(key);
    try {
      const res = await fetch(urlPath.startsWith("/api") ? `${process.env.REACT_APP_BACKEND_URL}${urlPath}` : urlPath, {
        credentials: "omit",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = filename;
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      showToast(`Завантажено: ${filename}`);
    } catch (e) { showToast(`Помилка: ${e.message}`, "err"); }
    finally { setDownloading(null); }
  };

  if (loading) return (
    <div className="min-h-screen bg-grid flex items-center justify-center">
      <div className="text-accent">Завантаження…</div>
    </div>
  );

  const compName = structure?.name || "Рота";

  // Якщо клікнули на сповіщення → перейти у вкладку Картки і відкрити модалку
  if (openSoldierId && tab !== "soldiers") setTab("soldiers");

  return (
    <div className="min-h-screen bg-grid">
      <header className="border-b border-mil sticky top-0 z-30 glass">
        <div className="max-w-[1400px] mx-auto px-6 py-3 flex items-center justify-between gap-4 flex-wrap">
          <div className="min-w-0">
            <h1 className="text-xl font-bold tracking-wider truncate" style={{ letterSpacing: "1.2px" }}>
              {compName.toUpperCase()}
            </h1>
            <div className="text-xs" style={{ color: "#7A8B6C" }}>
              Розвідувальний батальйон • {structure?.total_personnel} осіб
            </div>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <button className="btn-mil text-xs" disabled={downloading === "org"}
              onClick={() => downloadFile("/api/export/orgstructure.xml", `${compName} - Організаційна структура.xml`, "org")}
              data-testid="dl-org">⬇ Орг. (.xml)</button>
            <button className="btn-mil text-xs" disabled={downloading === "cmd"}
              onClick={() => downloadFile("/api/export/command.xml", `${compName} - Бойове управління.xml`, "cmd")}
              data-testid="dl-cmd">⬇ Бойове (.xml)</button>
            <button className="btn-mil text-xs" disabled={downloading === "int"}
              onClick={() => downloadFile("/api/export/interactions.xml", `${compName} - Матриця взаємодії.xml`, "int")}
              data-testid="dl-int">⬇ Матриця (.xml)</button>
            <button className="btn-mil btn-mil-primary text-xs" disabled={downloading === "zip"}
              onClick={() => downloadFile("/api/export/full-package.zip", `${compName} - пакет.zip`, "zip")}
              data-testid="dl-zip">{downloading === "zip" ? "⏳" : "⬇"} ZIP</button>
            <button className="btn-mil text-xs" disabled={downloading === "deploy"}
              onClick={() => downloadFile("/files/rota-rrr-deploy.zip", "rota-rrr-deploy.zip", "deploy")}
              data-testid="dl-deploy">🚀 Deploy</button>

            <div className="w-px h-6 bg-mil mx-1" />

            <button className="btn-mil text-xs" onClick={() => setShowProfile(true)} data-testid="btn-profile">
              👤 {user?.username} <span className="text-accent ml-1">{ROLE_LABELS[user?.role]?.split(" ")[0]}</span>
              {user?.totp_enabled && <span title="2FA увімкнено" className="text-accent ml-1">🔐</span>}
            </button>
          </div>
        </div>

        <div className="max-w-[1400px] mx-auto px-6 flex gap-1 border-t border-mil overflow-x-auto">
          <Tab id="structure" cur={tab} onSelect={setTab}>📦 Структура та засоби</Tab>
          <Tab id="ammo" cur={tab} onSelect={setTab}>🎯 Боєкомплект</Tab>
          <Tab id="warehouse" cur={tab} onSelect={setTab}>🏪 Склад</Tab>
          <Tab id="soldiers" cur={tab} onSelect={setTab}>👥 Картки солдатів</Tab>
          <Tab id="templates" cur={tab} onSelect={setTab}>📄 Документи</Tab>
          <Tab id="interactions" cur={tab} onSelect={setTab}>📡 Матриця взаємодії</Tab>
          {can.material(user) && (
            <Tab id="notifications" cur={tab} onSelect={setTab}>📨 Сповіщення</Tab>
          )}
          {can.commander(user) && (
            <Tab id="users" cur={tab} onSelect={setTab}>🔐 Користувачі</Tab>
          )}
          <Tab id="summary" cur={tab} onSelect={setTab}>📊 Зведення</Tab>
        </div>
      </header>

      {toast && (
        <div className={cls("fixed top-24 right-6 z-50 px-4 py-3 rounded-lg shadow-lg border",
                            toast.kind === "ok" ? "bg-mil border-accent text-accent" : "bg-mil text-red-300")}
             style={{ borderColor: toast.kind === "ok" ? "#A4C26A" : "#E89090" }}>
          {toast.msg}
        </div>
      )}

      <main className="max-w-[1400px] mx-auto px-6 py-5">
        {tab === "structure" && <StructureTab structure={structure} equipment={equipment} config={config} onChange={reload} showToast={showToast} />}
        {tab === "ammo" && <AmmoTab structure={structure} config={config} showToast={showToast} />}
        {tab === "warehouse" && <WarehouseTab config={config} showToast={showToast} />}
        {tab === "soldiers" && <SoldiersTab structure={structure} showToast={showToast} forceOpenId={openSoldierId} clearOpenId={() => setOpenSoldierId(null)} />}
        {tab === "templates" && <TemplatesTab showToast={showToast} />}
        {tab === "interactions" && <InteractionsTab interactions={interactions} structure={structure} channels={config?.interaction_channels || []} onChange={reload} showToast={showToast} />}
        {tab === "notifications" && can.material(user) && (
          <NotificationsTab showToast={showToast} onOpenSoldier={(id) => { setOpenSoldierId(id); setTab("soldiers"); }} />
        )}
        {tab === "users" && can.commander(user) && (
          <UsersTab structure={structure} showToast={showToast} />
        )}
        {tab === "summary" && <SummaryTab equipment={equipment} interactions={interactions} structure={structure} showToast={showToast} />}
      </main>

      {showProfile && <Profile onClose={() => setShowProfile(false)} showToast={showToast} />}
    </div>
  );
}

function Tab({ id, cur, onSelect, children }) {
  return (
    <div className={cls("tab-mil whitespace-nowrap", cur === id && "active")}
         onClick={() => onSelect(id)} data-testid={`tab-${id}`}>{children}</div>
  );
}


function SummaryTab({ equipment, interactions, structure, showToast }) {
  const { ax } = useAuth();
  const [ammo, setAmmo] = useState([]);
  const [soldiers, setSoldiers] = useState([]);

  useEffect(() => {
    Promise.all([ax().get("/ammo"), ax().get("/soldiers")]).then(([a, s]) => {
      setAmmo(a.data); setSoldiers(s.data);
    });
  }, []);

  const sumByCat = {}, sumByType = { штатний: 0, позаштатний: 0 };
  equipment.forEach(e => {
    sumByCat[e.category] = (sumByCat[e.category] || 0) + (e.qty || 1);
    sumByType[e.type] = (sumByType[e.type] || 0) + (e.qty || 1);
  });
  const total = sumByType.штатний + sumByType.позаштатний;

  const ammoTotal = ammo.reduce((a, b) => a + (b.qty || 0), 0);

  return (
    <div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <Stat value={structure.total_personnel} label="Особовий склад БЧС" color="#A4C26A" />
        <Stat value={soldiers.length} label="Карток ОС" color="#7AB8D8" />
        <Stat value={total} label="Засобів усього" color="#D8C36A" />
        <Stat value={ammoTotal.toLocaleString("uk")} label="БК (од.)" color="#D4A06A" />
        <Stat value={sumByType.штатний} label="Штатних засобів" color="#A4C26A" />
        <Stat value={sumByType.позаштатний} label="Позаштатних" color="#D4A06A" />
        <Stat value={interactions.length} label="Каналів зв'язку" color="#B8A0D6" />
        <Stat value={Object.keys(sumByCat).length} label="Категорій засобів" color="#7AB8D8" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <Card title="ЗАСОБИ ЗА КАТЕГОРІЯМИ" data={sumByCat} totalValue={total} accent="#A4C26A" />
        <Card title="БК ЗА ЗБРОЄЮ" data={ammo.reduce((m, a) => { m[a.weapon] = (m[a.weapon] || 0) + a.qty; return m; }, {})} totalValue={ammoTotal} accent="#7AB8D8" />
      </div>
    </div>
  );
}

function Card({ title, data, totalValue, accent }) {
  const sorted = Object.entries(data).sort((a, b) => b[1] - a[1]);
  return (
    <div className="bg-mil border border-mil rounded-lg p-5">
      <h3 className="font-bold tracking-wide mb-4" style={{ color: accent }}>{title}</h3>
      {sorted.length === 0 && <div className="text-sm" style={{ color: "#7A8B6C" }}>Поки немає даних</div>}
      {sorted.map(([k, v]) => (
        <div key={k} className="mb-3 last:mb-0">
          <div className="flex justify-between text-sm mb-1">
            <span className="truncate pr-2">{k}</span>
            <span className="font-bold" style={{ color: accent, fontFamily: "JetBrains Mono" }}>{v.toLocaleString("uk")}</span>
          </div>
          <div className="h-2 bg-mil-deep rounded overflow-hidden">
            <div className="h-full" style={{ width: `${totalValue ? (v / totalValue) * 100 : 0}%`,
                                              background: `linear-gradient(90deg, ${accent}40, ${accent})` }}></div>
          </div>
        </div>
      ))}
    </div>
  );
}


function Gate() {
  const { user } = useAuth();
  if (user === undefined) {
    return <div className="min-h-screen bg-grid flex items-center justify-center"><div className="text-accent">Перевірка авторизації…</div></div>;
  }
  if (!user) return <Login />;
  return <AppShell />;
}

export default function App() {
  return (
    <AuthProvider>
      <Gate />
    </AuthProvider>
  );
}
