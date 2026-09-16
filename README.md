# DRGTranslate

Deep Rock Galactic のチャットを自動翻訳する MOD です。

- **受信**: 英語・韓国語・中国語（そのほかの言語も）のチャットを **日本語** にしてチャット欄へ表示
- **送信**: 日本語で打った発言を **英語・韓国語・中国語（簡体字）** に翻訳して送信
- **中継**: 自分がホストのときは、他の隊員の発言も**全員に見える形で**翻訳して流す

```
Karl: watch out, swarm incoming
[訳] Karl: 気をつけろ、大群がやってくる

（自分が「回復お願いします」と打つと）
You: 回復お願いします
You: Please heal me / 회복 부탁드립니다 / 请帮我治疗一下
```

ゲームに入れる MOD（UE4SS という MOD 用の外部ツールの上で動きます）と、
翻訳サービスを呼び出す常駐プログラム（`DRGTranslate.exe`）の2つで動きます。

> Ghost Ship Games とは無関係の非公式なファンプロジェクトです。MIT License。
> 詳細は[ライセンス](#ライセンス)を参照してください。

ソースから動かす方法・exe のビルド・内部の仕組みは [開発者向けガイド](docs/DEVELOPMENT.md) にまとめています。

---

## 導入

[**Releases**](https://github.com/astail/drg-translation/releases) から
`DRGTranslate-vX.Y.Z-win64.zip` をダウンロードして展開してください。
中身は次の4つです。

```
DRGTranslate.exe   これだけで動きます
.env.example       設定ファイルの雛形（全項目の説明つき）
はじめに.txt       3ステップの手引き
README.md / LICENSE
```

**`DRGTranslate.exe` をダブルクリックするだけ**です。Python のインストールも
`pip` も必要ありません（exe に同梱されています）。用意するものは
**翻訳サービスのAPIキーだけ**です。

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

設定が終わるとそのまま翻訳プロセスが常駐するので、窓を開いたままゲームを起動してください。

2回目以降はセットアップを飛ばして、すぐ常駐状態になります。
やり直したいときは `DRGTranslate.exe --setup` を実行してください。

> **ウイルス対策ソフトの警告について**
>
> この exe は署名していないため、Windows Defender や一部のセキュリティソフトが
> 警告を出すことがあります。PyInstaller で作った未署名の exe に共通して起きる
> 誤検知で、中身はこのリポジトリのソースそのものです。
> 気になる場合は exe を使わずソースから動かすこともできます
> （[開発者向けガイド](docs/DEVELOPMENT.md#ソースから使う)）。

`.env`（設定とAPIキー）と `cache.json` は **exe と同じフォルダ**に作られます。
書き込める場所に置いてください（`Program Files` の中などは避けてください）。

---

## 使い方

1. **`DRGTranslate.exe` を起動**（黒い窓が出ます。閉じないでください）
2. **Deep Rock Galactic を起動**
3. 普段どおりチャットするだけです

設定に不足があると、黒い窓の起動直後に警告が出ます。

```
provider=openai / 受信→ja / 送信→en,ko,zh
==============================================================
翻訳できる状態になっていません:
  .env に OPENAI_API_KEY を設定してください（https://platform.openai.com/api-keys）
==============================================================
```

**この警告が出ていなければ、そのままゲームを起動して大丈夫です。**

| 操作 | 動作 |
|---|---|
| 他人が英語/韓国語/中国語で発言 | 日本語訳が次の行に出る |
| 自分が日本語で発言 | 英語・韓国語・中国語に翻訳されて送信される |
| 自分が英語で発言 | そのまま送信（翻訳しない） |
| `/` `!` `.` で始まる発言 | 翻訳しない（コマンド用） |
| **自分がホストのとき** | 他人の発言の訳を全員のチャットにも流す（下記） |
| **F9** | 翻訳のON/OFF切り替え（OFF にすると中継の順番待ちも捨てます）<br>切り替えたことは `[DRGTranslate] 翻訳 OFF` として画面に出ます。他の隊員がいるホストのときだけは出せないので、黒い窓に出します |

> **ゲームの言語を「日本語」にしておいてください。**
> 日本語フォントが読み込まれていないと、翻訳文が豆腐（□□□）になります。

### 自分の発言の送られ方

翻訳はネットワーク越しなので、Enter を押した瞬間には結果が間に合いません。
そこで **打った日本語をそのまま送り、翻訳が届いたら2通目として送る**形にしています。

```
You: 回復お願いします
You: Please heal me / 회복 부탁드립니다 / 请帮我治疗一下
```

原文が残るので、味方に日本人がいればそのまま読めます。誤訳があったときも
元が何だったか分かります。

### 受信した訳が出る場所

**受信した訳がゲーム内のどこに出るか**は立場で変わります。ゲーム側に
「自分にだけ見せる」手段が乏しいためです。

| 立場 | 受信の訳 |
|---|---|
| クライアントとして参加 | チャット欄に出ます |
| ホスト（ソロ） | チャット欄に出ます（配信先が自分だけなので） |
| ホスト（他の隊員がいる） | 出しません。出すと全員に見えてしまうためです。<br>ただし中継が有効なら日本語の行がチャットに流れるので、結果的に読めます。<br>中継を切っている場合は `.env` の `DRGT_OVERLAY_ENABLED=true` で小窓に出せます |

### 自分がホストのときの中継

MOD を入れているのは自分だけなので、ふつうは訳文が見えるのも自分だけです。
**ホスト（部屋を立てた側）のときだけ**は、他の隊員の発言の訳を全員のチャットに
流せます。MOD を持っていない隊員どうしでも会話が通じるようになります。

発言者の言語は除いて訳し、**全部の言語をまとめて1行**で流します
（自分の発言を訳して送るときと同じ形です）。言語の目印は付けません。

```
Karl: watch out, swarm incoming          ← 英語の発言
You: Karl: 気をつけろ、大群が来るぞ / 조심해, 무리가 온다 / 小心，虫群来了
```

行頭の `Karl:` は「誰の発言の訳か」を示すものです（中継はホストの名前で
送られるため、これが無いと誰の発言だったのか分からなくなります）。

| 発言者の言語 | 流す訳 |
|---|---|
| 英語 | 日本語・韓国語・中国語 |
| 韓国語 | 日本語・英語・中国語 |
| 中国語 | 日本語・英語・韓国語 |
| 日本語 | 英語・韓国語・中国語 |
| それ以外（ロシア語など） | 日本語・英語・韓国語・中国語 |

日本語の発言も中継します。自分の画面には訳を出しませんが
（`DRGT_INCOMING_SKIP_LANGUAGES=ja`、読めるものを二重に出しても邪魔なため）、
他の言語の隊員には届けます。日本語で話す味方が MOD を持っていなくても、
その発言が外国語の隊員に伝わります。

- **クライアントとして参加しているときは何もしません。** 他人の部屋のチャットを
  勝手に埋めることはありません。
- **ソロ（ロビーに自分しかいない）のときも中継しません。** 読む相手がいないのに
  4言語ぶん訳しても無駄なので、訳は日本語だけ作って自分の画面に出します。
- 翻訳は受信ぶんと同じ **1回の API 呼び出しにまとめられます**（訳す言語は増えます）。
- `Rock and Stone!` のように訳しても原文と変わらない発言は流しません。
- 止めるときは `.env` に `DRGT_RELAY_ENABLED=false` を書いてください。
  流す言語や書式も `.env` の `DRGT_RELAY_*` で変えられます。
- 長すぎてゲーム側で切られる場合は、`DRGT_RELAY_MAX_LINE_CHARS=200` のように
  書くと、その文字数で行を分けて流します（既定の `0` は分けません）。

> チャットの流量は確実に増えます。少人数の身内部屋なら快適ですが、
> 野良で会話が多いときは `DRGT_RELAY_TARGETS=en` のように絞るのがおすすめです。

---

## 設定

### `.env` — 翻訳まわり

exe と同じフォルダにある **`.env`** をメモ帳で開いて編集します
（初回のセットアップで作られます）。書き換えたら `DRGTranslate.exe` を起動し直してください。

**すべての項目が既定値つきでコメントアウトされています。**
変えたい行の先頭の `#` を外すだけです。

```ini
# 使う翻訳サービス。deepl / claude / openai のどれか
DRGT_PROVIDER=openai

# OpenAI  https://platform.openai.com/api-keys
OPENAI_API_KEY=sk-...

# 翻訳先（カンマ区切り）。英語だけでいいなら en
#DRGT_OUTGOING_TARGETS=en,ko,zh
```

主な項目は次のとおりです。全項目の説明は `.env.example` に書いてあります。

| キー | 説明 |
|---|---|
| `DRGT_PROVIDER` | `deepl` / `claude` / `openai` |
| `DEEPL_AUTH_KEY`<br>`ANTHROPIC_API_KEY`<br>`OPENAI_API_KEY` | APIキー。使うサービスのものだけでOK |
| `DRGT_OUTGOING_TARGETS` | 送信時の翻訳先。既定 `en,ko,zh`（英語・韓国語・簡体字中国語）。英語だけなら `en`、繁体字は `zh-tw` |
| `DRGT_RELAY_ENABLED` | ホストのとき、他人の発言の訳を全員に流すか。既定 `true` |
| `DRGT_RELAY_TARGETS` | 中継先の言語。既定 `ja,en,ko,zh`（発言者の言語は自動で除外） |
| `DRGT_RELAY_MAX_LINE_CHARS` | 中継の1行の上限文字数。既定 `0`（全言語を1行にまとめる） |
| `DRGT_INCOMING_FORMAT` | 表示形式。`{sender}` `{text}` `{lang}` `{original}` が使えます |
| `DRGT_INCOMING_SKIP_LANGUAGES` | この言語は自分のチャットに訳を出さない。既定 `ja`（ホストの中継はこの設定に関わらず動きます） |
| `DRGT_CACHE_ENABLED` | 翻訳結果を保存するか |
| `DRGT_OVERLAY_ENABLED` | ゲーム内表示が使えないときの保険となる小窓 |
| `DRGT_OVERLAY_HIDE_AFTER` | 小窓を引っ込めるまでの秒数。既定 `12`、`0` で出しっぱなし |

OS 側に同名の環境変数がある場合は、そちらが `.env` より優先されます。

### 翻訳サービスの選択

3つから選びます。どれも APIキーが必要です。

| provider | 特徴 |
|---|---|
| `deepl`（既定） | 機械翻訳としては最も自然。**月50万文字まで無料** |
| `claude` | **スラング・略語・誤字に強い**。`gg` `bulk inc` `res me` を文脈で訳せる |
| `openai` | 同上。OpenAI互換エンドポイント（ローカルLLM等）にも向けられる |

普通の会話が中心なら `deepl` で十分です。`Rock and Stone` のような定型句は
用語集で処理されるので、どのサービスでも同じ訳になります。
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

モデルに合わせて送る内容は自動で調整するので、`DRGT_CLAUDE_EFFORT` と
`DRGT_CLAUDE_REFUSAL_FALLBACK` の `auto` はそのままにしておいて問題ありません。

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

- **1回の送信で複数言語をまとめて訳します。** 英語＋韓国語＋中国語でも API 呼び出しは1回です。
- **API を呼ぶのは実際に発言したときだけです。** 入力中には翻訳を投げないので、
  打ちかけてやめた文章に課金されることはありません。
- **暴言などで翻訳を拒否されることがあります。** その1件だけ翻訳されず、
  ゲームの動作には影響しません。`claude-opus-5` など対応モデルを使う場合は
  自動で別モデルへ回す設定（`DRGT_CLAUDE_REFUSAL_FALLBACK`）が働きます。
- 応答は機械翻訳よりわずかに遅めです。原文の直後に翻訳が届くまで
  少し間が空きます。
- チャット本文が Anthropic / OpenAI に送信されます。外部に出したくない場合は
  上記のとおり `openai` + `DRGT_OPENAI_BASE_URL` でローカルLLMに向けてください。

### `glossary.json` — 用語集

`Rock and Stone!` のような定型句を、APIを経由せず即座に置き換えます。
DRG の頻出フレーズを最初から登録済みです（exe に同梱されています）。

自分で追記したいときは、[bridge/glossary.json](bridge/glossary.json) をダウンロードして
**exe と同じフォルダ**に置き、編集してください。同梱のものの代わりにそちらが使われます。

日本語の用語は [DRG 日本語 Wiki](https://wikiwiki.jp/rockandstone/) に合わせています
（ナイトラ / ビスモル / エノアパール など）。`Bulk Detonator` は正式には
「グリフィッドバルクデトネーター」ですが、日本語圏では **デトネーター** で通じるため
そちらを採用しています。

```json
{
  "incoming": { "leaf lover": "リーフラバー（軟弱者）" },
  "outgoing": { "ありがとう": { "en": "Thanks!", "ko": "고마워요!", "zh": "谢谢！" } }
}
```

キーは空白・記号・大文字小文字を無視して照合されるので、`rock and stone` と
`Rock and Stone!!` は同じ扱いになります。

### `config.lua` — ゲーム内の挙動

ゲームフォルダの `FSD\Binaries\Win64\Mods\DRGTranslate\Scripts\config.lua` にあります
（UE4SS の版によっては `Win64\ue4ss\Mods\...`）。

| 項目 | 説明 |
|---|---|
| `outgoing.enabled` | 自分の日本語発言を翻訳して送るか |
| `outgoing.ignore_prefixes` | この文字で始まる発言は翻訳しない |
| `outgoing.min_length` | この文字数未満は翻訳しない |
| `incoming.skip_own` | 自分の発言は翻訳しない |
| `host_relay.enabled` | ホストのとき他人の発言の訳を全員に流すか |
| `host_relay.interval_ms` | 中継を送る間隔。発言が重なったときの詰まり防止。既定 `700` |
| `host_relay.sender` | 中継行の送信者名。`self`（自分）/ `original`（元の発言者） |
| `display.strategy` | 翻訳の表示方法。`auto` / `gamestate` / `widget` / `off` |
| `debug` | UE4SS コンソールに詳細ログを出す |

`config.lua` を書き換えたら **ゲームを再起動**してください。
`DRGTranslate.exe --setup` をやり直すと MOD が入れ直され、編集していた
`config.lua` は `Mods\DRGTranslate.bak` に退避されます。

---

## 動作確認の状況

- 実機（ソロのホスト）で、日本語の送信・受信の訳・中継・F9 の切り替え・
  日本語/韓国語/中国語の表示までは確認しています。
- 実際の翻訳を確認したのは Claude だけです。**DeepL / OpenAI は未確認**です。
- **複数人のロビーで、中継が他の隊員に届くところはまだ確認していません。**
- 小窓（`DRGT_OVERLAY_ENABLED=true`）の実機での見え方も未確認です。

詳しくは [docs/TESTING.md](docs/TESTING.md) を参照してください。

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

  どちらも v0.2.1 以降のセットアップが自動でやります。古い版で入れた場合は
  `DRGTranslate.exe --setup` をもう一度実行すると直ります。
  それでも落ちる場合は `mods.txt` の `DRGTranslate : 1` を `: 0` にして起動し、
  MOD 本体が原因かどうかを切り分けてください。

  なお v0.2.2 には、起動直後に落ちる不具合がありました。v0.2.3 で解消しています。

**MODが読み込まれない**
: `FSD\Binaries\Win64` に `dwmapi.dll` と `UE4SS.dll` があるか確認してください。
  `Mods\mods.txt` に `DRGTranslate : 1` の行が必要です。
  読み込み状況は同じフォルダの `UE4SS.log` に出ます（起動のたびに書き直されます）。
  なお UE4SS の別窓コンソールは安定性のため既定で切ってあります。見たいときは
  `UE4SS-settings.ini` の `GuiConsoleEnabled` を `1` にしてください。

**「bridge との接続が切れました」と出る**
: `DRGTranslate.exe` が動いていません。ゲームより先に起動してください。

**翻訳が表示されない**
: `FSD\Binaries\Win64\UE4SS.log` に `hook 登録: ...` が2行出ているか確認してください。
  出ていない場合、ゲームのアップデートで関数名が変わった可能性があります。
  もっと詳しく見たいときは `config.lua` の `debug = true` にしてください。
  表示だけができない場合は `.env` の `DRGT_OVERLAY_ENABLED=true` にすると
  小窓に出せます（ゲームの表示設定を「ウィンドウ(フルスクリーン)」にしてください）。

**日本語が □□□ になる**
: ゲームの言語設定を日本語にしてください。

**自分の発言だけ翻訳を止めたい**
: `config.lua` の `outgoing.enabled` を `false` にしてください。受信の翻訳だけが残ります。

**他の隊員がいる部屋でホストをすると、受信の訳がチャット欄に出ない**
: 仕様です。ゲーム側に「自分にだけ見せる」手段がなく、チャット欄に出すと
  訳文が全員に見えてしまうためです（[受信した訳が出る場所](#受信した訳が出る場所)）。
  中継が有効なら日本語の行がチャットに流れるので、それで読めます。
  中継を切っている場合は `.env` の `DRGT_OVERLAY_ENABLED=true` にすると小窓に出せます。
  小窓は翻訳が届いたときだけ出て、12秒で引っ込みます（`DRGT_OVERLAY_HIDE_AFTER`）。
  ゲームの表示設定は「ウィンドウ(フルスクリーン)」にしないと前面に出ません。

---

## 注意

- UE4SS は Deep Rock Galactic 公式の MOD 管理（mod.io）の外側で動く仕組みです。導入は自己責任でお願いします。
- 翻訳して送った発言は当然ながら他のプレイヤーにも見えます。誤訳もそのまま送られます。
- **翻訳のため、他プレイヤーの発言を含むチャット本文が外部サービス（DeepL / Anthropic /
  OpenAI）へ送信されます。** 発言者本人の同意は得られません。外部に出したくない場合は
  `openai` + `DRGT_OPENAI_BASE_URL` でローカルLLMに向けてください。
- チャット本文は `cache.json`（exe と同じフォルダ）にも保存されます。不要なら `.env` の
  `DRGT_CACHE_ENABLED=false` にしてください。
- `claude` / `openai` は従量課金です。実際に発言したときだけ API を呼びます。

---

## 開発者向け

| | |
|---|---|
| [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) | 仕組み、ソースから使う方法、exe のビルド、リリース、ファイル構成 |
| [docs/TESTING.md](docs/TESTING.md) | テストの実行方法と、動作確認の状況の詳細 |
| [docs/INTERNALS.md](docs/INTERNALS.md) | 解析した DRG 側 API のメモ |

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
| [UE4SS](https://github.com/UE4SS-RE/RE-UE4SS) | MIT | **同梱していません**。セットアップ時に公式リリースから取得します |
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
