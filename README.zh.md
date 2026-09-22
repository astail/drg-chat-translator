# DRG Chat Translator (DCT)

[日本語](README.md) | [English](README.en.md) | [한국어](README.ko.md) | **简体中文** | [繁體中文](README.zh-TW.md) | [Русский](README.ru.md)

一个自动翻译 Deep Rock Galactic 聊天的 MOD。

*与 Ghost Ship Games 无关的非官方粉丝项目。*

| 能做什么 | 房主（联机） | 房主（单人） | 客户端 |
|---|:---:|:---:|:---:|
| **接收** — 把同伴矮人的聊天翻译成你的语言并显示在聊天栏 | 〇 | 〇 | 〇 |
| **发送** — 把你说的话翻译成其他语言再发出去 | 〇 | 〇 | 〇 |
| **转发** — 把同伴矮人发言的译文推送到所有人的聊天里 | 〇 | × | × |

"房主"是指自己开房的一方，"客户端"是指加入别人房间的一方。

安装时会先问你用哪种语言阅读，并据此写好设置。选择简体中文后，日语、英语、韩语等发言会
被翻译成**简体中文**，你用中文打的话会被翻译成**日语 · 英语 · 韩语**。从哪种语言翻译到
哪种语言都可以在设置文件（`settings.ini`）中修改（[更改语言](#更改语言)）。

```
Karl: watch out, swarm incoming
[TL] Karl: 小心，虫群来了

（当你打出"请帮我治疗一下"时）
You: 请帮我治疗一下
You: 回復お願いします / Please heal me / 회복 부탁드립니다
```

它由两部分组成：装进游戏里的 MOD（运行在 UE4SS 这个 MOD 用外部工具之上），以及调用翻译
服务的常驻程序（`DRGTranslate.exe`）。

> 与 Ghost Ship Games 无关的非官方同好项目。MIT License。
> 详情见[许可证](#许可证)。

从源码运行、构建 exe、内部实现都整理在[开发者指南](docs/DEVELOPMENT.md)（日语）中。

---

## 开始之前：准备翻译服务的 API 密钥

翻译交给外部的翻译服务完成。**在开始使用之前，请先在下列服务中任选一个注册并创建
"API 密钥"。** API 密钥是让本程序代表你使用该服务的一串字符，会在首次启动的安装过程中
粘贴。事先没有准备好的话，安装过程会中途卡住。

| 服务 | 特点 | 费用 | 注册 · 创建密钥 |
|---|---|---|---|
| **DeepL**（默认） | 机器翻译中最自然的 | 有免费额度。用完后转付费套餐 | https://www.deepl.com/pro-api |
| **Claude**（Anthropic） | 擅长俚语、缩写和错别字。能结合上下文翻译 `gg` `bulk inc` `res me` | 按用量付费。使用默认的 Claude Haiku 4.5 时，**1000 次翻译约 $1.5** | https://platform.claude.com/settings/keys |
| **OpenAI** | 擅长俚语、缩写和错别字。能结合上下文翻译 `gg` `bulk inc` `res me` | 按用量付费。使用默认的 gpt-4o-mini 时，**1000 次翻译约 $0.1～0.2** | https://platform.openai.com/api-keys |

如果以普通对话为主，DeepL 就足够了。想在缩写和打字错误较多的公开联机里提高准确度，就选
Claude 或 OpenAI。像 `Rock and Stone` 这样的固定说法由术语表处理，所以用哪个服务译文都
一样。

- 费用和免费额度的条件可能变化。注册前请确认各服务自己的价格页面。
- **不要把 API 密钥告诉别人。** 被他人使用的话，费用会算在你头上。

---

## 安装

从 [**Releases**](https://github.com/astail/drg-chat-translator/releases) 下载
`DRGTranslate-vX.Y.Z-win64.zip` 并解压。里面有：

```
DRGTranslate.exe      只要这个就能运行
settings.example.ini  设置文件的样例（含全部项目的说明。英文）
README.txt            简单的指引
LICENSE               许可证（MIT）
```

**只需双击 `DRGTranslate.exe`。** 没有别的东西需要安装。你要准备的只有**翻译服务的 API
密钥**（[开始之前](#开始之前准备翻译服务的-api-密钥)）。

首次启动时会按下面的顺序引导。**先问语言，之后的说明都用你选的语言显示。**

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
    番号 / number [1]: 4
    OK  将使用 简体中文（接收 -> zh / 发送 -> ja,en,ko）
[2] 正在查找 Deep Rock Galactic
    OK  G:\SteamLibrary\steamapps\common\Deep Rock Galactic
[3] 正在检查 UE4SS
    !!  尚未安装 UE4SS。MOD 需要它才能运行。
    现在下载并安装吗？ (Y/n):
[4] 正在复制 MOD
    OK  ...\Mods\DRGTranslate
    OK  已写入 mods.txt（DRGTranslate : 1）
[5] 请选择翻译服务
      1) DeepL    机器翻译。有免费额度
      2) OpenAI   擅长俚语和错别字。按用量计费
      3) Claude   擅长俚语和错别字。按用量计费。默认用最便宜的 Haiku
    编号 [1]:
    请粘贴 API 密钥（留空则取消）:
[6] 试着翻译一次
      watch out, swarm incoming
        → 小心，虫群来了
    OK  翻译成功
```

这里选的语言会记录在 `settings.ini` 的 `DRGT_UI_LANG` 中，第二次以后启动也会沿用（黑色
窗口里的消息也会是该语言）。

设置完成后翻译进程会直接常驻，请保持窗口打开并启动游戏。

第二次以后会跳过安装过程，直接进入常驻状态。

**想重新走一遍安装过程时**，删除 exe 同一文件夹中的 `settings.ini`，再启动
`DRGTranslate.exe`，就会从最开始重新开始（API 密钥也要重新输入，请先准备好）。

> **关于杀毒软件的警告**
>
> 这个 exe 没有签名，因此 Windows Defender 和部分安全软件可能会报警。这是用 PyInstaller
> 制作的未签名 exe 常见的误报，内容就是本仓库的源码本身。如果介意，也可以不用 exe 而从
> 源码运行（[开发者指南](docs/DEVELOPMENT.md)，日语）。

`settings.ini`（设置和 API 密钥）与 `cache.json` 会创建在 **exe 所在的同一文件夹**。
请放在可写入的位置（避免放在 `Program Files` 之类的目录里）。

---

## 使用方法

1. **启动 `DRGTranslate.exe`**（会出现黑色窗口，请不要关闭）
2. **启动 Deep Rock Galactic**
3. 像平时一样聊天即可

设置不完整时，黑色窗口启动后会立刻给出警告。

```
provider=openai / 接收 -> zh / 发送 -> ja,en,ko
==============================================================
还不能进行翻译:
  请在 settings.ini 中设置 OPENAI_API_KEY（https://platform.openai.com/api-keys）
==============================================================
```

**只要没有出现这个警告，直接启动游戏就没问题。**

| 情况 | 行为 |
|---|---|
| 同伴矮人用日语/英语/韩语发言 | 中文译文出现在下一行 |
| 你用中文发言 | 被翻译成日语 · 英语 · 韩语后发送 |
| 你用中文以外的语言发言 | 原样发送（不翻译） |
| 以 `/` `!` `.` 开头的发言 | 不翻译（留给命令用） |
| **你是房主时** | 同伴矮人发言的译文也会推送到所有人的聊天（[见下](#我作为房主时的转发)） |
| **F9** | 切换翻译开关（关掉时也会丢弃等待转发的队列）<br>切换结果会以 `[DRGTranslate] Translation OFF` 显示在画面上（为了让游戏语言是任何语言的人都能读懂，MOD 在游戏里输出的文字都用英文数字）。只有在有同伴矮人的房主状态下无法显示，这时会显示在黑色窗口里 |

上表中的语言以选择简体中文为前提。[更改语言](#更改语言)后，表中的"中文"会变成你选的
语言。

> **请把游戏语言设为你阅读的语言。**
> 如果游戏字体里没有相应的文字，译文会显示成方块（□□□）。

### 你自己的发言是怎么发出去的

翻译要经过网络，按下 Enter 的瞬间结果还来不及返回。因此采用**先把你打的原文照样发出去，
译文到达后作为第二条消息发送**的方式。

```
You: 请帮我治疗一下
You: 回復お願いします / Please heal me / 회복 부탁드립니다
```

原文保留下来，所以如果有懂中文的同伴可以直接读，出现误译时也能知道原本说的是什么。

### 我作为房主时的转发

装了 MOD 的只有你自己，所以通常也只有你能看到译文。**只有在你是房主（联机）时**，才能把
同伴矮人发言的译文推送到所有人的聊天里。这样，两个都没装 MOD 的矮人之间也能交流。

会去掉发言者本人的语言后翻译，并把**所有语言合并成一行**发出去（和翻译自己的发言时形式
相同）。不加语言标记。

```
Karl: watch out, swarm incoming          ← 英语发言
You: Karl: 気をつけろ、大群が来るぞ / 조심해, 무리가 온다 / 小心，虫群来了
```

行首的 `Karl:` 表示"这是谁的发言的译文"（转发是以房主的名义发出的，没有它就分不清是谁说
的了）。

| 发言者的语言 | 转发的译文 |
|---|---|
| 英语 | 中文 · 日语 · 韩语 |
| 日语 | 中文 · 英语 · 韩语 |
| 韩语 | 中文 · 日语 · 英语 |
| 中文 | 日语 · 英语 · 韩语 |
| 其他（俄语等） | 中文 · 日语 · 英语 · 韩语 |

中文发言也会被转发。虽然不会在你自己的画面上显示译文（用你自己的语言说的话默认不翻译，
把能读懂的东西再显示一遍反而碍事），但会送达用其他语言交流的同伴。这样，即使说中文的
同伴没有装 MOD，他的发言也能传达给说外语的同伴。

- **房主（单人）和作为客户端时不转发。** 单人时没有人要读，所以只生成中文译文显示在你
  自己的画面上。作为客户端时，不会擅自刷屏别人开的房间。
- 翻译会和接收部分合并到**同一次 API 调用**中（只是翻译的语言变多了）。
- 像 `Rock and Stone!` 这样翻译后和原文没有区别的发言不会转发。
- 想关闭的话，在 `settings.ini` 中写 `DRGT_RELAY_ENABLED=false`。转发的语言和格式也可以
  用 `settings.ini` 的 `DRGT_RELAY_*` 修改。
- 如果太长被游戏截断，可以写 `DRGT_RELAY_MAX_LINE_CHARS=200` 之类的值，按这个字数分行
  发送（默认 `0` 不分行）。

> 聊天量肯定会增加。人少的熟人房里很舒服，但公开房间对话多的时候，建议像
> `DRGT_RELAY_TARGETS=zh,en` 这样收窄。**请保留 `zh`。** 房主（联机）时你自己要读的译文
> 也是从这一行读的，去掉 `zh` 的话你的画面上就什么都不显示了。

---

## 设置

### `settings.ini` — 翻译相关

双击 exe 同一文件夹中的 **`settings.ini`** 会用记事本打开（首次安装时创建）。改完保存后，
请重新启动 `DRGTranslate.exe`。在不显示文件扩展名的电脑上，它显示为 `settings`。

**所有项目都带着默认值被注释掉了。**
只要去掉想修改那一行开头的 `#` 即可。
（文件里的说明用英文书写，以便使用任何语言的人都能读。）

```ini
# Which translation service to use: deepl / claude / openai
DRGT_PROVIDER=openai

# OpenAI  https://platform.openai.com/api-keys
OPENAI_API_KEY=sk-...

# Target languages (comma separated). Use just en if English is enough
#DRGT_OUTGOING_TARGETS=ja,en,ko
```

主要项目如下。全部项目的说明都写在 `settings.ini` 里面。

| 键 | 说明 |
|---|---|
| `DRGT_UI_LANG` | 安装过程和黑色窗口消息的语言。`ja` / `en` / `ko` / `zh` / `zh-tw` / `ru`。未设置时与 `DRGT_INCOMING_TARGET` 相同 |
| `DRGT_PROVIDER` | `deepl` / `claude` / `openai` |
| `DEEPL_AUTH_KEY`<br>`ANTHROPIC_API_KEY`<br>`OPENAI_API_KEY` | API 密钥。只需要你所用服务的那一个 |
| `DRGT_INCOMING_TARGET` | 把收到的发言翻译成哪种语言 |
| `DRGT_OUTGOING_SOURCE` | 翻译你用哪种语言打的发言（其他语言的发言原样发送） |
| `DRGT_OUTGOING_TARGETS` | 发送时的翻译目标。例如 `ja,en,ko`。只要英语就写 `en`，繁体字是 `zh-tw`。与原文相同的语言会自动排除 |
| `DRGT_OUTGOING_MIN_LENGTH` | 短于这个字数的发言不翻译。默认 `2` |
| `DRGT_OUTGOING_IGNORE_PREFIXES` | 以这些字符开头的发言不翻译（命令等）。用逗号分隔。默认 `/,!,.` |
| `DRGT_RELAY_ENABLED` | 作为房主时是否把同伴发言的译文推给所有人。默认 `true` |
| `DRGT_RELAY_TARGETS` | 转发的目标语言（发言者的语言会自动排除） |
| `DRGT_RELAY_MAX_LANGS` | 每条发言最多转发成几种语言。默认为 `DRGT_RELAY_TARGETS` 的数量；设得比它小时，末尾的语言可能不会被转发，启动时会发出警告 |
| `DRGT_RELAY_MAX_LINE_CHARS` | 转发单行的字数上限。默认 `0`（全部合并成一行） |
| `DRGT_INCOMING_FORMAT` | 显示格式。可以使用 `{sender}` `{text}` `{lang}` `{original}` |
| `DRGT_INCOMING_SKIP_LANGUAGES` | 这些语言不在你的聊天里显示译文。默认与 `DRGT_INCOMING_TARGET` 相同（房主转发不受此设置影响） |
| `DRGT_CACHE_ENABLED` | 是否保存翻译结果 |
| `DRGT_OVERLAY_ENABLED` | 游戏内显示不可用时作为保险的小窗 |
| `DRGT_OVERLAY_HIDE_AFTER` | 小窗收起前的秒数。默认 `12`，`0` 为一直显示 |

如果系统里存在同名的环境变量，那边会优先于 `settings.ini`。

### 更改语言

**通常只要在首次安装的 `[1]` 里选一次就够了。** 会按所选语言一并写入 `DRGT_UI_LANG` /
`DRGT_INCOMING_TARGET` / `DRGT_INCOMING_FORMAT` / `DRGT_OUTGOING_SOURCE` /
`DRGT_OUTGOING_TARGETS` / `DRGT_RELAY_TARGETS`（选繁体中文时
还会写入 `DRGT_INCOMING_SKIP_LANGUAGES`，因为语言判断无法区分简体和繁体）。之后想修改，
或者想用列表里没有的语言时，请直接编辑 `settings.ini`（[重新安装](#安装)也可以重新
选择）。

> 0.7.0 及以前的安装还会写入 `DRGT_INCOMING_SKIP_LANGUAGES` 和 `DRGT_RELAY_MAX_LANGS`。
> 这两行如果没有 `#` 仍留在文件里，修改语言后它们不会跟着变。请在行首加上 `#`，
> 或者重新安装一次。
> 但以繁体中文安装时写入的 `DRGT_INCOMING_SKIP_LANGUAGES=zh` 现在仍然需要，请保持不变。

语言写成 `ja`（日语）/ `en`（英语）/ `ko`（韩语）/ `zh`（中文简体）/
`zh-tw`（中文繁体）/ `ru`（俄语）这样的形式。

例如，一个**用英语读写的人**要和说日语、韩语的同伴一起工作时，可以这样写：

```ini
# 接收: 把别人的发言变成英语（英语发言不翻译）
DRGT_INCOMING_TARGET=en
DRGT_INCOMING_FORMAT=[TL] {sender}: {text}

# 发送: 把用英语打的发言翻译成日语和韩语
DRGT_OUTGOING_SOURCE=en
DRGT_OUTGOING_TARGETS=ja,ko

# 转发: 一定要包含自己的语言（en）
DRGT_RELAY_TARGETS=en,ja,ko
```

- **发送时被翻译的只有用 `DRGT_OUTGOING_SOURCE` 的语言打的发言。** 其他语言的发言会原样
  发送。
- `DRGT_INCOMING_SKIP_LANGUAGES` 可以不写。省略时会与 `DRGT_INCOMING_TARGET` 相同（用
  中文阅读时中文发言就不翻译）。只有想添加自己能读的语言时才写（中文阅读但也能读英语就
  写 `zh,en`）。
- **`DRGT_RELAY_TARGETS` 里要放入自己的语言。** 房主（联机）时你自己要读的译文也是从这
  一行读的，去掉的话你的画面上什么都不会显示。
- 语言是按文字种类区分的。所以 `en` 不只指英语，还包括德语、西班牙语等所有用拉丁字母书写
  的语言。设成 `DRGT_INCOMING_SKIP_LANGUAGES=en` 后，这些语言的发言也不会被翻译。
- 附带的术语表（`glossary.json`）目前只有日语译文。接收的翻译目标不是日语时，
  如果术语表中有该语言的译文就会使用（`Rock and Stone!` 这样的口号在任何语言下都原样显示）。

### 翻译服务的设置

用哪个翻译服务由 `DRGT_PROVIDER` 切换。各服务的特点和费用见
[开始之前](#开始之前准备翻译服务的-api-密钥)。

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

默认模型是 **`claude-haiku-4-5`**。聊天基本是一行左右的短句，用它就足够，而且最快最便宜。
如果觉得译文不够好，可以提高 `DRGT_CLAUDE_MODEL`。

| model | 输入/输出（每百万 token） | 适用情况 |
|---|---|---|
| `claude-haiku-4-5`（默认） | $1 / $5 | 短聊天用它就够 |
| `claude-sonnet-5` | $2 / $10 | 想让措辞更自然时 |
| `claude-opus-5` | $5 / $25 | 也会混入长文或复杂内容时 |

一次翻译（调用一次 API）连同系统提示词大约是输入 1,300 token、输出 30～60 token，所以用 Haiku 4.5 时
**大约 1000 次翻译约 $1.5**（仅供参考）。由术语表或缓存处理的发言不会调用 API，费用相应更低。
使用 Sonnet 5 / Opus 5 时，连续翻译会从缓存读取系统提示词部分，该部分只收一成的费用
（间隔 5 分钟以上后的第一次会写入缓存，费用为 1.25 倍；Haiku 4.5 的提示词太短，不会被缓存）。

发送的内容会根据模型自动调整，所以 `DRGT_CLAUDE_EFFORT` 和
`DRGT_CLAUDE_REFUSAL_FALLBACK` 保持 `auto` 就没问题。

**OpenAI**

```ini
DRGT_PROVIDER=openai
OPENAI_API_KEY=sk-...
#DRGT_OPENAI_MODEL=gpt-4o-mini
```

默认模型是最便宜最快的 `gpt-4o-mini`。

**设置 `DRGT_OPENAI_BASE_URL` 就能指向其他 OpenAI 兼容的端点。** 指定 Ollama /
LM Studio / llama.cpp 等本地 LLM 的话，聊天内容完全不会离开你的电脑。

```ini
DRGT_PROVIDER=openai
OPENAI_API_KEY=dummy
DRGT_OPENAI_BASE_URL=http://localhost:11434/v1
DRGT_OPENAI_MODEL=qwen2.5:7b
```

### 使用 LLM 时的注意事项

- **一次请求会同时翻译多种语言。** 英语 + 日语 + 韩语也只是一次 API 调用。
- **只有在你真的发言时才会调用 API。** 输入过程中不会发出翻译请求，所以打了一半又放弃的
  句子不会产生费用。
- **可能会因为脏话等原因被拒绝翻译。** 只有那一条不会被翻译，不影响游戏运行。使用
  `claude-opus-5` 等支持的模型时，会启用自动转到其他模型的设置
  （`DRGT_CLAUDE_REFUSAL_FALLBACK`）。
- 响应比机器翻译稍慢一些。原文之后到译文到达之间会有一点间隔。
- 聊天内容会发送给 Anthropic / OpenAI。不希望内容外传时，请按上面的说明用
  `openai` + `DRGT_OPENAI_BASE_URL` 指向本地 LLM。

### `glossary.json` — 术语表

像 `Rock and Stone!` 这样的固定说法不经过 API 就立即替换。DRG 的常用短语已经预先注册好了
（包含在 exe 里）。

想自己添加时，下载 [bridge/glossary.json](bridge/glossary.json) 放到 **exe 所在的同一
文件夹**再编辑即可。它会代替内置的那一份被使用。

日语术语参照 [DRG 日语 Wiki](https://wikiwiki.jp/rockandstone/)
（ナイトラ / ビスモル / エノアパール 等）。

```json
{
  "incoming": { "leaf lover": { "ja": "リーフラバー（軟弱者）", "ko": "리프 러버(겁쟁이)" } },
  "outgoing": { "ありがとう": { "en": "Thanks!", "ko": "고마워요!", "zh": "谢谢！" } }
}
```

`incoming` 的值是按语言区分的译文。写成 `"*"` 时，任何语言都原样使用该字符串。
译文为空的词（`{"*": ""}`）不翻译：不调用 API，不显示，也不转发。
附带的术语表对 `r?`（准备好了吗？）、`nt`（nice try）这类不必翻译的缩写就是这样处理的。

匹配键时会忽略空格、符号和大小写，所以 `rock and stone` 和 `Rock and Stone!!` 视为同一
条目。

### `config.lua` — 游戏内的行为

位于游戏文件夹的 `FSD\Binaries\Win64\Mods\DRGTranslate\Scripts\config.lua`
（某些 UE4SS 版本是 `Win64\ue4ss\Mods\...`）。

| 项目 | 说明 |
|---|---|
| `host_relay.interval_ms` | 发送转发的间隔。防止发言重叠时堵塞。默认 `700` |
| `host_relay.sender` | 转发行的发送者名。`self`（自己）/ `original`（原发言者） |
| `display.strategy` | 译文的显示方式。`auto` / `gamestate` / `widget` / `off` |
| `debug` | 在 UE4SS 控制台输出详细日志 |

文件里的说明用英文书写，以便使用任何语言的人都能读。
修改 `config.lua` 后请**重启游戏**。
[重新安装](#安装)会重新装入 MOD，你编辑过的 `config.lua` 会被移到
`Mods\DRGTranslate.bak`。

---

## 已验证的情况

- 直接使用发布的 exe，在实机上（单人房主）已确认日语的发送、接收翻译、转发、F9 切换以及
  日语/韩语/中文的显示。
- 把用英语打的发言翻译成日语、韩语的设置（[更改语言](#更改语言)）也在实机上确认过。
- DeepL / Claude / OpenAI 三者都已确认可以实际翻译。
- 安装过程和黑色窗口的消息，已用与发布相同方式构建的 exe 在 Windows 上逐一验证了 6 种语言。
- 已确认游戏的语言设置里有繁体中文和俄语的选项（来自游戏本身的数据）。
  不过**这两种语言下译文能否实际显示尚未确认**（日语、韩语、简体中文已确认）。
- **多人房间里转发能否送达同伴，尚未确认。**
- 小窗（`DRGT_OVERLAY_ENABLED=true`）已在实机上确认会显示在游戏上方，并且可以从输入框发送。

---

## 故障排查

**游戏启动后立刻崩溃（EXCEPTION_ACCESS_VIOLATION）**
: 先把 MOD 分离出来排查。把 `FSD\Binaries\Win64\dwmapi.dll` 改名为 `dwmapi.dll.off`，
  UE4SS 会整个失效，回到原版游戏。如果这样就好了，说明崩溃在 UE4SS 一侧。请确认以下两点。

  1. `UE4SS-settings.ini` 的 `bUseUObjectArrayCache` 是否为 `false`。为 `true` 时 UE4SS
     可能读到已失效对象的指针而崩溃。
  2. `Mods\mods.txt` 里 UE4SS 自带的示例 MOD（`ConsoleEnablerMod`、`BPModLoaderMod` 等）
     是否为 `: 0`。翻译不需要它们，而且它们会改写引擎内部，容易成为崩溃源。

  这两点从 v0.2.1 起安装过程会自动处理。如果是用旧版本装的，删除 `settings.ini` 后启动
  `DRGTranslate.exe` 重新走一遍安装过程即可解决。
  如果还是崩溃，把 `mods.txt` 里的 `DRGTranslate : 1` 改成 `: 0` 后启动，看看是不是 MOD
  本身的问题。

  另外，v0.2.2 存在启动后立刻崩溃的缺陷，已在 v0.2.3 中修复。

**MOD 没有被加载**
: 请确认 `FSD\Binaries\Win64` 中有 `dwmapi.dll` 和 `UE4SS.dll`。
  `Mods\mods.txt` 中需要有 `DRGTranslate : 1` 这一行。
  加载情况会写在同一文件夹的 `UE4SS.log` 里（每次启动都会重写）。
  UE4SS 的独立控制台窗口出于稳定性考虑默认是关闭的。想看的话，把
  `UE4SS-settings.ini` 的 `GuiConsoleEnabled` 设为 `1`。

**UE4SS 日志里出现 `Lost the bridge`**
: `DRGTranslate.exe` 没有在运行。请先于游戏启动它。

**译文不显示**
: 请确认 `FSD\Binaries\Win64\UE4SS.log` 中有两行 `hook registered: ...`。
  如果没有，可能是游戏更新导致函数名变了。
  想看得更详细，把 `config.lua` 的 `debug = true`。
  如果只是显示不出来，把 `settings.ini` 的 `DRGT_OVERLAY_ENABLED=true`，就可以显示在小窗
  里（请把游戏的显示设置改为"窗口（全屏）"）。

**文字变成 □□□**
: 请把游戏语言设为你阅读的语言。

**只想停止翻译自己的发言**
: 在 `settings.ini` 中设置 `DRGT_OUTGOING_ENABLED=false`，只保留接收翻译。

**作为房主（联机）时，接收的译文不是平时的格式／什么都不显示**
: 这是设计如此。放进房主聊天栏的内容会发给所有人，所以接收的译文是作为转发行合并成一行
  发出的（[我作为房主时的转发](#我作为房主时的转发)）。默认转发语言里包含你自己的语言，
  可以从那一行读到。
  如果关掉了转发，或从 `DRGT_RELAY_TARGETS` 中去掉了自己的语言，就什么都不会显示，这时把
  `settings.ini` 的 `DRGT_OVERLAY_ENABLED=true`，可以显示在小窗里。小窗只在译文到达时出现，
  12 秒后收起（`DRGT_OVERLAY_HIDE_AFTER`）。游戏的显示设置必须是"窗口（全屏）"才会显示在
  最前面。小窗的 ✕ 或 Esc 只会隐藏窗口，翻译不会停止（下一条译文到达时会再次出现）。
  在小窗输入框里输入的内容，和在聊天栏里输入时一样，会先发原文再发译文。

---

## 注意事项

- UE4SS 运行在 Deep Rock Galactic 官方 MOD 管理（mod.io）之外。是否安装请自行承担风险。
- 翻译后发送的发言当然同伴矮人也能看到。误译也会照样发出去。
- **为了翻译，包含其他玩家发言在内的聊天内容会被发送到外部服务（DeepL / Anthropic /
  OpenAI）。** 无法取得发言者本人的同意。不希望内容外传时，请用
  `openai` + `DRGT_OPENAI_BASE_URL` 指向本地 LLM。
- 聊天内容也会保存到 `cache.json`（exe 所在的同一文件夹）。不需要的话，把 `settings.ini`
  的 `DRGT_CACHE_ENABLED=false`。
- `claude` / `openai` 是按用量计费的。只有实际发言时才会调用 API。

---

## 给开发者

| | |
|---|---|
| [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) | 机制、从源码使用的方法、构建 exe、发布、文件结构 |
| [docs/INTERNALS.md](docs/INTERNALS.md) | 分析得到的 DRG 一侧 API 的笔记 |

这些文档是用日语写的。

---

## 许可证

本仓库的代码和文档采用 **MIT License**（[LICENSE](LICENSE)）。

### 关于非官方 MOD

本项目是**与 Ghost Ship Games 无关的非官方同好项目**，没有得到认可、赞助或合作。
"Deep Rock Galactic" 以及游戏内的名称与术语是 Ghost Ship Games 的商标或作品，本仓库仅在
说明互操作所必需的范围内提及。不包含游戏的任何素材、代码或可执行文件。

安装前请确认 Ghost Ship Games 的 UGC 政策。

### 依赖 · 引用的第三方内容

| | 许可证 | 处理方式 |
|---|---|---|
| [UE4SS](https://github.com/UE4SS-RE/RE-UE4SS) | MIT | **未内置。** 安装时从官方发布页获取 |
| [DRG-Modding/FSD-Template](https://github.com/DRG-Modding/FSD-Template)<br>[DRG-Modding/Header-Dumps](https://github.com/DRG-Modding/Header-Dumps) | 未设置 | 没有引入其代码。见下文 |
| DeepL / Anthropic / OpenAI | 各公司的使用条款 | API 密钥由使用者自行准备。遵守各公司条款是使用者的责任 |

`docs/INTERNALS.md` 中列出的函数签名与结构体定义，是**直接从游戏本体的可执行文件中提取
确认的**（提取步骤也记在同一文档中）。上述社区仓库只是作为交叉验证的参考列出，并没有引入
它们的文件。

### 免责

依照 MIT License，不提供任何担保。UE4SS 运行在 Deep Rock Galactic 官方 MOD 管理
（mod.io）之外。因安装 · 使用而产生的任何故障或账号方面的不利后果，作者概不负责。
