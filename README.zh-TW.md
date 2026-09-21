# DRG Chat Translator (DCT)

[日本語](README.md) | [English](README.en.md) | [한국어](README.ko.md) | [简体中文](README.zh.md) | **繁體中文** | [Русский](README.ru.md)

一個自動翻譯 Deep Rock Galactic 聊天的 MOD。

*與 Ghost Ship Games 無關的非官方粉絲專案。*

| 能做什麼 | 房主（連線） | 房主（單人） | 用戶端 |
|---|:---:|:---:|:---:|
| **接收** — 把同伴矮人的聊天翻成你的語言，顯示在聊天欄 | 〇 | 〇 | 〇 |
| **發送** — 把你說的話翻成其他語言再送出 | 〇 | 〇 | 〇 |
| **轉發** — 把同伴矮人發言的譯文送到所有人的聊天裡 | 〇 | × | × |

「房主」是自己開房的一方，「用戶端」是加入別人房間的一方。

安裝時會先問你用哪種語言閱讀，並依此寫好設定。選擇繁體中文後，日語、英語、韓語等發言會
被翻成**繁體中文**，你用中文打的話會被翻成**日語 · 英語 · 韓語 · 簡體中文**。哪種語言翻
成哪種語言都可以在設定檔（`settings.ini`）中修改（[變更語言](#變更語言)）。

```
Karl: watch out, swarm incoming
[TL] Karl: 小心，蟲群來了

（當你打出「請幫我治療一下」時）
You: 請幫我治療一下
You: 回復お願いします / Please heal me / 회복 부탁드립니다 / 请帮我治疗一下
```

它由兩個部分組成：放進遊戲裡的 MOD（執行在 UE4SS 這個 MOD 用外部工具之上），以及呼叫翻譯
服務的常駐程式（`DRGTranslate.exe`）。

> 與 Ghost Ship Games 無關的非官方同好專案。MIT License。
> 詳情請見[授權條款](#授權條款)。

從原始碼執行、建置 exe、內部運作方式都整理在[開發者指南](docs/DEVELOPMENT.md)（日文）中。

---

## 開始之前：準備翻譯服務的 API 金鑰

翻譯交給外部的翻譯服務處理。**開始使用之前，請先在下列服務中任選一個註冊並建立
「API 金鑰」。** API 金鑰是讓本程式代你使用該服務的一串文字，會在首次啟動的安裝過程中
貼上。事先沒有準備好的話，安裝過程會中途停住。

| 服務 | 特點 | 費用 | 註冊 · 建立金鑰 |
|---|---|---|---|
| **DeepL**（預設） | 機器翻譯中最自然的 | 有免費額度。用完後轉付費方案 | https://www.deepl.com/pro-api |
| **Claude**（Anthropic） | 擅長俚語、縮寫和錯字。能依上下文翻譯 `gg` `bulk inc` `res me` | 按用量付費。使用預設的 Claude Haiku 4.5 時，**1000 次翻譯約 $0.5** | https://platform.claude.com/settings/keys |
| **OpenAI** | 擅長俚語、縮寫和錯字。能依上下文翻譯 `gg` `bulk inc` `res me` | 按用量付費。使用預設的 gpt-4o-mini 時，**1000 次翻譯不到 $0.1** | https://platform.openai.com/api-keys |

若以一般對話為主，DeepL 就夠了。想在縮寫和打字錯誤較多的公開連線中提高準確度，就選
Claude 或 OpenAI。像 `Rock and Stone` 這種固定說法由術語表處理，所以用哪個服務譯文都
一樣。

- 費用和免費額度的條件可能變動。註冊前請確認各服務自己的價格頁面。
- **不要把 API 金鑰告訴別人。** 被他人使用的話，費用會算在你頭上。

---

## 安裝

從 [**Releases**](https://github.com/astail/drg-chat-translator/releases) 下載
`DRGTranslate-vX.Y.Z-win64.zip` 並解壓縮。裡面有：

```
DRGTranslate.exe      只要這個就能運作
settings.example.ini  設定檔範例（含全部項目的說明。英文）
README.txt            簡單的指引
LICENSE               授權（MIT）
```

**只要按兩下 `DRGTranslate.exe`。** 沒有別的東西需要安裝。你要準備的只有**翻譯服務的 API
金鑰**（[開始之前](#開始之前準備翻譯服務的-api-金鑰)）。

首次啟動時會依下列順序引導。**先問語言，之後的說明都用你選的語言顯示。**

```
[1] 言語を選んでください / Choose your language
      セットアップの案内と、他の人の発言の訳がこの言語になります。
      Setup and the chat you read are shown in this language.
      1) 日本語 (ja)
      2) English (en)
      3) 한국어 (ko)
      4) 简体中文 (zh)
      5) 繁體中文 (zh-tw)
      6) Русский (ru)
    番号 / number [1]: 5
    OK  將使用 繁體中文（接收 -> zh-tw / 發送 -> ja,en,ko,zh）
[2] 正在尋找 Deep Rock Galactic
    OK  G:\SteamLibrary\steamapps\common\Deep Rock Galactic
[3] 正在檢查 UE4SS
    !!  尚未安裝 UE4SS。MOD 需要它才能運作。
    現在下載並安裝嗎？ (Y/n):
[4] 正在複製 MOD
    OK  ...\Mods\DRGTranslate
    OK  已寫入 mods.txt（DRGTranslate : 1）
[5] 請選擇翻譯服務
      1) DeepL    機器翻譯。有免費額度
      2) OpenAI   擅長俚語和錯字。按用量計費
      3) Claude   擅長俚語和錯字。按用量計費。預設用最便宜的 Haiku
    編號 [1]:
    請貼上 API 金鑰（留空則取消）:
[6] 試著翻譯一次
      watch out, swarm incoming
        → 小心，蟲群來了
    OK  翻譯成功
```

這裡選的語言會記在 `settings.ini` 的 `DRGT_UI_LANG`，第二次之後啟動也會沿用（黑色視窗裡
的訊息也會是該語言）。

設定完成後翻譯程式就會直接常駐，請保持視窗開啟並啟動遊戲。

第二次之後會跳過安裝過程，直接進入常駐狀態。

**想重新走一次安裝過程時**，刪除 exe 同一資料夾中的 `settings.ini`，再啟動
`DRGTranslate.exe`，就會從最開始重來（API 金鑰也要重新輸入，請先準備好）。

> **關於防毒軟體的警告**
>
> 這個 exe 沒有簽章，因此 Windows Defender 和部分安全軟體可能會發出警告。這是用
> PyInstaller 製作的未簽章 exe 常見的誤判，內容就是本儲存庫的原始碼本身。如果介意，也可
> 以不用 exe 而從原始碼執行（[開發者指南](docs/DEVELOPMENT.md)，日文）。

`settings.ini`（設定和 API 金鑰）與 `cache.json` 會建立在 **exe 所在的同一資料夾**。
請放在可寫入的位置（避免放在 `Program Files` 之類的目錄裡）。

---

## 使用方式

1. **啟動 `DRGTranslate.exe`**（會出現黑色視窗，請不要關閉）
2. **啟動 Deep Rock Galactic**
3. 像平常一樣聊天就好

設定不完整時，黑色視窗啟動後會立刻出現警告。

```
provider=openai / 接收 -> zh-tw / 發送 -> ja,en,ko,zh
==============================================================
還不能進行翻譯:
  請在 settings.ini 中設定 OPENAI_API_KEY（https://platform.openai.com/api-keys）
==============================================================
```

**只要沒有出現這個警告，直接啟動遊戲就沒問題。**

| 情況 | 行為 |
|---|---|
| 同伴矮人用日語/英語/韓語發言 | 中文譯文出現在下一行 |
| 你用中文發言 | 被翻成日語 · 英語 · 韓語 · 簡體中文後送出 |
| 你用中文以外的語言發言 | 原樣送出（不翻譯） |
| 以 `/` `!` `.` 開頭的發言 | 不翻譯（留給指令用） |
| **你是房主時** | 同伴矮人發言的譯文也會送到所有人的聊天（[見下](#我是房主時的轉發)） |
| **F9** | 切換翻譯開關（關閉時也會丟掉等待轉發的佇列）<br>切換結果會以 `[DRGTranslate] Translation OFF` 顯示在畫面上（為了讓遊戲語言是任何語言的人都看得懂，MOD 在遊戲裡輸出的文字都用英數字）。只有在有同伴矮人的房主狀態下無法顯示，這時會顯示在黑色視窗裡 |

上表中的語言以選擇繁體中文為前提。[變更語言](#變更語言)後，表中的「中文」會變成你選的
語言。

> **請把遊戲語言設為你閱讀的語言。**
> 如果遊戲字型裡沒有相應的文字，譯文會顯示成方塊（□□□）。

### 你自己的發言是怎麼送出去的

翻譯要經過網路，按下 Enter 的瞬間結果還來不及回來。因此採用**先把你打的原文照樣送出，
譯文到達後再以第二則訊息送出**的方式。

```
You: 請幫我治療一下
You: 回復お願いします / Please heal me / 회복 부탁드립니다 / 请帮我治疗一下
```

原文保留下來，所以如果有懂中文的同伴可以直接讀，出現誤譯時也能知道原本說的是什麼。

### 我是房主時的轉發

裝了 MOD 的只有你自己，所以通常也只有你看得到譯文。**只有在你是房主（連線）時**，才能把
同伴矮人發言的譯文送到所有人的聊天裡。這樣，兩個都沒裝 MOD 的矮人之間也能溝通。

會去掉發言者本人的語言後翻譯，並把**所有語言合併成一行**送出（和翻譯自己的發言時形式
相同）。不加語言標記。

```
Karl: watch out, swarm incoming          ← 英語發言
You: Karl: 気をつけろ、大群が来るぞ / 조심해, 무리가 온다 / 小心，蟲群來了
```

行首的 `Karl:` 表示「這是誰的發言的譯文」（轉發是以房主的名義送出的，沒有它就分不出是誰
說的了）。

| 發言者的語言 | 轉發的譯文 |
|---|---|
| 英語 | 繁體中文 · 日語 · 韓語 · 簡體中文 |
| 日語 | 繁體中文 · 英語 · 韓語 · 簡體中文 |
| 韓語 | 繁體中文 · 日語 · 英語 · 簡體中文 |
| 中文 | 繁體中文 · 日語 · 英語 · 韓語 |
| 其他（俄語等） | 繁體中文 · 日語 · 英語 · 韓語 · 簡體中文 |

中文發言也會被轉發。雖然不會在你自己的畫面上顯示譯文（用你自己的語言說的話預設不翻譯，
把看得懂的東西再顯示一次反而礙事），但會送到用其他語言交流的同伴那裡。這樣，就算說中文
的同伴沒裝 MOD，他的發言也能傳達給說外語的同伴。

> 語言判斷是看文字種類，因此無法分辨簡體字和繁體字，兩者都會被當成「中文」。所以安裝時
> 會寫入 `DRGT_INCOMING_SKIP_LANGUAGES=zh`，讓所有中文發言都不在你自己的聊天裡重複顯示
> 譯文。

- **房主（單人）和作為用戶端時不轉發。** 單人時沒有人要讀，所以只產生繁體中文譯文顯示在
  你自己的畫面上。作為用戶端時，不會擅自洗版別人開的房間。
- 翻譯會和接收的部分合併到**同一次 API 呼叫**中（只是翻譯的語言變多了）。
- 像 `Rock and Stone!` 這種翻譯後和原文沒有差別的發言不會轉發。
- 想關閉的話，在 `settings.ini` 中寫 `DRGT_RELAY_ENABLED=false`。轉發的語言和格式也可以
  用 `settings.ini` 的 `DRGT_RELAY_*` 修改。
- 如果太長被遊戲截斷，可以寫 `DRGT_RELAY_MAX_LINE_CHARS=200` 之類的值，依這個字數分行送出
  （預設 `0` 不分行）。

> 聊天量一定會增加。人少的熟人房裡很舒服，但公開房間對話多的時候，建議像
> `DRGT_RELAY_TARGETS=zh-tw,en` 這樣縮減。**請保留 `zh-tw`。** 房主（連線）時你自己要讀
> 的譯文也是從這一行讀的，拿掉 `zh-tw` 的話你的畫面上就什麼都不會顯示了。

---

## 設定

### `settings.ini` — 翻譯相關

按兩下 exe 同一資料夾中的 **`settings.ini`** 會用記事本開啟（首次安裝時建立）。改完存檔
後，請重新啟動 `DRGTranslate.exe`。在不顯示副檔名的電腦上，它會顯示為 `settings`。

**所有項目都帶著預設值被註解掉了。**
只要拿掉想修改那一行開頭的 `#` 即可。
（檔案裡的說明用英文書寫，讓使用任何語言的人都讀得懂。）

```ini
# Which translation service to use: deepl / claude / openai
DRGT_PROVIDER=openai

# OpenAI  https://platform.openai.com/api-keys
OPENAI_API_KEY=sk-...

# Target languages (comma separated). Use just en if English is enough
#DRGT_OUTGOING_TARGETS=ja,en,ko,zh
```

主要項目如下。全部項目的說明都寫在 `settings.ini` 裡面。

| 鍵 | 說明 |
|---|---|
| `DRGT_UI_LANG` | 安裝過程和黑色視窗訊息的語言。`ja` / `en` / `ko` / `zh` / `zh-tw` / `ru`。未設定時與 `DRGT_INCOMING_TARGET` 相同 |
| `DRGT_PROVIDER` | `deepl` / `claude` / `openai` |
| `DEEPL_AUTH_KEY`<br>`ANTHROPIC_API_KEY`<br>`OPENAI_API_KEY` | API 金鑰。只需要你所用服務的那一個 |
| `DRGT_INCOMING_TARGET` | 把收到的發言翻成哪種語言 |
| `DRGT_OUTGOING_SOURCE` | 翻譯你用哪種語言打的發言（其他語言的發言原樣送出） |
| `DRGT_OUTGOING_TARGETS` | 送出時的翻譯目標。例如 `ja,en,ko,zh`。只要英語就寫 `en`。與原文相同的語言會自動排除 |
| `DRGT_OUTGOING_MIN_LENGTH` | 短於這個字數的發言不翻譯。預設 `2` |
| `DRGT_OUTGOING_IGNORE_PREFIXES` | 以這些字元開頭的發言不翻譯（指令等）。以逗號分隔。預設 `/,!,.` |
| `DRGT_RELAY_ENABLED` | 作為房主時是否把同伴發言的譯文送給所有人。預設 `true` |
| `DRGT_RELAY_TARGETS` | 轉發的目標語言（發言者的語言會自動排除） |
| `DRGT_RELAY_MAX_LANGS` | 每則發言最多轉發成幾種語言。預設為 `DRGT_RELAY_TARGETS` 的數量；設得比它小時，末尾的語言可能不會被轉發，啟動時會發出警告 |
| `DRGT_RELAY_MAX_LINE_CHARS` | 轉發單行的字數上限。預設 `0`（全部合併成一行） |
| `DRGT_INCOMING_FORMAT` | 顯示格式。可以使用 `{sender}` `{text}` `{lang}` `{original}` |
| `DRGT_INCOMING_SKIP_LANGUAGES` | 這些語言不在你的聊天裡顯示譯文。繁體中文的設定會寫成 `zh`（房主轉發不受這個設定影響） |
| `DRGT_CACHE_ENABLED` | 是否保存翻譯結果 |
| `DRGT_OVERLAY_ENABLED` | 遊戲內顯示不可用時作為備援的小視窗 |
| `DRGT_OVERLAY_HIDE_AFTER` | 小視窗收起前的秒數。預設 `12`，`0` 為一直顯示 |

如果系統裡有同名的環境變數，那邊會優先於 `settings.ini`。

### 變更語言

**通常只要在首次安裝的 `[1]` 選一次就夠了。** 會依所選語言一併寫入 `DRGT_UI_LANG` /
`DRGT_INCOMING_TARGET` / `DRGT_INCOMING_FORMAT` / `DRGT_OUTGOING_SOURCE` /
`DRGT_OUTGOING_TARGETS` / `DRGT_RELAY_TARGETS` / `DRGT_RELAY_MAX_LANGS`（繁體中文時還會
寫入 `DRGT_INCOMING_SKIP_LANGUAGES`）。之後想修改，或想用清單裡沒有的語言時，請直接編輯
`settings.ini`（[重新安裝](#安裝)也可以重新選擇）。

語言寫成 `ja`（日語）/ `en`（英語）/ `ko`（韓語）/ `zh`（中文簡體）/
`zh-tw`（中文繁體）/ `ru`（俄語）這樣的形式。

例如，一個**用英語讀寫的人**要和說日語、韓語的同伴一起工作時，可以這樣寫：

```ini
# 接收: 把別人的發言變成英語（英語發言不翻譯）
DRGT_INCOMING_TARGET=en
DRGT_INCOMING_FORMAT=[TL] {sender}: {text}

# 發送: 把用英語打的發言翻成日語和韓語
DRGT_OUTGOING_SOURCE=en
DRGT_OUTGOING_TARGETS=ja,ko

# 轉發: 一定要包含自己的語言（en）
DRGT_RELAY_TARGETS=en,ja,ko
```

- **送出時被翻譯的只有用 `DRGT_OUTGOING_SOURCE` 的語言打的發言。** 其他語言的發言會原樣
  送出。
- `DRGT_INCOMING_SKIP_LANGUAGES` 預設與 `DRGT_INCOMING_TARGET` 相同。繁體中文時因為無法
  和簡體字區分，安裝過程會寫成 `zh`。想再加上自己看得懂的語言時才需要修改（中文閱讀但也
  看得懂英語就寫 `zh,en`）。
- **`DRGT_RELAY_TARGETS` 裡要放自己的語言。** 房主（連線）時你自己要讀的譯文也是從這一行
  讀的，拿掉的話你的畫面上什麼都不會顯示。
- 語言是按文字種類區分的。所以 `en` 不只指英語，還包括德語、西班牙語等所有用拉丁字母書寫
  的語言。設成 `DRGT_INCOMING_SKIP_LANGUAGES=en` 後，這些語言的發言也不會被翻譯。
- 術語表（`glossary.json`）的譯文是日文，所以把接收的翻譯目標設為日文以外時不會被使用
  （`Rock and Stone!` 之類的口號會原樣顯示）。

### 翻譯服務的設定

要用哪個翻譯服務由 `DRGT_PROVIDER` 切換。各服務的特點和費用見
[開始之前](#開始之前準備翻譯服務的-api-金鑰)。

**DeepL**

```ini
DRGT_PROVIDER=deepl
DEEPL_AUTH_KEY=xxxxxxxx-....-xxxxxxxxxxxx:fx
```

**Claude**

```ini
DRGT_PROVIDER=claude
ANTHROPIC_API_KEY=sk-ant-...
```

預設模型是 **`claude-haiku-4-5`**。聊天基本上是一行左右的短句，用它就足夠，而且最快最
便宜。如果覺得譯文不夠好，可以提高 `DRGT_CLAUDE_MODEL`。

| model | 輸入/輸出（每百萬 token） | 適用情況 |
|---|---|---|
| `claude-haiku-4-5`（預設） | $1 / $5 | 短聊天用它就夠 |
| `claude-sonnet-5` | $2 / $10 | 想讓用字更自然時 |
| `claude-opus-5` | $5 / $25 | 也會混入長文或複雜內容時 |

一次翻譯連同系統提示詞大約是輸入 330 token、輸出 30 token，所以用 Haiku 4.5 時
**大約 1000 次翻譯約 $0.5**（僅供參考）。

送出的內容會依模型自動調整，所以 `DRGT_CLAUDE_EFFORT` 和
`DRGT_CLAUDE_REFUSAL_FALLBACK` 保持 `auto` 就沒問題。

**OpenAI**

```ini
DRGT_PROVIDER=openai
OPENAI_API_KEY=sk-...
#DRGT_OPENAI_MODEL=gpt-4o-mini
```

預設模型是最便宜最快的 `gpt-4o-mini`。

**設定 `DRGT_OPENAI_BASE_URL` 就能指向其他 OpenAI 相容的端點。** 指定 Ollama /
LM Studio / llama.cpp 等本機 LLM 的話，聊天內容完全不會離開你的電腦。

```ini
DRGT_PROVIDER=openai
OPENAI_API_KEY=dummy
DRGT_OPENAI_BASE_URL=http://localhost:11434/v1
DRGT_OPENAI_MODEL=qwen2.5:7b
```

### 使用 LLM 時的注意事項

- **一次請求會同時翻譯多種語言。** 英語 + 日語 + 韓語也只是一次 API 呼叫。
- **只有在你真的發言時才會呼叫 API。** 輸入過程中不會送出翻譯請求，所以打到一半又放棄的
  句子不會產生費用。
- **可能會因為髒話等原因被拒絕翻譯。** 只有那一則不會被翻譯，不影響遊戲運作。使用
  `claude-opus-5` 等支援的模型時，會啟用自動轉到其他模型的設定
  （`DRGT_CLAUDE_REFUSAL_FALLBACK`）。
- 回應比機器翻譯稍慢一些。原文之後到譯文到達之間會有一點間隔。
- 聊天內容會送到 Anthropic / OpenAI。不希望內容外傳時，請依上面的說明用
  `openai` + `DRGT_OPENAI_BASE_URL` 指向本機 LLM。

### `glossary.json` — 術語表

像 `Rock and Stone!` 這種固定說法不經過 API 就立即替換。DRG 的常用短語已經預先登錄好了
（包含在 exe 裡）。

想自己新增時，下載 [bridge/glossary.json](bridge/glossary.json) 放到 **exe 所在的同一
資料夾**再編輯即可。它會取代內建的那一份被使用。

日文術語參照 [DRG 日文 Wiki](https://wikiwiki.jp/rockandstone/)
（ナイトラ / ビスモル / エノアパール 等）。

```json
{
  "incoming": { "leaf lover": "リーフラバー（軟弱者）" },
  "outgoing": { "ありがとう": { "en": "Thanks!", "ko": "고마워요!", "zh": "谢谢！" } }
}
```

比對鍵時會忽略空格、符號和大小寫，所以 `rock and stone` 和 `Rock and Stone!!` 視為同一
筆。

### `config.lua` — 遊戲內的行為

位於遊戲資料夾的 `FSD\Binaries\Win64\Mods\DRGTranslate\Scripts\config.lua`
（某些 UE4SS 版本是 `Win64\ue4ss\Mods\...`）。

| 項目 | 說明 |
|---|---|
| `host_relay.interval_ms` | 送出轉發的間隔。防止發言重疊時塞車。預設 `700` |
| `host_relay.sender` | 轉發行的送出者名稱。`self`（自己）/ `original`（原發言者） |
| `display.strategy` | 譯文的顯示方式。`auto` / `gamestate` / `widget` / `off` |
| `debug` | 在 UE4SS 主控台輸出詳細記錄 |

檔案裡的說明用英文書寫，讓使用任何語言的人都讀得懂。
修改 `config.lua` 後請**重新啟動遊戲**。
[重新安裝](#安裝)會重新裝入 MOD，你編輯過的 `config.lua` 會被移到
`Mods\DRGTranslate.bak`。

---

## 已驗證的狀況

- 直接使用發布的 exe，在實機上（單人房主）已確認日語的發送、接收翻譯、轉發、F9 切換以及
  日語/韓語/中文的顯示。
- 把用英語打的發言翻成日語、韓語的設定（[變更語言](#變更語言)）也在實機上確認過。
- DeepL / Claude / OpenAI 三者都已確認可以實際翻譯。
- 安裝過程和黑色視窗的訊息，已用與發布相同方式建置的 exe 在 Windows 上逐一驗證了 6 種語言。
- 已確認遊戲的語言設定裡有繁體中文和俄語的選項（來自遊戲本身的資料）。
  不過**這兩種語言下譯文能否實際顯示尚未確認**（日語、韓語、簡體中文已確認）。
- **多人房間裡轉發能否送達同伴，尚未確認。**
- 小視窗（`DRGT_OVERLAY_ENABLED=true`）在實機上的顯示效果也未確認。

詳情請見 [docs/TESTING.md](docs/TESTING.md)（日文）。

---

## 疑難排解

**遊戲啟動後立刻當掉（EXCEPTION_ACCESS_VIOLATION）**
: 先把 MOD 分離出來排查。把 `FSD\Binaries\Win64\dwmapi.dll` 改名為 `dwmapi.dll.off`，
  UE4SS 會整個停用，回到原版遊戲。如果這樣就好了，表示當掉出在 UE4SS 那一側。請確認以下
  兩點。

  1. `UE4SS-settings.ini` 的 `bUseUObjectArrayCache` 是否為 `false`。為 `true` 時 UE4SS
     可能讀到已失效物件的指標而當掉。
  2. `Mods\mods.txt` 裡 UE4SS 內建的範例 MOD（`ConsoleEnablerMod`、`BPModLoaderMod` 等）
     是否為 `: 0`。翻譯不需要它們，而且它們會改寫引擎內部，容易成為當機來源。

  這兩點從 v0.2.1 起安裝過程會自動處理。如果是用舊版本裝的，刪除 `settings.ini` 後啟動
  `DRGTranslate.exe` 重新走一次安裝過程即可解決。
  如果還是當掉，把 `mods.txt` 裡的 `DRGTranslate : 1` 改成 `: 0` 後啟動，看看是不是 MOD
  本身的問題。

  另外，v0.2.2 有啟動後立刻當掉的問題，已在 v0.2.3 修正。

**MOD 沒有被載入**
: 請確認 `FSD\Binaries\Win64` 中有 `dwmapi.dll` 和 `UE4SS.dll`。
  `Mods\mods.txt` 中需要有 `DRGTranslate : 1` 這一行。
  載入狀況會寫在同一資料夾的 `UE4SS.log`（每次啟動都會重寫）。
  UE4SS 的獨立主控台視窗為了穩定性預設是關閉的。想看的話，把
  `UE4SS-settings.ini` 的 `GuiConsoleEnabled` 設為 `1`。

**UE4SS 記錄檔中出現 `Lost the bridge`**
: `DRGTranslate.exe` 沒有在執行。請比遊戲先啟動它。

**譯文沒有顯示**
: 請確認 `FSD\Binaries\Win64\UE4SS.log` 中有兩行 `hook registered: ...`。
  如果沒有，可能是遊戲更新導致函式名稱變了。
  想看得更詳細，把 `config.lua` 的 `debug = true`。
  如果只是顯示不出來，把 `settings.ini` 的 `DRGT_OVERLAY_ENABLED=true`，就可以顯示在小
  視窗裡（請把遊戲的顯示設定改為「視窗（全螢幕）」）。

**文字變成 □□□**
: 請把遊戲語言設為你閱讀的語言。

**只想停止翻譯自己的發言**
: 在 `settings.ini` 中設定 `DRGT_OUTGOING_ENABLED=false`，只留下接收翻譯。

**作為房主（連線）時，接收的譯文不是平常的格式／什麼都沒有顯示**
: 這是設計如此。放進房主聊天欄的內容會送給所有人，所以接收的譯文是以轉發行合併成一行送出
  的（[我是房主時的轉發](#我是房主時的轉發)）。預設轉發語言裡包含你自己的語言，可以從那
  一行讀到。
  如果關掉了轉發，或從 `DRGT_RELAY_TARGETS` 拿掉了自己的語言，就什麼都不會顯示，這時把
  `settings.ini` 的 `DRGT_OVERLAY_ENABLED=true`，可以顯示在小視窗裡。小視窗只在譯文到達時
  出現，12 秒後收起（`DRGT_OVERLAY_HIDE_AFTER`）。遊戲的顯示設定必須是「視窗（全螢幕）」
  才會顯示在最前面。

---

## 注意事項

- UE4SS 執行在 Deep Rock Galactic 官方 MOD 管理（mod.io）之外。是否安裝請自行承擔風險。
- 翻譯後送出的發言當然同伴矮人也看得到。誤譯也會照樣送出。
- **為了翻譯，包含其他玩家發言在內的聊天內容會被送到外部服務（DeepL / Anthropic /
  OpenAI）。** 無法取得發言者本人的同意。不希望內容外傳時，請用
  `openai` + `DRGT_OPENAI_BASE_URL` 指向本機 LLM。
- 聊天內容也會保存到 `cache.json`（exe 所在的同一資料夾）。不需要的話，把 `settings.ini`
  的 `DRGT_CACHE_ENABLED=false`。
- `claude` / `openai` 是按用量計費的。只有實際發言時才會呼叫 API。

---

## 給開發者

| | |
|---|---|
| [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) | 運作方式、從原始碼使用的方法、建置 exe、發布、檔案結構 |
| [docs/TESTING.md](docs/TESTING.md) | 驗證狀況的詳細內容（也包括哪些尚未驗證） |
| [docs/INTERNALS.md](docs/INTERNALS.md) | 分析得到的 DRG 那一側 API 的筆記 |

這些文件是用日文寫的。

---

## 授權條款

本儲存庫的程式碼和文件採用 **MIT License**（[LICENSE](LICENSE)）。

### 關於非官方 MOD

本專案是**與 Ghost Ship Games 無關的非官方同好專案**，沒有得到認可、贊助或合作。
「Deep Rock Galactic」以及遊戲內的名稱與術語是 Ghost Ship Games 的商標或著作，本儲存庫僅
在說明互通所必需的範圍內提及。不包含遊戲的任何素材、程式碼或執行檔。

安裝前請確認 Ghost Ship Games 的 UGC 政策。

### 依賴 · 參考的第三方內容

| | 授權 | 處理方式 |
|---|---|---|
| [UE4SS](https://github.com/UE4SS-RE/RE-UE4SS) | MIT | **未內建。** 安裝時從官方發布頁取得 |
| [DRG-Modding/FSD-Template](https://github.com/DRG-Modding/FSD-Template)<br>[DRG-Modding/Header-Dumps](https://github.com/DRG-Modding/Header-Dumps) | 未設定 | 沒有引入其程式碼。見下文 |
| DeepL / Anthropic / OpenAI | 各公司的使用條款 | API 金鑰由使用者自行準備。遵守各公司條款是使用者的責任 |

`docs/INTERNALS.md` 中列出的函式簽章與結構定義，是**直接從遊戲本體的執行檔中擷取確認的**
（擷取步驟也記在同一份文件中）。上述社群儲存庫只是作為交叉驗證的參考列出，並沒有引入
它們的檔案。

### 免責

依照 MIT License，不提供任何擔保。UE4SS 執行在 Deep Rock Galactic 官方 MOD 管理
（mod.io）之外。因安裝 · 使用而產生的任何問題或帳號上的不利後果，作者概不負責。
