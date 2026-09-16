<#
.SYNOPSIS
    DRGTranslate を Deep Rock Galactic にインストールします。

.DESCRIPTION
    - Deep Rock Galactic のインストール先を自動検出（Steam のライブラリを走査）
    - UE4SS の有無を確認（-InstallUE4SS を付けると GitHub から取得して展開）
    - mod フォルダを UE4SS の Mods 配下へコピーし、mods.txt に登録
    - settings.ini を用意し、通信フォルダを作成

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\install.ps1
    powershell -ExecutionPolicy Bypass -File .\install.ps1 -InstallUE4SS
    powershell -ExecutionPolicy Bypass -File .\install.ps1 -GamePath "G:\SteamLibrary\steamapps\common\Deep Rock Galactic"
#>

[CmdletBinding()]
param(
    [string]$GamePath,
    [switch]$InstallUE4SS,
    [string]$UE4SSVersion = "v3.0.1",
    [switch]$Uninstall
)

$ErrorActionPreference = "Stop"
$ModName = "DRGTranslate"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path

function Info($m) { Write-Host "[+] $m" -ForegroundColor Cyan }
function Ok($m)   { Write-Host "[o] $m" -ForegroundColor Green }
function Warn($m) { Write-Host "[!] $m" -ForegroundColor Yellow }
function Die($m)  { Write-Host "[x] $m" -ForegroundColor Red; exit 1 }

# ---------------------------------------------------------------------------
# 1. Deep Rock Galactic を探す
# ---------------------------------------------------------------------------

