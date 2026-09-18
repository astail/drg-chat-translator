# DRGTranslate

[日本語](README.md) | [English](README.en.md) | **한국어** | [简体中文](README.zh.md) | [繁體中文](README.zh-TW.md) | [Русский](README.ru.md)

Deep Rock Galactic 의 채팅을 자동으로 번역하는 모드입니다.

| 할 수 있는 것 | 호스트(멀티) | 호스트(솔로) | 클라이언트 |
|---|:---:|:---:|:---:|
| **수신** — 동료 드워프의 채팅을 내 언어로 번역해 채팅창에 표시 | 〇 | 〇 | 〇 |
| **송신** — 내가 한 말을 다른 언어로 번역해서 전송 | 〇 | 〇 | 〇 |
| **중계** — 동료 드워프의 말의 번역을 모두의 채팅에 흘려보냄 | 〇 | × | × |

"호스트"는 내가 방을 연 쪽, "클라이언트"는 남의 방에 들어간 쪽입니다.

설치할 때 어떤 언어로 읽을지 묻고, 그에 맞춰 설정을 써 줍니다. 한국어를 고르면 일본어,
영어, 중국어 등의 말이 **한국어**가 되고, 한국어로 친 말은 **일본어 · 영어 ·
중국어(간체)** 로 번역됩니다. 어느 언어에서 어느 언어로 번역할지는 설정 파일
(`settings.ini`)에서 바꿀 수 있습니다 ([언어 바꾸기](#언어-바꾸기)).

```
Karl: watch out, swarm incoming
[TL] Karl: 조심해, 무리가 온다

(내가 "회복 부탁드립니다" 라고 치면)
You: 회복 부탁드립니다
You: 回復お願いします / Please heal me / 请帮我治疗一下
```

게임에 넣는 모드(UE4SS 라는 모드용 외부 도구 위에서 동작합니다)와, 번역 서비스를
호출하는 상주 프로그램(`DRGTranslate.exe`) 두 가지로 동작합니다.

> Ghost Ship Games 와는 무관한 비공식 팬 프로젝트입니다. MIT License.
> 자세한 내용은 [라이선스](#라이선스)를 참고하세요.

소스에서 실행하는 방법, exe 빌드, 내부 구조는
[개발자 가이드](docs/DEVELOPMENT.md)(일본어)에 정리해 두었습니다.

---

## 시작하기 전에: 번역 서비스 API 키 준비

번역은 외부 번역 서비스에 맡깁니다. **쓰기 시작하기 전에 아래 중 하나에 가입해서
"API 키"를 발급해 두세요.** API 키는 그 서비스를 이 프로그램에서 쓰기 위한 암호 같은
문자열이며, 첫 실행 설치 과정에서 붙여넣습니다. 미리 준비해 두지 않으면 설치 도중에
멈추게 됩니다.

| 서비스 | 특징 | 요금 | 가입 · API 키 발급 |
|---|---|---|---|
| **DeepL**(기본값) | 기계 번역 중에서는 가장 자연스러움 | 무료 체험 한도 있음. 다 쓰면 유료 플랜 | https://www.deepl.com/pro-api |
| **Claude**(Anthropic) | 속어 · 줄임말 · 오타에 강함. `gg` `bulk inc` `res me` 를 문맥으로 번역 | 쓴 만큼 내는 종량 과금. 기본값인 Claude Haiku 4.5 라면 **1000회 번역에 약 $0.5** | https://platform.claude.com/settings/keys |
| **OpenAI** | 속어 · 줄임말 · 오타에 강함. `gg` `bulk inc` `res me` 를 문맥으로 번역 | 쓴 만큼 내는 종량 과금. 기본값인 gpt-4o-mini 라면 **1000회 번역에 약 $0.1 미만** | https://platform.openai.com/api-keys |

평범한 대화가 중심이라면 DeepL 로 충분합니다. 줄임말과 오타가 많은 공개 멀티에서
정확도를 올리고 싶다면 Claude 나 OpenAI 를 고르세요. `Rock and Stone` 같은 관용구는
용어집이 처리하므로 어느 서비스를 써도 같은 번역이 나옵니다.

- 요금과 무료 한도 조건은 바뀔 수 있습니다. 가입하기 전에 각 서비스의 요금 페이지를
  확인하세요.
- **API 키는 남에게 알려주지 마세요.** 다른 사람이 쓰면 그만큼 요금이 청구됩니다.

---

## 설치

[**Releases**](https://github.com/astail/drg-translation/releases) 에서
`DRGTranslate-vX.Y.Z-win64.zip` 을 받아 압축을 푸세요. 내용물은 다음과 같습니다.

```
DRGTranslate.exe      이것만 있으면 동작합니다
settings.example.ini  설정 파일 견본(모든 항목 설명 포함. 영어)
はじめに.txt          3단계 안내(일본어)
README.md 등          각 언어의 README / LICENSE
```

**`DRGTranslate.exe` 를 더블클릭하기만 하면 됩니다.** 따로 설치할 것은 없습니다.
준비할 것은 **번역 서비스의 API 키뿐**입니다
([시작하기 전에](#시작하기-전에-번역-서비스-api-키-준비)).

첫 실행 때 다음 순서로 안내합니다. **먼저 언어를 묻고, 그 뒤의 안내는 고른 언어로
나옵니다.**

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
    番号 / number [1]: 3
    OK  한국어 로 설정합니다 (수신 -> ko / 송신 -> ja,en,zh)
[2] Deep Rock Galactic 을 찾는 중입니다
    OK  G:\SteamLibrary\steamapps\common\Deep Rock Galactic
[3] UE4SS 를 확인하는 중입니다
    !!  UE4SS 가 설치되어 있지 않습니다. 모드 동작에 필요합니다.
    지금 다운로드해서 설치할까요? (Y/n):
[4] 모드를 복사하는 중입니다
    OK  ...\Mods\DRGTranslate
    OK  mods.txt 에 등록했습니다 (DRGTranslate : 1)
[5] 번역 서비스를 선택하세요
      1) DeepL    기계 번역. 무료 체험 한도 있음
      2) OpenAI   속어와 오타에 강함. 쓴 만큼 과금
      3) Claude   속어와 오타에 강함. 쓴 만큼 과금. 기본값은 가장 저렴한 Haiku
    번호 [1]:
    API 키를 붙여넣으세요 (비워 두면 취소):
[6] 번역을 한 번 시험합니다
      watch out, swarm incoming
        → 조심해, 무리가 온다
    OK  번역에 성공했습니다
```

여기서 고른 언어는 `settings.ini` 의 `DRGT_UI_LANG` 에 남아 두 번째 실행부터도
쓰입니다(검은 창에 나오는 메시지도 그 언어가 됩니다).

설정이 끝나면 그대로 번역 프로세스가 상주하므로, 창을 열어 둔 채로 게임을 실행하세요.

두 번째부터는 설치 과정을 건너뛰고 바로 상주 상태가 됩니다.

**설치를 처음부터 다시 하고 싶을 때**는 exe 와 같은 폴더에 있는 `settings.ini` 를 지운
뒤 `DRGTranslate.exe` 를 실행하세요. 처음 설치 과정부터 시작됩니다(API 키도 다시
넣어야 하므로 미리 준비해 두세요).

> **백신 프로그램 경고에 대해**
>
> 이 exe 는 서명되어 있지 않아 Windows Defender 나 일부 보안 소프트웨어가 경고를 낼 수
> 있습니다. PyInstaller 로 만든 서명 없는 exe 에서 흔히 일어나는 오탐이며, 내용물은 이
> 저장소의 소스 그대로입니다. 신경 쓰인다면 exe 대신 소스에서 실행할 수도 있습니다
> ([개발자 가이드](docs/DEVELOPMENT.md), 일본어).

`settings.ini`(설정과 API 키)와 `cache.json` 은 **exe 와 같은 폴더**에 만들어집니다.
쓰기가 가능한 곳에 두세요(`Program Files` 안 등은 피하세요).

---

## 사용법

1. **`DRGTranslate.exe` 실행**(검은 창이 뜹니다. 닫지 마세요)
2. **Deep Rock Galactic 실행**
3. 평소처럼 채팅하면 됩니다

설정이 부족하면 검은 창이 뜬 직후에 경고가 나옵니다.

```
provider=openai / 수신 -> ko / 송신 -> ja,en,zh
==============================================================
아직 번역할 수 없는 상태입니다:
  settings.ini 에 OPENAI_API_KEY 를 설정하세요 (https://platform.openai.com/api-keys)
==============================================================
```

**이 경고가 나오지 않으면 그대로 게임을 실행해도 됩니다.**

| 상황 | 동작 |
|---|---|
| 동료 드워프가 일본어/영어/중국어로 말함 | 한국어 번역이 다음 줄에 나옴 |
| 내가 한국어로 말함 | 일본어 · 영어 · 중국어로 번역되어 전송됨 |
| 내가 한국어 외의 언어로 말함 | 그대로 전송(번역하지 않음) |
| `/` `!` `.` 로 시작하는 말 | 번역하지 않음(명령어용) |
| **내가 호스트일 때** | 동료 드워프의 말의 번역을 모두의 채팅에도 흘려보냄([아래](#내가-호스트일-때의-중계)) |
| **F9** | 번역 ON/OFF 전환(OFF 로 하면 중계 대기열도 버립니다)<br>전환한 것은 `[DRGTranslate] Translation OFF` 로 화면에 나옵니다(게임 언어가 무엇이든 읽을 수 있도록, 게임 안에 내보내는 글자는 영숫자로 맞췄습니다). 동료 드워프가 있는 호스트일 때만은 내보낼 수 없어 검은 창에 표시합니다 |

언어는 한국어를 고른 경우입니다. [언어 바꾸기](#언어-바꾸기)를 하면 이 표의 "한국어"가
그 언어로 바뀝니다.

> **게임 언어를 자신이 읽는 언어로 맞춰 두세요.**
> 게임 글꼴에 해당 문자가 없으면 번역문이 네모(□□□)로 보입니다.

### 내가 한 말이 전송되는 방식

번역은 네트워크를 거치므로 Enter 를 누른 순간에는 결과가 나오지 않습니다. 그래서
**친 말을 그대로 먼저 보내고, 번역이 도착하면 두 번째 메시지로 보내는** 방식입니다.

```
You: 회복 부탁드립니다
You: 回復お願いします / Please heal me / 请帮我治疗一下
```

원문이 남으므로 한국어를 아는 동료가 있으면 그대로 읽을 수 있고, 오역이 있어도 원래
무엇이었는지 알 수 있습니다.

### 내가 호스트일 때의 중계

모드를 넣은 것은 나뿐이라서 보통은 번역문이 보이는 것도 나뿐입니다. **호스트(멀티)일
때만** 동료 드워프의 말의 번역을 모두의 채팅에 흘려보낼 수 있습니다. 모드를 갖고 있지
않은 동료들끼리도 대화가 통하게 됩니다.

말한 사람의 언어는 빼고 번역해서, **모든 언어를 묶어 한 줄**로 흘려보냅니다(내 말을
번역해서 보낼 때와 같은 모양입니다). 언어 표시는 붙이지 않습니다.

```
Karl: watch out, swarm incoming          ← 영어 발언
You: Karl: 気をつけろ、大群が来るぞ / 조심해, 무리가 온다 / 小心，虫群来了
```

줄 앞의 `Karl:` 은 "누구의 말의 번역인지"를 나타냅니다(중계는 호스트의 이름으로
보내지므로, 이것이 없으면 누구의 말이었는지 알 수 없게 됩니다).

| 말한 사람의 언어 | 흘려보내는 번역 |
|---|---|
| 영어 | 한국어 · 일본어 · 중국어 |
| 일본어 | 한국어 · 영어 · 중국어 |
| 중국어 | 한국어 · 일본어 · 영어 |
| 한국어 | 일본어 · 영어 · 중국어 |
| 그 외(러시아어 등) | 한국어 · 일본어 · 영어 · 중국어 |

한국어 발언도 중계합니다. 내 화면에는 번역을 내보내지 않지만(내 언어로 된 말은 기본적으로
번역하지 않습니다. 읽을 수 있는 것을 두 번 보여 줘도 방해가 되기 때문입니다), 다른
언어로 말하는 동료에게는 전달합니다. 한국어로 말하는 동료가 모드를 갖고 있지 않아도, 그
말이 외국어로 말하는 동료에게 전해집니다.

- **호스트(솔로)일 때와 클라이언트일 때는 중계하지 않습니다.** 솔로에서는 읽을 상대가
  없으므로 번역은 한국어만 만들어 내 화면에 표시합니다. 클라이언트일 때는 남이 연 방의
  채팅을 멋대로 채우지 않습니다.
- 번역은 수신분과 같은 **한 번의 API 호출로 묶입니다**(번역할 언어는 늘어납니다).
- `Rock and Stone!` 처럼 번역해도 원문과 다르지 않은 말은 흘려보내지 않습니다.
- 끄려면 `settings.ini` 에 `DRGT_RELAY_ENABLED=false` 를 쓰세요. 흘려보낼 언어나 서식도
  `settings.ini` 의 `DRGT_RELAY_*` 로 바꿀 수 있습니다.
- 너무 길어서 게임 쪽에서 잘린다면 `DRGT_RELAY_MAX_LINE_CHARS=200` 처럼 쓰면 그 글자
  수로 줄을 나눠 보냅니다(기본값 `0` 은 나누지 않습니다).

> 채팅 양은 확실히 늘어납니다. 소수의 지인 방이라면 쾌적하지만, 공개 방에서 대화가 많을
> 때는 `DRGT_RELAY_TARGETS=ko,en` 처럼 줄이는 것을 권합니다. **`ko` 는 남겨 두세요.**
> 호스트(멀티)에서는 내가 읽는 번역도 이 줄에서 읽으므로, `ko` 를 빼면 내 화면에도
> 번역이 나오지 않습니다.

---

## 설정

### `settings.ini` — 번역 관련

exe 와 같은 폴더에 있는 **`settings.ini`** 를 더블클릭하면 메모장으로 열립니다(첫 설치
때 만들어집니다). 고쳐서 저장했으면 `DRGTranslate.exe` 를 다시 실행하세요. 파일 확장자를
표시하지 않는 PC 에서는 `settings` 로 보입니다.

**모든 항목이 기본값과 함께 주석 처리되어 있습니다.**
바꾸고 싶은 줄 앞의 `#` 을 지우기만 하면 됩니다.
(파일 안의 설명은 어느 언어를 쓰는 사람이든 읽을 수 있도록 영어로 쓰여 있습니다.)

```ini
# Which translation service to use: deepl / claude / openai
DRGT_PROVIDER=openai

# OpenAI  https://platform.openai.com/api-keys
OPENAI_API_KEY=sk-...

# Target languages (comma separated). Use just en if English is enough
#DRGT_OUTGOING_TARGETS=ja,en,zh
```

주요 항목은 다음과 같습니다. 모든 항목의 설명은 `settings.ini` 안에 쓰여 있습니다.

| 키 | 설명 |
|---|---|
| `DRGT_UI_LANG` | 설치 과정과 검은 창 메시지의 언어. `ja` / `en` / `ko` / `zh` / `zh-tw` / `ru`. 설정하지 않으면 `DRGT_INCOMING_TARGET` 과 같은 언어 |
| `DRGT_PROVIDER` | `deepl` / `claude` / `openai` |
| `DEEPL_AUTH_KEY`<br>`ANTHROPIC_API_KEY`<br>`OPENAI_API_KEY` | API 키. 쓰는 서비스의 것만 있으면 됩니다 |
| `DRGT_INCOMING_TARGET` | 받은 말을 어느 언어로 번역할지 |
| `DRGT_OUTGOING_SOURCE` | 어느 언어로 친 말을 번역할지(그 외 언어의 말은 그대로 전송) |
| `DRGT_OUTGOING_TARGETS` | 전송할 때의 번역 대상. 예: `ja,en,zh`. 영어만이면 `en`, 번체자는 `zh-tw`. 원문과 같은 언어는 자동으로 제외 |
| `DRGT_RELAY_ENABLED` | 호스트일 때 동료의 말의 번역을 모두에게 흘려보낼지. 기본값 `true` |
| `DRGT_RELAY_TARGETS` | 중계 대상 언어(말한 사람의 언어는 자동 제외) |
| `DRGT_RELAY_MAX_LANGS` | 한 발언당 중계할 언어 수 상한. 기본값 `4`(대상을 5개 언어로 늘리면 `5` 로 올리세요. 넘친 만큼은 나가지 않습니다) |
| `DRGT_RELAY_MAX_LINE_CHARS` | 중계 한 줄의 글자 수 상한. 기본값 `0`(전부 한 줄) |
| `DRGT_INCOMING_FORMAT` | 표시 형식. `{sender}` `{text}` `{lang}` `{original}` 을 쓸 수 있습니다 |
| `DRGT_INCOMING_SKIP_LANGUAGES` | 이 언어는 내 채팅에 번역을 내보내지 않음. 기본값은 `DRGT_INCOMING_TARGET` 과 동일(호스트 중계는 이 설정과 무관하게 동작합니다) |
| `DRGT_CACHE_ENABLED` | 번역 결과를 저장할지 |
| `DRGT_OVERLAY_ENABLED` | 게임 내 표시가 안 될 때의 보험이 되는 작은 창 |
| `DRGT_OVERLAY_HIDE_AFTER` | 작은 창이 사라지기까지의 초. 기본값 `12`, `0` 이면 계속 표시 |

OS 쪽에 같은 이름의 환경 변수가 있으면 그쪽이 `settings.ini` 보다 우선합니다.

### 언어 바꾸기

**보통은 첫 설치의 `[1]` 에서 고르는 것만으로 끝납니다.** 고른 언어에 맞춰
`DRGT_UI_LANG` / `DRGT_INCOMING_TARGET` / `DRGT_INCOMING_FORMAT` /
`DRGT_OUTGOING_SOURCE` / `DRGT_OUTGOING_TARGETS` / `DRGT_RELAY_TARGETS` /
`DRGT_RELAY_MAX_LANGS` 가 한꺼번에 쓰입니다(번체 중국어일 때는
`DRGT_INCOMING_SKIP_LANGUAGES` 도. 언어 판별이 간체와 번체를 구분하지 못하기 때문입니다). 나중에 바꾸고 싶거나 목록에 없는 언어를
쓰고 싶을 때는 `settings.ini` 를 고치세요([설치를 다시 하면](#설치) 다시 고를 수도
있습니다).

언어는 `ja`(일본어) / `en`(영어) / `ko`(한국어) / `zh`(중국어 간체) /
`zh-tw`(중국어 번체) / `ru`(러시아어) 처럼 씁니다.

예를 들어 **영어로 읽고 쓰는 사람**이 일본어 · 한국어로 말하는 동료와 일한다면 다음과
같이 합니다.

```ini
# 수신: 다른 사람의 말을 영어로(영어 발언은 번역하지 않음)
DRGT_INCOMING_TARGET=en
DRGT_INCOMING_FORMAT=[TL] {sender}: {text}

# 송신: 영어로 친 말을 일본어와 한국어로
DRGT_OUTGOING_SOURCE=en
DRGT_OUTGOING_TARGETS=ja,ko

# 중계: 자신의 언어(en)를 반드시 넣기
DRGT_RELAY_TARGETS=en,ja,ko
```

- **송신에서 번역되는 것은 `DRGT_OUTGOING_SOURCE` 의 언어로 친 말뿐입니다.** 그 외
  언어로 친 말은 그대로 전송됩니다.
- `DRGT_INCOMING_SKIP_LANGUAGES` 는 쓰지 않아도 됩니다. 생략하면
  `DRGT_INCOMING_TARGET` 과 같은 언어가 됩니다(한국어로 읽으면 한국어 발언은 번역하지
  않음). 자신이 읽을 수 있는 언어를 더하고 싶을 때만 쓰세요(한국어로 읽지만 영어도
  읽는다면 `ko,en`).
- **`DRGT_RELAY_TARGETS` 에는 자신의 언어를 넣으세요.** 호스트(멀티)에서는 내가 읽는
  번역도 이 줄에서 읽으므로, 빼면 내 화면에 아무것도 나오지 않습니다.
- 언어는 문자의 종류로 구분합니다. 그래서 `en` 은 영어뿐 아니라 독일어나 스페인어 등
  라틴 문자를 쓰는 모든 언어를 가리킵니다. `DRGT_INCOMING_SKIP_LANGUAGES=en` 으로 하면
  그 언어들의 발언도 번역하지 않게 됩니다.
- 용어집(`glossary.json`)의 번역은 일본어이므로, 수신 번역 대상을 일본어 외로 하면
  쓰이지 않습니다(`Rock and Stone!` 같은 구호는 그대로 나옵니다).

### 번역 서비스 설정

쓸 번역 서비스는 `DRGT_PROVIDER` 로 바꿉니다. 서비스별 특징과 요금은
[시작하기 전에](#시작하기-전에-번역-서비스-api-키-준비)를 보세요.

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

기본 모델은 **`claude-haiku-4-5`** 입니다. 채팅은 한 줄 정도의 짧은 글이라 이것으로
충분하고 가장 빠르고 저렴합니다. 번역이 아쉬우면 `DRGT_CLAUDE_MODEL` 을 올리세요.

| model | 입력/출력 (100만 토큰당) | 기준 |
|---|---|---|
| `claude-haiku-4-5` (기본값) | $1 / $5 | 짧은 채팅이라면 이것으로 충분 |
| `claude-sonnet-5` | $2 / $10 | 표현의 자연스러움을 올리고 싶을 때 |
| `claude-opus-5` | $5 / $25 | 긴 글이나 복잡한 내용도 섞일 때 |

한 번의 번역은 시스템 프롬프트를 포함해 입력 약 330 토큰 · 출력 약 30 토큰이므로,
Haiku 4.5 라면 **대략 1000회 번역에 $0.5 정도**입니다(어디까지나 기준).

모델에 맞춰 보내는 내용은 자동으로 조정되므로, `DRGT_CLAUDE_EFFORT` 와
`DRGT_CLAUDE_REFUSAL_FALLBACK` 의 `auto` 는 그대로 두어도 문제없습니다.

**OpenAI**

```ini
DRGT_PROVIDER=openai
OPENAI_API_KEY=sk-...
#DRGT_OPENAI_MODEL=gpt-4o-mini
```

기본 모델은 가장 저렴하고 빠른 `gpt-4o-mini` 입니다.

**`DRGT_OPENAI_BASE_URL` 을 설정하면 OpenAI 호환의 다른 엔드포인트로 향할 수 있습니다.**
Ollama / LM Studio / llama.cpp 같은 로컬 LLM 을 지정하면 채팅 본문을 전혀 밖으로 내보내지
않고 번역할 수 있습니다.

```ini
DRGT_PROVIDER=openai
OPENAI_API_KEY=dummy
DRGT_OPENAI_BASE_URL=http://localhost:11434/v1
DRGT_OPENAI_MODEL=qwen2.5:7b
```

### LLM 을 쓸 때의 주의

- **한 번의 전송으로 여러 언어를 한꺼번에 번역합니다.** 영어 + 일본어 + 중국어라도 API
  호출은 한 번입니다.
- **API 를 부르는 것은 실제로 말했을 때뿐입니다.** 입력 중에는 번역을 보내지 않으므로,
  치다 만 문장에 과금되는 일은 없습니다.
- **욕설 등으로 번역이 거부될 수 있습니다.** 그 한 건만 번역되지 않을 뿐 게임 동작에는
  영향이 없습니다. `claude-opus-5` 같은 대응 모델을 쓰는 경우에는 자동으로 다른 모델로
  돌리는 설정(`DRGT_CLAUDE_REFUSAL_FALLBACK`)이 동작합니다.
- 응답은 기계 번역보다 약간 느립니다. 원문 직후에 번역이 도착하기까지 조금 간격이
  생깁니다.
- 채팅 본문이 Anthropic / OpenAI 로 전송됩니다. 밖으로 내보내고 싶지 않다면 위와 같이
  `openai` + `DRGT_OPENAI_BASE_URL` 로 로컬 LLM 을 향하게 하세요.

### `glossary.json` — 용어집

`Rock and Stone!` 같은 관용구를 API 를 거치지 않고 즉시 치환합니다. DRG 의 자주 쓰는
표현이 처음부터 등록되어 있습니다(exe 에 포함되어 있습니다).

직접 추가하고 싶을 때는 [bridge/glossary.json](bridge/glossary.json) 을 받아 **exe 와
같은 폴더**에 두고 편집하세요. 포함된 것 대신 그쪽이 쓰입니다.

일본어 용어는 [DRG 일본어 위키](https://wikiwiki.jp/rockandstone/)에 맞추고 있습니다
(ナイトラ / ビスモル / エノアパール 등).

```json
{
  "incoming": { "leaf lover": "リーフラバー（軟弱者）" },
  "outgoing": { "ありがとう": { "en": "Thanks!", "ko": "고마워요!", "zh": "谢谢！" } }
}
```

키는 공백 · 기호 · 대소문자를 무시하고 대조하므로 `rock and stone` 과
`Rock and Stone!!` 은 같은 것으로 취급됩니다.

### `config.lua` — 게임 안에서의 동작

게임 폴더의 `FSD\Binaries\Win64\Mods\DRGTranslate\Scripts\config.lua` 에 있습니다
(UE4SS 버전에 따라서는 `Win64\ue4ss\Mods\...`).

| 항목 | 설명 |
|---|---|
| `outgoing.enabled` | 내 발언을 번역해서 보낼지 |
| `outgoing.ignore_prefixes` | 이 문자로 시작하는 발언은 번역하지 않음 |
| `outgoing.min_length` | 이 글자 수 미만은 번역하지 않음 |
| `incoming.skip_own` | 내 발언은 번역하지 않음 |
| `host_relay.enabled` | 호스트일 때 동료의 말의 번역을 모두에게 흘려보낼지 |
| `host_relay.interval_ms` | 중계를 보내는 간격. 발언이 겹쳤을 때의 밀림 방지. 기본값 `700` |
| `host_relay.sender` | 중계 줄의 발신자 이름. `self`(나) / `original`(원래 발언자) |
| `display.strategy` | 번역 표시 방법. `auto` / `gamestate` / `widget` / `off` |
| `debug` | UE4SS 콘솔에 상세 로그를 출력 |

파일 안의 설명은 어느 언어를 쓰는 사람이든 읽을 수 있도록 영어로 쓰여 있습니다.
`config.lua` 를 고쳤으면 **게임을 재시작**하세요.
[설치를 다시 하면](#설치) 모드가 다시 설치되고, 편집하던 `config.lua` 는
`Mods\DRGTranslate.bak` 으로 옮겨집니다.

---

## 동작 확인 현황

- 배포 중인 exe 를 그대로 써서 실제 환경(솔로 호스트)에서 일본어 송신 · 수신 번역 ·
  중계 · F9 전환 · 일본어/한국어/중국어 표시까지는 확인했습니다.
- 영어로 친 말을 일본어 · 한국어로 번역하는 설정([언어 바꾸기](#언어-바꾸기))도 실제
  환경에서 확인했습니다.
- DeepL / Claude / OpenAI 세 가지 모두 실제로 번역되는 것을 확인했습니다.
- 설치 과정과 검은 창 메시지는 6개 언어 모두 기계적으로 확인했습니다(실제 게임을 실행한 확인은 아직입니다).
- **러시아어와 번체 중국어가 게임 글꼴로 표시되는지는 확인하지 못했습니다**(일본어 · 한국어 · 간체 중국어는 확인 완료).
- **여러 명이 있는 로비에서 중계가 동료에게 도달하는 것은 아직 확인하지 못했습니다.**
- 작은 창(`DRGT_OVERLAY_ENABLED=true`)이 실제 환경에서 어떻게 보이는지도 미확인입니다.

자세한 내용은 [docs/TESTING.md](docs/TESTING.md)(일본어)를 참고하세요.

---

## 문제 해결

**게임이 실행 직후에 튕긴다(EXCEPTION_ACCESS_VIOLATION)**
: 먼저 모드를 분리해 봅니다. `FSD\Binaries\Win64\dwmapi.dll` 의 이름을
  `dwmapi.dll.off` 로 바꾸면 UE4SS 째로 꺼져 순정 게임으로 돌아갑니다. 이걸로 해결되면
  튕김은 UE4SS 쪽입니다. 다음을 확인하세요.

  1. `UE4SS-settings.ini` 의 `bUseUObjectArrayCache` 가 `false` 인지. `true` 면 UE4SS 가
     오래된 객체의 포인터를 읽어 튕길 수 있습니다.
  2. `Mods\mods.txt` 에서 UE4SS 에 포함된 예제 모드(`ConsoleEnablerMod`,
     `BPModLoaderMod` 등)가 `: 0` 인지. 번역에는 불필요하고 엔진 내부를 건드리므로 튕김의
     원인이 되기 쉽습니다.

  둘 다 v0.2.1 이후의 설치 과정이 자동으로 합니다. 옛 버전으로 넣었다면 `settings.ini`
  를 지운 뒤 `DRGTranslate.exe` 를 실행해 설치를 다시 하면 해결됩니다.
  그래도 튕긴다면 `mods.txt` 의 `DRGTranslate : 1` 을 `: 0` 으로 바꿔 실행해, 모드 본체가
  원인인지 확인하세요.

  참고로 v0.2.2 에는 실행 직후 튕기는 문제가 있었습니다. v0.2.3 에서 해결되었습니다.

**모드가 로드되지 않는다**
: `FSD\Binaries\Win64` 에 `dwmapi.dll` 과 `UE4SS.dll` 이 있는지 확인하세요.
  `Mods\mods.txt` 에 `DRGTranslate : 1` 줄이 필요합니다.
  로드 상황은 같은 폴더의 `UE4SS.log` 에 나옵니다(실행할 때마다 새로 쓰입니다).
  UE4SS 의 별도 콘솔 창은 안정성을 위해 기본적으로 꺼 두었습니다. 보고 싶다면
  `UE4SS-settings.ini` 의 `GuiConsoleEnabled` 를 `1` 로 하세요.

**"bridge 와의 연결이 끊겼습니다" 라고 나온다**
: `DRGTranslate.exe` 가 동작하고 있지 않습니다. 게임보다 먼저 실행하세요.

**번역이 표시되지 않는다**
: `FSD\Binaries\Win64\UE4SS.log` 에 `hook 登録: ...` 이 두 줄 나오는지 확인하세요.
  나오지 않는다면 게임 업데이트로 함수 이름이 바뀌었을 가능성이 있습니다.
  더 자세히 보려면 `config.lua` 의 `debug = true` 로 하세요.
  표시만 안 되는 경우에는 `settings.ini` 의 `DRGT_OVERLAY_ENABLED=true` 로 하면 작은 창에
  띄울 수 있습니다(게임 표시 설정을 "창 모드(전체 화면)"로 하세요).

**글자가 □□□ 로 보인다**
: 게임 언어 설정을 자신이 읽는 언어로 맞추세요.

**내 발언만 번역을 멈추고 싶다**
: `config.lua` 의 `outgoing.enabled` 를 `false` 로 하세요. 수신 번역만 남습니다.

**호스트(멀티)일 때 수신 번역이 평소 서식으로 나오지 않는다 / 아무것도 나오지 않는다**
: 사양입니다. 호스트의 채팅창에 내보낸 것은 모두에게 전달되므로, 수신 번역은 중계 줄로
  한 줄에 묶어 흘려보내고 있습니다([내가 호스트일 때의 중계](#내가-호스트일-때의-중계)).
  기본값에서는 중계 언어에 자신의 언어가 포함되므로 그 줄에서 읽을 수 있습니다.
  중계를 껐거나 `DRGT_RELAY_TARGETS` 에서 자신의 언어를 뺀 경우에는 아무것도 나오지
  않으므로, `settings.ini` 의 `DRGT_OVERLAY_ENABLED=true` 로 하면 작은 창에 띄울 수
  있습니다. 작은 창은 번역이 도착했을 때만 나오고 12초 뒤에 사라집니다
  (`DRGT_OVERLAY_HIDE_AFTER`). 게임 표시 설정은 "창 모드(전체 화면)"가 아니면 앞으로
  나오지 않습니다.

---

## 주의

- UE4SS 는 Deep Rock Galactic 공식 모드 관리(mod.io) 바깥에서 동작하는 구조입니다. 도입은
  자기 책임으로 부탁드립니다.
- 번역해서 보낸 말은 당연히 동료 드워프에게도 보입니다. 오역도 그대로 전송됩니다.
- **번역을 위해 다른 플레이어의 발언을 포함한 채팅 본문이 외부 서비스(DeepL / Anthropic /
  OpenAI)로 전송됩니다.** 발언자 본인의 동의는 받을 수 없습니다. 밖으로 내보내고 싶지
  않다면 `openai` + `DRGT_OPENAI_BASE_URL` 로 로컬 LLM 을 향하게 하세요.
- 채팅 본문은 `cache.json`(exe 와 같은 폴더)에도 저장됩니다. 필요 없으면 `settings.ini`
  의 `DRGT_CACHE_ENABLED=false` 로 하세요.
- `claude` / `openai` 는 종량 과금입니다. 실제로 말했을 때만 API 를 부릅니다.

---

## 개발자용

| | |
|---|---|
| [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) | 구조, 소스에서 쓰는 법, exe 빌드, 릴리스, 파일 구성 |
| [docs/TESTING.md](docs/TESTING.md) | 동작 확인 현황의 상세(무엇이 미확인인지도) |
| [docs/INTERNALS.md](docs/INTERNALS.md) | 분석한 DRG 쪽 API 메모 |

이 문서들은 일본어로 쓰여 있습니다.

---

## 라이선스

이 저장소의 코드와 문서는 **MIT License** 입니다([LICENSE](LICENSE)).

### 비공식 모드라는 것에 대해

본 프로젝트는 **Ghost Ship Games 와는 무관한 비공식 팬 프로젝트**입니다.
공인 · 후원 · 제휴 어느 것도 아닙니다.
"Deep Rock Galactic" 및 게임 내 명칭 · 용어는 Ghost Ship Games 의 상표 또는 저작물이며,
본 저장소에서는 상호 운용을 설명하는 데 필요한 범위에서 언급할 뿐입니다.
게임의 에셋 · 코드 · 실행 파일은 일절 포함하지 않았습니다.

도입 전에 Ghost Ship Games 의 UGC 정책을 확인하세요.

### 의존 · 참조하는 제삼자의 것

| | 라이선스 | 취급 |
|---|---|---|
| [UE4SS](https://github.com/UE4SS-RE/RE-UE4SS) | MIT | **포함하지 않았습니다.** 설치할 때 공식 릴리스에서 받습니다 |
| [DRG-Modding/FSD-Template](https://github.com/DRG-Modding/FSD-Template)<br>[DRG-Modding/Header-Dumps](https://github.com/DRG-Modding/Header-Dumps) | 미설정 | 코드는 가져오지 않았습니다. 아래 참조 |
| DeepL / Anthropic / OpenAI | 각 사의 이용 약관 | API 키는 이용자가 준비합니다. 각 사의 약관 준수는 이용자의 책임입니다 |

`docs/INTERNALS.md` 에 실린 함수 시그니처 · 구조체 정의는 **게임 본체의 실행 파일에서
직접 추출해 확인한 것**입니다(추출 절차도 같은 문서에 기재). 위 커뮤니티 저장소는 교차
확인용으로 들었을 뿐이며, 그 파일들을 가져오지는 않았습니다.

### 면책

MIT License 대로 무보증입니다. UE4SS 는 Deep Rock Galactic 공식 모드 관리(mod.io) 바깥에서
동작합니다. 도입 · 이용으로 생긴 어떠한 문제 · 계정상의 불이익에 대해서도 작성자는 책임을
지지 않습니다.
