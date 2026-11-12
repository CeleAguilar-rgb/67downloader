/* =========================================================
   1. Detección de plataforma
   Cada plataforma tiene un patrón para reconocer sus links.
   ========================================================= */
const PLATFORMS = {
  tiktok: {
    name: "TikTok",
    color: "#FF2D6F",
    pattern: /(^|\.)tiktok\.com\//i
  },
  instagram: {
    name: "Instagram",
    color: "#C13584",
    pattern: /(^|\.)instagram\.com\/(p|reel|reels|tv)\//i
  },
  twitter: {
    name: "X / Twitter",
    color: "#3D5AFE",
    pattern: /(^|\.)(twitter|x)\.com\/.+\/status\/\d+/i
  },
  facebook: {
    name: "Facebook",
    color: "#1F6FEB",
    pattern: /((^|\.)facebook\.com\/|(^|\.)fb\.watch\/)/i
  },
  youtube: {
    name: "YouTube",
    color: "#E62117",
    // Videos normales, Shorts, directos y links cortos de youtu.be
    pattern: /((^|\.)youtube\.com\/(watch|shorts\/|live\/)|(^|\.)youtu\.be\/)/i
  }
};

function detectPlatform(text) {
  let url;
  try {
    url = new URL(text.trim());
  } catch {
    return null; // No es un link válido todavía
  }
  const target = url.hostname + url.pathname;
  for (const [key, p] of Object.entries(PLATFORMS)) {
    if (p.pattern.test(target)) return key;
  }
  return "unknown";
}

/* =========================================================
   2. Conexión con el backend
   ========================================================= */
async function fetchVideoInfo(url) {
  const res = await fetch("/api/info", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url })
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    // El backend manda el mensaje de error en "detail"
    throw new Error(data.detail || "No se pudo obtener el video.");
  }
  return data;
}

function downloadUrl(url, formatId) {
  const params = new URLSearchParams({ url, format: formatId });
  return `/api/download?${params}`;
}

/* =========================================================
   3. Interfaz
   ========================================================= */
const $ = id => document.getElementById(id);
const input = $("url");
const goBtn = $("go");
const clearBtn = $("clear");
const hint = $("hint");
const dropzone = $("dropzone");
const chips = $("platforms");
const loading = $("loading");
const result = $("result");
const resultError = $("r-error");

const ICON_DOWNLOAD = '<svg viewBox="0 0 20 20" aria-hidden="true"><path d="M10 3v10m0 0l-4-4m4 4l4-4M4 16h12" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>';
const ICON_DONE = '<svg viewBox="0 0 20 20" aria-hidden="true"><path d="M4 10.5l4 4 8-9" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg>';

let currentPlatform = null;
let searching = false;

function updateDetection() {
  const value = input.value;
  const platform = detectPlatform(value);
  currentPlatform = platform;
  clearBtn.hidden = !value;

  chips.classList.toggle("idle", !value.trim());
  chips.querySelectorAll("li").forEach(li => {
    li.classList.toggle("active", li.dataset.p === platform);
  });

  hint.classList.remove("error");
  if (!value.trim()) {
    hint.textContent = "";
    dropzone.classList.remove("has-platform");
    goBtn.disabled = true;
    return;
  }

  if (platform && platform !== "unknown") {
    const p = PLATFORMS[platform];
    dropzone.style.setProperty("--platform-color", p.color);
    dropzone.classList.add("has-platform");
    hint.textContent = `Link de ${p.name} detectado.`;
    goBtn.disabled = searching;
  } else {
    dropzone.classList.remove("has-platform");
    goBtn.disabled = true;
    hint.textContent = platform === "unknown"
      ? "Ese link no es de TikTok, Instagram, X, Facebook o YouTube."
      : "Pega el link completo, empezando con https://";
    if (platform === "unknown") hint.classList.add("error");
  }
}

async function handleSearch() {
  if (searching || !currentPlatform || currentPlatform === "unknown") return;
  searching = true;
  result.hidden = true;
  loading.hidden = false;
  goBtn.disabled = true;
  goBtn.classList.add("busy");
  goBtn.textContent = "Buscando…";
  input.blur(); // en el celular cierra el teclado para que se vea el resultado

  let found = false;
  try {
    const info = await fetchVideoInfo(input.value.trim());
    renderResult(info);
    found = true;
  } catch (err) {
    hint.textContent = err.message || "No se pudo obtener el video. Revisa que el link sea público e inténtalo otra vez.";
    hint.classList.add("error");
  } finally {
    searching = false;
    loading.hidden = true;
    goBtn.classList.remove("busy");
    goBtn.textContent = "Buscar video";
    goBtn.disabled = false;
  }
  if (found) result.scrollIntoView({ behavior: "smooth", block: "start" });
}

