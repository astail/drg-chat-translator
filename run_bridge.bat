@echo off
chcp 65001 > nul
setlocal
cd /d "%~dp0"

title DRGTranslate bridge

set PY=
where py >nul 2>nul && set PY=py -3
if "%PY%"=="" (where python >nul 2>nul && set PY=python)
if "%PY%"=="" (
    echo Python が見つかりません。https://www.python.org/downloads/ から 3.10 以降を入れてください。
    pause
    exit /b 1
)

if not exist settings.ini (
    echo settings.ini がないので settings.example.ini からコピーします。
    copy /y settings.example.ini settings.ini > nul
    echo.
    echo   settings.ini をメモ帳で開いて、APIキーを設定してください。
    echo   %~dp0settings.ini
    echo.
    pause
    exit /b 1
)

echo ===============================================
echo  DRGTranslate bridge
echo  この窓は閉じずに Deep Rock Galactic を起動してください
echo ===============================================
echo.

%PY% bridge\drg_bridge.py %*

echo.
echo bridge が終了しました。
pause
