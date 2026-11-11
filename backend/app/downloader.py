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

# "kind" decide el post-proceso: "video" termina siempre en .mp4,
# "mp3" extrae el audio y lo convierte, "m4a" deja el audio tal cual.
FORMATS = {
    "hd": {
        "label": "Video HD",
        "sub": "MP4, sin marca de agua",
        "kind": "video",
        # Prefiere H.264 + AAC (reproduce en todos lados); si no hay, baja
        # lo que haya y ffmpeg lo convierte a MP4 al final.
        "selector": (
            f"bv*{NO_WATERMARK}[vcodec^=avc1][ext=mp4]+ba[ext=m4a]"
            f"/bv*{NO_WATERMARK}[ext=mp4]+ba[ext=m4a]"
            f"/b{NO_WATERMARK}[ext=mp4]"
            f"/bv*{NO_WATERMARK}+ba"
            f"/b{NO_WATERMARK}/b"
            if HAS_FFMPEG
            else f"b{NO_WATERMARK}[ext=mp4]/b{NO_WATERMARK}/b"
        ),
        "primary": True,
    },
    "sd": {
        "label": "Video ligero",
        "sub": "MP4, menor calidad",
        "kind": "video",
        "selector": (
            f"b{NO_WATERMARK}[height<=480][ext=mp4]"
            f"/wv*{NO_WATERMARK}[ext=mp4]+wa"
            f"/w{NO_WATERMARK}/w"
            if HAS_FFMPEG
            else f"b{NO_WATERMARK}[height<=480][ext=mp4]/w{NO_WATERMARK}[ext=mp4]/w{NO_WATERMARK}/w"
        ),
    },
    "mp3": {
        "label": "Audio MP3",
        "sub": "Solo el sonido, 192 kbps",
        "kind": "mp3",
        "selector": "ba/b",
        "needs_ffmpeg": True,
    },
    "audio": {
        "label": "Audio M4A",
        "sub": "Solo el sonido, sin convertir",
        "kind": "m4a",
        "selector": "ba[ext=m4a]/ba",
    },
}


def _available_formats() -> dict:
    return {k: f for k, f in FORMATS.items() if HAS_FFMPEG or not f.get("needs_ffmpeg")}


def _output_ext(kind: str) -> str | None:
    return {"video": ".mp4", "mp3": ".mp3"}.get(kind)


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
            for key, f in _available_formats().items()
        ],
    }


def download(url: str, format_id: str) -> tuple[Path, Path]:
    """Descarga a una carpeta temporal. Regresa (archivo, carpeta)."""
    fmt = _available_formats().get(format_id)
    if not fmt:
        raise DownloadError("Ese formato no existe.")

    tmp_dir = Path(tempfile.mkdtemp(prefix="67dl-"))
    opts = _base_opts() | {
        "format": fmt["selector"],
        "outtmpl": str(tmp_dir / "%(title).80s.%(ext)s"),
    }
    if fmt["kind"] == "video" and HAS_FFMPEG:
        opts["merge_output_format"] = "mp4"
        # Si lo que bajó no es mp4 (webm, mkv...), lo convierte; si ya es
        # mp4 no hace nada.
        opts["postprocessors"] = [{"key": "FFmpegVideoConvertor", "preferedformat": "mp4"}]
    elif fmt["kind"] == "mp3":
        opts["postprocessors"] = [
            {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}
        ]

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
    # Si hay varios archivos, se queda con el que tiene la extensión pedida
    ext = _output_ext(fmt["kind"])
    if ext:
        files.sort(key=lambda p: p.suffix.lower() != ext)
    return files[0], tmp_dir