function Find-DRG {
    $candidates = @()

    $steamPath = $null
    foreach ($key in @("HKCU:\Software\Valve\Steam", "HKLM:\SOFTWARE\WOW6432Node\Valve\Steam")) {
        try {
            $p = (Get-ItemProperty -Path $key -ErrorAction Stop).SteamPath
            if ($p) { $steamPath = $p.Replace("/", "\"); break }
        } catch { }
    }

    $libraryRoots = @()
    if ($steamPath) {
        $libraryRoots += $steamPath
        $vdf = Join-Path $steamPath "steamapps\libraryfolders.vdf"
        if (Test-Path $vdf) {
            foreach ($line in Get-Content $vdf) {
                if ($line -match '"path"\s+"(.+?)"') {
                    $libraryRoots += $Matches[1].Replace("\\", "\")
                }
            }
        }
    }
    # ドライブ直下の SteamLibrary もよくある配置なので見る
    foreach ($drive in (Get-PSDrive -PSProvider FileSystem)) {
        $libraryRoots += (Join-Path $drive.Root "SteamLibrary")
    }

    foreach ($lib in ($libraryRoots | Select-Object -Unique)) {
        $p = Join-Path $lib "steamapps\common\Deep Rock Galactic"
        if (Test-Path (Join-Path $p "FSD\Binaries\Win64\FSD-Win64-Shipping.exe")) {
            $candidates += $p
        }
    }
    return ($candidates | Select-Object -Unique)
}

if (-not $GamePath) {
    Info "Deep Rock Galactic を探しています..."
    $found = @(Find-DRG)
    if ($found.Count -eq 0) {
        Die "見つかりませんでした。-GamePath でインストール先を指定してください。"
    }
    $GamePath = $found[0]
    if ($found.Count -gt 1) {
        Warn "複数見つかりました。1つ目を使います:"
        $found | ForEach-Object { Write-Host "      $_" }
    }
}

$Win64 = Join-Path $GamePath "FSD\Binaries\Win64"
if (-not (Test-Path (Join-Path $Win64 "FSD-Win64-Shipping.exe"))) {
    Die "Deep Rock Galactic のフォルダではないようです: $GamePath"
}
Ok "ゲーム: $GamePath"

# ---------------------------------------------------------------------------
# 2. UE4SS
# ---------------------------------------------------------------------------

function Get-ModsDir {
    foreach ($rel in @("ue4ss\Mods", "Mods")) {
        $p = Join-Path $Win64 $rel
        if (Test-Path $p) { return $p }
    }
    return $null
}

$ue4ssDll = @("UE4SS.dll", "ue4ss\UE4SS.dll") | ForEach-Object { Join-Path $Win64 $_ } |
            Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $ue4ssDll) {
    if ($InstallUE4SS) {
        $url = "https://github.com/UE4SS-RE/RE-UE4SS/releases/download/$UE4SSVersion/UE4SS_$UE4SSVersion.zip"
        $zip = Join-Path $env:TEMP "UE4SS_$UE4SSVersion.zip"
        Info "UE4SS $UE4SSVersion を取得します"
        Write-Host "      $url"
        Invoke-WebRequest -Uri $url -OutFile $zip -UseBasicParsing
        Info "展開先: $Win64"
        Expand-Archive -Path $zip -DestinationPath $Win64 -Force
        Remove-Item $zip -Force
        Ok "UE4SS を展開しました"
    } else {
        Warn "UE4SS が見つかりません。"
        Write-Host ""
        Write-Host "  次のどちらかを行ってください:" -ForegroundColor Yellow
        Write-Host "   (a) このスクリプトを -InstallUE4SS 付きで実行して自動導入する"
        Write-Host "   (b) https://github.com/UE4SS-RE/RE-UE4SS/releases から UE4SS_$UE4SSVersion.zip を"
        Write-Host "       ダウンロードし、中身を次のフォルダへ展開する:"
        Write-Host "       $Win64" -ForegroundColor White
        Write-Host ""
        Die "UE4SS の導入後にもう一度実行してください。"
    }
}

$ModsDir = Get-ModsDir
if (-not $ModsDir) {
    $ModsDir = Join-Path $Win64 "Mods"
    New-Item -ItemType Directory -Path $ModsDir -Force | Out-Null
}
Ok "Mods フォルダ: $ModsDir"

# ---------------------------------------------------------------------------
# UE4SS の既定値のうち、クラッシュ要因になりうるものを落とす
#
#   bUseUObjectArrayCache : UObject 配列をキャッシュする。GC でオブジェクトが
#                           破棄・移動されると古いポインタを読んで
#                           EXCEPTION_ACCESS_VIOLATION になる
#   GuiConsoleEnabled     : 別ウィンドウのコンソール。翻訳には不要
#   EnableDumping         : オブジェクトダンプ。翻訳には不要
# ---------------------------------------------------------------------------

$SettingsIni = Join-Path $Win64 "UE4SS-settings.ini"
if (Test-Path $SettingsIni) {
    $safe = @{
        "bUseUObjectArrayCache" = "false"
        "GuiConsoleEnabled"     = "0"
        "EnableDumping"         = "0"
    }
    $changed = @()
    $iniLines = @(Get-Content $SettingsIni)
    for ($i = 0; $i -lt $iniLines.Count; $i++) {
        $key = ($iniLines[$i] -split "=", 2)[0].Trim()
        if ($safe.ContainsKey($key)) {
            $want = $safe[$key]
            if ((($iniLines[$i] -split "=", 2)[1]).Trim() -ne $want) {
                $iniLines[$i] = "$key = $want"
                $changed += "$key=$want"
            }
        }
    }
    if ($changed.Count -gt 0) {
        Set-Content -Path $SettingsIni -Value $iniLines -Encoding UTF8
        Ok ("UE4SS を安全な設定にしました（" + ($changed -join ", ") + "）")
    }
}

# ---------------------------------------------------------------------------
# 3. mod のコピー / 削除
# ---------------------------------------------------------------------------

$Dest = Join-Path $ModsDir $ModName
$ModsTxt = Join-Path $ModsDir "mods.txt"

if ($Uninstall) {
    if (Test-Path $Dest) { Remove-Item $Dest -Recurse -Force; Ok "$ModName を削除しました" }
    if (Test-Path $ModsTxt) {
        (Get-Content $ModsTxt) | Where-Object { $_ -notmatch "^\s*$ModName\s*:" } |
            Set-Content $ModsTxt -Encoding UTF8
        Ok "mods.txt から削除しました"
    }
    exit 0
}

$Src = Join-Path $Root "mod\$ModName"
if (-not (Test-Path $Src)) { Die "mod フォルダが見つかりません: $Src" }

if (Test-Path $Dest) {
    Info "既存の $ModName を更新します"
    # ユーザーが編集した config.lua は退避しておく
    $userCfg = Join-Path $Dest "Scripts\config.lua"
    if (Test-Path $userCfg) {
        Copy-Item $userCfg (Join-Path $env:TEMP "DRGTranslate.config.lua.bak") -Force
        Warn "既存の config.lua は $env:TEMP\DRGTranslate.config.lua.bak に退避しました"
    }
    Remove-Item $Dest -Recurse -Force
}
Copy-Item $Src $Dest -Recurse -Force
Ok "mod をコピーしました: $Dest"

# mods.txt へ登録（UE4SS 3.x はこちらを見る）
#
# あわせて UE4SS 同梱のサンプル MOD を無効化する。翻訳には一切不要なうえ、
# エンジン内部を広く書き換えるのでクラッシュ源になりやすい。
# Keybinds は RegisterKeyBind が依存するので残す。
if (-not (Test-Path $ModsTxt)) { New-Item -ItemType File -Path $ModsTxt -Force | Out-Null }
$keep = @("keybinds", $ModName.ToLower())
$lines = @(Get-Content $ModsTxt -ErrorAction SilentlyContinue)
$registered = $false
$disabled = @()
$lines = $lines | ForEach-Object {
    $s = $_.Trim()
    if ($s -eq "" -or $s.StartsWith(";") -or (-not $s.Contains(":"))) { return $_ }
    $name = ($s -split ":", 2)[0].Trim()
    if ($name.ToLower() -eq $ModName.ToLower()) {
        $script:registered = $true
        return "$ModName : 1"
    }
    if ($keep -notcontains $name.ToLower()) {
        if ((($s -split ":", 2)[1]).Trim() -ne "0") { $script:disabled += $name }
        return "$name : 0"
    }
    return $_
}
if (-not $registered) { $lines += "$ModName : 1" }
Set-Content -Path $ModsTxt -Value $lines -Encoding UTF8
Ok "mods.txt に登録しました（$ModName : 1）"
if ($disabled.Count -gt 0) {
    Ok ("同梱サンプル MOD を無効化しました（" + ($disabled -join ", ") + "）")
}

# ---------------------------------------------------------------------------
# 4. bridge 側の準備
# ---------------------------------------------------------------------------

$IpcDir = Join-Path $env:APPDATA "DRGTranslate"
New-Item -ItemType Directory -Path $IpcDir -Force | Out-Null
Ok "通信フォルダ: $IpcDir"

$cfg = Join-Path $Root "settings.ini"
$example = Join-Path $Root "settings.example.ini"
$legacy = Join-Path $Root ".env"   # 0.5.5 までの名前
if (-not (Test-Path $cfg) -and (Test-Path $legacy)) {
    Rename-Item $legacy "settings.ini"
    Ok "設定ファイルの名前を .env から settings.ini に変えました"
} elseif (-not (Test-Path $cfg)) {
    Copy-Item $example $cfg
    Ok "settings.ini を作成しました"
} else {
    Info "settings.ini は既にあるのでそのままにします"
}

$py = $null
foreach ($c in @("py", "python", "python3")) {
    if (Get-Command $c -ErrorAction SilentlyContinue) { $py = $c; break }
}
if (-not $py) {
    Warn "Python が見つかりません。https://www.python.org/downloads/ から 3.10 以降を入れてください"
} else {
    Ok "Python: $py"
}

Write-Host ""
Write-Host "=== インストール完了 ===" -ForegroundColor Green
Write-Host ""
Write-Host " 1. settings.ini を開いてAPIキーを設定する" -ForegroundColor White
Write-Host "      $cfg"
Write-Host " 2. run_bridge.bat を実行して翻訳プロセスを起動する"
Write-Host " 3. Deep Rock Galactic を起動する"
Write-Host " 4. チャットで動作確認（ゲーム中は F9 で翻訳のON/OFF）"
Write-Host ""
