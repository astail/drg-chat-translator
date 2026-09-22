# 内部仕様メモ

DRGTranslate が依存している Deep Rock Galactic 側の API と、その調べ方。

## 調査の出典

一次情報は **ゲーム本体の実行ファイル**です。UE はリフレクション用の名前を
name pool に残すので、そこから直接拾えます。

```bash
strings -n 5 FSD-Win64-Shipping.exe | grep -iE "chat|message"
```

引数の型・並びは、この抽出結果とコミュニティの公開ダンプ
（[FSD-Template](https://github.com/DRG-Modding/FSD-Template) /
[Header-Dumps](https://github.com/DRG-Modding/Header-Dumps)）を突き合わせて確認しました。
これらのリポジトリはライセンスが設定されていないため、**ファイルの取り込みはせず、
裏取りの参照先として挙げるにとどめています。**

以下に記載しているのは、本MODが呼び出す・フックする対象を説明するために必要な
API のシグネチャだけです。ゲームのコードやアセットは含みません。

## チャット関連の定義

### 構造体

```cpp
// Source/FSD/Public/FSDChatMessage.h
USTRUCT(BlueprintType)
struct FFSDChatMessage {
    EChatMessageType MsgType;    // ES_Chat = 0, ES_Game = 1
    FString          Sender;
    EChatSenderType  SenderType; // NormalUser / DeluxUser / Developer / Streamer / Modder
    FString          Msg;
    FUniqueNetIdRepl SenderNetID;
};
```

`FFSDLocalizedChatMessage` はゲーム側の定型メッセージ用（`FText Msg` と `TArray<FText> Arguments`）。
プレイヤーの発言は通らないので、この MOD では扱っていません。

### 受信

```cpp
// Source/FSD/Public/FSDGameState.h
UFUNCTION(BlueprintCallable, NetMulticast, Reliable)
void ClientNewMessage(const FFSDChatMessage& Msg);
```

全プレイヤーの発言がここを通ってクライアントへ届くので、受信の hook 地点として最適です。
UE4SS の `RegisterHook` は `/Script/` 始まりのパスなら **pre コールバック**が使えます。

```lua
RegisterHook("/Script/FSD.FSDGameState:ClientNewMessage", function(Context, MsgParam)
    local msg = MsgParam:get()
    local text = msg.Msg:ToString()
end)
```

### 送信

```cpp
// Source/FSD/Public/FSDPlayerController.h
UFUNCTION(BlueprintCallable, Reliable, Server)
void Server_NewMessage(const FString& Sender, const FString& Text, EChatSenderType SenderType);
```

クライアントから呼ぶサーバRPC。MOD はこれを **自分で呼んで発言する** のに使い、
hook のほうは「自分が今送った」という合図を取るためだけに使います。

> ⚠ **この hook の中で `Sender` / `Text`（FString 引数）を読んではいけません。**
> 実際のチャット欄から送信すると、この関数は Blueprint 側から呼ばれます。
> そのとき引数を `:get()` で読むとプロセスごと落ちます（`pcall` では止まりません）。
> Lua から同じ関数を呼んだ場合は UE4SS が自前で引数バッファを用意するので
> 読めてしまい、その差が原因の特定を難しくしました。
>
> `Context`（呼び出し元の PlayerController）は安全に読めます。そのため MOD は
> `Context:get()` と `IsLocalController()` だけを使い、本文は後述の
> `ClientNewMessage` 側で受け取ります。

> ホストとして遊んでいる場合、他プレイヤーの `Server_NewMessage` もサーバ側で実行されるため
> 同じ hook を通ります。`IsLocalController()` で自分の分だけに絞る必要があります。

### ローカル表示

翻訳文は **自分にだけ** 見えなければいけません。

| 方法 | クライアント | ホスト |
|---|---|---|
| `AFSDGameState::PostGameMessage(FString)` | ローカルのみ ✅ | **全員に配信されてしまう** ❌（ソロなら問題ない） |
| `UHUD_Chat_C::"Add Chat Message"(FFSDChatMessage)` | ローカルのみ（のはず） | ローカルのみ（のはず）。ただし実機では呼び出しが失敗した |

`PostGameMessage` は内部で `ClientNewMessage`（NetMulticast）を呼んでいると見られます。
UE では **クライアントから NetMulticast を呼ぶとローカルでしか実行されない**ため、
クライアント側では安全に使えます。一方ホスト（権限あり）が呼ぶと全員に飛びます。

そのため MOD（`config.lua` の `display.strategy = "auto"`）は `HasAuthority()` と人数を見て、
- クライアント → `PostGameMessage`
- ソロのホスト（`PlayerArray` が1人）→ `PostGameMessage`（全員＝自分だけなので問題ない）
- 同僚がいるホスト → ゲーム内には出さない。自分の言語は中継先に入っているので、
  全員に流す中継行で読む（中継を切っているならオーバーレイで）

と切り替えています。判定できなかった場合はホスト扱い（＝安全側）にしています。
チャットウィジェットを直接呼ぶ方法は、実機で `Add Chat Message` / `NewMesssage` /
`NewMessage` の3つとも失敗した（`pcall` で捕まりゲームは落ちなかった）ので、
`auto` では使っていません。`display.strategy = "widget"` のときだけ試します。

### 中継（ホストのときだけ全員に配る）

ローカル表示とは逆に、**わざと全員に届けたい**のがホストの中継です。
使うのは `Server_NewMessage`（自分の翻訳送信とまったく同じ経路）で、
`PostGameMessage` は使いません。ホストの `PostGameMessage` も全員に届きますが、
配信されるかどうかが権限まかせになるより、通常のチャットとして送るほうが確実で、
受け取る側の見え方も普通のチャットと同じになるためです。

判定は `AFSDGameState::HasAuthority()`。ローカル表示側の判定と既定値が逆
（判定できないときローカル表示は「ホスト扱い」、中継は「中継しない」）ですが、
どちらも **確信が持てないなら他人に見せない** 方向へ倒したものです。

中継の訳はホストの名前で全員のチャットに流れるので、流す前に確かめます
（`drg_bridge.py` の `relay_text_ok`）。改行や制御文字は1行に畳み、原文に比べて
長すぎるもの・`/` で始まるものは捨てます。長さは原文の3倍（最低80文字）までで、
英語やロシア語など漢字・かな・ハングルを使わない言語への訳では、原文の漢字・かな・
ハングルを1文字2文字分と数えます（中国語の35文字の発言の英訳は140文字を超えるため）。
英語などラテン文字の言語は下の文字の確認が効かないので、上限はそれに届く程度にとどめています。
LLM（claude / openai）のときは、
日本語・韓国語・中国語・ロシア語への訳にその言語の文字が1つも無ければ捨てます。
他の隊員の発言で翻訳の指示を乗っ取られ、訳とは別物が返ってきたときに、そのまま
ホストの名前で流さないためです（DeepL は指示を受け付けないので、文字の確認はしません）。

中継行は全言語を `/` でつないだ 1行です（`Karl: 気をつけろ … / 조심해 … / 小心 …`）。
1言語1行で流していた頃は1つの発言でチャットが3〜4行埋まり、読む側が追えませんでした。
それでも複数の発言が重なると行は溜まるので、`700ms` 間隔で1行ずつ送ります。
まとめて送ると1フレームで `Server_NewMessage` を連打することになるためです。

言語の目印（`[JP]` など）は付けません。チャット欄は狭く、訳文は文字の
見た目で区別がつくためです。行頭の発言者名だけは残しています
（中継はホストの名前で送られるので、これが無いと誰の発言か分からなくなります）。

翻訳のループ防止は2段構えです。自分が流した行は `own_sent` で弾きます。
他人（別のホスト）が流した行は、**送信者と本文の食い違い**で見分けます
— 中継行は「ホストの名前で届くのに、本文は別人の名前で始まる」ので、
`Kiyo: Karl: …` のような行を中継行とみなします。ただし
`warning: swarm incoming` のような普通の発言を巻き込まないよう、
行頭の名前が `seen_senders`（少し前にチャットで見かけた人）にある場合だけです。
中継されるのは全員が受け取った発言の訳なので、元の発言者は必ず直前に喋っています。
さらに、本文が複数の訳を区切り（` / `）でつないだ形のときに限ります。
`Karl: 了解` のような、直前に喋った人への普通の返事を捨てないためです。
中継先が1言語だけのときや、ホストが区切りを変えているときは中継行と見なせず
訳し直してしまいますが、1行増えるだけで、返事が消えるよりは害が小さいと判断しています。

### チャットUI

```cpp
// /Game/UI/Chat/HUD_Chat.HUD_Chat_C
class UHUD_Chat_C : public UUserWidget {
    UEditableTextBox* NewChatEdit;      // 入力欄。MOD では使わない
    UEditableTextBox* OutsiteChatbox;
    UEditableTextBox* InputChatBox;
    bool IsChatOpen;

    void SendChatMessage(const FText& InText, TEnumAsByte<ETextCommit::Type> CommitMethod);
    void NewMesssage(const FFSDChatMessage& Message);   // 原文ママ（s が3つ）
    void Add Chat Message(FFSDChatMessage Msg);          // 関数名に空白が入っている
};
```

スペースリグ側の `WND_SpaceRig_Chat` は `HUD_Chat_C` を内包しているだけなので、
`HUD_Chat_C` を押さえれば両方カバーできます。

MOD が使うのは `Add Chat Message`（ローカル表示）だけです。入力欄
（`NewChatEdit` ほか）には触れません。翻訳が届いたら2通目として送る方式なので、
入力中の状態を知る必要がないからです。

自分の発言の本文も `ClientNewMessage` 側で受け取ります。送信した発言は自分にも
配信されて戻ってくるので、`Server_NewMessage` の hook で立てた合図と突き合わせて
「これは自分の発言だ」と判定し、そこで初めて自分のプレイヤー名も分かります。
ただし名前が分からないうちは、合図のあと約2秒（`main.lua` の `NAME_DECIDE_MS`）のあいだに
届いた発言を集め、送信者が1人だけのときに限ってその人を自分とします。自分の戻りより先に
他の隊員の発言が届くことがあり、最初に届いた発言を自分のものと決めると、その隊員の発言を
自分の発言として訳し、その人の名前で送ってしまうためです。送信者が複数いたら名前は覚えず、
集めた発言はすべて他の隊員の発言として訳します（次に自分が発言したときにまた試す）。
このため、最初の発言だけは訳の2通目が約2秒遅れます。
名前を `PlayerState` から辿りに行かないのは、その経路で過去に2種類のクラッシュを
出したためです（hook の中で辿る／ループから毎秒辿る、のどちらも落ちました）。

## UE4SS の Lua API で押さえておくこと

| | |
|---|---|
| `RegisterHook(path, pre, post)` | `/Script/` 始まりのみ pre が使える。Blueprint (`/Game/...`) は post のみ |
| コールバック引数 | すべて `RemoteUnrealParam`。`:get()` で取得、`:set()` で書き換え |
| フックは中断できない | 「呼ばせない」ことはできないので、引数を空にするなどで代替する |
| `LoopAsync` はゲームスレッド外 | UObject に触るときは `ExecuteInGameThread` で包む |
| ソケットが無い | 外部プロセスとの通信は `io` によるファイル経由 |

## IPC プロトコル

`%APPDATA%\DRGTranslate\` に置かれるテキストファイルでやり取りします。
追記専用の2本はそれぞれ書き手が片側だけなので、書き込みは競合しません。

```
to_bridge.txt   mod -> bridge（mod が追記 / bridge が読む）
to_game.txt     bridge -> mod（bridge が追記 / mod が読む）
bridge.alive    bridge の生存確認。bridge が1秒ごとに「<版> <起動番号> <UNIX時刻>」で上書き
game.alive      mod の生存確認。mod が1秒ごとに「<版> <UNIX時刻>」で上書き
bridge.lock     bridge が動いている間だけ OS の排他ロックを取るファイル（中身は空）
```

1行1メッセージ、TAB 区切り。各フィールドは `\` `\t` `\r` `\n` をエスケープ済み
（`util.lua` の `esc` / `unesc` と `drg_bridge.py` の `esc` / `unesc` は同じ規則）。
どちらの側も、読み取りは「最後の改行まで」を切り出してから行に分けるので、
書き込みの途中を読んでも行や文字が欠けることはありません。

### mod → bridge

| | |
|---|---|
| `HELLO <version>` | 接続開始。bridge とつながるたびに送る（下記「起動と再起動」）。bridge は自分の `HELLO` を返し、版が違えば警告する（下記） |
| `NAME <playername>` | 自分のプレイヤー名 |
| `REQ <id> in <sender> <text> <host>` | 受信文を訳す（既定は日本語へ）。`host`=`1` なら中継用の訳も一緒に |
| `REQ <id> out <sender> <text> <host>` | 自分の発言を翻訳（結果を2通目として送る）。mod は中身を見ずに送り、訳さない発言（OFF・翻訳元の言語でない・短すぎる・`/` などで始まる）なら bridge が空の結果を返す。判定は settings.ini の `DRGT_OUTGOING_*` だけで決まる |
| `DISPLAY ok\|fail [理由]` | ゲーム内表示ができているか。理由が `host` なら、同僚がいるホストなので設計どおり出していない（失敗ではない。bridge はそのように表示する） |
| `TOGGLE ON\|OFF` | F9 で翻訳を切り替えた。bridge はログとオーバーレイに出す |
| `PING` | bridge が `NOTE` で応答する。いまは mod から送っていない（手で確かめる用） |

bridge は **どの `REQ` にも必ず `RES` か `ERR` を返します**。項目が足りない、
種別が分からない、翻訳に失敗した、のいずれでも `ERR` を返すので、mod 側が
返事を待ち続けることはありません。

### bridge → mod

| | |
|---|---|
| `HELLO <version>` | `HELLO` への返事 |
| `RES <id> <kind> <srclang> <text> [中継行...]` | 結果。`text` が空なら「何もしない」。6番目以降はホストが全員に流す行（ふつうは全言語まとめて1行） |
| `ERR <id> <message>` | 失敗。`message` はログ用で、ゲーム内には出さない |
| `SAY <text>` | この文字列をチャットに送信せよ（オーバーレイの入力欄から） |
| `NOTE <text>` | ゲーム内にローカル表示だけする。ゲームの言語によっては日本語などのフォントが無いので、**本文は英数字で書く** |

`DIAG` / `SIMSAY` は開発者が `to_game.txt` に手で書いて使う診断用で、
`config.lua` の `debug = true` のときだけ mod が受け付けます。

- `DIAG` … MOD の状態（GameState と PlayerController を見つけられたか、ホストか、人数、
  自分の名前、ON/OFF、中継の順番待ち）を UE4SS のコンソールに出す
- `SIMSAY<TAB>本文<TAB>送信者名` … その送信者名と本文で `Server_NewMessage` を呼ぶ。
  チャット欄から打ったときと同じ経路（`on_outgoing` の合図 → `ClientNewMessage` で戻る）を
  通るので、実機で自分や他の隊員の発言を模すのに使う

> `SIMSAY` で他の隊員の発言を模すときは、先に自分の名前で1回流して、MOD に自分の名前を
> 覚えさせてください。名前が分からないうちは、`Server_NewMessage` の直後（約2秒）に届いた
> 発言の送信者が1人だけならそれを自分の名前と学習するので、最初に `Karl` で流すと自分の名前が
> `Karl` になり、以降の `Karl` の発言が自分の発言として扱われます。

### 起動と再起動

- 同じ通信フォルダで bridge は1つしか動かない。bridge は起動時に `bridge.lock` の排他ロックを取り、
  取れなければ（すでに動いていれば）ファイルに触らずに終了する。2つ動くと、どちらも同じ `REQ` を
  読んで翻訳 API を二重に呼ぶため。`--test` とウィザードの疎通確認は通信フォルダを使わない
- mod は起動時（ゲームの起動時・MOD の再読み込み時）に両ファイルを空にする
- bridge も起動時に両ファイルを空にする。空にしないと、bridge を再起動したときに
  `to_bridge.txt` を頭から読み直し、前回までに処理した `REQ` を二重に翻訳・送信してしまう
- 相手が先にファイルを空にしても、読む側は「ファイルが読み取り位置より小さくなった」
  ことに気づいて読み取り位置を 0 に戻すので、どちらを先に起動しても復帰する
- bridge が起動時に `to_bridge.txt` を空にすると、それより前に mod が書いた `HELLO` /
  `NAME` も消える。そのため mod は `HELLO`（名前が分かっていれば `NAME` も）を、起動時ではなく
  **bridge とつながるたびに**送る。つながったとき・切断のあとにつながり直したときに加えて、
  `bridge.alive` の起動番号が変わったとき（切断に気づく前の約4秒以内に bridge が
  再起動したとき）も送り直す（`ipc.lua` の `check_alive` / `set_on_connect`）

bridge の再起動で `to_bridge.txt` が空になると、mod が書いたがまだ読まれていなかった
`REQ` は失われます。mod は返事の来ない要求を **60 秒**で諦めて捨てるので
（`ipc.lua` の `PENDING_TTL_MS`）、待ち続けて溜まることはありません。

### 生存確認

`*.alive` の中の UNIX 時刻（壁時計、行末の数字）を相手側が読み、現在時刻との差で判定します。
`bridge.alive` の起動番号（bridge の起動時刻のミリ秒）は、再起動に気づくためだけに使います。
起動番号の無い古い形（「<版> <UNIX時刻>」）も読めます。

| | 見ているファイル | 「生きている」とみなす条件 |
|---|---|---|
| mod | `bridge.alive` | 差が −5〜10 秒。外れても4回（約4秒）続くまでは切断とみなさない |
| bridge | `game.alive` | 差が −5〜20 秒、または直近 20 秒以内に mod から何か届いた |

両側のしきい値はそろっていません（なぜこの値なのかは記録に残っていません）。
変えるときは、両方の実装とこの表をあわせて直してください。

### 版の確認

`HELLO` で互いの版を送り合い、違っていれば警告します。MOD はゲームフォルダに
入っているので、exe だけ更新して MOD が古いまま、という状態になりやすいためです。

- bridge: ログに警告を出し、ゲーム内にも `NOTE` で英語の案内を出す
- mod: UE4SS のコンソールに警告を出す

版は `bridge/drg_bridge.py` の `VERSION` と `main.lua` の `MOD_VERSION` で、
リリースの CI がこの2つとタグの一致を確かめています。
