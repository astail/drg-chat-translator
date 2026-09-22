#!/usr/bin/env python3
"""DRGTranslate bridge — Deep Rock Galactic のチャットを翻訳するローカル常駐プロセス。

ゲーム内の UE4SS Lua mod とは %APPDATA%\\DRGTranslate 配下のテキストファイルで
やり取りする（UE4SS の Lua にはソケットが無いため）。

  to_bridge.txt : mod -> bridge
  to_game.txt   : bridge -> mod
  bridge.alive  : 生存確認

翻訳プロバイダは deepl / claude / openai の3つ。exe（ソースならリポジトリ）と
同じフォルダの settings.ini で選ぶ。

使い方:
    python drg_bridge.py                    通常起動
    python drg_bridge.py --test "こんにちは"      翻訳だけ試す（ゲーム不要）
    python drg_bridge.py --selftest --fake  APIキー無しでファイルIPCの疎通確認
"""

from __future__ import annotations

import argparse
import logging
import os
import queue
import re
import signal
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from logging.handlers import RotatingFileHandler

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import i18n  # noqa: E402
from i18n import t  # noqa: E402
from translate import (  # noqa: E402
    DENSE_LANGUAGES,
    Cache,
    Glossary,
    StubProvider,
    TranslationError,
    Translator,
    build_provider,
    check_claude_params,
    count_dense,
    detect_language,
    has_script_of,
    is_translatable,
    is_written_in,
    same_phrase,
)

VERSION = "0.7.0"
log = logging.getLogger("drgtl")

LLM_PROVIDERS = {"claude", "openai"}

HERE = os.path.dirname(os.path.abspath(__file__))

FROZEN = getattr(sys, "frozen", False)

if FROZEN:
    APP_DIR = os.path.dirname(os.path.abspath(sys.executable))
    BUNDLE_DIR = getattr(sys, "_MEIPASS", APP_DIR)
else:
    APP_DIR = os.path.dirname(HERE)
    BUNDLE_DIR = APP_DIR

ROOT = APP_DIR

SETTINGS_FILE = "settings.ini"
SETTINGS_EXAMPLE_FILE = "settings.example.ini"


def bundled(*parts: str) -> str:
    """同梱リソースのパス。exe なら展開先、ソース実行ならリポジトリ内。"""
    return os.path.join(BUNDLE_DIR, *parts)


DEFAULTS: dict = {
    "provider": "deepl",
    "providers": {
        "deepl": {"api_key": "", "api_url": ""},
        "claude": {
            "api_key": "",
            "model": "claude-haiku-4-5",
            "max_tokens": 1024,
            "effort": "auto",
            "refusal_fallback": "auto",
        },
        "openai": {
            "api_key": "",
            "model": "gpt-4o-mini",
            "base_url": "",
            "max_tokens": 1024,
        },
    },
    "incoming": {
        "enabled": True,
        "target": "ja",
        "skip_languages": ["ja"],
        "format": "[訳] {sender}: {text}",
        "max_chars": 400,
    },
    "outgoing": {
        "enabled": True,
        "source": "ja",
        "targets": ["en", "ko", "zh"],
        "separator": " / ",
        "include_source": False,
        "max_chars": 200,
        "min_length": 2,
        "ignore_prefixes": ["/", "!", "."],
    },
    "relay": {
        "enabled": True,
        "targets": ["ja", "en", "ko", "zh"],
        "format": "{sender}: {text}",
        "item_format": "{text}",
        "separator": " / ",
        "max_chars": 200,
        "max_langs": 4,
        "max_line_chars": 0,
    },
    "cache": {
        "enabled": True,
        "max_entries": 5000,
        "path": "cache.json" if FROZEN else "bridge/cache.json",
    },
    "glossary": {
        "enabled": True,
        "path": "glossary.json" if FROZEN else "bridge/glossary.json",
    },
    "overlay": {
        "enabled": False,
        "mode": "auto",
        "hide_after": 12.0,
        "lines": 8,
        "font_size": 13,
        "opacity": 0.85,
        "x": 40,
        "y": 40,
        "width": 520,
        "composer": True,
    },
    "network": {
        "timeout_sec": 6.0,
        "llm_timeout_sec": 20.0,
        "max_workers": 4,
        "min_interval_sec": 0.0,
    },
    "log_level": "info",
}


LANG_TAGS = {"ja": "JP", "ko": "KR"}

# 利用者が settings.ini で書き換えられる書式と、その中で使える差し込み名
FORMAT_SETTINGS = (
    ("incoming", "format", "DRGT_INCOMING_FORMAT"),
    ("relay", "format", "DRGT_RELAY_FORMAT"),
    ("relay", "item_format", "DRGT_RELAY_ITEM_FORMAT"),
)
FORMAT_FIELDS = ("sender", "text", "lang", "original")


def load_dotenv(path: str) -> int:
    """設定ファイル（settings.ini）を読んで os.environ に入れる。読み込んだ件数を返す。"""
    if not os.path.exists(path):
        return 0
    loaded = 0
    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.lower().startswith("export "):
                line = line[7:].lstrip()
            key, sep, value = line.partition("=")
            if not sep:
                continue
            key = key.strip()
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            if key and key not in os.environ:
                os.environ[key] = value
                loaded += 1
    return loaded


def _str(key: str, default: str) -> str:
    v = os.environ.get(key)
    return default if v is None or v == "" else v


def _bool(key: str, default: bool) -> bool:
    v = os.environ.get(key)
    if v is None or v == "":
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


