"""Todo lo que habla con yt-dlp vive aquí."""
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import yt_dlp

FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")
HAS_FFMPEG = FFMPEG is not None and FFPROBE is not None

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
            f"/b{NO_WATERMARK}[vcodec^=avc1][ext=mp4]"
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
            f"b{NO_WATERMARK}[height<=480][vcodec^=avc1][ext=mp4]"
            f"/bv*{NO_WATERMARK}[height<=480][vcodec^=avc1]+ba[ext=m4a]"
            f"/b{NO_WATERMARK}[height<=480][ext=mp4]"
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
            formats = []
            for key, f in _available_formats().items():
                size, approx = _estimate_size(ydl, info, f)
                formats.append({
                    "id": key,
                    "label": f["label"],
                    "sub": f["sub"],
                    "primary": f.get("primary", False),
                    "size": size,
                    "approx": approx,
                })
    except yt_dlp.utils.DownloadError as e:
        raise DownloadError(
            "No se pudo leer ese video. Revisa que sea público o inténtalo en un rato."
        ) from e

    return {
        "title": info.get("title") or "Video sin título",
        "author": info.get("uploader") or info.get("channel") or "",
        "duration": _format_duration(info.get("duration")),
        "thumbnail": info.get("thumbnail"),
        "formats": formats,
    }


def _stream_size(f: dict, duration) -> tuple[int | None, bool]:
    """Peso de un formato de yt-dlp: exacto si lo da la red, si no estimado."""
    if f.get("filesize"):
        return int(f["filesize"]), False
    if f.get("filesize_approx"):
        return int(f["filesize_approx"]), True
    if f.get("tbr") and duration:
        return int(f["tbr"] * 1000 / 8 * duration), True
    return None, True


def _estimate_size(ydl, info: dict, fmt: dict) -> tuple[int | None, bool]:
    """Cuánto pesará el archivo de esta opción, sin descargar nada.

    Regresa (bytes, aproximado). bytes es None si no hay forma de saberlo.
    """
    duration = info.get("duration")
    if fmt["kind"] == "mp3":
        # Se convierte a 192 kbps, así que depende solo de la duración
        return (int(duration * 192_000 / 8), True) if duration else (None, True)

    try:
        # Usa el mismo selector que la descarga para escoger el formato real
        chosen = ydl._select_formats(info.get("formats") or [], ydl.build_format_selector(fmt["selector"]))
    except Exception:
        return None, True
    if not chosen:
        return None, True
    choice = chosen[0]

    total, approx = 0, False
    for part in choice.get("requested_formats") or [choice]:
        size, part_approx = _stream_size(part, duration)
        if size is None:
            return None, True
        total += size
        approx = approx or part_approx
    if fmt["kind"] == "video":
        vcodec = (choice.get("vcodec") or "").lower()
        # Si no viene en H.264 se recodifica y el peso cambia
        if not vcodec.startswith(("avc1", "h264")):
            approx = True
    return total, approx


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
    result = files[0]

    if fmt["kind"] == "video" and HAS_FFMPEG:
        try:
            result = _ensure_h264(result)
        except (subprocess.SubprocessError, OSError) as e:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            raise DownloadError("No se pudo convertir el video. Inténtalo otra vez.") from e
    return result, tmp_dir


def _codec(path: Path, stream: str) -> str:
    """Codec del primer stream de video ("v") o audio ("a"); "" si no hay."""
    out = subprocess.run(
        [
            FFPROBE, "-v", "error", "-select_streams", f"{stream}:0",
            "-show_entries", "stream=codec_name", "-of", "csv=p=0", str(path),
        ],
        capture_output=True, text=True, timeout=30, check=True,
    )
    return out.stdout.strip().lower()


def _ensure_h264(path: Path) -> Path:
    """Deja el MP4 en H.264 + AAC para que abra en editores (Premiere, CapCut...).

    Algunas redes (Instagram, YouTube) sirven VP9 o AV1 dentro de un .mp4;
    el archivo se reproduce, pero los editores lo rechazan. En ese caso se
    recodifica. Si ya es H.264 no se toca.
    """
    vcodec = _codec(path, "v")
    acodec = _codec(path, "a")
    if vcodec == "h264" and acodec in ("aac", ""):
        return path

    out = path.with_name(path.stem + ".h264.mp4")
    cmd = [FFMPEG, "-y", "-v", "error", "-i", str(path)]
    if vcodec == "h264":
        cmd += ["-c:v", "copy"]
    else:
        cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p"]
    if acodec in ("aac", ""):
        cmd += ["-c:a", "copy"]
    else:
        cmd += ["-c:a", "aac", "-b:a", "192k"]
    cmd += ["-movflags", "+faststart", str(out)]
    subprocess.run(cmd, capture_output=True, timeout=900, check=True)

    path.unlink()
    final = path.with_suffix(".mp4")
    out.rename(final)
    return final