function renderResult(info) {
  const p = PLATFORMS[info.platform];
  result.style.setProperty("--platform-color", p.color);
  const thumb = $("thumb");
  thumb.textContent = "";
  thumb.style.removeProperty("--ar");
  if (info.thumbnail) {
    const img = document.createElement("img");
    img.alt = "";
    img.referrerPolicy = "no-referrer";
    // La miniatura toma la forma real del video (vertical u horizontal).
    // Si la red la bloquea, se queda el bloque de color.
    img.onload = () => {
      if (img.naturalWidth && img.naturalHeight) {
        thumb.style.setProperty("--ar", `${img.naturalWidth} / ${img.naturalHeight}`);
      }
      thumb.appendChild(img);
    };
    img.src = info.thumbnail;
  }
  $("r-title").textContent = info.title;
  $("r-meta").textContent = [p.name, info.author, info.duration].filter(Boolean).join(", ");
  resultError.hidden = true;

  const options = $("r-options");
  options.innerHTML = "";
  const videoUrl = input.value.trim();
  info.formats.forEach(f => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "option" + (f.primary ? " primary" : "");
    btn.innerHTML = `<span><span class="option-title"><strong></strong><span class="size"></span></span><span class="sub"></span></span><span class="state">${ICON_DOWNLOAD}</span>`;
    btn.querySelector("strong").textContent = f.label;
    btn.querySelector(".size").textContent = formatSize(f.size, f.approx);
    btn.querySelector(".sub").textContent = f.sub;
    btn.addEventListener("click", () => startDownload(btn, f, videoUrl, info));
    options.appendChild(btn);
  });

  result.hidden = false;
}

/* Descarga con fetch para poder mostrar "preparando", el porcentaje
   y los errores en la misma página (con un link normal fallaba en silencio). */
async function startDownload(btn, format, videoUrl, info) {
  if (btn.classList.contains("busy")) return;
  const sub = btn.querySelector(".sub");
  const state = btn.querySelector(".state");
  const setState = (cls, html) => {
    btn.classList.remove("busy", "done");
    if (cls) btn.classList.add(cls);
    state.classList.remove("pct");
    state.innerHTML = html;
  };

  resultError.hidden = true;
  btn.disabled = true;
  btn.setAttribute("aria-busy", "true");
  setState("busy", "");
  sub.textContent = "Preparando, puede tardar…";

  try {
    const res = await fetch(downloadUrl(videoUrl, format.id));
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      if (res.status === 429) throw new Error("Hiciste muchas descargas seguidas. Espera un minuto y vuelve a intentarlo.");
      throw new Error(data.detail || "La descarga falló. Inténtalo otra vez en un ratito.");
    }

    const total = Number(res.headers.get("content-length")) || 0;
    let blob;
    if (res.body && total) {
      const reader = res.body.getReader();
      const chunks = [];
      let received = 0;
      sub.textContent = "Descargando…";
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        chunks.push(value);
        received += value.length;
        state.classList.add("pct");
        state.textContent = `${Math.min(99, Math.floor((received / total) * 100))}%`;
      }
      blob = new Blob(chunks, { type: res.headers.get("content-type") || "" });
    } else {
      blob = await res.blob();
    }

    const fallback = format.id === "mp3" ? "audio.mp3" : format.id === "audio" ? "audio.m4a" : "video.mp4";
    saveBlob(blob, filenameFrom(res) || fallback);
    setState("done", ICON_DONE);
    sub.textContent = "Listo, revisa tus descargas";
    showToast(`${format.label} descargado`);
    addToHistory({
      url: videoUrl,
      title: info.title,
      platform: info.platform,
      thumbnail: info.thumbnail || "",
      format: format.label,
      at: Date.now()
    });
  } catch (err) {
    setState("", ICON_DOWNLOAD);
    sub.textContent = format.sub;
    resultError.textContent = err.message || "La descarga falló. Inténtalo otra vez en un ratito.";
    resultError.hidden = false;
  } finally {
    btn.disabled = false;
    btn.removeAttribute("aria-busy");
  }
}

function formatSize(bytes, approx) {
  if (!bytes) return "";
  const mb = bytes / 1_000_000;
  const text = mb >= 10 ? `${Math.round(mb)} MB`
    : mb >= 1 ? `${mb.toFixed(1)} MB`
    : `${Math.max(1, Math.round(bytes / 1000))} KB`;
  return approx ? `≈ ${text}` : text;
}

/* =========================================================
   4. Historial
   Solo vive en este navegador (localStorage); nada se manda al servidor.
   ========================================================= */
const HISTORY_KEY = "67dl-history";
const HISTORY_MAX = 12;
const historyBox = $("history");
const historyList = $("history-list");

