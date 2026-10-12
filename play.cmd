@echo off
setlocal enabledelayedexpansion

rem ============================================================
rem  play.cmd  --  double-click to play (no command line needed)
rem
rem  IMPORTANT: this file is intentionally ASCII-ONLY.
rem
rem  cmd.exe parses .cmd files byte-by-byte using the *current*
rem  console code page. Non-ASCII text in a .cmd file breaks as soon
rem  as the code page differs from the file encoding. The symptoms are
rem  nasty and misleading: comment lines get executed as commands,
rem  arguments get silently dropped (so the emulator starts *without*
rem  the ROM), and the script still "looks" fine in an editor.
rem  Keeping this file pure ASCII makes it work on any code page and
rem  any Windows locale. Chinese documentation lives in README.md and
rem  docs\ instead -- please keep the strings in this file ASCII.
rem
rem  Measured on this machine:
rem    mGBA 0.10.5      OK   (verified: 60 fps, screen matches code)
rem    NanoBoyAdvance   crashes while loading a ROM
rem    SkyEmu           crashes at startup
rem  So mGBA is the default; reorder the list below to change that.
rem ============================================================

set "ROOT=%~dp0"
set "ROM=%ROOT%gba_ai.gba"

if not exist "%ROM%" (
    echo.
    echo   [play] No ROM found. Build it first:
    echo          powershell -ExecutionPolicy Bypass -File "%ROOT%build.ps1"
    echo.
    pause
    exit /b 1
)

rem --- pick the first emulator that exists ---
rem (NanoBoyAdvance and SkyEmu were removed by scripts\clean-caches.ps1:
rem  both crash on this machine when loading a ROM. Only mGBA is kept.)
set "EMU="
for %%E in (
    "%ROOT%.toolchain\mgba\mGBA-0.10.5-win64\mGBA.exe"
    "%ROOT%.toolchain\mgba\mGBA-0.10.5-win64\mgba-sdl.exe"
    "%ProgramFiles%\mGBA\mGBA.exe"
) do (
    if not defined EMU (
        if exist %%E set "EMU=%%~E"
    )
)

if not defined EMU (
    echo.
    echo   [play] No emulator found. Install one first:
    echo          powershell -ExecutionPolicy Bypass -File "%ROOT%scripts\setup-emulator.ps1"
    echo.
    pause
    exit /b 1
)

for %%F in ("%EMU%") do set "PNAME=%%~nxF"

echo.
echo   [play] ROM      : %ROM%
echo   [play] Emulator : %EMU%
echo.
echo   Controls: D-Pad = move,  A = change color,  START = recenter.
echo   The HUD in the top-left shows live position and color.
echo.

start "" "%EMU%" "%ROM%"

rem Wait 5 seconds, then check whether the emulator is still alive.
rem The very first launch of a freshly extracted exe can be interrupted
rem by antivirus scanning, so retry once rather than looking broken.
rem "ping" is used instead of "timeout" because timeout errors out when
rem standard input is redirected.
ping -n 6 127.0.0.1 >nul 2>&1
tasklist /fi "imagename eq %PNAME%" 2>nul | find /i "%PNAME%" >nul
if errorlevel 1 (
    echo   [play] First launch exited immediately; retrying once...
    start "" "%EMU%" "%ROM%"
)

exit /b 0