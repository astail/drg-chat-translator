# DRGTranslate

[日本語](README.md) | **English** | [한국어](README.ko.md) | [简体中文](README.zh.md) | [繁體中文](README.zh-TW.md) | [Русский](README.ru.md)

A mod that translates Deep Rock Galactic chat for you.

| What it does | Host (multiplayer) | Host (solo) | Client |
|---|:---:|:---:|:---:|
| **Incoming** — translate what your fellow dwarves say into your language and show it in chat | Yes | Yes | Yes |
| **Outgoing** — translate what you say into other languages before it is sent | Yes | Yes | Yes |
| **Relay** — push translations of other people's messages to everyone's chat | Yes | No | No |

"Host" means you started the game; "client" means you joined someone else's.

Setup asks which language you read, and writes the settings to match. If you pick
English, chat in Japanese, Korean, Chinese and so on is turned into **English**, and
what you type in English is translated into **Japanese, Korean and Chinese (simplified)**.
Every language pair can be changed in the settings file (`settings.ini`), so translating
Japanese into Korean only, or English into German, works too
([Change the language](#change-the-language)).

```
Karl: 気をつけろ、大群が来るぞ
[TL] Karl: Watch out, swarm incoming

(when you type "please heal me")
You: please heal me
You: 回復お願いします / 회복 부탁드립니다 / 请帮我治疗一下
```

It is two pieces: a mod that goes into the game (it runs on top of UE4SS, an external
tool for mods) and a small program that calls the translation service
(`DRGTranslate.exe`) and stays running in the background.

> An unofficial fan project, not affiliated with Ghost Ship Games. MIT License.
> See [License](#license) for details.

Running from source, building the exe and how the internals work are covered in the
[developer guide](docs/DEVELOPMENT.md) (Japanese).

---

## Before you start: get an API key

Translation is done by an outside service. **Before you use this, sign up with one of
these and create an "API key".** An API key is a string of text that lets this program
use that service on your behalf; you paste it during the first-run setup. Without one,
setup cannot finish.

| Service | Strengths | Price | Sign up / create a key |
|---|---|---|---|
| **DeepL** (default) | The most natural of the machine translators | Has a free tier. Paid plan once you use it up | https://www.deepl.com/pro-api |
| **Claude** (Anthropic) | Handles slang, abbreviations and typos. Reads `gg`, `bulk inc`, `res me` in context | Pay for what you use. With the default Claude Haiku 4.5, **about $0.5 per 1000 translations** | https://platform.claude.com/settings/keys |
| **OpenAI** | Handles slang, abbreviations and typos. Reads `gg`, `bulk inc`, `res me` in context | Pay for what you use. With the default gpt-4o-mini, **under about $0.1 per 1000 translations** | https://platform.openai.com/api-keys |

If your chat is mostly ordinary conversation, DeepL is enough. Pick Claude or OpenAI if
you want better accuracy in public lobbies full of abbreviations and typos. Set phrases
like `Rock and Stone` are handled by the glossary, so they come out the same whichever
service you use.

- Prices and free-tier terms change. Check the service's own pricing page before you
  sign up.
- **Never share your API key.** Anyone who has it can spend your money.

---

## Install

Download `DRGTranslate-vX.Y.Z-win64.zip` from
[**Releases**](https://github.com/astail/drg-translation/releases) and unzip it.
It contains:

```
DRGTranslate.exe      everything you need
settings.example.ini  a sample settings file (every option, explained)
はじめに.txt          a three-step guide (Japanese)
README.md and more    the README in each language / LICENSE
```

**Just double-click `DRGTranslate.exe`.** There is nothing else to install. The only
thing you need to bring is an API key for a translation service
([Before you start](#before-you-start-get-an-api-key)).

The first time it runs, it walks you through the following. **It asks for your language
first, and everything after that is shown in the language you picked.**

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
    番号 / number [1]: 2
    OK  Using English (incoming -> en / outgoing -> ja,ko,zh)
[2] Looking for Deep Rock Galactic
    OK  G:\SteamLibrary\steamapps\common\Deep Rock Galactic
[3] Checking UE4SS
    !!  UE4SS is not installed. The mod needs it to run.
    Download and install it now? (Y/n):
[4] Copying the mod
    OK  ...\Mods\DRGTranslate
    OK  Registered in mods.txt (DRGTranslate : 1)
[5] Choose a translation service
      1) DeepL    Machine translation. Has a free tier
      2) OpenAI   Good with slang and typos. Pay as you go
      3) Claude   Good with slang and typos. Pay as you go. Cheapest Haiku by default
    number [1]:
    Paste your API key (blank to cancel):
[6] Testing one translation
      気をつけろ、大群が来るぞ
        → Watch out, swarm incoming
    OK  Translation works
```

The language you pick is stored as `DRGT_UI_LANG` in `settings.ini` and used on every
later launch too (the messages in the console window are in that language as well).

Once setup is done the translator keeps running, so leave the window open and start the
game.

From the second launch on, setup is skipped and it goes straight to running.

**To run setup again**, delete `settings.ini` (next to the exe) and start
`DRGTranslate.exe`. It starts over from the beginning (you will have to paste your API
key again, so keep it at hand).

> **About antivirus warnings**
>
> This exe is not code-signed, so Windows Defender and some security software may warn
> about it. It is the usual false positive for an unsigned exe built with PyInstaller;
> the contents are exactly the source in this repository. If it bothers you, you can run
> from source instead (see the [developer guide](docs/DEVELOPMENT.md), Japanese).

`settings.ini` (settings and API key) and `cache.json` are created **next to the exe**,
so put the exe somewhere writable (not inside `Program Files`, for example).

---

## How to use it

1. **Start `DRGTranslate.exe`** (a console window opens — do not close it)
2. **Start Deep Rock Galactic**
3. Chat as you normally would

If something is missing from the settings, a warning appears in the console window right
after it starts.

```
provider=openai / incoming -> en / outgoing -> ja,ko,zh
==============================================================
Not ready to translate:
  Set OPENAI_API_KEY in settings.ini (https://platform.openai.com/api-keys)
==============================================================
```

**If you do not see that warning, you are good to start the game.**

| Situation | What happens |
|---|---|
| A fellow dwarf writes in Japanese/Korean/Chinese | The English translation appears on the next line |
| You write in English | It is translated into Japanese, Korean and Chinese and sent |
| You write in another language | Sent as is (not translated) |
| A message starting with `/` `!` `.` | Not translated (meant for commands) |
| **While you host** | Translations of other people's messages also go to everyone's chat ([below](#relaying-while-you-host)) |
| **F9** | Turns translation on and off (turning it off also drops anything queued for relay)<br>The change is shown on screen as `[DRGTranslate] Translation OFF` (everything the mod prints in game is plain ASCII so that it is readable whatever language the game runs in). While you host with other dwarves present it cannot be shown in game, so it goes to the console window instead |

The languages above assume the settings written for English.
[Change the language](#change-the-language) and "English" becomes whatever you picked.

> **Set the game language to the one you read.**
> If the game's font does not contain your characters, translations show up as boxes
> (□□□). This matters for Japanese, Korean, Chinese and Russian.

### How your own messages are sent

Translation goes over the network, so the result is not ready the instant you press
Enter. So **what you typed is sent as is, and the translation follows as a second
message** once it arrives.

```
You: please heal me
You: 回復お願いします / 회복 부탁드립니다 / 请帮我治疗一下
```

The original stays in the chat, so any dwarf who reads English can read it directly, and
when a translation goes wrong everyone can still see what it started from.

### Relaying while you host

You are the only one running the mod, so normally you are the only one who sees the
translations. **Only while you host a multiplayer game** can translations of other
people's messages be pushed to everyone's chat. That lets two dwarves who both lack the
mod understand each other.

The speaker's own language is left out, and **every language goes on one line**
(the same shape as your own translated messages). Languages are not labelled.

```
Karl: 気をつけろ、大群が来るぞ          <- a Japanese message
You: Karl: Watch out, swarm incoming / 조심해, 무리가 온다 / 小心，虫群来了
```

The `Karl:` at the front says whose message was translated (the relay is sent under the
host's name, so without it nobody could tell).

| Speaker's language | What gets relayed |
|---|---|
| Japanese | English, Korean, Chinese |
| Korean | English, Japanese, Chinese |
| Chinese | English, Japanese, Korean |
| English | Japanese, Korean, Chinese |
| Anything else (Russian and so on) | English, Japanese, Korean, Chinese |

English messages are relayed too. They are not shown translated on your own screen
(messages in your own language are not translated by default — showing something you can
already read twice just gets in the way), but they do reach dwarves who read other
languages. So even when a dwarf who writes in English does not have the mod, what they
say reaches the ones who do not read English.

- **Nothing is relayed when you host solo or play as a client.** Solo there is nobody to
  read it, so only your own translation is made and shown on your screen. As a client,
  the mod will not fill up somebody else's lobby chat.
- The translation shares the **one API call** already made for the incoming message
  (it just covers more languages).
- Messages that come out the same as the original, such as `Rock and Stone!`, are not
  relayed.
- To turn it off, put `DRGT_RELAY_ENABLED=false` in `settings.ini`. The languages and the
  format can be changed there too, with the `DRGT_RELAY_*` options.
- If lines get cut off by the game for being too long, set something like
  `DRGT_RELAY_MAX_LINE_CHARS=200` and lines are split at that length (the default `0`
  never splits).

> This definitely adds chat traffic. It is pleasant in a small lobby with friends, but in
> a busy public game narrowing it down, for example `DRGT_RELAY_TARGETS=en,ja`, is a good
> idea. **Keep your own language in the list.** While you host a multiplayer game the
> translation you read comes from this very line, so removing it leaves your own screen
> empty.

---

## Settings

### `settings.ini` — everything about translation

Double-click **`settings.ini`** next to the exe and it opens in Notepad (it is created
during the first-run setup). Save your changes and restart `DRGTranslate.exe`.
On a PC that hides file extensions it shows up as `settings`.

**Every option is listed with its default value and commented out.**
Just remove the leading `#` from the line you want to change.

```ini
# Which translation service to use: deepl / claude / openai
DRGT_PROVIDER=openai

# OpenAI  https://platform.openai.com/api-keys
OPENAI_API_KEY=sk-...

# Target languages (comma separated). Use just en if English is enough
#DRGT_OUTGOING_TARGETS=en,ko,zh
```

The main options are below. Every option is explained inside `settings.ini` itself.

| Key | What it does |
|---|---|
| `DRGT_UI_LANG` | Language of the setup wizard and the console window. `ja` / `en` / `ko` / `zh` / `zh-tw` / `ru`. When unset, the same language as `DRGT_INCOMING_TARGET` |
| `DRGT_PROVIDER` | `deepl` / `claude` / `openai` |
| `DEEPL_AUTH_KEY`<br>`ANTHROPIC_API_KEY`<br>`OPENAI_API_KEY` | API keys. You only need the one for the service you use |
| `DRGT_INCOMING_TARGET` | Which language incoming messages are translated into |
| `DRGT_OUTGOING_SOURCE` | Which language you type in (messages in any other language are sent as is) |
| `DRGT_OUTGOING_TARGETS` | Languages your messages are translated into, for example `ja,ko,zh`. Use `en` for English only, `zh-tw` for traditional Chinese. The source language is dropped automatically |
| `DRGT_RELAY_ENABLED` | Whether to push translations of other people's messages to everyone while you host. Default `true` |
| `DRGT_RELAY_TARGETS` | Languages to relay into (the speaker's own language is dropped automatically) |
| `DRGT_RELAY_MAX_LANGS` | How many languages one message may be relayed into. Default `4` (raise it to `5` if you relay into five languages, or the rest is silently dropped) |
| `DRGT_RELAY_MAX_LINE_CHARS` | Character limit for one relayed line. Default `0` (everything on one line) |
| `DRGT_INCOMING_FORMAT` | How a translation is shown. `{sender}` `{text}` `{lang}` `{original}` work |
| `DRGT_INCOMING_SKIP_LANGUAGES` | Languages that get no translation in your own chat. Defaults to the same as `DRGT_INCOMING_TARGET` (host relay works regardless of this) |
| `DRGT_CACHE_ENABLED` | Whether to store translations |
| `DRGT_OVERLAY_ENABLED` | A small window, as a backup when in-game display does not work |
| `DRGT_OVERLAY_HIDE_AFTER` | Seconds before the small window hides. Default `12`, `0` keeps it visible |

An environment variable of the same name set in Windows takes priority over
`settings.ini`.

### Change the language

**Normally picking a language at step `[1]` of the first-run setup is all you need.**
It writes `DRGT_UI_LANG`, `DRGT_INCOMING_TARGET`, `DRGT_INCOMING_FORMAT`,
`DRGT_OUTGOING_SOURCE`, `DRGT_OUTGOING_TARGETS`, `DRGT_RELAY_TARGETS` and
`DRGT_RELAY_MAX_LANGS` together to match (plus `DRGT_INCOMING_SKIP_LANGUAGES` for
traditional Chinese, because the language check cannot tell it apart from simplified). Edit `settings.ini` when you want to change it
later, or to use a language that is not on the list
([running setup again](#install) lets you pick another one).

Languages are written like `ja` (Japanese), `en` (English), `ko` (Korean),
`zh` (Chinese, simplified), `zh-tw` (Chinese, traditional), `ru` (Russian).

For example, someone who **reads and writes Japanese** and works with dwarves who speak
English and Korean would use:

```ini
# Incoming: turn what others say into Japanese (Japanese messages are left alone)
DRGT_INCOMING_TARGET=ja
DRGT_INCOMING_FORMAT=[訳] {sender}: {text}

# Outgoing: translate what you type in Japanese into English and Korean
DRGT_OUTGOING_SOURCE=ja
DRGT_OUTGOING_TARGETS=en,ko

# Relay: always include your own language (ja)
DRGT_RELAY_TARGETS=ja,en,ko
```

- **Only messages written in `DRGT_OUTGOING_SOURCE` are translated on the way out.**
  Anything in another language is sent unchanged.
- You do not need to set `DRGT_INCOMING_SKIP_LANGUAGES`. When left out it is the same as
  `DRGT_INCOMING_TARGET` (if you read English, English messages are not translated). Set
  it only to add languages you can read yourself (`ja,en` if you read Japanese but
  English is fine too).
- **Keep your own language in `DRGT_RELAY_TARGETS`.** While you host a multiplayer game
  the translation you read comes from that line, so removing it leaves your screen empty.
- Languages are told apart by their script. That means `en` covers not only English but
  every language written in the Latin alphabet, German and Spanish included. With
  `DRGT_INCOMING_SKIP_LANGUAGES=en`, none of those are translated.
- The glossary (`glossary.json`) translates into Japanese, so it is not used when
  incoming messages go into any other language (phrases like `Rock and Stone!` are simply
  left as they are).

### Translation service settings

`DRGT_PROVIDER` picks the service. Strengths and prices are listed under
[Before you start](#before-you-start-get-an-api-key).

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

The default model is **`claude-haiku-4-5`**. Chat is about one line at a time, so this is
plenty, and it is the fastest and cheapest. Raise `DRGT_CLAUDE_MODEL` if the wording is
not good enough.

| model | input/output (per million tokens) | when to use it |
|---|---|---|
| `claude-haiku-4-5` (default) | $1 / $5 | Plenty for short chat |
| `claude-sonnet-5` | $2 / $10 | For more natural phrasing |
| `claude-opus-5` | $5 / $25 | When long or complicated messages show up too |

One translation is roughly 330 input tokens (system prompt included) and 30 output
tokens, so with Haiku 4.5 **1000 translations cost around $0.5** (a rough figure).

What gets sent is adjusted to the model automatically, so leaving `DRGT_CLAUDE_EFFORT`
and `DRGT_CLAUDE_REFUSAL_FALLBACK` on `auto` is fine.

**OpenAI**

```ini
DRGT_PROVIDER=openai
OPENAI_API_KEY=sk-...
#DRGT_OPENAI_MODEL=gpt-4o-mini
```

The default model is `gpt-4o-mini`, the cheapest and fastest.

**Set `DRGT_OPENAI_BASE_URL` to point at another OpenAI-compatible endpoint.**
Point it at a local LLM (Ollama, LM Studio, llama.cpp and so on) and chat text never
leaves your PC.

```ini
DRGT_PROVIDER=openai
OPENAI_API_KEY=dummy
DRGT_OPENAI_BASE_URL=http://localhost:11434/v1
DRGT_OPENAI_MODEL=qwen2.5:7b
```

### Things to know about the LLM providers

- **Several languages are translated in one request.** English plus Korean plus Chinese
  is still a single API call.
- **The API is called only when you actually say something.** Nothing is translated while
  you type, so a message you started and gave up on costs nothing.
- **A translation can be refused**, over abusive wording for example. Only that one
  message goes untranslated; the game is unaffected. On models that support it, such as
  `claude-opus-5`, the automatic fallback to another model
  (`DRGT_CLAUDE_REFUSAL_FALLBACK`) kicks in.
- Replies are a little slower than machine translation. There is a short gap between the
  original message and its translation.
- Chat text is sent to Anthropic / OpenAI. If you would rather it did not leave your PC,
  use `openai` with `DRGT_OPENAI_BASE_URL` pointed at a local LLM as described above.

### `glossary.json` — the glossary

Set phrases such as `Rock and Stone!` are replaced immediately, without going through the
API. Common DRG phrases are registered out of the box (the file is bundled in the exe).

To add your own, download [bridge/glossary.json](bridge/glossary.json), put it **next to
the exe** and edit it. It is used instead of the bundled one.

The Japanese terms follow the [DRG Japanese wiki](https://wikiwiki.jp/rockandstone/)
(ナイトラ / ビスモル / エノアパール and so on). `Bulk Detonator` is officially
「グリフィッドバルクデトネーター」, but **デトネーター** is what Japanese players actually
say, so that is what is used.

```json
{
  "incoming": { "leaf lover": "リーフラバー（軟弱者）" },
  "outgoing": { "ありがとう": { "en": "Thanks!", "ko": "고마워요!", "zh": "谢谢！" } }
}
```

Keys are matched ignoring spaces, punctuation and letter case, so `rock and stone` and
`Rock and Stone!!` are treated as the same phrase.

### `config.lua` — behaviour inside the game

It lives in the game folder, at
`FSD\Binaries\Win64\Mods\DRGTranslate\Scripts\config.lua`
(some UE4SS versions use `Win64\ue4ss\Mods\...`).

| Option | What it does |
|---|---|
| `outgoing.enabled` | Whether your own messages are translated before they are sent |
| `outgoing.ignore_prefixes` | Messages starting with these are not translated |
| `outgoing.min_length` | Messages shorter than this are not translated |
| `incoming.skip_own` | Do not translate your own messages |
| `host_relay.enabled` | Whether to push translations to everyone while you host |
| `host_relay.interval_ms` | Delay between relayed lines, so they do not pile up. Default `700` |
| `host_relay.sender` | Name a relayed line is sent under. `self` (you) / `original` (the speaker) |
| `display.strategy` | How translations are displayed. `auto` / `gamestate` / `widget` / `off` |
| `debug` | Write verbose logs to the UE4SS console |

The file is commented in English so that it is readable whatever language you play in.
**Restart the game** after editing `config.lua`.
[Running setup again](#install) reinstalls the mod, and the `config.lua` you edited is
moved aside to `Mods\DRGTranslate.bak`.

---

## What has been tested

- Using the released exe as is, on a real machine (hosting solo): sending, translating
  incoming messages, relaying, the F9 toggle and Japanese/Korean/Chinese display all
  confirmed.
- Translating English messages into Japanese and Korean
  ([Change the language](#change-the-language)) confirmed on a real machine as well.
- DeepL, Claude and OpenAI have all been confirmed to actually translate.
- Setup and the console messages were checked in all six languages by automated runs
  (not yet inside a running game).
- **Whether Russian and traditional Chinese render in the game's font has not been
  checked** (Japanese, Korean and simplified Chinese have been).
- **Relaying to fellow dwarves in a lobby with several people has not been confirmed
  yet.**
- How the small window (`DRGT_OVERLAY_ENABLED=true`) looks in a real game is unconfirmed.

See [docs/TESTING.md](docs/TESTING.md) (Japanese) for details.

---

## Troubleshooting

**The game crashes right after it starts (EXCEPTION_ACCESS_VIOLATION)**
: First find out whether mods are the cause. Rename `FSD\Binaries\Win64\dwmapi.dll` to
  `dwmapi.dll.off` and UE4SS is disabled entirely, leaving the plain game. If that fixes
  it, the crash is on the UE4SS side. Check the following.

  1. Whether `bUseUObjectArrayCache` in `UE4SS-settings.ini` is `false`. With `true`,
     UE4SS can read a stale object pointer and crash.
  2. Whether the sample mods that ship with UE4SS (`ConsoleEnablerMod`, `BPModLoaderMod`
     and so on) are set to `: 0` in `Mods\mods.txt`. They are not needed for translation,
     and since they alter engine internals they are a common source of crashes.

  Setup does both of these automatically since v0.2.1. If you installed with an older
  version, delete `settings.ini`, start `DRGTranslate.exe` and go through setup again.
  If it still crashes, change `DRGTranslate : 1` in `mods.txt` to `: 0` and start the
  game to find out whether this mod itself is the cause.

  Note that v0.2.2 had a bug that crashed the game right after startup. It was fixed in
  v0.2.3.

**The mod is not loaded**
: Check that `dwmapi.dll` and `UE4SS.dll` are in `FSD\Binaries\Win64`.
  `Mods\mods.txt` needs a `DRGTranslate : 1` line.
  What was loaded is written to `UE4SS.log` in the same folder (rewritten on every
  launch). The separate UE4SS console window is off by default for stability; set
  `GuiConsoleEnabled` to `1` in `UE4SS-settings.ini` if you want to see it.

**It says the connection to the bridge was lost**
: `DRGTranslate.exe` is not running. Start it before the game.

**Translations do not show up**
: Check that `FSD\Binaries\Win64\UE4SS.log` has two `hook 登録: ...` lines. If they are
  missing, a game update may have renamed the functions. For more detail, set
  `debug = true` in `config.lua`.
  If only the display is broken, set `DRGT_OVERLAY_ENABLED=true` in `settings.ini` to get
  a small window instead (set the game's display mode to "Windowed (Fullscreen)").

**Text shows up as □□□**
: Set the game language to the language you read.

**I want to stop translating only my own messages**
: Set `outgoing.enabled` to `false` in `config.lua`. Incoming translation stays on.

**While hosting multiplayer, incoming translations do not use the usual format, or do not
appear at all**
: That is how it works. Anything put in the host's chat box reaches everyone, so incoming
  translations go out as a relay line, all languages on one line
  ([Relaying while you host](#relaying-while-you-host)). Your own language is among the
  relay targets by default, so you read it from that line.
  If you turned the relay off, or removed your language from `DRGT_RELAY_TARGETS`,
  nothing is shown, so set `DRGT_OVERLAY_ENABLED=true` in `settings.ini` to get a small
  window instead. It appears only when a translation arrives and hides after 12 seconds
  (`DRGT_OVERLAY_HIDE_AFTER`). The game's display mode has to be
  "Windowed (Fullscreen)" for it to stay in front.

---

## Things to be aware of

- UE4SS works outside Deep Rock Galactic's official mod management (mod.io). Install it
  at your own risk.
- What you say, once translated and sent, is of course visible to your fellow dwarves.
  Mistranslations are sent just the same.
- **For translation, chat text — including what other players say — is sent to an outside
  service (DeepL / Anthropic / OpenAI).** The people who said it cannot consent to that.
  If you would rather it did not leave your PC, use `openai` with `DRGT_OPENAI_BASE_URL`
  pointed at a local LLM.
- Chat text is also stored in `cache.json` (next to the exe). Set
  `DRGT_CACHE_ENABLED=false` in `settings.ini` if you do not want that.
- `claude` and `openai` are pay-as-you-go. The API is called only when you actually say
  something.

---

## For developers

| | |
|---|---|
| [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) | How it works, running from source, building the exe, releasing, file layout |
| [docs/TESTING.md](docs/TESTING.md) | Details of what has been tested (and what has not) |
| [docs/INTERNALS.md](docs/INTERNALS.md) | Notes on the DRG-side API that was analysed |

These documents are written in Japanese.

---

## License

The code and documentation in this repository are under the **MIT License**
([LICENSE](LICENSE)).

### About being an unofficial mod

This is an **unofficial fan project with no connection to Ghost Ship Games**. It is not
endorsed, sponsored or affiliated in any way.
"Deep Rock Galactic" and the names and terms from the game are trademarks or works of
Ghost Ship Games; this repository only mentions them as far as is needed to explain
interoperability. No game assets, code or executables are included.

Please read Ghost Ship Games' UGC policy before installing.

### Third-party things this depends on or references

| | License | How it is handled |
|---|---|---|
| [UE4SS](https://github.com/UE4SS-RE/RE-UE4SS) | MIT | **Not bundled.** Setup fetches it from the official release |
| [DRG-Modding/FSD-Template](https://github.com/DRG-Modding/FSD-Template)<br>[DRG-Modding/Header-Dumps](https://github.com/DRG-Modding/Header-Dumps) | Not stated | No code taken from them. See below |
| DeepL / Anthropic / OpenAI | Their own terms of service | You bring your own API key. Following their terms is your responsibility |

The function signatures and struct definitions in `docs/INTERNALS.md` were **extracted
directly from the game's own executable** (the procedure is in that document too). The
community repositories above are listed only as a cross-reference used to check the
findings; none of their files were taken.

### Disclaimer

As the MIT License says, there is no warranty. UE4SS operates outside Deep Rock
Galactic's official mod management (mod.io). The author is not responsible for any
problem or account consequence arising from installing or using this.
