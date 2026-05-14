import { useEffect, useState } from "react";
import { useAuth } from "../AuthContext";

export default function FilePreviewModal({ fileId, filename, mime, onClose }) {
  const { token } = useAuth();
  const [url, setUrl] = useState("");
  const [err, setErr] = useState("");

  useEffect(() => {
    if (!fileId) return;
    let active = true; let objUrl = "";
    (async () => {
      try {
        const res = await fetch(
          `${process.env.REACT_APP_BACKEND_URL}/api/documents/${fileId}?inline=1`,
          { headers: { Authorization: `Bearer ${token}` } }
        );
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const blob = await res.blob();
        objUrl = URL.createObjectURL(blob);
        if (active) setUrl(objUrl);
      } catch (e) { if (active) setErr(e.message); }
    })();
    return () => { active = false; if (objUrl) URL.revokeObjectURL(objUrl); };
  }, [fileId, token]);

  const isPdf = (mime || "").includes("pdf") || (filename || "").toLowerCase().endsWith(".pdf");
  const isImage = (mime || "").startsWith("image/") ||
                  /\.(png|jpe?g|webp|gif|heic|heif)$/i.test(filename || "");

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4"
         style={{ background: "rgba(14,26,20,.92)", backdropFilter: "blur(8px)" }}
         onClick={onClose}>
      <div className="bg-mil border border-mil rounded-lg w-full max-w-5xl max-h-[95vh] flex flex-col"
           onClick={(e) => e.stopPropagation()}>
        <div className="flex justify-between items-center p-4 border-b border-mil">
          <div className="min-w-0">
            <div className="text-xs uppercase" style={{ color: "#7A8B6C" }}>Перегляд документа</div>
            <h3 className="text-lg font-bold text-accent truncate">{filename}</h3>
          </div>
          <div className="flex gap-2 ml-3">
            <a className="btn-mil text-xs" href={url} download={filename} target="_blank" rel="noreferrer">⬇ Завантажити</a>
            <button className="btn-mil text-xs" onClick={onClose}>✕</button>
          </div>
        </div>
        <div className="flex-1 overflow-auto bg-black" style={{ minHeight: "60vh" }}>
          {err ? (
            <div className="text-center py-10" style={{ color: "#E89090" }}>Помилка: {err}</div>
          ) : !url ? (
            <div className="text-center py-10" style={{ color: "#7A8B6C" }}>Завантаження…</div>
          ) : isPdf ? (
            <iframe src={url} title={filename} className="w-full h-full" style={{ minHeight: "70vh", border: 0 }} />
          ) : isImage ? (
            <div className="flex items-center justify-center p-4">
              <img src={url} alt={filename} style={{ maxWidth: "100%", maxHeight: "80vh" }} />
            </div>
          ) : (
            <div className="text-center py-10" style={{ color: "#D4A06A" }}>
              <div className="text-5xl mb-3">📄</div>
              <div>Цей тип файла не може бути показаний у браузері.</div>
              <a className="btn-mil btn-mil-primary mt-3 inline-block" href={url} download={filename}>
                ⬇ Завантажити «{filename}»
              </a>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