function readHistory() {
  try {
    const list = JSON.parse(localStorage.getItem(HISTORY_KEY) || "[]");
    return Array.isArray(list) ? list.filter(h => h && h.url && PLATFORMS[h.platform]) : [];
  } catch {
    return [];
  }
}

function writeHistory(list) {
  try {
    localStorage.setItem(HISTORY_KEY, JSON.stringify(list));
  } catch { /* modo privado o almacenamiento lleno: el historial es opcional */ }
}

function addToHistory(entry) {
  // El mismo video sube al principio en lugar de repetirse
  const list = [entry, ...readHistory().filter(h => h.url !== entry.url)].slice(0, HISTORY_MAX);
  writeHistory(list);
  renderHistory();
}

const relTime = new Intl.RelativeTimeFormat("es", { numeric: "auto" });
function timeAgo(ts) {
  const minutes = Math.round((Date.now() - ts) / 60000);
  if (minutes < 1) return "ahora";
  if (minutes < 60) return relTime.format(-minutes, "minute");
  const hours = Math.round(minutes / 60);
  if (hours < 24) return relTime.format(-hours, "hour");
  const days = Math.round(hours / 24);
  if (days < 30) return relTime.format(-days, "day");
  return new Date(ts).toLocaleDateString("es");
}

function renderHistory() {
  const list = readHistory();
  historyBox.hidden = list.length === 0;
  historyList.innerHTML = "";
  list.forEach(h => {
    const p = PLATFORMS[h.platform];
    const li = document.createElement("li");
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "history-item";
    btn.style.setProperty("--c", p.color);
    btn.innerHTML = `<span class="history-thumb"></span><span class="history-text"><span class="history-title"></span><span class="history-meta"></span></span>`;
    btn.querySelector(".history-title").textContent = h.title || "Video sin título";
    btn.querySelector(".history-meta").textContent = `${p.name}, ${h.format}, ${timeAgo(h.at)}`;
    if (h.thumbnail) {
      // Las miniaturas de algunas redes caducan; si falla queda el color
      const img = document.createElement("img");
      img.alt = "";
      img.loading = "lazy";
      img.referrerPolicy = "no-referrer";
      img.onload = () => btn.querySelector(".history-thumb").appendChild(img);
      img.src = h.thumbnail;
    }
    btn.setAttribute("aria-label", `Volver a abrir ${h.title || "el video"}`);
    btn.addEventListener("click", () => {
      input.value = h.url;
      updateDetection();
      window.scrollTo({ top: 0, behavior: "smooth" });
      handleSearch();
    });
    li.appendChild(btn);
    historyList.appendChild(li);
  });
}

$("history-clear").addEventListener("click", () => {
  writeHistory([]);
  renderHistory();
  showToast("Historial borrado");
});

renderHistory();

function filenameFrom(res) {
  const cd = res.headers.get("content-disposition") || "";
  const star = cd.match(/filename\*=utf-8''([^;]+)/i);
  if (star) {
    try { return decodeURIComponent(star[1]); } catch { /* sigue abajo */ }
  }
  const plain = cd.match(/filename="?([^";]+)"?/);
  return plain ? plain[1] : "";
}

function saveBlob(blob, name) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  // Se libera después para no cortar la descarga en navegadores lentos
  setTimeout(() => URL.revokeObjectURL(a.href), 60000);
}

let toastTimer;
function showToast(msg) {
  const t = $("toast");
  t.textContent = msg;
  t.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove("show"), 2600);
}

input.addEventListener("input", updateDetection);
input.addEventListener("keydown", e => {
  if (e.key === "Enter" && !goBtn.disabled) handleSearch();
});
goBtn.addEventListener("click", handleSearch);

clearBtn.addEventListener("click", () => {
  input.value = "";
  updateDetection();
  input.focus();
});

$("paste").addEventListener("click", async () => {
  try {
    const text = await navigator.clipboard.readText();
    input.value = text.trim();
    updateDetection();
    // Si el link es válido busca solo: un toque menos en el celular
    if (!goBtn.disabled) handleSearch();
    else input.focus();
  } catch {
    hint.textContent = "Tu navegador no dejó leer el portapapeles. Mantén presionado el campo y elige Pegar.";
    hint.classList.add("error");
    input.focus();
  }
});

/* =========================================================
   PWA: service worker y botón "Instalar app"
   ========================================================= */
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("sw.js").catch(() => {});
  });
}

let installPrompt = null;
const installBtn = document.getElementById("install");
window.addEventListener("beforeinstallprompt", e => {
  e.preventDefault();
  installPrompt = e;
  installBtn.hidden = false;
});
installBtn.addEventListener("click", async () => {
  if (!installPrompt) return;
  installPrompt.prompt();
  await installPrompt.userChoice;
  installPrompt = null;
  installBtn.hidden = true;
});
window.addEventListener("appinstalled", () => { installBtn.hidden = true; });
