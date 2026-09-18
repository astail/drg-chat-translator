# 開発者向けガイド

exe を使わずにソースから動かす場合や、exe のビルド・リリースを行う場合の手順です。
ふつうに遊ぶだけなら [README](../README.md) の手順（exe）で足ります。

- [仕組み](#仕組み)
- [ソースから使う](#ソースから使う)
- [exe をビルドする](#exe-をビルドする)
- [リリースの作り方（メンテナ向け）](#リリースの作り方メンテナ向け)
- [ファイル構成](#ファイル構成)

関連ドキュメント

- [TESTING.md](TESTING.md) — テストの実行方法と、どこまで動作確認できているか
- [INTERNALS.md](INTERNALS.md) — 解析した DRG 側 API のメモ

---

## 仕組み

翻訳APIを呼ぶ必要があるため、公式の Mod SDK（Blueprint のみで HTTP 通信ができない）ではなく
**UE4SS の Lua MOD + ローカル常駐プロセス** という構成にしています。

```
  Deep Rock Galactic
  ├─ UE4SS ── DRGTranslate (Lua)
  │            ├─ AFSDGameState::ClientNewMessage      を hook  … 受信を横取り
  │            └─ AFSDPlayerController::Server_NewMessage を hook … 送信を横取り
  │                    ↕  %APPDATA%\DRGTranslate\*.txt （ファイルIPC）
  └─ bridge (Python) ── 言語判定 → 用語集 → 翻訳API → キャッシュ
```

UE4SS の Lua にはソケットが無いため、追記専用のテキストファイル2本で双方向通信しています。
IPC の書式は [INTERNALS.md](INTERNALS.md#ipc-プロトコル) を参照してください。

---

## ソースから使う

### 必要なもの

| | |
|---|---|
| Deep Rock Galactic | Steam 版（Windows） |
| [UE4SS](https://github.com/UE4SS-RE/RE-UE4SS/releases) | v3.0.1 以降。インストーラで自動導入できます |
| Python | 3.10 以降を推奨（`openai` が 3.10+ を要求。`deepl` / `claude` なら 3.9 でも可） |
| 翻訳APIのキー | **必須**。DeepL / Claude / OpenAI のいずれか |

`claude` または `openai` を使う場合のみ、追加で SDK が必要です。
`deepl` なら標準ライブラリだけで動くので pip install は不要です。

```
py -3 -m pip install anthropic     # provider を claude にする場合
py -3 -m pip install openai        # provider を openai にする場合
```

> **`pip install ...` ではなく `py -3 -m pip install ...` を使ってください。**
> Windows に Python が複数入っていると、`pip` が `run_bridge.bat` の使う
> Python とは別の場所にインストールしてしまい、「入れたのに見つからない」
> という状態になります。`run_bridge.bat` は `py -3` を優先して使うので、
> 同じ `py -3` から入れておけば確実です。
>
> 入ったか確認するには次を実行します（何も表示されなければ成功）。
>
> ```
> py -3 -c "import openai; print(openai.__version__)"
> ```
>
> どちらも純Pythonのパッケージで、依存も含めて Windows 用のビルド済み
> ファイルが配布されています。コンパイラ（Visual Studio Build Tools）は不要です。

### インストール

PowerShell をリポジトリのフォルダで開いて実行してください。

```powershell
# UE4SS も一緒に入れる場合
powershell -ExecutionPolicy Bypass -File .\install.ps1 -InstallUE4SS

# UE4SS を既に入れている場合
powershell -ExecutionPolicy Bypass -File .\install.ps1

# ゲームの場所を自動検出できないとき
powershell -ExecutionPolicy Bypass -File .\install.ps1 -GamePath "G:\SteamLibrary\steamapps\common\Deep Rock Galactic"
```

インストーラは次のことをします。

1. Steam のライブラリから Deep Rock Galactic を探す
2. UE4SS の有無を確認（`-InstallUE4SS` なら GitHub から取得して `FSD\Binaries\Win64` へ展開）
3. `mod\DRGTranslate` を UE4SS の `Mods` 配下へコピーし、`mods.txt` に登録
4. `settings.ini` を用意し、通信用フォルダ `%APPDATA%\DRGTranslate` を作成

アンインストールは `-Uninstall` を付けて実行してください。

### ⚠ インストーラは APIキーと言語までは設定しません

`settings.ini` は作られますが**APIキーは空**で、言語は既定（日本語）のままです。
`install.ps1` はセットアップウィザードを通らないので、
ウィザードの `[4]`（言語）と `[5]`（翻訳サービス）に当たるぶんを手で書く必要があります。
日本語以外で使うなら README の[言語を変える](../README.md#言語を変える)を見てください。
ウィザードをそのまま使いたい場合は `py -3 bridge\drg_bridge.py --setup` でも動きます。

続けて次の2つを行ってください。

**(1) SDK を入れる**（`claude` / `openai` を使う場合のみ）

```
py -3 -m pip install openai
```

**(2) `settings.ini` を開いてキーを設定する**（リポジトリのフォルダ直下）

使うサービスの2行だけ、行頭の `#` を外して書きます。

```ini
DRGT_PROVIDER=openai
OPENAI_API_KEY=sk-...
```

`settings.ini` が無い場合は `settings.example.ini` をコピーして作ります。`run_bridge.bat` を
実行したときも、`settings.ini` が無ければ自動でコピーされます。

```
copy settings.example.ini settings.ini
```

`settings.ini` の各項目は README の[設定](../README.md#設定)と `settings.example.ini` を参照してください。

### 動作確認

ゲームを起動せずに試せます。

```
py -3 bridge\drg_bridge.py --test "watch out, swarm incoming"
```

```
入力      : watch out, swarm incoming
言語判定  : en
受信用翻訳: 気をつけろ、大群がやってくる  (元言語: en)
```

このように訳が出れば準備完了です。

### 起動

1. **`run_bridge.bat` を実行**（黒い窓が出ます。閉じないでください）
2. **Deep Rock Galactic を起動**

`run_bridge.bat` は exe の `DRGTranslate.exe` と同じ役割です。ゲーム内での使い方は
README の[使い方](../README.md#使い方)を参照してください。

### そのほかのコマンド

```
py -3 bridge\drg_bridge.py --test "回復お願いします"      # 送信方向を試す
py -3 bridge\drg_bridge.py --selftest --fake             # APIキー無しで疎通確認
py -3 bridge\drg_bridge.py --provider claude --test "bulk inc, res me"   # 一時的に上書き
py -3 bridge\drg_bridge.py --setup                       # exe と同じセットアップウィザード
py -3 bridge\drg_bridge.py --config other.ini            # 別の設定ファイルで動かす
```

### ファイルの置き場所（exe との違い）

| | ソース | exe |
|---|---|---|
| `settings.ini` | リポジトリ直下 | exe と同じフォルダ |
| キャッシュ | `bridge\cache.json` | exe と同じフォルダの `cache.json` |
| 用語集 | `bridge\glossary.json` | exe と同じフォルダの `glossary.json`。無ければ exe に同梱したもの |

### 設定まわりの補足

- `settings.ini` の書式は `KEY=value` で、`#` から始まる行はコメントです。
- `settings.ini` は `.gitignore` 済みなので、APIキーがリポジトリに入ることはありません。
- APIキー以外に `DRGT_` が付いているのは、`LOG_LEVEL` や `MAX_WORKERS` のような
  一般的な名前が他のツールの環境変数と衝突するのを避けるためです。
- Claude はモデルによって使えるパラメータが違う（`effort` は 4.6 以降のみ、
  `temperature` はそれ以前のみ）ため、指定したモデルに合わせて自動で送り分けます。
  `DRGT_CLAUDE_EFFORT` と `DRGT_CLAUDE_REFUSAL_FALLBACK` の `auto` はこのためのものです。

---

## exe をビルドする

`build.bat` をダブルクリックすると `dist\DRGTranslate.exe` ができます。
必要なもの（PyInstaller・各SDK）は自動で入ります。

```
build.bat
```

配布するのは `dist\DRGTranslate.exe` の1ファイルだけです。
Python 本体・翻訳SDK・MOD本体・用語集をすべて内包しています。

ビルド設定は `DRGTranslate.spec` にあります。誤検知を減らすため
UPX 圧縮は無効にし、未使用の重いライブラリは除外してあります。

---

## リリースの作り方（メンテナ向け）

タグを打つと GitHub Actions が Windows ランナーで exe をビルドし、
配布用 zip を作って Releases に添付します。

バージョンはアプリ全体で1つです。bridge と MOD で番号を分けず、リリースのたびに
次の2か所を同じ番号にしてからタグを打ちます（MOD を変えていないリリースでも MOD の番号を上げます）。

- `bridge/drg_bridge.py` の `VERSION`
- `mod/DRGTranslate/Scripts/main.lua` の `MOD_VERSION`

```bash
git tag v0.5.5        # 上の2か所と揃えること
git push origin v0.5.5
```

2か所の番号とタグ名のどれかが食い違っているとビルドを止めます。
`--selftest --fake` も CI で走るので、壊れたものは出ていきません。
公開前に中身を確認したいときは、Actions から `release` を手動実行すると
リリースを作らずに zip だけが成果物として残ります。

zip に入るのは `DRGTranslate.exe` / `settings.example.ini` / `README.md` / `LICENSE` と
`docs\*.txt`（`はじめに.txt`）です。`docs` の `.md` は入りません。

---

## ファイル構成

```
settings.example.ini         設定のひな形（初回に settings.ini としてコピーされる）
DRGTranslate.spec            exe のビルド定義（PyInstaller）
build.bat                    exe をビルドする
LICENSE                      MIT
install.ps1                  インストーラ（ソースから使う場合）
run_bridge.bat               翻訳プロセスの起動（ソースから使う場合）
mod/DRGTranslate/            UE4SS の Mods へコピーされる本体
  Scripts/main.lua             フック・表示・送信
  Scripts/ipc.lua              bridge とのファイルIPC
  Scripts/util.lua             文字列処理・スケジューラ
  Scripts/config.lua           ゲーム内の設定
bridge/
  drg_bridge.py              常駐プロセス本体（exe のエントリでもある）
  setup_wizard.py            初回セットアップの対話ウィザード
  translate.py               翻訳API・言語判定・キャッシュ・用語集
  overlay.py                 保険用の小窓（tkinter）
  glossary.json              DRG 定型句の対訳表
tools/                       実機なしで動かすテスト用スタブ
docs/
  DEVELOPMENT.md             このファイル
  TESTING.md                 テストの実行方法と動作確認の状況
  INTERNALS.md               解析した DRG 側 API のメモ
  はじめに.txt               配布 zip に入れる手引き
```
