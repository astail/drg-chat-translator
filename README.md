# DRGTranslate

Deep Rock Galactic のチャットを自動翻訳する MOD です。

- **受信**: 英語・韓国語（そのほかの言語も）のチャットを **日本語** にしてチャット欄へ表示
- **送信**: 日本語で打った発言を **英語・韓国語** に翻訳して送信

```
Karl: watch out, swarm incoming
[訳] Karl: 気をつけろ、大群がやってくる

（自分が「回復お願いします」と打つと）
You: 回復お願いします
You: Please heal me / 회복 부탁드립니다
```

> Ghost Ship Games とは無関係の非公式なファンプロジェクトです。MIT License。
> 詳細は[ライセンス](#ライセンス)を参照してください。

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

### 送信のしかた

翻訳はネットワーク越しなので、Enter を押した瞬間には結果が間に合いません。
そこで **打った日本語をそのまま送り、翻訳が届いたら2通目として送る**形にしています。

```
You: 回復お願いします
You: Please heal me / 회복 부탁드립니다
```

原文が残るので、味方に日本人がいればそのまま読めます。誤訳があったときも
元が何だったか分かります。

---

## かんたんな導入（exe）

**`DRGTranslate.exe` をダブルクリックするだけ**です。Python のインストールも
`pip` も必要ありません（exe に同梱されています）。

初回起動時に、次を順番に案内します。

```
[1] Deep Rock Galactic を探しています
    OK  G:\SteamLibrary\steamapps\common\Deep Rock Galactic
[2] UE4SS を確認しています
    !!  UE4SS が入っていません。MOD の動作に必要です。
    今すぐダウンロードして導入しますか？ (Y/n):
[3] MOD をコピーしています
    OK  ...\Mods\DRGTranslate
    OK  mods.txt に登録しました（DRGTranslate : 1）
[4] 翻訳サービスを選んでください
      1) DeepL    機械翻訳。月50万文字まで無料
      2) OpenAI   スラングや誤字に強い。従量課金
      3) Claude   同上。既定は最安の Haiku
    番号 [1]:
    APIキーを貼り付けてください（空欄で中止）:
[5] 翻訳を1回試します
      watch out, swarm incoming
        → 気をつけろ、大群がやってくる
    OK  翻訳できました
```

**用意するものは翻訳サービスのAPIキーだけ**です。設定が終わるとそのまま
翻訳プロセスが常駐するので、窓を開いたままゲームを起動してください。

2回目以降はセットアップを飛ばして、すぐ常駐状態になります。
やり直したいときは `DRGTranslate.exe --setup` を実行してください。

> **ウイルス対策ソフトの警告について**
>
> この exe は署名していないため、Windows Defender や一部のセキュリティソフトが
> 警告を出すことがあります。PyInstaller で作った未署名の exe に共通して起きる
> 誤検知で、中身はこのリポジトリのソースそのものです。
> 気になる場合は下の「ソースから使う」の手順を使ってください。

`.env`（設定とAPIキー）と `cache.json` は **exe と同じフォルダ**に作られます。
書き込める場所に置いてください（`Program Files` の中などは避けてください）。

---

## ソースから使う場合に必要なもの

exe を使わず、リポジトリのまま動かす場合です。

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

---

## インストール

PowerShell をこのフォルダで開いて実行してください。

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
4. `.env` を用意し、通信用フォルダ `%APPDATA%\DRGTranslate` を作成

アンインストールは `-Uninstall` を付けて実行してください。

### ⚠ インストーラは APIキーまでは設定しません

`.env` は作られますが**中身は空**です。続けて次の2つを行ってください。

**(1) SDK を入れる**（`claude` / `openai` を使う場合のみ）

```
py -3 -m pip install openai
```

**(2) `.env` を開いてキーを設定する**（プロジェクトのフォルダ直下）

使うサービスの2行だけ、行頭の `#` を外して書きます。

```ini
DRGT_PROVIDER=openai
OPENAI_API_KEY=sk-...
```

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

---

## 使い方

1. **`run_bridge.bat` を実行**（黒い窓が出ます。閉じないでください）
2. **Deep Rock Galactic を起動**
3. 普段どおりチャットするだけです

設定に不足があると、黒い窓の起動直後に警告が出ます。

```
provider=openai / 受信→ja / 送信→en,ko
==============================================================
翻訳できる状態になっていません:
  .env に OPENAI_API_KEY を設定してください（https://platform.openai.com/api-keys）
==============================================================
```

**この警告が出ていなければ、そのままゲームを起動して大丈夫です。**

| 操作 | 動作 |
|---|---|
| 他人が英語/韓国語で発言 | 日本語訳が次の行に出る |
| 自分が日本語で発言 | 英語・韓国語に翻訳されて送信される |
| 自分が英語で発言 | そのまま送信（翻訳しない） |
| `/` `!` `.` で始まる発言 | 翻訳しない（コマンド用） |
| **F9** | 翻訳のON/OFF切り替え |

> **ゲームの言語を「日本語」にしておいてください。**
> 日本語フォントが読み込まれていないと、翻訳文が豆腐（□□□）になります。

### そのほかのコマンド

```
py -3 bridge\drg_bridge.py --test "回復お願いします"      # 送信方向を試す
py -3 bridge\drg_bridge.py --selftest --fake             # APIキー無しで疎通確認
py -3 bridge\drg_bridge.py --provider claude --test "bulk inc, res me"   # 一時的に上書き
```

---

## 設定

### `.env` — 翻訳まわり

プロジェクトルートの `.env.example` を **`.env`** にコピーして使います。
`run_bridge.bat` を実行すれば自動でコピーされます。

```
copy .env.example .env
```

**すべての項目が既定値つきでコメントアウトされています。**
変えたい行の先頭の `#` を外すだけです。

```ini
# 使う翻訳サービス。deepl / claude / openai のどれか
DRGT_PROVIDER=openai

# OpenAI  https://platform.openai.com/api-keys
OPENAI_API_KEY=sk-...

# 翻訳先（カンマ区切り）。英語だけでいいなら en
#DRGT_OUTGOING_TARGETS=en,ko
```

主な項目は次のとおりです。全項目の説明は `.env.example` に書いてあります。

| キー | 説明 |
|---|---|
| `DRGT_PROVIDER` | `deepl` / `claude` / `openai` |
| `DEEPL_AUTH_KEY`<br>`ANTHROPIC_API_KEY`<br>`OPENAI_API_KEY` | APIキー。使うサービスのものだけでOK |
| `DRGT_OUTGOING_TARGETS` | 送信時の翻訳先。既定 `en,ko`。英語だけなら `en` |
| `DRGT_INCOMING_FORMAT` | 表示形式。`{sender}` `{text}` `{lang}` `{original}` が使えます |
| `DRGT_INCOMING_SKIP_LANGUAGES` | この言語は翻訳しない。既定 `ja` |
| `DRGT_CACHE_ENABLED` | 翻訳結果を保存するか |
| `DRGT_OVERLAY_ENABLED` | ゲーム内表示が使えないときの保険となる小窓 |
| `DRGT_OVERLAY_HIDE_AFTER` | 小窓を引っ込めるまでの秒数。既定 `12`、`0` で出しっぱなし |

APIキー以外に `DRGT_` が付いているのは、`LOG_LEVEL` や `MAX_WORKERS` のような
一般的な名前が他のツールの環境変数と衝突するのを避けるためです。

`.env` は `.gitignore` 済みなので、APIキーがリポジトリに入ることはありません。
OS 側に同名の環境変数がある場合は、そちらが `.env` より優先されます。

### 翻訳プロバイダの選択

3つから選びます。どれも APIキーが必要です。

| provider | pip install | 特徴 |
|---|---|---|
| `deepl`（既定） | 不要 | 機械翻訳としては最も自然。**月50万文字まで無料** |
| `claude` | `anthropic` | **スラング・略語・誤字に強い**。`gg` `bulk inc` `res me` を文脈で訳せる |
| `openai` | `openai` | 同上。OpenAI互換エンドポイント（ローカルLLM等）にも向けられる |

普通の会話が中心なら `deepl` で十分です。`Rock and Stone` のような定型句は
用語集で処理されるので、どのプロバイダでも同じ訳になります。
略語やタイプミスの多い野良マルチで精度を上げたいなら `claude` / `openai` を。

**DeepL**（既定。無料枠が大きい）

```ini
DRGT_PROVIDER=deepl
DEEPL_AUTH_KEY=xxxxxxxx-....-xxxxxxxxxxxx:fx
```

**Claude**（ゲーム内スラングまで正しく訳したい場合）

```ini
DRGT_PROVIDER=claude
ANTHROPIC_API_KEY=sk-ant-...
```

既定モデルは **`claude-haiku-4-5`** です。チャットは1行程度の短文なので、
これで十分なうえ最速・最安です。訳が物足りなければ `DRGT_CLAUDE_MODEL` を上げてください。

| model | 入力/出力 (100万トークンあたり) | 目安 |
|---|---|---|
| `claude-haiku-4-5` （既定） | $1 / $5 | 短いチャットならこれで十分 |
| `claude-sonnet-5` | $3 / $15 | 言い回しの自然さを上げたいとき |
| `claude-opus-5` | $5 / $25 | 長文や込み入った内容も混ざるとき |

1回の翻訳はシステムプロンプト込みで入力約330トークン・出力約30トークンなので、
Haiku 4.5 なら**おおよそ1000回の翻訳で $0.5 程度**です（あくまで目安）。

モデルによって使えるパラメータが違う（`effort` は 4.6 以降のみ、`temperature` は
それ以前のみ）ため、指定したモデルに合わせて自動で送り分けます。
`DRGT_CLAUDE_EFFORT` と `DRGT_CLAUDE_REFUSAL_FALLBACK` の `auto` は
そのままにしておいて問題ありません。

**OpenAI**

```ini
DRGT_PROVIDER=openai
OPENAI_API_KEY=sk-...
#DRGT_OPENAI_MODEL=gpt-4o-mini
```

既定モデルは最安・最速の `gpt-4o-mini` です。

**`DRGT_OPENAI_BASE_URL` を設定すれば OpenAI 互換の別エンドポイントに向けられます。**
Ollama / LM Studio / llama.cpp などのローカルLLMを指定すれば、チャット本文を
一切外部に出さずに翻訳できます。

```ini
DRGT_PROVIDER=openai
OPENAI_API_KEY=dummy
DRGT_OPENAI_BASE_URL=http://localhost:11434/v1
DRGT_OPENAI_MODEL=qwen2.5:7b
```

### LLM を使うときの注意

- **1回の送信で複数言語をまとめて訳します。** 英語＋韓国語でも API 呼び出しは1回です。
- **API を呼ぶのは実際に発言したときだけです。** 入力中には翻訳を投げないので、
  打ちかけてやめた文章に課金されることはありません。
- **暴言などで翻訳を拒否されることがあります。** その1件だけ翻訳されず、
  ゲームの動作には影響しません。`claude-opus-5` など対応モデルを使う場合は
  自動で別モデルへ回す設定（`DRGT_CLAUDE_REFUSAL_FALLBACK`）が働きます。
- 応答は機械翻訳よりわずかに遅めです。原文の直後に翻訳が届くまで
  少し間が空きます。
- チャット本文が Anthropic / OpenAI に送信されます。外部に出したくない場合は
  上記のとおり `openai` + `DRGT_OPENAI_BASE_URL` でローカルLLMに向けてください。

### `bridge\glossary.json` — 用語集

`Rock and Stone!` のような定型句を、APIを経由せず即座に置き換えます。
DRG の頻出フレーズを最初から登録済みです。自由に追記してください。

日本語の用語は [DRG 日本語 Wiki](https://wikiwiki.jp/rockandstone/) に合わせています
（ナイトラ / ビスモル / エノアパール など）。`Bulk Detonator` は正式には
「グリフィッドバルクデトネーター」ですが、日本語圏では **デトネーター** で通じるため
そちらを採用しています。

```json
{
  "incoming": { "leaf lover": "リーフラバー（軟弱者）" },
  "outgoing": { "ありがとう": { "en": "Thanks!", "ko": "고마워요!" } }
}
```

キーは空白・記号・大文字小文字を無視して照合されるので、`rock and stone` と
`Rock and Stone!!` は同じ扱いになります。

### `mod\DRGTranslate\Scripts\config.lua` — ゲーム内の挙動

| 項目 | 説明 |
|---|---|
| `outgoing.enabled` | 自分の日本語発言を翻訳して送るか |
| `outgoing.ignore_prefixes` | この文字で始まる発言は翻訳しない |
| `outgoing.min_length` | この文字数未満は翻訳しない |
| `incoming.skip_own` | 自分の発言は翻訳しない |
| `display.strategy` | 翻訳の表示方法。`auto` / `gamestate` / `widget` / `off` |
| `debug` | UE4SS コンソールに詳細ログを出す |

`config.lua` を書き換えたら **ゲームを再起動**してください。

---

## 動作確認の状況

正直に書いておきます。

**検証済み**

- **実際のAPIキーを使った翻訳の往復**（Claude / `claude-haiku-4-5`）
  - 英語→日本語: `watch out, swarm incoming from the left` → 左から群れが来るぞ、気をつけろ
  - 韓国語→日本語: `탄약이 부족해요, 나이트라 찾아주세요` → 弾薬が足りない、ニトラを探してくれ
  - 日本語→英語+韓国語: `回復お願いします` → `heal plz / 힐 부탁합니다`（呼び出しは1回）
  - ゲーム内スラング: `bulk inc, res me` → バルク来た、俺を助けてくれ
  - 用語集の直接置換: `rock and stone!` → ロックアンドストーン！（APIを経由しない）
  - キャッシュのヒット（2回目はAPIを呼ばない）
- bridge のファイルIPC 一式（`--selftest --fake` が PASS）
- LLMプロバイダ（`claude` / `openai`）のロジックをスタブで検証：
  多言語を1回の呼び出しにまとめる、` ```json ` フェンス付き応答の解析、
  引用符の除去、キャッシュ済み言語のスキップ、不足分だけの再問い合わせ、
  壊れた応答と翻訳拒否のエラー化 — 8項目すべて PASS
- Claude のモデル世代ごとのパラメータ送り分け（Haiku 4.5 等には `effort`/`thinking` を
  送らず `temperature` を使う／Opus 5 等にはその逆）を、送信内容を捕捉して検証
- Lua の構文チェックと文字列処理のユニットテスト（UTF-8判定、エスケープ往復）
- **UE4SS を模したスタブによる MOD ロジックの通し確認**（`tools/mock_test.lua`）
  受信フックからの翻訳表示、送信フックからの2通目送信、日本語以外・`/` コマンド・
  短すぎる発言のスキップ、用語集のヒット、自分の発言のループ防止、
  クライアント/ホストでの表示先の切り替え — クライアント21項目・ホスト21項目すべて PASS

```bash
# 実行方法（Lua 5.4 が必要。APIキーは不要）
python3 bridge/drg_bridge.py --fake --dir /tmp/drgtl &
lua5.4 tools/mock_test.lua /tmp/drgtl client
lua5.4 tools/mock_test.lua /tmp/drgtl host
```

`--fake` は翻訳APIを呼ばずに目印を付けて返すテスト専用モードです。
`provider` として設定から選ぶことはできません。

- **セットアップウィザードの通し確認**（`bridge/setup_wizard.py`）
  ゲームフォルダの手入力、UE4SS の検出、MOD のコピー、`mods.txt` の登録
  （既存行の有効化・他MODの保持・重複しないこと）、プロバイダ選択、
  `.env` への書き込み、疎通確認の成功／失敗の両方 — すべて実行して確認
- **exe（PyInstaller）のパス解決**を frozen 状態を再現して確認：
  `.env` とキャッシュが exe の隣に作られること、同梱した用語集・MOD本体・
  `.env.example` が読めること、exe の隣に置いた `glossary.json` が
  同梱版より優先されること

- **exe を実際にビルドして Windows 上で実行**（Python 3.11.9 / PyInstaller 6.21.0、19MB）
  - `--selftest` が PASS（同梱した用語集が読めていることも確認）
  - **`anthropic` / `openai` が同梱され、実際に各社APIへ到達**（偽キーで 401 が返る＝
    SDK が exe 内で動作している）
  - セットアップウィザードの完走。**Steam レジストリからのゲーム自動検出も実機で成功**
  - 同梱した MOD 本体がゲームフォルダへ展開され、`mods.txt` に登録されること
    （他MODの行が保持され、重複しないことも確認）
  - `.env` とキャッシュが exe の隣に作られること
  - APIキー未設定・SDK未導入それぞれで、クラッシュせず案内が出ること

**未検証**

- **`deepl` / `openai` の実際の翻訳結果**。認証エラー（401/403）まで到達することは
  確認済みですが、有効なキーでの往復は `claude` でのみ確認しています
- **ゲームへの実インストールと、ゲーム内での動作**。ウィザードは偽のゲームフォルダに対して
  検証しており、実際の Deep Rock Galactic には導入していません
- UE4SS の hook が実際のゲームで発火するか（`ClientNewMessage` / `Server_NewMessage`）
- ホスト時のチャットウィジェット直叩き（構造体引数を Lua のテーブルで渡せるか）

hook 名・構造体の定義は
[DRG-Modding/FSD-Template](https://github.com/DRG-Modding/FSD-Template) のヘッダーダンプと
ゲーム本体バイナリの文字列から確認した実物ですが、実際の挙動は必ず一度確かめてください。
うまく動かないときは `config.lua` の `debug = true` にして UE4SS コンソールのログを見てください。

---

## トラブルシューティング

**ゲームが起動直後にクラッシュする（EXCEPTION_ACCESS_VIOLATION）**
: まず MOD を切り分けます。`FSD\Binaries\Win64\dwmapi.dll` の名前を
  `dwmapi.dll.off` に変えると UE4SS ごと無効になり、素のゲームに戻ります。
  これで直るならクラッシュは UE4SS 側です。次を確認してください。

  1. `UE4SS-settings.ini` の `bUseUObjectArrayCache` が `false` になっているか。
     `true` だと UE4SS が古いオブジェクトのポインタを読んで落ちることがあります。
  2. `Mods\mods.txt` で UE4SS 同梱のサンプル MOD（`ConsoleEnablerMod`、
     `BPModLoaderMod` など）が `: 0` になっているか。翻訳には不要で、
     エンジン内部を書き換えるためクラッシュ源になりやすいものです。

  どちらも v0.2.1 以降のインストーラが自動でやります。古い版で入れた場合は
  `DRGTranslate.exe --setup` をもう一度実行すると直ります。
  それでも落ちる場合は `mods.txt` の `DRGTranslate : 1` を `: 0` にして起動し、
  MOD 本体が原因かどうかを切り分けてください。

  なお v0.2.2 には、起動直後に落ちる不具合がありました（自分の名前を取りに
  レベルロード中の UObject を毎秒たどっていたため）。v0.2.3 で解消しています。

**MODが読み込まれない**
: `FSD\Binaries\Win64` に `dwmapi.dll` と `UE4SS.dll` があるか確認してください。
  `Mods\mods.txt` に `DRGTranslate : 1` の行が必要です。
  読み込み状況は同じフォルダの `UE4SS.log` に出ます（起動のたびに書き直されます）。
  なお UE4SS の別窓コンソールは安定性のため既定で切ってあります。見たいときは
  `UE4SS-settings.ini` の `GuiConsoleEnabled` を `1` にしてください。

**「bridge との接続が切れました」と出る**
: `run_bridge.bat` が動いていません。ゲームより先に起動してください。

**翻訳が表示されない**
: `FSD\Binaries\Win64\UE4SS.log` に `hook 登録: ...` が2行出ているか確認してください。
  出ていない場合、ゲームのアップデートで関数名が変わった可能性があります。
  表示だけができない場合は `.env` の `DRGT_OVERLAY_ENABLED=true` にすると
  小窓に出せます（ゲームの表示設定を「ウィンドウ(フルスクリーン)」にしてください）。

**日本語が □□□ になる**
: ゲームの言語設定を日本語にしてください。

**自分の発言だけ翻訳を止めたい**
: `config.lua` の `outgoing.enabled` を `false` にしてください。受信の翻訳だけが残ります。

**ホストで遊ぶと翻訳がチャット欄に出ない**
: 仕様です。ホストが `PostGameMessage` を呼ぶと訳文が全員に配信されてしまい、
  チャットウィジェットを直接叩く方法は構造体引数を渡すためゲームごと落ちる
  危険があります。そのためホストではゲーム内に出さず、bridge の小窓に出します。
  小窓は翻訳が届いたときだけ出て、12秒で引っ込みます（`DRGT_OVERLAY_HIDE_AFTER`）。
  `.env` の `DRGT_OVERLAY_ENABLED=true` にしてください（ゲームの表示設定は
  「ウィンドウ(フルスクリーン)」にしないと前面に出ません）。
  クライアントとして参加しているときは、これまで通りチャット欄に出ます。

---

## 注意

- UE4SS は Deep Rock Galactic 公式の MOD 管理（mod.io）の外側で動く仕組みです。導入は自己責任でお願いします。
- 翻訳して送った発言は当然ながら他のプレイヤーにも見えます。誤訳もそのまま送られます。
- **翻訳のため、他プレイヤーの発言を含むチャット本文が外部サービス（DeepL / Anthropic /
  OpenAI）へ送信されます。** 発言者本人の同意は得られません。外部に出したくない場合は
  `openai` + `DRGT_OPENAI_BASE_URL` でローカルLLMに向けてください。
- チャット本文は `bridge\cache.json` にも保存されます。不要なら `.env` の
  `DRGT_CACHE_ENABLED=false` にしてください。
- `claude` / `openai` は従量課金です。実際に発言したときだけ API を呼びます。

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

## ファイル構成

```
.env.example                 設定のひな形（.env にコピーして使う）
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
docs/INTERNALS.md            解析した DRG 側 API のメモ
```

## 内部仕様

解析した DRG 側の API については [docs/INTERNALS.md](docs/INTERNALS.md) を参照してください。

---

## ライセンス

このリポジトリのコードとドキュメントは **MIT License** です（[LICENSE](LICENSE)）。

### 非公式MODであることについて

本プロジェクトは **Ghost Ship Games とは無関係の非公式なファンプロジェクト**です。
公認・後援・提携のいずれもありません。
"Deep Rock Galactic" およびゲーム内の名称・用語は Ghost Ship Games の商標または
著作物であり、本リポジトリでは相互運用の説明に必要な範囲で言及しているだけです。
ゲームのアセット・コード・実行ファイルは一切含んでいません。

導入前に Ghost Ship Games の UGC ポリシーをご確認ください。

### 依存・参照している第三者のもの

| | ライセンス | 扱い |
|---|---|---|
| [UE4SS](https://github.com/UE4SS-RE/RE-UE4SS) | MIT | **同梱していません**。`install.ps1 -InstallUE4SS` が公式リリースから取得します |
| [DRG-Modding/FSD-Template](https://github.com/DRG-Modding/FSD-Template)<br>[DRG-Modding/Header-Dumps](https://github.com/DRG-Modding/Header-Dumps) | 未設定 | コードは取り込んでいません。下記参照 |
| DeepL / Anthropic / OpenAI | 各社の利用規約 | APIキーは利用者が用意します。各社の規約は利用者の責任で遵守してください |

`docs/INTERNALS.md` に載せている関数シグネチャ・構造体定義は、**ゲーム本体の
実行ファイルから直接抽出して確認したもの**です（抽出手順も同ドキュメントに記載）。
上記コミュニティリポジトリは裏取りの相互参照として挙げているだけで、
それらのファイルを取り込んではいません。

### 免責

MIT License のとおり無保証です。UE4SS は Deep Rock Galactic 公式のMOD管理
（mod.io）の外側で動作します。導入・利用によって生じたいかなる不具合・
アカウント上の不利益についても、作者は責任を負いません。