def _int(key: str, default: int) -> int:
    try:
        return int(_str(key, str(default)))
    except ValueError:
        log.warning(t("b.config.not_int"), key, default)
        return default


def _float(key: str, default: float) -> float:
    try:
        return float(_str(key, str(default)))
    except ValueError:
        log.warning(t("b.config.not_num"), key, default)
        return default


def _list(key: str, default: list[str]) -> list[str]:
    v = os.environ.get(key)
    if v is None or v.strip() == "":
        return list(default)
    return [item.strip() for item in v.split(",") if item.strip()]


def build_config() -> dict:
    """環境変数（settings.ini 読み込み済み）から設定を組み立てる。

    既定値は必ず DEFAULTS から引くこと（ここに数値や文字列を直接書かない）。
    環境変数が何も無いときに DEFAULTS と一致することを test_config_defaults.py で縛っている。
    """
    d = DEFAULTS
    pr, inc, out, rel = d["providers"], d["incoming"], d["outgoing"], d["relay"]
    ov, net = d["overlay"], d["network"]
    incoming_target = _str("DRGT_INCOMING_TARGET", inc["target"])
    relay_targets = _list("DRGT_RELAY_TARGETS", rel["targets"])
    source = _str("DRGT_OUTGOING_SOURCE", out["source"])
    return {
        "provider": _str("DRGT_PROVIDER", d["provider"]).strip().lower(),
        "providers": {
            "deepl": {
                "api_key": _str("DEEPL_AUTH_KEY", pr["deepl"]["api_key"]),
                "api_url": _str("DRGT_DEEPL_API_URL", pr["deepl"]["api_url"]),
            },
            "claude": {
                "api_key": _str("ANTHROPIC_API_KEY", pr["claude"]["api_key"]),
                "model": _str("DRGT_CLAUDE_MODEL", pr["claude"]["model"]),
                "max_tokens": _int("DRGT_CLAUDE_MAX_TOKENS", pr["claude"]["max_tokens"]),
                "effort": _str("DRGT_CLAUDE_EFFORT", pr["claude"]["effort"]),
                "refusal_fallback": _str("DRGT_CLAUDE_REFUSAL_FALLBACK",
                                         pr["claude"]["refusal_fallback"]),
            },
            "openai": {
                "api_key": _str("OPENAI_API_KEY", pr["openai"]["api_key"]),
                "model": _str("DRGT_OPENAI_MODEL", pr["openai"]["model"]),
                "base_url": _str("DRGT_OPENAI_BASE_URL", pr["openai"]["base_url"]),
                "max_tokens": _int("DRGT_OPENAI_MAX_TOKENS", pr["openai"]["max_tokens"]),
            },
        },
        "incoming": {
            "enabled": _bool("DRGT_INCOMING_ENABLED", inc["enabled"]),
            "target": incoming_target,
            # 書いていなければ受信の訳す先に追従する（自分の言語の発言は訳さない）
            "skip_languages": _list("DRGT_INCOMING_SKIP_LANGUAGES", [incoming_target]),
            "format": _str("DRGT_INCOMING_FORMAT", inc["format"]),
            "max_chars": _int("DRGT_INCOMING_MAX_CHARS", inc["max_chars"]),
        },
        "outgoing": {
            "enabled": _bool("DRGT_OUTGOING_ENABLED", out["enabled"]),
            # auto なら翻訳元を決めず、打った発言の言語を判定して訳す
            "source": "" if source.strip().lower() == "auto" else source,
            "targets": _list("DRGT_OUTGOING_TARGETS", out["targets"]),
            "separator": os.environ.get("DRGT_OUTGOING_SEPARATOR") or out["separator"],
            "include_source": _bool("DRGT_OUTGOING_INCLUDE_SOURCE", out["include_source"]),
            "max_chars": _int("DRGT_OUTGOING_MAX_CHARS", out["max_chars"]),
            "min_length": _int("DRGT_OUTGOING_MIN_LENGTH", out["min_length"]),
            "ignore_prefixes": _list("DRGT_OUTGOING_IGNORE_PREFIXES", out["ignore_prefixes"]),
        },
        "relay": {
            "enabled": _bool("DRGT_RELAY_ENABLED", rel["enabled"]),
            "targets": relay_targets,
            "format": _str("DRGT_RELAY_FORMAT", rel["format"]),
            "item_format": _str("DRGT_RELAY_ITEM_FORMAT", rel["item_format"]),
            "separator": os.environ.get("DRGT_RELAY_SEPARATOR") or rel["separator"],
            "max_chars": _int("DRGT_RELAY_MAX_CHARS", rel["max_chars"]),
            # 書いていなければ中継先の数にする。固定の既定（4）だと、中継先を5言語に
            # したときに黙って末尾が落ちていた。DRGT_RELAY_MAX_LINES は 0.5.0〜0.5.3 での
            # 旧名（0.5.4 で改名）。古い settings.ini のために読む
            "max_langs": _int("DRGT_RELAY_MAX_LANGS",
                              _int("DRGT_RELAY_MAX_LINES", len(relay_targets))),
            "max_line_chars": _int("DRGT_RELAY_MAX_LINE_CHARS", rel["max_line_chars"]),
        },
        "cache": {
            "enabled": _bool("DRGT_CACHE_ENABLED", d["cache"]["enabled"]),
            "max_entries": _int("DRGT_CACHE_MAX_ENTRIES", d["cache"]["max_entries"]),
            "path": _str("DRGT_CACHE_PATH", d["cache"]["path"]),
        },
        "glossary": {
            "enabled": _bool("DRGT_GLOSSARY_ENABLED", d["glossary"]["enabled"]),
            "path": _str("DRGT_GLOSSARY_PATH", d["glossary"]["path"]),
        },
        "overlay": {
            "enabled": _bool("DRGT_OVERLAY_ENABLED", ov["enabled"]),
            "mode": _str("DRGT_OVERLAY_MODE", ov["mode"]),
            "hide_after": _float("DRGT_OVERLAY_HIDE_AFTER", ov["hide_after"]),
            "lines": _int("DRGT_OVERLAY_LINES", ov["lines"]),
            "font_size": _int("DRGT_OVERLAY_FONT_SIZE", ov["font_size"]),
            "opacity": _float("DRGT_OVERLAY_OPACITY", ov["opacity"]),
            "x": _int("DRGT_OVERLAY_X", ov["x"]),
            "y": _int("DRGT_OVERLAY_Y", ov["y"]),
            "width": _int("DRGT_OVERLAY_WIDTH", ov["width"]),
            "composer": _bool("DRGT_OVERLAY_COMPOSER", ov["composer"]),
        },
        "network": {
            "timeout_sec": _float("DRGT_TIMEOUT_SEC", net["timeout_sec"]),
            "llm_timeout_sec": _float("DRGT_LLM_TIMEOUT_SEC", net["llm_timeout_sec"]),
            "max_workers": _int("DRGT_MAX_WORKERS", net["max_workers"]),
            "min_interval_sec": _float("DRGT_MIN_INTERVAL_SEC", net["min_interval_sec"]),
        },
        "log_level": _str("DRGT_LOG_LEVEL", d["log_level"]),
    }


