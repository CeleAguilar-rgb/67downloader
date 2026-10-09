# 67downloader

Una sola página para bajar videos de TikTok (sin marca de agua), Instagram, X/Twitter, Facebook y YouTube. Pegas el link y listo.

## Cómo está armado

```
67downloader/
├── frontend/
│   └── index.html        ← la página (HTML + CSS + JS, con el gato 67)
└── backend/
    ├── requirements.txt
    └── app/
        ├── main.py       ← rutas de la API y sirve el frontend
        ├── downloader.py ← todo lo que habla con yt-dlp
        └── platforms.py  ← detecta de qué red es un link
```

Flujo: la página manda el link a `POST /api/info` → el backend usa yt-dlp para sacar título, miniatura y opciones → al elegir una opción, el navegador abre `GET /api/download?url=...&format=hd|sd|audio` y el backend manda el archivo.

## Correrlo en tu compu

Necesitas Python 3.10 o más nuevo y, de preferencia, **ffmpeg** (sin él YouTube solo da calidades bajas).

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
# Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8067
```

Abre http://localhost:8067 y pega un link.

## Cuando algo deje de funcionar

Las redes cambian seguido y rompen los descargadores. Casi siempre se arregla con:

```bash
pip install -U yt-dlp
```

## Instagram

Si Instagram pide iniciar sesión, exporta las cookies de una cuenta **secundaria** a un archivo `cookies.txt` (hay extensiones de navegador para eso) y arranca así:

```bash
COOKIES_FILE=cookies.txt uvicorn app.main:app --port 8067
```

`cookies.txt` está en el `.gitignore` para que nunca se suba al repo.

## Pendientes

- [ ] Probar con links reales de cada red
- [ ] Desplegarlo (Railway, Render o un VPS)
- [ ] Historial de descargas recientes
