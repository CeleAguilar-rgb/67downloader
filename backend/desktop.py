"""Versión de escritorio: levanta el servidor en tu compu y abre la app en su ventana.

Corre igual desde el código (`python desktop.py`) que empaquetado como .exe.
Todo pasa en 127.0.0.1, así que no hay servidor externo ni contraseña, y las
descargas salen desde tu propia conexión.
"""
import os
import socket
import subprocess
import sys
import threading
import time
import traceback
import urllib.request
import webbrowser
from pathlib import Path

APP_NAME = "67downloader"
FIRST_PORT = 8067  # puerto fijo para que el historial (localStorage) no se pierda
DATA_DIR = Path(os.getenv("LOCALAPPDATA") or Path.home()) / APP_NAME

BASE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))


def _prepare_environment() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    # Sin consola, stdout/stderr no existen y yt-dlp/uvicorn truenan al escribir
    for name in ("stdout", "stderr"):
        if getattr(sys, name) is None:
            setattr(sys, name, open(os.devnull, "w", encoding="utf-8"))
    # ffmpeg y ffprobe viajan dentro del paquete; deben estar en el PATH
    # antes de importar la app, que los busca al cargar.
    bin_dir = BASE_DIR / "bin"
    if bin_dir.is_dir():
        os.environ["PATH"] = str(bin_dir) + os.pathsep + os.environ.get("PATH", "")


def _port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def _is_our_app(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1) as r:
            return b'"ok"' in r.read()
    except Exception:
        return False


def _find_browser() -> str | None:
    """Edge viene con Windows; Chrome sirve igual. Ambos soportan --app."""
    roots = [os.getenv("ProgramFiles(x86)"), os.getenv("ProgramFiles"), os.getenv("LOCALAPPDATA")]
    candidates = [
        r"Microsoft\Edge\Application\msedge.exe",
        r"Google\Chrome\Application\chrome.exe",
    ]
    for rel in candidates:
        for root in filter(None, roots):
            path = Path(root) / rel
            if path.exists():
                return str(path)
    return None


def _open_window(url: str, browser: str) -> subprocess.Popen:
    # Perfil propio: así el proceso vive mientras la ventana esté abierta
    # y el historial queda guardado aparte del navegador normal.
    return subprocess.Popen([
        browser,
        f"--app={url}",
        f"--user-data-dir={DATA_DIR / 'profile'}",
        "--window-size=520,900",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-background-mode",  # que no quede un Edge escondido al cerrar
    ])


def _profile_in_use() -> bool:
    """¿Queda algún Edge/Chrome usando el perfil de la app?"""
    script = (
        "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*67downloader*profile*' "
        "-and $_.Name -match 'msedge|chrome' } | Select-Object -First 1 -ExpandProperty ProcessId"
    )
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True, text=True, timeout=20,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return bool(out.stdout.strip())
    except Exception:
        return False


def _wait_for_window(proc: subprocess.Popen) -> None:
    """Espera a que se cierre la ventana. Si Edge devuelve el control enseguida
    (porque se lo pasó a una instancia que ya estaba abierta con el mismo
    perfil), sigue esperando mientras ese perfil siga en uso."""
    started = time.time()
    proc.wait()
    if time.time() - started < 5:
        while _profile_in_use():
            time.sleep(3)


def _wait_until_up(port: int, timeout: float = 15) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        if _is_our_app(port):
            return True
        time.sleep(0.15)
    return False


def _wait_for_exit_without_edge() -> None:
    """Respaldo si no hay Edge ni Chrome: abre el navegador normal y deja una
    ventanita para poder cerrar el programa."""
    import tkinter as tk

    root = tk.Tk()
    root.title(APP_NAME)
    root.geometry("300x110")
    tk.Label(root, text="67downloader está corriendo.\nCierra esta ventana para salir.").pack(pady=20)
    tk.Button(root, text="Salir", command=root.destroy).pack()
    root.mainloop()


def main() -> None:
    _prepare_environment()

    port = FIRST_PORT
    if not _port_is_free(port):
        if _is_our_app(port):
            # Ya hay una copia corriendo: solo abre otra ventana hacia ella
            browser = _find_browser()
            url = f"http://127.0.0.1:{port}"
            _open_window(url, browser) if browser else webbrowser.open(url)
            return
        port = next((p for p in range(FIRST_PORT + 1, FIRST_PORT + 30) if _port_is_free(p)), 0)
        if not port:
            raise RuntimeError("No encontré un puerto libre para arrancar.")

    import uvicorn

    from app.main import app

    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=port, log_config=None, access_log=False)
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    if not _wait_until_up(port):
        raise RuntimeError("El servidor local no arrancó a tiempo.")

    url = f"http://127.0.0.1:{port}"
    browser = _find_browser()
    if browser:
        _wait_for_window(_open_window(url, browser))
    else:
        webbrowser.open(url)
        _wait_for_exit_without_edge()

    server.should_exit = True
    thread.join(timeout=5)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Sin consola no habría forma de ver qué falló
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        (DATA_DIR / "error.log").write_text(traceback.format_exc(), encoding="utf-8")
        raise
