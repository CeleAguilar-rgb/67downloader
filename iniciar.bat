@echo off
rem 67downloader en tu compu, sin servidor: doble clic y se abre su ventana.
rem La primera vez prepara todo (Python, dependencias y ffmpeg); despues abre al instante.
rem Variables solo para pruebas: PY67 = ruta de un python.exe, NOASK=1 = no hacer preguntas.
setlocal EnableExtensions
title 67downloader
cd /d "%~dp0backend"

set "APPDIR=%LOCALAPPDATA%\67downloader"
set "VENV=%APPDIR%\venv"

if exist "%VENV%\.ready" goto :run

echo ============================================
echo   67downloader - preparando la primera vez
echo   (tarda unos minutos, solo pasa una vez)
echo ============================================
echo.

rem ---------- 1. Python 3.10 o mas nuevo ----------
call :find_python
if defined PY goto :have_python
echo No encontre Python 3.10 o mas nuevo.
if defined NOASK exit /b 1
choice /m "Instalarlo ahora con winget"
if errorlevel 2 (
  echo Instalalo desde https://www.python.org/downloads/ ^(marca "Add python.exe to PATH"^) y vuelve a abrir este archivo.
  pause
  exit /b 1
)
winget install -e --id Python.Python.3.12
echo.
echo Listo. Cierra esta ventana y vuelve a abrir iniciar.bat.
pause
exit /b 0

:have_python
rem ---------- 2. Entorno y dependencias (fuera de la carpeta del proyecto) ----------
echo Creando entorno...
"%PY%" %PYARG% -m venv "%VENV%" || goto :fail
echo Instalando dependencias...
"%VENV%\Scripts\python.exe" -m pip install --upgrade pip -q
"%VENV%\Scripts\python.exe" -m pip install -r requirements.txt || goto :fail
echo ok> "%VENV%\.ready"

rem ---------- 3. ffmpeg (hace falta para MP4 y MP3) ----------
where ffmpeg >nul 2>&1 && where ffprobe >nul 2>&1 && goto :ffmpeg_ok
echo.
echo ffmpeg no esta instalado y hace falta para MP4 y MP3.
if defined NOASK goto :ffmpeg_ok
choice /m "Instalarlo ahora con winget"
if errorlevel 2 goto :ffmpeg_ok
winget install -e --id Gyan.FFmpeg
echo.
echo ffmpeg instalado. Cierra esta ventana y vuelve a abrir iniciar.bat
echo ^(Windows necesita una ventana nueva para encontrarlo^).
pause
exit /b 0
:ffmpeg_ok

rem ---------- 4. Acceso directo (opcional) ----------
if defined NOASK goto :run
echo.
choice /m "Crear un acceso directo en el escritorio"
if errorlevel 2 goto :run
powershell -NoProfile -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\67downloader.lnk'); $s.TargetPath='%~dp0iniciar.bat'; $s.WorkingDirectory='%~dp0'; $s.IconLocation='%~dp0backend\icon.ico'; $s.WindowStyle=7; $s.Save()"

:run
rem pythonw no abre consola; esta ventana se cierra sola
start "" "%VENV%\Scripts\pythonw.exe" desktop.py
exit /b 0

:fail
echo.
echo Algo fallo. Si es la primera vez, borra la carpeta "%APPDIR%\venv" y vuelve a intentar.
pause
exit /b 1

rem ---------- Busca un Python real (el "python" de la Microsoft Store no cuenta) ----------
:find_python
set "PY=" & set "PYARG="
if defined PY67 set "PY=%PY67%" & exit /b 0
py -3 -c "import sys; sys.exit(0 if sys.version_info>=(3,10) else 1)" >nul 2>&1
if not errorlevel 1 set "PY=py" & set "PYARG=-3" & exit /b 0
for /f "delims=" %%P in ('where python 2^>nul') do call :try_python "%%~P"
exit /b 0

:try_python
if defined PY exit /b 0
echo %~1| findstr /i "WindowsApps" >nul && exit /b 0
"%~1" -c "import sys; sys.exit(0 if sys.version_info>=(3,10) else 1)" >nul 2>&1
if not errorlevel 1 set "PY=%~1"
exit /b 0