def load_config(env_path: str | None) -> dict:
    path = env_path or os.path.join(APP_DIR, SETTINGS_FILE)
    n = load_dotenv(path)
    i18n.init()
    if n:
        log.info(t("b.config.loaded"), path, n)
    elif not os.path.exists(path):
        log.warning(t("b.config.missing"), path)
    return build_config()


def check_formats(cfg: dict) -> None:
    """書式を一度ためしに埋めてみて、壊れていれば警告して既定に戻す。

    書き間違い（{name} など）のまま動かすと、発言のたびに format() が失敗して
    受信の翻訳がすべて黙って止まるため、起動時に見つけておく。
    """
    sample = {name: name for name in FORMAT_FIELDS}
    for section, key, env in FORMAT_SETTINGS:
        fmt = cfg[section][key]
        try:
            fmt.format(**sample)
        except (KeyError, IndexError, ValueError, AttributeError) as exc:
            default = DEFAULTS[section][key]
            log.warning(t("b.config.bad_format"), env, fmt, exc,
                        ", ".join("{%s}" % n for n in FORMAT_FIELDS), default)
            cfg[section][key] = default


# 中継する訳の長さの上限。原文の長さのこの倍数か、下の文字数の大きいほうまで
RELAY_MAX_RATIO = 3
RELAY_MIN_LIMIT = 80
# 漢字・かな・ハングル1文字は、ラテン文字・キリル文字に訳すと数文字になる。
# その向きの訳では原文のこれらの文字をこの倍数で数える（中国語の35文字の発言の
# 英訳は140文字を超える＝約4倍）。ラテン文字の言語は文字の種類での確認が効かず
# 長さだけが頼りなので、実測に余裕を持たせた程度（2 × 3 = 約6倍）にとどめる
RELAY_DENSE_WEIGHT = 2


def relay_source_length(original: str, target: str) -> int:
    """長さの上限を決めるための原文の長さ。訳す先に合わせて文字の重みを変える。"""
    if (target or "").split("-")[0].lower() in DENSE_LANGUAGES:
        return len(original)
    return len(original) + (RELAY_DENSE_WEIGHT - 1) * count_dense(original)


def relay_text_ok(value: str, original: str, target: str, check_script: bool) -> str | None:
    """中継に流す前に訳文を確かめる。流してよければ整えた文を、だめなら None を返す。

    中継の訳はホストの名前で全員のチャットに流れる。他の隊員の発言で翻訳の指示を
    乗っ取られ、訳とは別物が返ってきたときに、そのまま流さないための安い確かめ。
    check_script は LLM のときだけ真にする（発言で出力を操れるのは LLM だけ）。
    """
    text = "".join(ch for ch in " ".join(value.split()) if ch.isprintable())
    if not text or text.startswith("/"):
        return None
    if len(text) > max(RELAY_MIN_LIMIT, RELAY_MAX_RATIO * relay_source_length(original, target)):
        return None
    if check_script and not has_script_of(text, target):
        return None
    return text


def check_relay_limit(cfg: dict) -> None:
    """中継の上限が中継先の数より小さいと、末尾の言語が黙って落ちる。起動時に知らせる。"""
    rel = cfg["relay"]
    limit, targets = int(rel["max_langs"]), list(rel["targets"])
    if rel["enabled"] and limit < len(targets):
        log.warning(t("b.config.relay_limit"), limit, len(targets),
                    ", ".join(targets[max(0, limit):]))


def resolve_path(cfg_path: str) -> str:
    """相対パスは exe（またはリポジトリルート）基準で解決する。"""
    return cfg_path if os.path.isabs(cfg_path) else os.path.join(APP_DIR, cfg_path)


def resolve_glossary(cfg_path: str) -> str:
    """用語集のパス。exe の隣に置かれていればそれを、無ければ同梱のものを使う。"""
    path = resolve_path(cfg_path)
    if os.path.exists(path):
        return path
    fallback = bundled("glossary.json")
    return fallback if os.path.exists(fallback) else path


