# Estado del proyecto (11 nov 2026)

Resumen rápido para retomar el trabajo en otra compu. Para la descripción general y cómo correrlo, ver [README.md](README.md).

## Qué hace hoy

Pegas un link de TikTok, Instagram, X, Facebook o YouTube y baja el video. Opciones que ofrece la API (`/api/info`):

| id | Nombre | Resultado |
|---|---|---|
| `hd` | Video HD | `.mp4` (H.264 + AAC cuando existe), sin marca de agua en TikTok |
| `sd` | Video ligero | `.mp4`, hasta 480p |
| `mp3` | Audio MP3 | `.mp3` a 192 kbps (solo aparece si hay ffmpeg) |
| `audio` | Audio M4A | `.m4a` sin convertir |

Lo último que se cambió ([backend/app/downloader.py](backend/app/downloader.py)):
- Antes, si la red no daba mp4, el archivo salía en webm/mkv. Ahora el selector prefiere mp4 y, si no hay, ffmpeg lo convierte a `.mp4` al final (`FFmpegVideoConvertor`).
- Se agregó MP3 con `FFmpegExtractAudio`. Sin ffmpeg esa opción se oculta.
- Algunos videos (Instagram sobre todo) venían en `.mp4` pero con VP9 adentro, y Premiere/CapCut los rechazaban. Ahora, al terminar, se revisa el codec con ffprobe y si no es H.264 + AAC se recodifica (`_ensure_h264`). Los selectores también prefieren `avc1` primero para no tener que recodificar.
- Probado con un video de YouTube: HD salió `.mp4` (h264+aac) y MP3 salió `.mp3` válido. **No se ha probado con TikTok, Instagram, X ni Facebook.**

## Para correrlo en la otra compu

```bash
git clone https://github.com/CeleAguilar-rgb/67downloader.git
cd 67downloader/backend
python -m venv .venv
.venv\Scripts\activate          # Windows (Mac/Linux: source .venv/bin/activate)
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8067
```

Abrir http://localhost:8067. Necesita **ffmpeg** en el PATH (en Windows: `winget install Gyan.FFmpeg`, y reabrir la terminal). Sin ffmpeg no hay MP3 ni conversión a MP4.

Si algo deja de descargar, casi siempre se arregla con `pip install -U yt-dlp`.

## Despliegue (Render, plan gratis)

- URL: https://six7downloader.onrender.com
- Servicio web con Docker, plan **Free**, creado desde el repo público de GitHub (rama `main`). ID del servicio: `srv-dbqf848n74is73c0ve0g`.
- Usa el [Dockerfile](Dockerfile) tal cual (ya instala ffmpeg). El puerto lo toma de la variable `PORT` que pone Render.
- Variables de entorno en Render: `APP_USER` y `APP_PASS` activan el Basic Auth de toda la app. **Los valores no están en el repo**; se ven y se cambian en Render → servicio → Environment. Si faltan, la app queda abierta a cualquiera.
- Para actualizar: commit + push a `main` y, si no se redespliega solo, "Manual Deploy" en el panel de Render.
- El plan gratis se duerme tras 15 min sin visitas; la primera visita después tarda cerca de un minuto.

## App instalable (PWA)

La página se puede instalar como app desde el navegador (Chrome/Edge: ícono de instalar en la barra o botón "Instalar app" al pie; Android: menú → Instalar app). Archivos en `frontend/`: `manifest.webmanifest`, `sw.js` (service worker; nunca toca `/api`) e `icons/`. El `<link rel="manifest">` lleva `crossorigin="use-credentials"` porque, con Basic Auth, si no el navegador pide el manifest sin contraseña y falla. Si cambias `style.css` o `app.js`, sube el `?v=` en `index.html` **y** en `SHELL` de `sw.js`.
**Sin probar todavía en un navegador real**: solo se comprobó que el servidor sirve todos esos archivos.

## Versión de escritorio (.exe): no funciona en esta compu

- `backend/desktop.py` levanta el servidor en 127.0.0.1:8067 y abre una ventana de Edge/Chrome en modo app. **Con Python sí funciona** (`python desktop.py` desde `backend/`).
- `backend/build_desktop.py` lo empaqueta con PyInstaller (carpeta de ~490 MB con ffmpeg dentro; `pip install -r requirements-desktop.txt`). Compila bien, pero **Windows (Smart App Control) bloquea el .exe por no estar firmado**, así que no se pudo probar ya empaquetado. Solo funcionaría con una firma digital de pago o apagando Smart App Control (no recomendado).
- La carpeta `backend/dist/` y `backend/build/` están en `.gitignore`; se pueden borrar.

## Cosas descartadas

- **Vercel:** no sirve para este backend (sin ffmpeg, límites de tiempo y de tamaño de respuesta).
- **Hugging Face Spaces:** los Spaces Docker ahora requieren plan PRO de pago.

## Pendiente

- [ ] Probar descargas reales de TikTok, Instagram, X y Facebook en la URL de Render (y MP4/MP3 desde el navegador).
- [ ] Revisar si YouTube/TikTok bloquean la IP de Render; si pasa, hay que revisar el mensaje de error y valorar cookies (`COOKIES_FILE`) u otro host.
- [ ] Confirmar si Render redespliega solo al hacer push.
- [ ] Probar la instalación de la PWA en la URL de Render (PC y celular).
- [ ] Historial de descargas recientes (idea del README original).
