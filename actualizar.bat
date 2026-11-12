@echo off
rem Actualiza yt-dlp. Hazlo cuando una red deje de descargar (cambian seguido).
"%LOCALAPPDATA%\67downloader\venv\Scripts\python.exe" -m pip install -U yt-dlp
echo.
pause
