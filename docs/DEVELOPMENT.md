# 開発者向けガイド

exe を使わずにソースから動かす場合や、exe のビルド・リリースを行う場合の手順です。
ふつうに遊ぶだけなら [README](../README.md) の手順（exe）で足ります。

- [仕組み](#仕組み)
- [表示言語（多言語対応）](#表示言語多言語対応)
- [ソースから使う](#ソースから使う)
- [exe をビルドする](#exe-をビルドする)
- [リリースの作り方（メンテナ向け）](#リリースの作り方メンテナ向け)
- [ファイル構成](#ファイル構成)

関連ドキュメント

- [TESTING.md](TESTING.md) — どこまで動作確認できていて、どこが未確認か
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

## 表示言語（多言語対応）

利用者に見せる文言は `bridge/i18n.py` の1つの表にまとまっています。
対応言語は `ja` / `en` / `ko` / `zh` / `zh-tw` / `ru` の6つです。

```python
from i18n import t

log.info(t("b.startup"), provider_name, ...)   # logging の書式はそのまま
warn(t("w.failed", err=exc))                   # {name} は kwargs で埋める
```

- 表示言語は `i18n.init()` が決めます。`DRGT_UI_LANG` →
  `DRGT_INCOMING_TARGET` → OS の言語 → 英語、の順に見ます。候補は順に
  `normalize()` して、最初に解決したものを採ります。対応していない言語が
  途中にあっても（受信を `de` にしている等）そこで止まらず次の候補へ進みます。
  `DRGT_UI_LANG` を持たない古い `settings.ini` でも、これまでと同じ言語で出ます。
- OS の言語は、Windows では `GetUserDefaultUILanguage` + `LCIDToLocaleName` で
  聞きます（`LANG` などの環境変数を持たないため）。`locale.getdefaultlocale()` は
  Python 3.15 で消えるので使っていません。
- セットアップは最初の質問で言語を聞き、`i18n.set_lang()` を呼んでから残りを進めます。
  選ばれた言語は `settings.ini` の `DRGT_UI_LANG` に書かれます。
- 訳が無いキーは英語にフォールバックします（落ちません）。

**言語を増やすとき**

1. `i18n.py` の `LANGUAGES` に `("xx", "その言語での表記")` を足す
2. `_M` の各キーに `"xx"` を足す（足し忘れたキーは英語で出ます）
3. `README.xx.md` を追加し、全 README 冒頭の言語リンクに足す
4. `i18n.readme()` が返す URL と一致しているか確認する
5. `docs/README.txt` にその言語の3行を足す

**英語で書くもの / 日本語のままにするもの**

- 利用者が編集する設定ファイル（`settings.example.ini`、`config.lua`）の
  コメントは**英語**です。言語ごとに用意すると数が増えるため、
  どの言語の人でも読める英語に寄せています。
- **ゲーム内に出す文字**（F9 の `Translation ON/OFF`、bridge が `NOTE` で送る案内）は
  **英数字**です。ゲームの言語によっては日本語などのフォントが読み込まれず、
  豆腐になるためです。
- MOD（Lua）が UE4SS のコンソールに出すログと、bridge の開発者向けの経路
  （`--test` / `--selftest` の出力、`--help`）は**英語**です。
- `docs/` 以下の開発者向け文書と、ソースコードのコメントは日本語のままです。

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

アンインストールは `-Uninstall` を付けて実行してください。MOD と入れ直しのときの控え
（`DRGTranslate.bak`）を消し、`mods.txt` から行を外します（元の内容は `mods.txt.bak`）。
UE4SS の確認や `UE4SS-settings.ini` の書き換えはしないので、UE4SS を先に消していても動きます。

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

### 翻訳を試す

ゲームを起動せずに試せます。

```
py -3 bridge\drg_bridge.py --test "watch out, swarm incoming"
```

```
input       : watch out, swarm incoming
detected    : en
incoming    : 気をつけろ、大群がやってくる  (source: en)
relay (host): Karl: 気をつけろ、大群がやってくる / 조심해, 무리가 온다 / 小心，虫群来了
```

自分が打った場合の訳（`outgoing`）は翻訳元の言語の発言のときに、他の隊員が言った場合の訳
（`incoming`）はそれ以外のときに出ます。翻訳元を `auto` にしているときは両方出ます。

このように訳が出れば準備完了です。

### 起動

1. **`run_bridge.bat` を実行**（黒い窓が出ます。閉じないでください）
2. **Deep Rock Galactic を起動**

`run_bridge.bat` は exe の `DRGTranslate.exe` と同じ役割です。ゲーム内での使い方は
README の[使い方](../README.md#使い方)を参照してください。

### そのほかのコマンド

```
py -3 bridge\drg_bridge.py --test "回復お願いします"      # 送信方向を試す
py -3 bridge\drg_bridge.py --provider claude --test "bulk inc, res me"   # 一時的に上書き
py -3 bridge\drg_bridge.py --setup                       # exe と同じセットアップウィザード
py -3 bridge\drg_bridge.py --config other.ini            # 別の設定ファイルで動かす
```

### テストを走らせる

どれも APIキーは要りません。push と pull request のたびに CI（`.github/workflows/ci.yml`）で
同じものが走ります。テストに使うものは `requirements-dev.txt` にまとめてあります。

```
py -3 -m pip install -r requirements-dev.txt
```

**bridge の単体テストと lint**

```
py -3 -m pytest bridge
py -3 -m ruff check bridge
```

**bridge の通し確認**

```
py -3 bridge\drg_bridge.py --selftest --fake
```

同梱される `anthropic` が、こちらの送る引数を受け付けるかもここで確認します（SDK の
更新で引数が消えると、その SDK を同梱した exe だけ翻訳に失敗するため）。
`anthropic` が入っていないと、この確認は省かれます。

同梱する SDK の版は `requirements.txt` で固定しています。上げるときは、上の確認が
通ることを確かめてから上げてください。

**MOD のロジック**（UE4SS を模したスタブ。Lua 5.4 が必要）

```bash
python3 bridge/drg_bridge.py --fake --defaults --dir /tmp/drgtl &
lua5.4 tools/mock_test.lua /tmp/drgtl client
lua5.4 tools/mock_test.lua /tmp/drgtl host
lua5.4 tools/ipc_test.lua                  # 接続判定だけ（bridge 不要）
```

`--fake` は翻訳APIを呼ばずに目印を付けて返すテスト専用モードです。
`provider` として設定から選ぶことはできません。
`--defaults` は settings.ini の言語などを読まずに既定の設定で動かします（モックの合否は
既定の設定＝日本語で読み書き、が前提のため）。`--selftest` は付けなくても既定の設定で動きます。

どこまで動作確認できているかは [TESTING.md](TESTING.md) にまとめてあります。

### ファイルの置き場所（exe との違い）

| | ソース | exe |
|---|---|---|
| `settings.ini` | リポジトリ直下 | exe と同じフォルダ |
| キャッシュ | `bridge\cache.json` | exe と同じフォルダの `cache.json` |
| 用語集 | `bridge\glossary.json` | exe と同じフォルダの `glossary.json`。無ければ exe に同梱したもの |
| ログ | `%APPDATA%\DRGTranslate\bridge.log` | 同じ（`--dir` を付けたらそのフォルダ） |

ログファイルは画面に出るものと同じですが、発言の本文（受信・送信・中継の訳）は
書きません。APIキーは画面・ファイルとも伏せて出します。512KB を超えたら
`bridge.log.1` に回し、2世代だけ残します。

### 設定まわりの補足

- `settings.ini` の書式は `KEY=value` で、`#` から始まる行はコメントです。
- `settings.ini` は `.gitignore` 済みなので、APIキーがリポジトリに入ることはありません。
- APIキー以外に `DRGT_` が付いているのは、`LOG_LEVEL` や `MAX_WORKERS` のような
  一般的な名前が他のツールの環境変数と衝突するのを避けるためです。
- Claude はモデルによって使えるパラメータが違う（`effort` と `thinking` を
  受け付けるのは新しい世代だけ）ため、指定したモデルに合わせて自動で送り分けます。
  `temperature` はどのモデルにも送りません（0.5.7 でやめた）。
  `DRGT_CLAUDE_EFFORT` と `DRGT_CLAUDE_REFUSAL_FALLBACK` の `auto` はこのためのものです。
  モデルが受け付けない値（書き間違い、4.6 世代への `xhigh` など）は起動時に警告して
  `auto` に戻します。Claude Opus 5 は effort が `xhigh` / `max` のとき `thinking` を
  disabled にできないので、そのときだけ `thinking` を送りません（`ClaudeProvider` の表）。
- Claude のシステムプロンプトにはキャッシュの印（`cache_control`）を付けています。いまのプロンプトは
  約1,300トークンで、最小の長さに届く Sonnet 5 / Opus 5 などでは続けて翻訳するとその部分が1割の
  料金になり、届かない Haiku 4.5（最小 4,096）では何も起きません。キャッシュは5分使われないと
  消え、次の1回は書き込みとして1.25倍になるので、発言が5分以上あく静かな部屋ではわずかに高くなります。
- README の料金の目安（Haiku 4.5 で1000回あたり約 $1.5）は、プロンプトの長さから計算しています。
  `GAME_CONTEXT` を変えたら、Anthropic の `count_tokens`（課金なし）で数え直して README を直してください。

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

UE4SS のバージョンも同じステップで照合します。上げるときは
`bridge/setup_wizard.py` の `UE4SS_VERSION` と `install.ps1` の `$UE4SSVersion` を
両方そろえてください（片方だけ上げると、exe で入れた人と `install.ps1` で
入れた人に別の版の UE4SS が入ります）。

公開前に中身を確認したいときは、Actions から `release` を手動実行すると
リリースを作らずに zip だけが成果物として残ります。

zip に入るのは `DRGTranslate.exe` / `settings.example.ini` /
`docs/README.txt`（zip の中では `README.txt`）/ `LICENSE` の4つだけです。
各言語の `README.md` は同梱せず、`README.txt` から GitHub へ誘導します
（zip を小さく保ち、古い README が手元に残らないようにするため）。

---

## ファイル構成

```
README.md                    日本語版（本体）。冒頭の言語リンクから各言語へ
README.en.md ほか            各言語版（en / ko / zh / zh-TW / ru）
settings.example.ini         設定のひな形（初回に settings.ini としてコピーされる。英語）
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
  i18n.py                    利用者向け文言の対訳表（6言語）
  setup_wizard.py            初回セットアップの対話ウィザード
  translate.py               翻訳API・言語判定・キャッシュ・用語集
  overlay.py                 保険用の小窓（tkinter）
  glossary.json              DRG 定型句の対訳表
tools/                       実機なしで動かすテスト用スタブ
docs/
  DEVELOPMENT.md             このファイル
  TESTING.md                 動作確認の状況
  INTERNALS.md               解析した DRG 側 API のメモ
  README.txt                 配布 zip に入れる手引き（6言語・これだけ同梱）
```
