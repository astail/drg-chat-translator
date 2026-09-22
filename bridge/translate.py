"""翻訳エンジン・言語判定・キャッシュ・用語集。

対応プロバイダは deepl / claude / openai の3つ。
deepl は標準ライブラリだけで動く。claude と openai は各社の公式SDKを使うが、
import は実際に使うときまで遅延させてあるので、未インストールでも
bridge の起動自体は成功する（翻訳しようとしたときにだけ案内を出す）。
"""

from __future__ import annotations

import hashlib
import inspect
import json
import logging
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from i18n import t

log = logging.getLogger("drgtl.translate")


_RANGES = {
    "hangul": ((0xAC00, 0xD7A3), (0x1100, 0x11FF), (0x3130, 0x318F)),
    "kana": ((0x3040, 0x30FF), (0xFF66, 0xFF9D)),
    "han": ((0x3400, 0x4DBF), (0x4E00, 0x9FFF), (0xF900, 0xFAFF)),
    "cyrillic": ((0x0400, 0x04FF),),
    "latin": ((0x0041, 0x005A), (0x0061, 0x007A), (0x00C0, 0x024F)),
}


def _script_counts(text: str) -> dict[str, int]:
    counts = dict.fromkeys(_RANGES, 0)
    for ch in text:
        cp = ord(ch)
        for name, ranges in _RANGES.items():
            if any(lo <= cp <= hi for lo, hi in ranges):
                counts[name] += 1
                break
    return counts


def detect_language(text: str) -> str:
    """ざっくりした言語判定。'ja' / 'ko' / 'zh' / 'ru' / 'en' / 'und' を返す。"""
    c = _script_counts(text)
    if c["kana"] > 0:
        return "ja"
    if c["hangul"] > 0:
        return "ko"
    if c["han"] > 0:
        return "zh"
    if c["cyrillic"] > 0:
        return "ru"
    if c["latin"] > 0:
        return "en"
    return "und"


def is_written_in(text: str, lang: str) -> bool:
    """発言がその言語で書かれているか。送信で「訳す発言か」を決めるのに使う。"""
    base = (lang or "").split("-")[0].lower()
    if not base:
        return detect_language(text) != "und"
    if base == "ja":
        c = _script_counts(text)
        return c["kana"] > 0 or c["han"] > 0
    return detect_language(text) == base


# その言語で書かれた訳なら必ず含むはずの文字の種類（ラテン文字の言語は見分けられないので無い）
_TARGET_SCRIPTS = {"ja": ("kana", "han"), "ko": ("hangul",), "zh": ("han",), "ru": ("cyrillic",)}


def has_script_of(text: str, lang: str) -> bool:
    """訳文にその言語の文字が含まれているか。文字で見分けられない言語は常に True。"""
    scripts = _TARGET_SCRIPTS.get((lang or "").split("-")[0].lower())
    if not scripts:
        return True
    counts = _script_counts(text)
    return any(counts[name] > 0 for name in scripts)


# 漢字・かな・ハングルで書く言語。1文字あたりの情報が多い
DENSE_LANGUAGES = ("ja", "ko", "zh")


def count_dense(text: str) -> int:
    """漢字・かな・ハングルの文字数。"""
    counts = _script_counts(text)
    return counts["han"] + counts["kana"] + counts["hangul"]


_URL_RE = re.compile(r"https?://\S+")
_EMOTE_RE = re.compile(r"^[\W\d_]+$", re.UNICODE)


def is_translatable(text: str) -> bool:
    """記号だけ・数字だけ・URL だけの発言は翻訳しない。"""
    t = _URL_RE.sub("", text).strip()
    if not t:
        return False
    if _EMOTE_RE.match(t):
        return False
    return True


_NORM_RE = re.compile(r"[\s!?！？。、.,~〜ー\-_*]+")


def _normalize(text: str) -> str:
    return _NORM_RE.sub("", text.strip().lower())


def same_phrase(a: str, b: str) -> bool:
    """記号・空白・大文字小文字の違いを無視して同じ文言か。"""
    return _normalize(a) == _normalize(b)


