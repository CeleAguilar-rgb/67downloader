"""API de 67downloader."""
import base64
import os
import secrets
import shutil
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware

from .downloader import DownloadError, download, get_info
from .platforms import detect_platform

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"

limiter = Limiter(key_func=get_remote_address)

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
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
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


def _require_same_site(request: Request) -> None:
    # Con Basic Auth el navegador reenvía las credenciales a cualquier sitio
    # que las pida, así que un <img>/<iframe> de otra página podría disparar
    # una descarga a nombre del usuario. Lo bloqueamos si el fetch viene
    # marcado como cross-site (los navegadores viejos que no manden este
    # header simplemente no quedan cubiertos por esta capa extra).
    if APP_USER and APP_PASS and request.headers.get("sec-fetch-site") == "cross-site":
        raise HTTPException(status_code=403, detail="Solicitud bloqueada por seguridad.")


@app.get("/api/health")
def health():
    return {"ok": True}


@app.post("/api/info")
@limiter.limit("30/minute")
async def info(request: Request, body: InfoRequest):
    platform = _require_platform(body.url)
    try:
        # yt-dlp bloquea, por eso corre en un hilo aparte
        data = await run_in_threadpool(get_info, body.url)
    except DownloadError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return data | {"platform": platform}


@app.get("/api/download")
@limiter.limit("10/minute")
async def download_file(
    request: Request,
    background: BackgroundTasks,
    url: str = Query(...),
    format: str = Query("hd"),
):
    _require_same_site(request)
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
