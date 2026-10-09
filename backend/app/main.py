"""API de 67downloader.

Rutas:
  POST /api/info       -> datos del video (sin descargar)
  GET  /api/download   -> descarga el archivo
  /                    -> sirve el frontend
"""
import shutil
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .downloader import DownloadError, download, get_info
from .platforms import detect_platform

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"

app = FastAPI(title="67downloader")


class InfoRequest(BaseModel):
    url: str


def _require_platform(url: str) -> str:
    platform = detect_platform(url)
    if not platform:
        raise HTTPException(
            status_code=400,
            detail="Ese link no es de TikTok, Instagram, X, Facebook o YouTube.",
        )
    return platform


@app.get("/api/health")
def health():
    return {"ok": True}


@app.post("/api/info")
async def info(body: InfoRequest):
    platform = _require_platform(body.url)
    try:
        # yt-dlp es bloqueante, así que lo corremos en un hilo aparte
        data = await run_in_threadpool(get_info, body.url)
    except DownloadError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return data | {"platform": platform}


@app.get("/api/download")
async def download_file(
    background: BackgroundTasks,
    url: str = Query(...),
    format: str = Query("hd"),
):
    _require_platform(url)
    try:
        file_path, tmp_dir = await run_in_threadpool(download, url, format)
    except DownloadError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # Borrar la carpeta temporal cuando ya se mandó el archivo
    background.add_task(shutil.rmtree, tmp_dir, ignore_errors=True)
    return FileResponse(file_path, filename=file_path.name)


# El frontend se monta al final para que no tape las rutas de /api
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