def ipc_dir(override: str | None) -> str:
    if override:
        return override
    appdata = os.environ.get("APPDATA")
    if appdata:
        return os.path.join(appdata, "DRGTranslate")
    return os.path.join(os.path.expanduser("~"), ".config", "DRGTranslate")


def esc(s: str) -> str:
    return (
        str(s)
        .replace("\\", "\\\\")
        .replace("\t", "\\t")
        .replace("\r", "\\r")
        .replace("\n", "\\n")
    )


def unesc(s: str) -> str:
    out = []
    i = 0
    while i < len(s):
        c = s[i]
        if c == "\\" and i + 1 < len(s):
            n = s[i + 1]
            out.append({"t": "\t", "n": "\n", "r": "\r", "\\": "\\"}.get(n, "\\" + n))
            i += 2
        else:
            out.append(c)
            i += 1
    return "".join(out)


def encode_line(*fields) -> str:
    return "\t".join(esc(f) for f in fields) + "\n"


def decode_line(line: str) -> list[str]:
    return [unesc(f) for f in line.split("\t")]


class Ipc:
    def __init__(self, directory: str):
        self.dir = directory
        os.makedirs(directory, exist_ok=True)
        self.p_in = os.path.join(directory, "to_bridge.txt")
        self.p_out = os.path.join(directory, "to_game.txt")
        self.p_alive = os.path.join(directory, "bridge.alive")
        self.p_game_alive = os.path.join(directory, "game.alive")
        self._offset = 0
        self._buf = b""
        self._wlock = threading.Lock()
        for p in (self.p_out, self.p_in):
            try:
                with open(p, "w", encoding="utf-8"):
                    pass
            except OSError:
                pass
        try:
            os.remove(self.p_game_alive)
        except OSError:
            pass

    def read_lines(self) -> list[list[str]]:
        """届いた分を読み、完結した行だけを返す。

        読み出しが文字の途中に当たると decode でマルチバイト文字が壊れるため、
        Lua 側（ipc.lua）と同じく「最後の改行まで」を切り出してから decode する。
        改行（0x0A）は UTF-8 のマルチバイト列に現れないので、この位置は必ず
        文字の境界になる。残った半端なバイト列は次回の読み出しに持ち越す。
        """
        try:
            size = os.path.getsize(self.p_in)
        except OSError:
            return []
        if size < self._offset:
            self._offset = 0
            self._buf = b""
        if size == self._offset:
            return []
        try:
            with open(self.p_in, "rb") as f:
                f.seek(self._offset)
                chunk = f.read()
        except OSError:
            return []
        self._offset += len(chunk)
        self._buf += chunk

        cut = self._buf.rfind(b"\n")
        if cut < 0:
            return []
        complete, self._buf = self._buf[: cut + 1], self._buf[cut + 1 :]

        out = []
        for line in complete.decode("utf-8", "replace").split("\n"):
            line = line.strip("\r")
            if line:
                out.append(decode_line(line))
        return out

    def write(self, *fields) -> None:
        payload = encode_line(*fields)
        with self._wlock:
            try:
                with open(self.p_out, "a", encoding="utf-8", newline="") as f:
                    f.write(payload)
            except OSError as exc:
                log.warning(t("b.ipc.write_failed"), exc)

    def heartbeat(self) -> None:
        try:
            with open(self.p_alive, "w", encoding="utf-8") as f:
                f.write(f"{VERSION} {int(time.time())}\n")
        except OSError:
            pass

    def game_alive(self) -> bool:
        """MOD が生きているか。game.alive の更新時刻で判定する。"""
        try:
            with open(self.p_game_alive, encoding="utf-8") as f:
                content = f.readline()
        except OSError:
            return False
        m = re.search(r"(\d+)\s*$", content.strip())
        if not m:
            return False
        age = time.time() - int(m.group(1))
        return -5.0 <= age <= 20.0

    def cleanup(self) -> None:
        try:
            os.remove(self.p_alive)
        except OSError:
            pass


