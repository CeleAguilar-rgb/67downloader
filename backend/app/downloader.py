"""Todo lo que habla con yt-dlp vive aquí."""
import os
import shutil
import tempfile
from pathlib import Path

import yt_dlp

HAS_FFMPEG = shutil.which("ffmpeg") is not None

# Cookies opcionales para contenido logueado. Ruta en COOKIES_FILE.
COOKIES_FILE = os.getenv("COOKIES_FILE")

# TikTok marca con "download" el id de su copia con marca de agua.
NO_WATERMARK = "[format_id!*=download]"

FORMATS = {
    "hd": {
        "label": "Video HD",
        "sub": "MP4, sin marca de agua",
        "selector": (
            f"bv*{NO_WATERMARK}[ext=mp4]+ba[ext=m4a]/b{NO_WATERMARK}[ext=mp4]/b{NO_WATERMARK}/b"
            if HAS_FFMPEG
            else f"b{NO_WATERMARK}[ext=mp4]/b{NO_WATERMARK}/b"
        ),
        "primary": True,
    },
    "sd": {
        "label": "Video ligero",
        "sub": "MP4, menor calidad",
        "selector": (
            f"b{NO_WATERMARK}[height<=480][ext=mp4]/wv*{NO_WATERMARK}[ext=mp4]+wa/w{NO_WATERMARK}/w"
            if HAS_FFMPEG
            else f"b{NO_WATERMARK}[height<=480]/w{NO_WATERMARK}/w"
        ),
    },
    "audio": {
        "label": "Solo audio",
        "sub": "M4A",
        "selector": "ba[ext=m4a]/ba",
    },
}


class DownloadError(Exception):
    """Error con mensaje que sí se le puede enseñar al usuario."""


def _base_opts() -> dict:
    opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "socket_timeout": 20,
    }
    if COOKIES_FILE:
        opts["cookiefile"] = COOKIES_FILE
    return opts


def _format_duration(seconds) -> str:
    if not seconds:
        return ""
    seconds = int(seconds)
    return f"{seconds // 60}:{seconds % 60:02d}"


def get_info(url: str) -> dict:
    """Saca título, autor, miniatura y opciones sin descargar nada."""
    try:
        with yt_dlp.YoutubeDL(_base_opts()) as ydl:
            info = ydl.extract_info(url, download=False)
    except yt_dlp.utils.DownloadError as e:
        raise DownloadError(
            "No se pudo leer ese video. Revisa que sea público o inténtalo en un rato."
        ) from e

    return {
        "title": info.get("title") or "Video sin título",
        "author": info.get("uploader") or info.get("channel") or "",
        "duration": _format_duration(info.get("duration")),
        "thumbnail": info.get("thumbnail"),
        "formats": [
            {"id": key, "label": f["label"], "sub": f["sub"], "primary": f.get("primary", False)}
            for key, f in FORMATS.items()
        ],
    }


def download(url: str, format_id: str) -> tuple[Path, Path]:
    """Descarga a una carpeta temporal. Regresa (archivo, carpeta)."""
    if format_id not in FORMATS:
        raise DownloadError("Ese formato no existe.")

    tmp_dir = Path(tempfile.mkdtemp(prefix="67dl-"))
    opts = _base_opts() | {
        "format": FORMATS[format_id]["selector"],
        "outtmpl": str(tmp_dir / "%(title).80s.%(ext)s"),
    }
    if HAS_FFMPEG and format_id != "audio":
        opts["merge_output_format"] = "mp4"

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
    except yt_dlp.utils.DownloadError as e:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise DownloadError("La descarga falló. Inténtalo otra vez en un ratito.") from e

    files = [p for p in tmp_dir.iterdir() if p.is_file()]
    if not files:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise DownloadError("No se generó ningún archivo.")
    return files[0], tmp_dir
