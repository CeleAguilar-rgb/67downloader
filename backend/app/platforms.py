"""Detecta la plataforma de un link. Valida en el server: nunca confíes en el navegador."""
import re
from urllib.parse import urlparse

PLATFORMS = {
    "tiktok": re.compile(r"(^|\.)tiktok\.com/", re.I),
    "instagram": re.compile(r"(^|\.)instagram\.com/(p|reel|reels|tv)/", re.I),
    "twitter": re.compile(r"(^|\.)(twitter|x)\.com/.+/status/\d+", re.I),
    "facebook": re.compile(r"((^|\.)facebook\.com/|(^|\.)fb\.watch/)", re.I),
    "youtube": re.compile(r"((^|\.)youtube\.com/(watch|shorts/|live/)|(^|\.)youtu\.be/)", re.I),
}


def detect_platform(url: str) -> str | None:
    """Regresa la clave de la plataforma, o None si no es soportada."""
    try:
        parsed = urlparse(url.strip())
    except ValueError:
        return None
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return None
    target = parsed.hostname + parsed.path
    for key, pattern in PLATFORMS.items():
        if pattern.search(target):
            return key
    return None