class Bridge:
    def __init__(self, cfg: dict, directory: str, fake: bool = False):
        check_formats(cfg)
        check_relay_limit(cfg)
        self.cfg = cfg
        self.ipc = Ipc(directory)
        self.stop_event = threading.Event()

        net = cfg["network"]
        provider_name = "stub" if fake else cfg["provider"]
        timeout = float(
            net["llm_timeout_sec"] if provider_name in LLM_PROVIDERS else net["timeout_sec"]
        )
        if fake:
            provider = StubProvider({}, timeout)
        else:
            provider = build_provider(
                provider_name, cfg["providers"].get(provider_name, {}), timeout
            )
        # --fake の目印つきの訳を、本物のキャッシュ（利用者の cache.json）に混ぜない
        cache = Cache(
            resolve_path(cfg["cache"]["path"]),
            int(cfg["cache"]["max_entries"]),
            bool(cfg["cache"]["enabled"]) and not fake,
        )
        glossary = Glossary(
            resolve_glossary(cfg["glossary"]["path"]) if cfg["glossary"]["enabled"] else None
        )
        self.translator = Translator(provider, cache, glossary, float(net["min_interval_sec"]))
        # 中継する訳が本当にその言語で書かれているかは、LLM のときだけ確かめる
        self.check_relay_script = provider_name in LLM_PROVIDERS
        self.cache = cache
        self.glossary = glossary
        self.pool = ThreadPoolExecutor(max_workers=int(net["max_workers"]),
                                       thread_name_prefix="tr")
        # オーバーレイから打った文は、打った順に送りたいので1本で順に処理する
        self.overlay_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ov")

        self.player_name = ""
        self.game_connected = False
        self.last_game_msg = 0.0
        self.ingame_display_ok: bool | None = None

        # overlay_queue を読むのはオーバーレイだけ。既定ではオーバーレイを使わない
        # （= 誰も読まない）ので、繋がっていない間は積まずに捨てる。
        self.overlay_attached = False
        self.overlay_queue: queue.Queue[tuple[str, str]] = queue.Queue()
        self.outbound_from_overlay: queue.Queue[str] = queue.Queue()

        log.info(t("b.startup"),
                 provider_name,
                 cfg["incoming"]["target"],
                 ",".join(cfg["outgoing"]["targets"]))

        problem = provider.setup_problem()
        if problem:
            log.warning("=" * 62)
            log.warning(t("b.not_ready"))
            for line in problem.splitlines():
                log.warning("  %s", line)
            log.warning("=" * 62)

    def show_on_overlay(self, kind: str, line: str) -> None:
        """オーバーレイに 1 行渡す。繋がっていなければ何もしない。

        表示用なので、読み手がいないときに溜め込む意味はない。
        """
        if self.overlay_attached:
            self.overlay_queue.put((kind, line))

    def relay_targets(self, source_lang: str) -> list[str]:
        """中継先の言語。発言者の言語は除く。"""
        rel = self.cfg["relay"]
        if not rel["enabled"]:
            return []
        targets = [t for t in rel["targets"] if t != source_lang]
        return targets[: max(0, int(rel["max_langs"]))]

    def translate_incoming(self, text: str, relay: bool = False
                           ) -> tuple[str, str, dict[str, str]]:
        """受信文を訳す。(検出言語, 自分向けの訳, 中継用の訳) を返す。"""
        inc = self.cfg["incoming"]
        if not inc["enabled"]:
            return "", "", {}
        if len(text) > int(inc["max_chars"]) or not is_translatable(text):
            return "", "", {}

        lang = detect_language(text)
        skip_self = lang in set(inc["skip_languages"])

        target = inc["target"]
        targets = self.relay_targets(lang) if relay else []
        if relay and len(text) > int(self.cfg["relay"]["max_chars"]):
            targets = []

        # 用語集は言語ごとに訳を持つ。自分自身への対応（掛け声など）は中継もしない
        hit = self.glossary.lookup_incoming(text, target)
        if hit is not None and same_phrase(hit, text):
            targets = []

        if not targets:
            if skip_self:
                return lang, "", {}
            if hit is not None:
                return lang, hit, {}
            translated, detected = self.translator.translate(text, None, target)
            return detected, translated, {}

        pending = list(targets)
        if not skip_self and hit is None and target not in pending:
            pending.append(target)
        results = self.translator.translate_multi(text, None, pending)
        if not skip_self and hit is not None:
            results.setdefault(target, hit)
        relayed: dict[str, str] = {}
        for code in targets:
            value = results.get(code)
            if not value or same_phrase(value, text):
                continue
            checked = relay_text_ok(value, text, code, self.check_relay_script)
            if checked is None:
                log.warning(t("b.relay.dropped"), code)
                continue
            relayed[code] = checked
        return lang, "" if skip_self else results.get(target, ""), relayed

    def relay_lines(self, sender: str, text: str, relayed: dict[str, str]) -> list[str]:
        """中継用の訳を1行にまとめる。max_line_chars を超えるときだけ行を分ける。"""
        rel = self.cfg["relay"]
        pieces = [
            (rel["format"] if i == 0 else rel["item_format"]).format(
                lang=LANG_TAGS.get(code, code.upper()),
                sender=sender, text=value, original=text)
            for i, (code, value) in enumerate(relayed.items())
        ]
        if not pieces:
            return []

        sep = rel["separator"]
        limit = max(0, int(rel["max_line_chars"]))
        if limit <= 0:
            return [sep.join(pieces)]

        lines: list[str] = []
        current = pieces[0]
        for piece in pieces[1:]:
            joined = current + sep + piece
            if len(joined) > limit:
                lines.append(current)
                current = piece
            else:
                current = joined
        lines.append(current)
        return lines

    def _do_incoming(self, req_id: str, sender: str, text: str,
                     host: bool = False) -> None:
        inc = self.cfg["incoming"]
        try:
            detected, translated, relayed = self.translate_incoming(text, relay=host)
            if not translated and not relayed:
                self.ipc.write("RES", req_id, "in", detected, "")
                return

            lang = detected or detect_language(text)
            line = inc["format"].format(
                sender=sender, text=translated, lang=lang.upper(), original=text
            ) if translated else ""
            relay_lines = self.relay_lines(sender, text, relayed)
            self.ipc.write("RES", req_id, "in", detected, line, *relay_lines)
            if line:
                self.show_on_overlay("in", line)
            if translated:
                log.info(t("b.in"), sender, text, translated, extra=CHAT)
            if relay_lines:
                log.info(t("b.relay"), " | ".join(relay_lines), extra=CHAT)
        except TranslationError as exc:
            log.warning(t("b.in.failed"), exc)
            self.ipc.write("ERR", req_id, str(exc))
        except Exception as exc:  # noqa: BLE001
            log.exception(t("b.in.error"))
            self.ipc.write("ERR", req_id, str(exc))

    def translate_outgoing(self, text: str) -> str:
        """自分の発言を設定された言語すべてに訳して 1 行にまとめる。"""
        out = self.cfg["outgoing"]
        source = out["source"] or None
        same = source or detect_language(text)
        targets: list[str] = [t for t in out["targets"] if t != same]

        results: dict[str, str] = {}
        pending: list[str] = []
        for target in targets:
            hit = self.glossary.lookup_outgoing(text, target)
            if hit:
                results[target] = hit
            else:
                pending.append(target)

        if pending:
            try:
                results.update(self.translator.translate_multi(text, source, pending))
            except TranslationError as exc:
                log.warning(t("b.out.failed"), ",".join(pending), exc)

        pieces: list[str] = [text] if out["include_source"] else []
        pieces += [results[t] for t in targets if results.get(t)]
        return out["separator"].join(p for p in pieces if p)

    def outgoing_wanted(self, text: str) -> bool:
        """自分の発言を訳すかどうか。翻訳の方針はすべてここ（settings.ini）で決める。"""
        out = self.cfg["outgoing"]
        body = text.strip()
        if not out["enabled"] or not body:
            return False
        if len(body) < int(out["min_length"]) or len(body) > int(out["max_chars"]):
            return False
        if any(p and body.startswith(p) for p in out["ignore_prefixes"]):
            return False
        return is_written_in(body, out["source"])

    def _do_outgoing(self, req_id: str, text: str) -> None:
        out = self.cfg["outgoing"]
        try:
            if not self.outgoing_wanted(text):
                self.ipc.write("RES", req_id, "out", "", "")
                return
            joined = self.translate_outgoing(text)
            self.ipc.write("RES", req_id, "out", out["source"], joined)
            if joined:
                log.info(t("b.out"), text, joined, extra=CHAT)
                self.show_on_overlay("out", joined)
        except Exception as exc:  # noqa: BLE001
            log.exception(t("b.out.error"))
            self.ipc.write("ERR", req_id, str(exc))

    def _do_overlay_outgoing(self, text: str) -> None:
        """オーバーレイの入力欄から打った文を訳してチャットへ送る。"""
        try:
            translated = self.translate_outgoing(text)
            if translated:
                self.ipc.write("SAY", translated)
                self.show_on_overlay("out", translated)
        except Exception:  # noqa: BLE001
            log.exception(t("b.out.error"))

    def handle(self, fields: list[str]) -> None:
        kind = fields[0] if fields else ""
        self.last_game_msg = time.time()
        if not self.game_connected:
            self.game_connected = True
            log.info(t("b.game.connected"))

        if kind == "REQ" and len(fields) >= 5:
            req_id, req_kind, sender, text = fields[1], fields[2], fields[3], fields[4]
            host = len(fields) > 5 and fields[5] == "1"
            if req_kind == "in":
                self.pool.submit(self._do_incoming, req_id, sender, text, host)
            elif req_kind == "out":
                self.pool.submit(self._do_outgoing, req_id, text)
            else:
                self.ipc.write("ERR", req_id, t("b.ipc.unknown_kind", kind=req_kind))

        elif kind == "REQ":
            # 形が合わなくても返事はする（しないと MOD 側が返事を待ち続ける）
            req_id = fields[1] if len(fields) > 1 else ""
            self.ipc.write("ERR", req_id, t("b.ipc.bad_req", n=len(fields)))

        elif kind == "HELLO":
            mod_version = fields[1] if len(fields) > 1 else "?"
            log.info(t("b.mod_version"), mod_version)
            self.ipc.write("HELLO", VERSION)
            if mod_version != VERSION:
                # MOD はゲームフォルダにあるので、exe だけ更新して MOD が古いままになりやすい
                log.warning(t("b.version_mismatch"), VERSION, mod_version)
                # ゲーム内の表示は、どの言語設定でもフォントがある英数字で書く
                self.ipc.write("NOTE", f"[DRGTranslate] Version mismatch: exe {VERSION} / "
                                       f"MOD {mod_version}. Run the setup again to update the MOD")

        elif kind == "NAME":
            self.player_name = fields[1] if len(fields) > 1 else ""
            log.info(t("b.player"), self.player_name)

        elif kind == "DISPLAY":
            ok = (len(fields) > 1 and fields[1] == "ok")
            self.ingame_display_ok = ok
            log.info(t("b.display"), "OK" if ok else t("b.display.failed"))

        elif kind == "TOGGLE":
            state = fields[1] if len(fields) > 1 else "?"
            log.info(t("b.toggle"), state)
            self.show_on_overlay("in", t("o.toggle", state=state))

        elif kind == "PING":
            self.ipc.write("NOTE", "[DRGTranslate] bridge is running")

    def run_loop(self) -> None:
        log.info(t("b.waiting"), self.ipc.dir)
        last_beat = 0.0
        while not self.stop_event.is_set():
            try:
                for fields in self.ipc.read_lines():
                    self.handle(fields)

                while True:
                    try:
                        text = self.outbound_from_overlay.get_nowait()
                    except queue.Empty:
                        break
                    # 翻訳は数十秒かかりうるので、ここで待つと生存通知も受信も止まる
                    if text:
                        self.overlay_pool.submit(self._do_overlay_outgoing, text)

                now = time.time()
                if now - last_beat >= 1.0:
                    last_beat = now
                    self.ipc.heartbeat()
                    self.cache.maybe_save()
                    alive = (
                        self.ipc.game_alive()
                        or (now - self.last_game_msg) <= 20.0
                    )
                    if alive and not self.game_connected:
                        self.game_connected = True
                        log.info(t("b.game.connected"))
                    elif not alive and self.game_connected:
                        self.game_connected = False
                        log.info(t("b.game.lost"))
            except Exception:  # noqa: BLE001
                log.exception(t("b.loop.error"))

            self.stop_event.wait(0.05)

        self.cache.maybe_save(force=True)
        self.ipc.cleanup()
        self.pool.shutdown(wait=False)
        self.overlay_pool.shutdown(wait=False)
        log.info(t("b.stopped"))

    def stop(self) -> None:
        self.stop_event.set()


