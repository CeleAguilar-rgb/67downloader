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
const hint = $("hint");
const dropzone = $("dropzone");
const chips = $("platforms");
const loading = $("loading");
const result = $("result");

let currentPlatform = null;

function updateDetection() {
  const value = input.value;
  const platform = detectPlatform(value);
  currentPlatform = platform;

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
    goBtn.disabled = false;
  } else {
    dropzone.classList.remove("has-platform");
    goBtn.disabled = true;
    hint.textContent = platform === "unknown"
      ? "Ese link no es de TikTok, Instagram, X, Facebook o YouTube."
      : "Pega el link completo, empezando con https://";
    if (platform === "unknown") hint.classList.add("error");
  }
}

async function handleDownload() {
  if (!currentPlatform || currentPlatform === "unknown") return;
  result.hidden = true;
  loading.hidden = false;
  goBtn.disabled = true;

  try {
    const info = await fetchVideoInfo(input.value.trim());
    renderResult(info);
  } catch (err) {
    hint.textContent = err.message || "No se pudo obtener el video. Revisa que el link sea público e inténtalo otra vez.";
    hint.classList.add("error");
  } finally {
    loading.hidden = true;
    goBtn.disabled = false;
  }
}

function renderResult(info) {
  const p = PLATFORMS[info.platform];
  result.style.setProperty("--platform-color", p.color);
  const thumb = $("thumb");
  thumb.textContent = p.name;
  if (info.thumbnail) {
    const img = document.createElement("img");
    img.src = info.thumbnail;
    img.alt = "";
    img.referrerPolicy = "no-referrer";
    // Si la red bloquea la miniatura, se queda el bloque de color
    img.onload = () => { thumb.textContent = ""; thumb.appendChild(img); };
  }
  $("r-title").textContent = info.title;
  $("r-meta").textContent = [info.author, info.duration].filter(Boolean).join(", ");

  const options = $("r-options");
  options.innerHTML = "";
  info.formats.forEach(f => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "option" + (f.primary ? " primary" : "");
    btn.innerHTML = `<span><strong>${f.label}</strong><span class="sub">${f.sub}</span></span><span class="size">↓</span>`;
    btn.addEventListener("click", () => {
      // Un link normal hace que el navegador baje el archivo solito
      const a = document.createElement("a");
      a.href = downloadUrl(input.value.trim(), f.id);
      a.download = "";
      document.body.appendChild(a);
      a.click();
      a.remove();
      showToast(`Preparando ${f.label.toLowerCase()}… puede tardar unos segundos`);
    });
    options.appendChild(btn);
  });

  result.hidden = false;
  result.scrollIntoView({ behavior: "smooth", block: "start" });
}

let toastTimer;
function showToast(msg) {
  const t = $("toast");
  t.textContent = msg;
  t.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove("show"), 2200);
}

input.addEventListener("input", updateDetection);
input.addEventListener("keydown", e => {
  if (e.key === "Enter" && !goBtn.disabled) handleDownload();
});
goBtn.addEventListener("click", handleDownload);

$("paste").addEventListener("click", async () => {
  try {
    const text = await navigator.clipboard.readText();
    input.value = text;
    updateDetection();
    input.focus();
  } catch {
    hint.textContent = "Tu navegador no dejó leer el portapapeles. Pega el link con Ctrl+V.";
    hint.classList.add("error");
    input.focus();
  }
});
