@echo off
chcp 65001 > nul
setlocal
cd /d "%~dp0"

echo ===============================================
echo  DRGTranslate.exe をビルドします
echo ===============================================
echo.

set PY=
where py >nul 2>nul && set PY=py -3
if "%PY%"=="" (where python >nul 2>nul && set PY=python)
if "%PY%"=="" (
    echo Python が見つかりません。
    echo https://www.python.org/downloads/ から 3.10 以降を入れてください。
    pause
    exit /b 1
)

echo [1/3] ビルドに必要なものを入れます
%PY% -m pip install --upgrade pyinstaller anthropic openai
if errorlevel 1 (
    echo.
    echo pip install に失敗しました。
    pause
    exit /b 1
)

echo.
echo [2/3] 前回のビルド結果を消します
if exist build rmdir /s /q build
if exist dist\DRGTranslate.exe del /q dist\DRGTranslate.exe

echo.
echo [3/3] ビルド中（数分かかります）
%PY% -m PyInstaller DRGTranslate.spec --noconfirm
if errorlevel 1 (
    echo.
    echo ビルドに失敗しました。
    pause
    exit /b 1
)

echo.
echo ===============================================
echo  完成: dist\DRGTranslate.exe
echo ===============================================
echo.
echo  配布するときは dist\DRGTranslate.exe だけを渡してください。
echo  settings.ini とキャッシュは exe と同じフォルダに作られます。
echo.
echo  注意: 署名していない exe はウイルス対策ソフトに
echo        警告されることがあります。README を参照してください。
echo.
pause