LOG_FILE_NAME = "bridge.log"
LOG_FILE_MAX_BYTES = 512 * 1024
LOG_FORMAT = "%(asctime)s %(levelname)-7s %(message)s"
SECRET_ENV_NAMES = ("DEEPL_AUTH_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY")


class MaskingFormatter(logging.Formatter):
    """APIキーがログに出ないよう、書き出す直前に伏せる（例外の文面も含めて）。"""

    def __init__(self, fmt: str, datefmt: str, secrets: list[str]):
        super().__init__(fmt, datefmt)
        self.secrets = [s for s in secrets if len(s) >= 8]

    def format(self, record: logging.LogRecord) -> str:
        text = super().format(record)
        for secret in self.secrets:
            text = text.replace(secret, secret[:4] + "****")
        return text


class NoChatFilter(logging.Filter):
    """発言の本文（自分や他の隊員のチャット）はファイルに残さない。"""

    def filter(self, record: logging.LogRecord) -> bool:
        return not getattr(record, "chat", False)


# 発言の本文を含むログに付ける目印。画面には出すが、ファイルには残さない
CHAT = {"chat": True}


def setup_logging(level: str, log_file: str | None = None) -> None:
    """ログの出力先とレベルを設定する。2回目以降の呼び出しも効かせるため force を付ける。

    log_file を渡すと、画面に加えてファイルにも書く。窓を閉じたあとでも何が起きたか
    分かるようにするため。発言の本文は書かず、数百KBで打ち切って1世代だけ残す。
    """
    secrets = [os.environ.get(name, "").strip() for name in SECRET_ENV_NAMES]
    console = logging.StreamHandler()
    console.setFormatter(MaskingFormatter(LOG_FORMAT, "%H:%M:%S", secrets))
    handlers: list[logging.Handler] = [console]
    if log_file:
        try:
            os.makedirs(os.path.dirname(log_file) or ".", exist_ok=True)
            to_file = RotatingFileHandler(log_file, maxBytes=LOG_FILE_MAX_BYTES,
                                          backupCount=1, encoding="utf-8")
            to_file.setFormatter(MaskingFormatter(LOG_FORMAT, "%Y-%m-%d %H:%M:%S", secrets))
            to_file.addFilter(NoChatFilter())
            handlers.append(to_file)
        except OSError:
            pass
    logging.basicConfig(level=getattr(logging, level.upper(), logging.INFO),
                        handlers=handlers, force=True)