class Glossary:
    """定型句をAPIに投げずに直接置き換えるための対応表。"""

    def __init__(self, path: str | None):
        self.incoming: dict[str, dict[str, str]] = {}
        self.outgoing: dict[str, dict[str, str]] = {}
        if path and os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                self.incoming = {_normalize(k): self._by_language(k, v)
                                 for k, v in data.get("incoming", {}).items()}
                self.outgoing = {
                    _normalize(k): v for k, v in data.get("outgoing", {}).items()
                }
                log.info(t("p.glossary.loaded"),
                         path, len(self.incoming), len(self.outgoing))
            except Exception as exc:  # noqa: BLE001
                log.warning(t("p.glossary.failed"), path, exc)

    @staticmethod
    def _by_language(phrase: str, value) -> dict[str, str]:
        """受信の対訳を「言語 → 訳」の形にそろえる。

        いまの形は {"ja": "...", "ko": "..."}、どの言語でも同じなら {"*": "..."}。
        以前の形（値が文字列）の用語集も読めるよう、文字列なら、自分自身への対応
        （掛け声など）はどの言語でも、それ以外は日本語の訳として扱う（以前と同じ意味）。
        """
        if isinstance(value, dict):
            return {str(k): str(v) for k, v in value.items()}
        return {"*" if same_phrase(phrase, str(value)) else "ja": str(value)}

    def lookup_incoming(self, text: str, target: str) -> str | None:
        """受信した発言の、target の言語での対訳。無ければ None。"""
        entry = self.incoming.get(_normalize(text))
        if not entry:
            return None
        return entry.get(target) or entry.get("*")

    def lookup_outgoing(self, text: str, target: str) -> str | None:
        entry = self.outgoing.get(_normalize(text))
        if entry:
            return entry.get(target)
        return None


