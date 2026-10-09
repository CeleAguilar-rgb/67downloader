"""API de 67downloader."""
import base64
import os
import secrets
import shutil
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware

from .downloader import DownloadError, download, get_info
from .platforms import detect_platform

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"

# Si se definen APP_USER y APP_PASS, toda la app pide basic auth.
# Sin esas variables (como en desarrollo local) queda abierta.
APP_USER = os.getenv("APP_USER")
APP_PASS = os.getenv("APP_PASS")


class BasicAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        auth = request.headers.get("authorization", "")
        if auth.startswith("Basic "):
            try:
                user, pw = base64.b64decode(auth[6:]).decode().split(":", 1)
            except Exception:
                user, pw = "", ""
            if secrets.compare_digest(user, APP_USER) and secrets.compare_digest(pw, APP_PASS):
                return await call_next(request)
        return Response(status_code=401, headers={"WWW-Authenticate": 'Basic realm="67downloader"'})


app = FastAPI(title="67downloader")
if APP_USER and APP_PASS:
    app.add_middleware(BasicAuthMiddleware)


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
        # yt-dlp bloquea, por eso corre en un hilo aparte
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

    # Borra la carpeta temporal tras enviar el archivo
    background.add_task(shutil.rmtree, tmp_dir, ignore_errors=True)
    return FileResponse(file_path, filename=file_path.name)


# Va al final para no tapar las rutas de /api
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