def run_test(bridge: Bridge, text: str) -> int:
    print(f"input       : {text}")
    print(f"detected    : {detect_language(text)}")
    try:
        if is_written_in(text, bridge.cfg["outgoing"]["source"]):
            print(f"outgoing    : {bridge.translate_outgoing(text)}")
            _, _, relayed = bridge.translate_incoming(text, relay=True)
            for line in bridge.relay_lines("Karl", text, relayed):
                print(f"relay (host): {line}")
        else:
            detected, translated, relayed = bridge.translate_incoming(text, relay=True)
            if translated:
                print(f"incoming    : {translated}  (source: {detected or 'unknown'})")
            else:
                print(f"incoming    : (not translated. source: {detected or 'undetermined'})")
            for line in bridge.relay_lines("Karl", text, relayed):
                print(f"relay (host): {line}")
    except TranslationError as exc:
        print(f"failed: {exc}")
        return 1
    bridge.cache.maybe_save(force=True)
    return 0


def run_selftest(bridge: Bridge) -> int:
    """mod 役も自分で演じて、ファイルIPC全体を確認する。"""
    t = threading.Thread(target=bridge.run_loop, daemon=True)
    t.start()
    time.sleep(0.3)

    p_in = bridge.ipc.p_in
    with open(p_in, "w", encoding="utf-8", newline="") as f:
        f.write(encode_line("HELLO", VERSION))
        f.write(encode_line("REQ", "1", "in", "Karl", "Rock and Stone!"))
        f.write(encode_line("REQ", "2", "in", "Karl", "watch out, swarm incoming"))
        f.write(encode_line("REQ", "3", "in", "민수", "안녕하세요"))
        f.write(encode_line("REQ", "4", "in", "Someone", "こんにちは"))
        f.write(encode_line("REQ", "5", "out", "Me", "回復お願いします"))
        f.write(encode_line("REQ", "8", "out", "Me", "hello everyone"))
        f.write(encode_line("REQ", "9", "out", "Me", "了解"))
        f.write(encode_line("REQ", "6", "in", "Karl", "swarm from the left", "1"))
        f.write(encode_line("REQ", "7", "in", "Someone", "左から来てる、下がって", "1"))
        f.write(encode_line("DISPLAY", "ok"))

    deadline = time.time() + 25
    seen: dict[str, list[str]] = {}
    offset = 0
    while time.time() < deadline and len(seen) < 10:
        time.sleep(0.2)
        try:
            with open(bridge.ipc.p_out, "rb") as f:
                f.seek(offset)
                chunk = f.read()
                offset += len(chunk)
        except OSError:
            continue
        for raw in chunk.decode("utf-8", "replace").splitlines():
            if not raw.strip():
                continue
            fields = decode_line(raw)
            key = fields[1] if fields[0] in ("RES", "ERR") and len(fields) > 1 else fields[0]
            seen[key] = fields

    bridge.stop()
    ok = True
    print("\n--- selftest results ---")
    for key in ("HELLO", "1", "2", "3", "4", "5", "6", "7", "8", "9"):
        fields = seen.get(key)
        if fields is None:
            print(f"  {key}: no response")
            ok = False
            continue
        print(f"  {key}: {fields}")
    relay = seen.get("6") or []
    if len(relay) < 6:
        print("  !! no relay lines came back")
        ok = False
    ja_relay = seen.get("7") or []
    if len(ja_relay) < 6:
        print("  !! no relay lines came back for the Japanese message")
        ok = False
    elif ja_relay[4] != "":
        print("  !! the Japanese message got a Japanese translation")
        ok = False
    en_out = seen.get("8") or []
    if len(en_out) > 4 and en_out[4] != "":
        print("  !! a message not in the source language was translated")
        ok = False
    kanji_out = seen.get("9") or []
    if len(kanji_out) > 4 and kanji_out[4] == "":
        print("  !! a kanji-only message was not translated")
        ok = False
    try:
        import anthropic  # noqa: F401
    except ImportError:
        # 入っていなければ確かめようがない。FAIL にはしないが、確かめていないことは出す
        print("  -- anthropic is not installed: skipped checking that it accepts "
              "the parameters we send")
    else:
        for problem in check_claude_params():
            print(f"  !! {problem}")
            ok = False
    print("--- " + ("PASS" if ok else "FAIL") + " ---")
    return 0 if ok else 1