class Cache:
    """翻訳結果の保存。"""

    def __init__(self, path: str, max_entries: int = 5000, enabled: bool = True):
        self.path = path
        self.max_entries = max_entries
        self.enabled = enabled
        self._data: dict[str, str] = {}
        self._lock = threading.Lock()
        self._dirty = False
        self._last_save = 0.0
        if enabled and os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as f:
                    self._data = json.load(f)
                log.info(t("p.cache.loaded"), len(self._data))
            except Exception as exc:  # noqa: BLE001
                log.warning(t("p.cache.load_failed"), exc)

    @staticmethod
    def key(scope: str, text: str, src: str, tgt: str) -> str:
        return f"{scope}|{src}|{tgt}|{text}"

    def get(self, scope: str, text: str, src: str, tgt: str) -> str | None:
        if not self.enabled:
            return None
        with self._lock:
            return self._data.get(self.key(scope, text, src, tgt))

    def put(self, scope: str, text: str, src: str, tgt: str, value: str) -> None:
        if not self.enabled or not value:
            return
        with self._lock:
            if len(self._data) >= self.max_entries:
                for k in list(self._data)[: max(1, self.max_entries // 10)]:
                    del self._data[k]
            self._data[self.key(scope, text, src, tgt)] = value
            self._dirty = True

    def maybe_save(self, interval: float = 10.0, force: bool = False) -> None:
        if not self.enabled:
            return
        now = time.time()
        with self._lock:
            if not self._dirty:
                return
            if not force and (now - self._last_save) < interval:
                return
            snapshot = dict(self._data)
            self._dirty = False
            self._last_save = now
        tmp = self.path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(snapshot, f, ensure_ascii=False)
            os.replace(tmp, self.path)
        except Exception as exc:  # noqa: BLE001
            # 書けなかった分は次の機会にもう一度書く。書きかけの .tmp は残さない
            with self._lock:
                self._dirty = True
            try:
                os.remove(tmp)
            except OSError:
                pass
            log.warning(t("p.cache.save_failed"), exc)


class TranslationError(RuntimeError):
    pass


def _http(url: str, *, data: bytes | None = None, headers: dict | None = None,
          timeout: float = 6.0) -> bytes:
    req = urllib.request.Request(url, data=data, headers=headers or {})
    req.add_header("User-Agent", "DRGTranslate/0.1 (+local mod bridge)")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8", "replace")[:300]
        except Exception:  # noqa: BLE001
            pass
        raise TranslationError(f"HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise TranslationError(t("p.conn_failed", reason=exc.reason)) from exc
    except TimeoutError as exc:
        raise TranslationError(t("p.timeout")) from exc


LANG_NAMES = {
    "ja": "Japanese", "en": "English", "ko": "Korean",
    "zh": "Simplified Chinese (as used in mainland China)",
    "zh-tw": "Traditional Chinese (as used in Taiwan)",
    "ru": "Russian", "de": "German", "fr": "French", "es": "Spanish",
    "pt": "Portuguese", "it": "Italian", "pl": "Polish", "tr": "Turkish",
}

SOURCE_LANG_NAMES = {"zh": "Chinese", "zh-tw": "Chinese"}


def lang_name(code: str) -> str:
    return LANG_NAMES.get(code, code)


def source_lang_name(code: str) -> str:
    return SOURCE_LANG_NAMES.get(code) or lang_name(code)


class Provider:
    name = "base"

    def __init__(self, opts: dict, timeout: float = 6.0):
        self.opts = opts or {}
        self.timeout = timeout

    def cache_scope(self) -> str:
        """キャッシュを分ける単位。訳文が変わりうる要素をすべて含めること。"""
        return self.name

    def setup_problem(self) -> str | None:
        """設定不足があれば案内文を返す。無ければ None。"""
        return None

    def translate(self, text: str, source: str | None, target: str) -> tuple[str, str]:
        """(翻訳文, 検出された元言語) を返す。source=None なら自動判定。"""
        raise NotImplementedError

    def translate_multi(self, text: str, source: str | None,
                        targets: list[str]) -> dict[str, str]:
        """複数の言語へまとめて翻訳する。"""
        out: dict[str, str] = {}
        for target in targets:
            translated, _ = self.translate(text, source, target)
            if translated:
                out[target] = translated
        return out


class StubProvider(Provider):
    """テスト専用。APIを呼ばず目印を付けて返すだけ。"""

    name = "stub"

    def translate(self, text: str, source: str | None, target: str) -> tuple[str, str]:
        return f"[{target}] {text}", source or detect_language(text)


class DeepLProvider(Provider):
    """DeepL API。api_key が空なら環境変数 DEEPL_AUTH_KEY を使う。"""

    name = "deepl"

    _LANG = {"en": "EN-US", "ko": "KO", "ja": "JA", "zh": "ZH", "zh-tw": "ZH-HANT",
             "de": "DE", "fr": "FR", "es": "ES", "ru": "RU", "pt": "PT-BR", "it": "IT"}

    def setup_problem(self) -> str | None:
        if (self.opts.get("api_key") or os.environ.get("DEEPL_AUTH_KEY") or "").strip():
            return None
        return t("p.need_key", key="DEEPL_AUTH_KEY", url="https://www.deepl.com/pro-api")

    def translate(self, text: str, source: str | None, target: str) -> tuple[str, str]:
        key = (self.opts.get("api_key") or os.environ.get("DEEPL_AUTH_KEY") or "").strip()
        if not key:
            raise TranslationError(t("p.no_key", name="DeepL", key="DEEPL_AUTH_KEY"))
        url = self.opts.get("api_url") or (
            "https://api-free.deepl.com/v2/translate"
            if key.endswith(":fx")
            else "https://api.deepl.com/v2/translate"
        )
        params = {"text": text, "target_lang": self._LANG.get(target, target.upper())}
        if source:
            params["source_lang"] = self._LANG.get(source, source.upper()).split("-")[0]
        raw = _http(
            url,
            data=urllib.parse.urlencode(params).encode("utf-8"),
            headers={
                "Authorization": f"DeepL-Auth-Key {key}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            timeout=self.timeout,
        )
        data = json.loads(raw.decode("utf-8"))
        tr = data["translations"][0]
        return tr["text"], (tr.get("detected_source_language") or "").lower() or (source or "")


GAME_CONTEXT = """\
You translate in-game text chat for the co-op game Deep Rock Galactic.
Messages are short, informal, and often contain typos, abbreviations, or
game-specific slang. Players are dwarven miners fighting bugs underground.

When translating into Japanese, use exactly these renderings. They are the
forms Japanese DRG players actually use — do not invent your own katakana.

Minerals: nitra=ナイトラ, morkite=モーカイト, gold=ゴールド,
  compressed gold=固まったゴールド, bismor=ビスモル, croppa=クロッパ,
  enor pearl=エノアパール, jadiz=ジャディズ, magnite=マグナイト,
  umanite=ユマナイト, aquarq=アクアーク, hollomite=ホロマイト,
  dystrum=ダイストラム, phazyonite=フェイジオナイト, red sugar=レッドシュガー,
  error cube=エラーキューブ, bittergem=ビタージェム, alien egg=エイリアンの卵,
  apoca bloom=アポカブルーム, boolo cap=ブールーキャップ, ebonut=エボナッツ,
  gunk seed=ガンクシード, oil shale=オイルシェール, fossil=エイリアンの化石
Enemies: grunt=グラント, guard=ガード, slasher=スラッシャー,
  praetorian=プレトリアン, oppressor=オプレッサー, exploder=エクスプローダー,
  bulk / bulk detonator=デトネーター, swarmer=スウォーマー, spawn=スポーン,
  web spitter=ウェブスピッター, acid spitter=アシッドスピッター, menace=メナス,
  warden=ウォーデン, brood nexus=ブルードネクサス, dreadnought=ドレッドノート,
  mactera=マクテラ, grabber=グラバー, goo bomber=グーボンバー,
  tri-jaw=トライジョー, brundle=ブランドル, breeder=ブリーダー,
  patrol bot=パトロールボット, nemesis=ネメシス, korlok=コーロック,
  leech / cave leech=リーチ, stingtail=スティングテイル
Classes: driller=ドリラー, gunner=ガンナー, scout=スカウト, engineer=エンジニア
Gear: zipline=ジップライン, platform=プラットフォーム, flare=フレア,
  resupply=補給, drop pod=ドロップポッド, molly / mule=モリー,
  doretta / dotty / drilldozer=ドレッタ, bosco=ボスコ, BET-C=BET-C
Missions: mining expedition=採掘遠征, egg hunt=卵狩り, elimination=殲滅,
  point extraction=地点採掘, salvage=回収作戦, on-site refining=現地精錬,
  escort=護衛任務, industrial sabotage=妨害工作, deep dive=ディープダイブ
Other: haz / hazard=ハザード, overclock=オーバークロック, perk=パーク,
  promotion=昇進, swarm=スウォーム, machine event=マシンイベント,
  Hoxxes=ホクシス, Karl=カール, mod / mods=MOD

When translating into Chinese, write Simplified Chinese as used in mainland China —
never Traditional characters — unless the target language explicitly says Traditional.
Use the terms from the game's official Simplified Chinese localization for minerals,
enemies, classes and missions, and leave short English chat abbreviations
(gg, afk, brb, ez, nice) as they are.

Keep these as-is rather than translating them: Rock and Stone (the players'
rallying cry), leaf lover (an insult for a non-dwarf — リーフラバー), and
mod / mods (a game modification — write MOD in Japanese and leave the word
alone in other languages; never render it as オーバークロック or 改造).

Watch for these meanings, which differ from everyday English:
- "run" / "mission" = one playthrough of a mission, not physical running
- "res" / "rez" = revive a downed player
- "inc" = incoming
- "down" / "dwarf down" = a teammate is incapacitated
- "leaf lover" = a mild insult, not a literal description

Rules:
- Output only the translation. No preamble, no quotes, no notes, no explanation.
- Match the register of the original: casual chat stays casual, short stays short.
- Keep player names, numbers, and emotes as they are.
- If the message is already in the target language, return it unchanged.
- Do not include internal or system XML tags in your response.\
"""


def _missing_sdk_message(package: str) -> str:
    """SDK 未導入の案内。"""
    return (
        t("p.missing_sdk", package=package) + "\n"
        + f'    "{sys.executable}" -m pip install {package}'
    )


class LLMProvider(Provider):
    """Claude / OpenAI 共通の土台。プロンプト組み立てと応答の後始末を持つ。"""

    name = "llm"
    default_model = ""

    def __init__(self, opts: dict, timeout: float = 6.0):
        super().__init__(opts, timeout)
        self.model = (self.opts.get("model") or self.default_model).strip()
        self.max_tokens = int(self.opts.get("max_tokens") or 1024)
        self._client = None
        self._prompts: dict[str, str] = {}

    def cache_scope(self) -> str:
        # 同じモデルでもプロンプト（用語の指定など）を変えれば訳が変わるので、その指紋も含める
        return f"{self.name}:{self.model}:{self.prompt_fingerprint()}"

    def prompt_fingerprint(self) -> str:
        """プロンプトの指紋。GAME_CONTEXT も指示の文面も、変われば値が変わる。"""
        sample = (self.system_prompt("src", ["dst1", "dst2"], True)
                  + self.system_prompt("src", ["dst1"], False))
        return hashlib.sha256(sample.encode("utf-8")).hexdigest()[:8]

    sdk_package = ""
    key_env = ""
    key_url = ""

    def api_key(self) -> str:
        return (self.opts.get("api_key") or os.environ.get(self.key_env) or "").strip()

    def _require_key(self) -> None:
        """キーが無いことを SDK より先に自前で判定する。"""
        if not self.api_key():
            raise TranslationError(t("p.need_key", key=self.key_env, url=self.key_url))

    def setup_problem(self) -> str | None:
        try:
            __import__(self.sdk_package)
        except ImportError:
            return _missing_sdk_message(self.sdk_package)
        if not self.api_key():
            return t("p.need_key", key=self.key_env, url=self.key_url)
        return None


    def system_prompt(self, source: str | None, targets: list[str],
                      as_json: bool) -> str:
        key = f"{source or 'auto'}|{','.join(targets)}|{as_json}"
        cached = self._prompts.get(key)
        if cached:
            return cached

        src = source_lang_name(source) if source else "whatever language it is written in"
        parts = [GAME_CONTEXT, ""]
        if as_json:
            fields = ", ".join(f'"{t}" = {lang_name(t)}' for t in targets)
            parts.append(
                f"Translate the user's message from {src} into each of these "
                f"languages and return a JSON object with exactly these keys: {fields}. "
                "Each value is the translation as a plain string."
            )
        else:
            parts.append(
                f"Translate the user's message from {src} into {lang_name(targets[0])}."
            )
        prompt = "\n".join(parts)
        self._prompts[key] = prompt
        return prompt

    @staticmethod
    def _clean(text: str) -> str:
        text = (text or "").strip()
        for quote in ('"', "'", "「", "『"):
            if text.startswith(quote):
                closing = {'"': '"', "'": "'", "「": "」", "『": "』"}[quote]
                if text.endswith(closing) and len(text) > 1:
                    text = text[1:-1].strip()
                break
        return text

    def _parse_json(self, raw: str, targets: list[str]) -> dict[str, str]:
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.strip("`")
            raw = raw.split("\n", 1)[-1] if "\n" in raw else raw
            raw = raw.rsplit("```", 1)[0]
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise TranslationError(t("p.bad_json", raw=raw[:120])) from exc
        if not isinstance(data, dict):
            raise TranslationError(t("p.not_object"))
        return {t: self._clean(str(data[t])) for t in targets
                if isinstance(data.get(t), str) and data[t].strip()}


    def _complete(self, system: str, user: str, json_targets: list[str] | None) -> str:
        raise NotImplementedError


    def translate(self, text: str, source: str | None, target: str) -> tuple[str, str]:
        raw = self._complete(self.system_prompt(source, [target], False), text, None)
        out = self._clean(raw)
        if not out:
            raise TranslationError(t("p.empty"))
        return out, (source or detect_language(text))

    def translate_multi(self, text: str, source: str | None,
                        targets: list[str]) -> dict[str, str]:
        if len(targets) == 1:
            translated, _ = self.translate(text, source, targets[0])
            return {targets[0]: translated}
        raw = self._complete(self.system_prompt(source, targets, True), text, targets)
        return self._parse_json(raw, targets)


class ClaudeProvider(LLMProvider):
    """Anthropic Claude (Messages API)。`pip install anthropic` が必要。"""

    name = "claude"
    default_model = "claude-haiku-4-5"
    sdk_package = "anthropic"
    key_env = "ANTHROPIC_API_KEY"
    key_url = "https://platform.claude.com/settings/keys"

    def __init__(self, opts: dict, timeout: float = 6.0):
        super().__init__(opts, timeout)
        self._warned_model = False
        # 設定の書き間違いは、翻訳のたびに 400 になる前に起動時に知らせて auto に戻す
        self.effort = self._checked_effort(self.opts.get("effort"))
        self.refusal_fallback = self._checked_fallback(self.opts.get("refusal_fallback"))

    def _get_client(self):
        if self._client is not None:
            return self._client
        try:
            import anthropic
        except ImportError as exc:
            raise TranslationError(_missing_sdk_message("anthropic")) from exc
        self._require_key()

        key = (self.opts.get("api_key") or "").strip()
        kwargs: dict = {"timeout": self.timeout, "max_retries": 1}
        if key:
            kwargs["api_key"] = key
        try:
            self._client = anthropic.Anthropic(**kwargs)
        except Exception as exc:  # noqa: BLE001
            raise TranslationError(
                t("p.need_key", key=self.key_env, url=self.key_url)
            ) from exc
        return self._client

    # モデルの世代ごとに、送れる引数が違う。新しいモデルが出たら、ここに足す。
    # どの表にも当てはまらないモデルは旧世代として扱い、最初の1回だけ警告する。
    #
    # 思考が常に有効で、thinking を送ると（disabled でも）400 になる。省いて送る
    _THINKING_ALWAYS_ON = ("claude-fable-5", "claude-mythos-5")
    # effort を受け付ける（上の2つ以外は thinking を disabled にできる）
    _EFFORT_CAPABLE = (
        "claude-opus-5", "claude-opus-4-8", "claude-opus-4-7", "claude-opus-4-6",
        "claude-sonnet-5", "claude-sonnet-4-6",
    ) + _THINKING_ALWAYS_ON
    # effort も thinking も送らない旧世代（知っているもの）
    _LEGACY = (
        "claude-haiku-4-5", "claude-sonnet-4-5", "claude-opus-4-5", "claude-opus-4-1",
        "claude-opus-4-0", "claude-sonnet-4-0", "claude-3",
    )
    _FALLBACK_CAPABLE = ("claude-opus-5", "claude-fable-5", "claude-mythos-5")

    # effort に書ける値。xhigh は Opus 4.7 からなので、4.6 の世代は受け付けない
    _EFFORT_LEVELS = ("low", "medium", "high", "xhigh", "max")
    _NO_XHIGH = ("claude-opus-4-6", "claude-sonnet-4-6")
    # thinking を disabled にできるのは effort が high 以下のときだけ（xhigh / max だと 400）
    _DISABLE_THINKING_UP_TO_HIGH = ("claude-opus-5",)

    _TRUE = ("1", "true", "yes", "on")
    _FALSE = ("0", "false", "no", "off")

    def _is_modern(self) -> bool:
        return self.model.startswith(self._EFFORT_CAPABLE)

    def _warn_if_unknown(self) -> None:
        if self._warned_model or self.model.startswith(self._EFFORT_CAPABLE + self._LEGACY):
            return
        self._warned_model = True
        log.warning(t("p.unknown_model"), self.model)

    def effort_levels(self) -> tuple[str, ...]:
        """このモデルの effort に書ける値（auto を除く）。effort を送らないモデルなら空。"""
        if not self._is_modern():
            return ()
        if self.model.startswith(self._NO_XHIGH):
            return tuple(v for v in self._EFFORT_LEVELS if v != "xhigh")
        return self._EFFORT_LEVELS

    def _checked_effort(self, value) -> str:
        """DRGT_CLAUDE_EFFORT を確かめる。使えない値は警告して auto にする。"""
        effort = str(value or "auto").strip().lower() or "auto"
        if effort == "auto":
            return effort
        levels = self.effort_levels()
        if not levels:
            log.warning(t("p.effort_ignored"), self.model)
            return "auto"
        if effort not in levels:
            log.warning(t("p.effort_invalid"), value, self.model, " / ".join(levels))
            return "auto"
        return effort

    def _checked_fallback(self, value) -> bool | None:
        """DRGT_CLAUDE_REFUSAL_FALLBACK を読む。None は auto（モデルに任せる）。

        settings.ini の値は文字列なので bool() にかけてはいけない（"false" も真になる）。
        """
        if value is None or isinstance(value, bool):
            return value
        setting = str(value).strip().lower()
        if setting in ("", "auto"):
            return None
        if setting in self._TRUE:
            return True
        if setting in self._FALSE:
            return False
        log.warning(t("p.fallback_invalid"), value)
        return None

    def _use_fallback(self) -> bool:
        if self.refusal_fallback is None:
            return self.model.startswith(self._FALLBACK_CAPABLE)
        return self.refusal_fallback

    def _can_disable_thinking(self, effort: str) -> bool:
        """thinking: disabled を送ってよいか。送れないときは省く（そのモデルの既定で動く）。"""
        if self.model.startswith(self._THINKING_ALWAYS_ON):
            return False
        if self.model.startswith(self._DISABLE_THINKING_UP_TO_HIGH):
            return effort in ("low", "medium", "high")
        return True

    def _build_params(self, system: str, user: str,
                      json_targets: list[str] | None) -> dict:
        """messages.create に渡す引数を組み立てる。"""
        self._warn_if_unknown()
        modern = self._is_modern()
        effort = "low" if self.effort == "auto" else self.effort

        output_config: dict = {}
        if modern:
            output_config["effort"] = effort

        if json_targets:
            output_config["format"] = {
                "type": "json_schema",
                "schema": {
                    "type": "object",
                    "properties": {t: {"type": "string"} for t in json_targets},
                    "required": list(json_targets),
                    "additionalProperties": False,
                },
            }

        params: dict = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        if output_config:
            params["output_config"] = output_config

        if modern and self._can_disable_thinking(effort):
            params["thinking"] = {"type": "disabled"}

        if self._use_fallback():
            params["betas"] = ["server-side-fallback-2026-07-01"]
            params["fallbacks"] = "default"
        return params

    def _complete(self, system: str, user: str, json_targets: list[str] | None) -> str:
        client = self._get_client()
        params = self._build_params(system, user, json_targets)

        try:
            if "betas" in params:
                resp = client.beta.messages.create(**params)
            else:
                resp = client.messages.create(**params)
        except Exception as exc:  # noqa: BLE001
            raise TranslationError(t("p.api_failed", name="Claude", err=exc)) from exc

        if getattr(resp, "stop_reason", None) == "refusal":
            detail = ""
            details = getattr(resp, "stop_details", None)
            if details is not None:
                detail = f" ({getattr(details, 'category', '') or ''})"
            raise TranslationError(t("p.refused", detail=detail))

        return "".join(
            block.text for block in resp.content if getattr(block, "type", "") == "text"
        )


def check_claude_params() -> list[str]:
    """同梱の anthropic SDK が、こちらの送る引数を受け付けるか確かめる。"""
    try:
        import anthropic
    except ImportError:
        return []

    client = anthropic.Anthropic(api_key="dummy-for-signature-check")
    methods = {
        "messages.create": client.messages.create,
        "beta.messages.create": client.beta.messages.create,
    }
    problems: list[str] = []
    for model in ("claude-haiku-4-5", "claude-sonnet-5", "claude-opus-5", "claude-fable-5-1"):
        params = ClaudeProvider({"model": model})._build_params("system", "user", ["ja"])
        name = "beta.messages.create" if "betas" in params else "messages.create"
        accepted = inspect.signature(methods[name]).parameters
        for key in params:
            if key not in accepted:
                problems.append(
                    f"{model}: {name}() in anthropic {anthropic.__version__} "
                    f"does not accept {key}"
                )
    return problems

class OpenAIProvider(LLMProvider):
    """OpenAI (Chat Completions)。`pip install openai` が必要。"""

    name = "openai"
    default_model = "gpt-4o-mini"
    sdk_package = "openai"
    key_env = "OPENAI_API_KEY"
    key_url = "https://platform.openai.com/api-keys"

    def __init__(self, opts: dict, timeout: float = 6.0):
        super().__init__(opts, timeout)
        # モデルによって受け付けない引数がある（max_tokens / temperature）。
        # 一度通った組み合わせを覚えておき、次からは最初からそれで送る
        self._optional: dict | None = None

    def _adjusted(self, exc: Exception, optional: dict) -> dict | None:
        """引数を理由に断られたら、差し替えた組み合わせを返す。直しようがなければ None。"""
        if getattr(exc, "status_code", None) != 400:
            return None
        msg = str(exc)
        fixed = dict(optional)
        if "max_tokens" in fixed and "max_completion_tokens" in msg:
            fixed["max_completion_tokens"] = fixed.pop("max_tokens")
        if "temperature" in fixed and "temperature" in msg:
            fixed.pop("temperature")
        return fixed if fixed != optional else None

    def _get_client(self):
        if self._client is not None:
            return self._client
        try:
            import openai
        except ImportError as exc:
            raise TranslationError(_missing_sdk_message("openai")) from exc
        self._require_key()

        kwargs: dict = {"timeout": self.timeout, "max_retries": 1}
        key = (self.opts.get("api_key") or "").strip()
        if key:
            kwargs["api_key"] = key
        if self.opts.get("base_url"):
            kwargs["base_url"] = self.opts["base_url"]
        try:
            self._client = openai.OpenAI(**kwargs)
        except Exception as exc:  # noqa: BLE001
            raise TranslationError(
                t("p.need_key", key=self.key_env, url=self.key_url)
            ) from exc
        return self._client

    def _complete(self, system: str, user: str, json_targets: list[str] | None) -> str:
        client = self._get_client()
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        params: dict = {"model": self.model, "messages": messages}
        if json_targets:
            params["response_format"] = {"type": "json_object"}

        optional = (dict(self._optional) if self._optional is not None
                    else {"max_tokens": self.max_tokens, "temperature": 0})
        # 断られた理由の引数を差し替えて送り直す。差し替えは2種類なので最大3回
        for _ in range(3):
            try:
                resp = client.chat.completions.create(**params, **optional)
                break
            except Exception as exc:  # noqa: BLE001
                fixed = self._adjusted(exc, optional)
                if fixed is None:
                    raise TranslationError(t("p.api_failed", name="OpenAI", err=exc)) from exc
                optional = fixed
        else:
            raise TranslationError(t("p.api_failed", name="OpenAI", err="parameters rejected"))
        self._optional = optional

        choice = resp.choices[0]
        if getattr(choice, "finish_reason", None) == "content_filter":
            raise TranslationError(t("p.refused", detail=" (content_filter)"))
        return choice.message.content or ""


PROVIDERS: dict[str, type[Provider]] = {
    "deepl": DeepLProvider,
    "claude": ClaudeProvider,
    "openai": OpenAIProvider,
}


def build_provider(name: str, opts: dict, timeout: float) -> Provider:
    cls = PROVIDERS.get(name)
    if cls is None:
        raise ValueError(
            t("p.unknown_provider", name=name, names=", ".join(sorted(PROVIDERS)))
        )
    return cls(opts, timeout)


class Translator:
    def __init__(self, provider: Provider, cache: Cache, glossary: Glossary,
                 min_interval: float = 0.0):
        self.provider = provider
        self.cache = cache
        self.scope = provider.cache_scope()
        self.glossary = glossary
        self.min_interval = min_interval
        self._rate_lock = threading.Lock()
        # 失敗の数え上げは複数のワーカから同時に触るので、ロックの中で行う
        self._state_lock = threading.Lock()
        self._last_call = 0.0
        self._fail_streak = 0
        self._cooldown_until = 0.0

    def _throttle(self) -> None:
        if self.min_interval <= 0:
            return
        with self._rate_lock:
            wait = self._last_call + self.min_interval - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            self._last_call = time.monotonic()

    def _check_cooldown(self) -> None:
        if time.monotonic() < self._cooldown_until:
            raise TranslationError(t("p.cooldown"))

    def _note_failure(self) -> None:
        with self._state_lock:
            self._fail_streak += 1
            cooling = self._fail_streak >= 5
            if cooling:
                self._cooldown_until = time.monotonic() + 30.0
        if cooling:
            log.warning(t("p.cooldown_start"))

    def _note_success(self) -> None:
        with self._state_lock:
            self._fail_streak = 0

    def translate(self, text: str, source: str | None, target: str) -> tuple[str, str]:
        src_key = source or "auto"
        cached = self.cache.get(self.scope, text, src_key, target)
        if cached is not None:
            return cached, source or detect_language(text)

        self._check_cooldown()
        self._throttle()
        try:
            out, detected = self.provider.translate(text, source, target)
        except TranslationError:
            self._note_failure()
            raise
        self._note_success()
        out = out.strip()
        self.cache.put(self.scope, text, src_key, target, out)
        return out, (detected or source or detect_language(text)).lower()

    def translate_multi(self, text: str, source: str | None,
                        targets: list[str]) -> dict[str, str]:
        """複数言語へまとめて翻訳する。キャッシュ済みの言語は問い合わせない。"""
        src_key = source or "auto"
        out: dict[str, str] = {}
        pending: list[str] = []
        for target in targets:
            cached = self.cache.get(self.scope, text, src_key, target)
            if cached is not None:
                out[target] = cached
            else:
                pending.append(target)
        if not pending:
            return out

        self._check_cooldown()
        self._throttle()
        try:
            fresh = self.provider.translate_multi(text, source, pending)
        except TranslationError:
            self._note_failure()
            raise
        self._note_success()
        for target, value in fresh.items():
            value = (value or "").strip()
            if value:
                self.cache.put(self.scope, text, src_key, target, value)
                out[target] = value
        return out
