"""Empaqueta 67downloader como programa de Windows (carpeta con .exe).

Uso (desde backend/, con el venv activo y `pip install -r requirements-desktop.txt`):

    python build_desktop.py

Necesita ffmpeg y ffprobe en el PATH: se copian dentro del paquete para que
el programa funcione sin instalar nada más. Resultado en dist/67downloader/
y un zip listo para pasar a otra compu en dist/67downloader-windows.zip.
"""
import shutil
import sys
from pathlib import Path

import PyInstaller.__main__

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
NAME = "67downloader"
SEP = ";" if sys.platform == "win32" else ":"


def main() -> None:
    ffmpeg, ffprobe = shutil.which("ffmpeg"), shutil.which("ffprobe")
    if not (ffmpeg and ffprobe):
        sys.exit("No encontré ffmpeg/ffprobe en el PATH. Instálalos (winget install Gyan.FFmpeg) y reintenta.")

    # --add-data copia los archivos tal cual (sin analizarlos como librerías)
    PyInstaller.__main__.run([
        str(HERE / "desktop.py"),
        "--name", NAME,
        "--noconfirm", "--clean",
        "--windowed",
        "--icon", str(HERE / "icon.ico"),
        "--distpath", str(HERE / "dist"),
        "--workpath", str(HERE / "build"),
        "--specpath", str(HERE / "build"),
        "--paths", str(HERE),
        "--add-data", f"{ROOT / 'frontend'}{SEP}frontend",
        "--add-data", f"{ffmpeg}{SEP}bin",
        "--add-data", f"{ffprobe}{SEP}bin",
        # yt-dlp carga sus extractores por nombre; curl_cffi trae DLLs propias
        "--collect-all", "yt_dlp",
        "--collect-all", "curl_cffi",
        "--collect-submodules", "uvicorn",
        "--hidden-import", "app.main",
        "--hidden-import", "tkinter",
    ])

    out = HERE / "dist" / NAME
    archive = shutil.make_archive(str(HERE / "dist" / f"{NAME}-windows"), "zip", HERE / "dist", NAME)
    print(f"\nListo: {out / (NAME + '.exe')}\nZip:   {archive}")


if __name__ == "__main__":
    main()
