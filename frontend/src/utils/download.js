/**
 * Універсальний хелпер скачування файлу з авторизованого endpoint.
 *
 * Працює навіть у обмежених iframe-середовищах (target="_blank" + delayed cleanup).
 *
 * @param {string} url        — повний URL до файлу
 * @param {string} filename   — імʼя файлу (fallback)
 * @param {string} token      — Bearer токен (опціонально)
 * @returns {Promise<{filename:string, size:number}>}
 */
export async function downloadAuthFile(url, filename, token) {
  const res = await fetch(url, {
    credentials: "omit",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  // Витягуємо filename з Content-Disposition якщо є
  const cd = res.headers.get("content-disposition") || "";
  const m = cd.match(/filename\*=UTF-8''([^;]+)/);
  if (m) {
    try { filename = decodeURIComponent(m[1]); } catch (_) {}
  } else {
    const m2 = cd.match(/filename="([^"]+)"/);
    if (m2) filename = m2[1];
  }
  const blob = await res.blob();
  const blobUrl = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = blobUrl;
  a.download = filename;
  a.rel = "noopener";
  a.target = "_blank";
  a.style.display = "none";
  document.body.appendChild(a);
  a.click();
  setTimeout(() => {
    try { a.remove(); URL.revokeObjectURL(blobUrl); } catch (_) {}
  }, 4000);
  return { filename, size: blob.size };
}