def needs_setup(env_path: str) -> bool:
    """初回起動かどうか。設定ファイルが無ければ未セットアップ。"""
    return not os.path.exists(env_path)


def run_setup(env_path: str, args) -> bool:
    import setup_wizard

    def build_bridge():
        cfg = load_config(env_path)
        if args.provider:
            cfg["provider"] = args.provider
        return Bridge(cfg, ipc_dir(args.dir))

    return setup_wizard.run(
        env_path=env_path,
        example_path=bundled(SETTINGS_EXAMPLE_FILE),
        mod_source=bundled("mod", "DRGTranslate"),
        build_bridge=build_bridge,
    )


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass

    ap = argparse.ArgumentParser(description="DRGTranslate bridge")
    ap.add_argument("--config", metavar="FILE", help=f"settings file (default: {SETTINGS_FILE})")
    ap.add_argument("--dir", help="IPC folder (default: %%APPDATA%%\\DRGTranslate)")
    ap.add_argument("--test", metavar="TEXT", help="try a translation only (no game needed)")
    ap.add_argument("--selftest", action="store_true", help="check the file IPC end to end")
    ap.add_argument("--provider", help="override PROVIDER (deepl/claude/openai)")
    ap.add_argument("--fake", action="store_true",
                    help="for testing: tag the text instead of calling the API (no API key needed)")
    ap.add_argument("--no-overlay", action="store_true", help="do not use the overlay")
    ap.add_argument("--setup", action="store_true", help="run the setup wizard again")
    ap.add_argument("--no-setup", action="store_true",
                    help="start without the wizard even if it is not configured yet")
    args = ap.parse_args(argv)

    env_path = args.config or os.path.join(APP_DIR, SETTINGS_FILE)

    interactive = not (args.test or args.selftest or args.fake or args.no_setup)
    if interactive and (args.setup or needs_setup(env_path)):
        setup_logging("warning")
        if not run_setup(env_path, args):
            print("\n" + t("w.incomplete"))
            return 1

    cfg = load_config(env_path)
    if args.provider:
        cfg["provider"] = args.provider
    directory = ipc_dir(args.dir)
    setup_logging(cfg["log_level"], os.path.join(directory, LOG_FILE_NAME))

    try:
        bridge = Bridge(cfg, directory, fake=args.fake)
    except ValueError as exc:
        log.error("%s", exc)
        return 2

    if args.test:
        return run_test(bridge, args.test)
    if args.selftest:
        return run_selftest(bridge)

    def on_signal(_sig, _frm):
        log.info(t("b.stopping"))
        bridge.stop()

    signal.signal(signal.SIGINT, on_signal)
    try:
        signal.signal(signal.SIGTERM, on_signal)
    except (AttributeError, ValueError):
        pass

    use_overlay = cfg["overlay"]["enabled"] and not args.no_overlay
    if use_overlay:
        try:
            import overlay as overlay_mod
        except Exception as exc:  # noqa: BLE001
            log.warning(t("b.overlay.failed"), exc)
            use_overlay = False

    if use_overlay:
        # ここから overlay_queue に読み手がつく（import 失敗や --no-overlay では付かない）。
        bridge.overlay_attached = True
        worker = threading.Thread(target=bridge.run_loop, name="ipc", daemon=True)
        worker.start()
        overlay_mod.run(bridge)
        bridge.stop()
        worker.join(timeout=3)
    else:
        bridge.run_loop()
    return 0


def cli() -> int:
    """exe のエントリポイント。ダブルクリック起動やエラー終了では窓を閉じずに入力を待つ。"""
    try:
        code = main()
    except KeyboardInterrupt:
        code = 0
    except Exception:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        code = 1

    double_clicked = FROZEN and len(sys.argv) == 1
    if double_clicked or (FROZEN and code != 0):
        try:
            input("\n" + t("b.press_enter"))
        except (EOFError, KeyboardInterrupt):
            pass
    return code


if __name__ == "__main__":
    sys.exit(cli())
