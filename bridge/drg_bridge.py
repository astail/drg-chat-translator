#!/usr/bin/env python3
"""DRGTranslate bridge — Deep Rock Galactic のチャットを翻訳するローカル常駐プロセス。

ゲーム内の UE4SS Lua mod とは %APPDATA%\\DRGTranslate 配下のテキストファイルで
やり取りする（UE4SS の Lua にはソケットが無いため）。

  to_bridge.txt : mod -> bridge
  to_game.txt   : bridge -> mod
  bridge.alive  : 生存確認

翻訳プロバイダは deepl / claude / openai の3つ。プロジェクトルートの .env で選ぶ。

使い方:
    python drg_bridge.py                    通常起動
    python drg_bridge.py --test "こんにちは"      翻訳だけ試す（ゲーム不要）
    python drg_bridge.py --selftest --fake  APIキー無しでファイルIPCの疎通確認
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import queue
import re
import signal
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from translate import (  # noqa: E402
    Cache,
    Glossary,
    StubProvider,
    TranslationError,
    Translator,
    build_provider,
    detect_language,
    is_translatable,
    same_phrase,
)

VERSION = "0.5.2"
log = logging.getLogger("drgtl")

# 応答が遅い代わりにスラングや誤字に強いプロバイダ
LLM_PROVIDERS = {"claude", "openai"}

HERE = os.path.dirname(os.path.abspath(__file__))

# PyInstaller で固めた exe として動いているか
FROZEN = getattr(sys, "frozen", False)

if FROZEN:
    # onefile の exe は実行のたび一時フォルダへ展開される。
    # .env やキャッシュはそこに置くと消えるので、exe と同じ場所を使う。
    APP_DIR = os.path.dirname(os.path.abspath(sys.executable))
    # 同梱したリソース（用語集・MOD本体）の展開先
    BUNDLE_DIR = getattr(sys, "_MEIPASS", APP_DIR)
else:
    APP_DIR = os.path.dirname(HERE)    # リポジトリのルート
    BUNDLE_DIR = APP_DIR

ROOT = APP_DIR   # 後方互換


def bundled(*parts: str) -> str:
    """同梱リソースのパス。exe なら展開先、ソース実行ならリポジトリ内。"""
    return os.path.join(BUNDLE_DIR, *parts)


# ---------------------------------------------------------------------------
# 設定
# ---------------------------------------------------------------------------

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
        # zh は簡体字（中国大陸）。DRG の中国語話者はこちらが大多数
        "targets": ["en", "ko", "zh"],
        "separator": " / ",
        "include_source": False,
        "max_chars": 200,
    },
    # 中継（自分がホストのときだけ、他人の発言の訳を全員に配る）
    #
    # 発言者の言語は除いて訳す。英語の発言なら ja/ko/zh、
    # 韓国語の発言なら ja/en/zh、どれでもない言語なら4つすべて。
    # 1言語=1行で送る（1行にまとめるとチャットの文字数制限に引っかかる）。
    "relay": {
        "enabled": True,
        "targets": ["ja", "en", "ko", "zh"],
        "format": "[{lang}] {sender}: {text}",
        "max_chars": 200,
        "max_lines": 4,
    },
    # exe のときは exe の隣、ソース実行のときは bridge/ の下
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
        # LLM(claude/openai)は応答に時間がかかるので別枠のタイムアウトを使う
        "llm_timeout_sec": 20.0,
        "max_workers": 4,
        "min_interval_sec": 0.0,
    },
    "log_level": "info",
}


# 中継行に付ける言語の目印。チャットで見慣れた書き方に寄せる（ja→JP, ko→KR）
LANG_TAGS = {"ja": "JP", "ko": "KR"}


def load_dotenv(path: str) -> int:
    """.env を読んで os.environ に入れる。読み込んだ件数を返す。

    既に環境変数として設定されている値は上書きしない（実環境の指定が優先）。
    python-dotenv は使わない — 依存を増やさないため。

    対応する書き方:
        KEY=value
        KEY = value          前後の空白は無視
        KEY="value with spaces"   引用符で囲めば空白を保持
        # comment            行頭の # はコメント
    """
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
        log.warning("%s は整数として読めません。既定値 %s を使います", key, default)
        return default


def _float(key: str, default: float) -> float:
    try:
        return float(_str(key, str(default)))
    except ValueError:
        log.warning("%s は数値として読めません。既定値 %s を使います", key, default)
        return default


def _list(key: str, default: list[str]) -> list[str]:
    v = os.environ.get(key)
    if v is None or v.strip() == "":
        return list(default)
    return [item.strip() for item in v.split(",") if item.strip()]


def build_config() -> dict:
    """環境変数（.env 読み込み済み）から設定を組み立てる。

    APIキーだけは各SDKが読む慣習的な名前をそのまま使い、
    それ以外は他ツールと衝突しないよう DRGT_ を付けている
    （LOG_LEVEL や MAX_WORKERS のような名前は実際によくぶつかる）。
    """
    d = DEFAULTS
    return {
        "provider": _str("DRGT_PROVIDER", d["provider"]).strip().lower(),
        "providers": {
            "deepl": {
                # api_key が空ならプロバイダ側が DEEPL_AUTH_KEY を読む
                "api_key": _str("DEEPL_AUTH_KEY", ""),
                "api_url": _str("DRGT_DEEPL_API_URL", ""),
            },
            "claude": {
                "api_key": _str("ANTHROPIC_API_KEY", ""),
                "model": _str("DRGT_CLAUDE_MODEL", d["providers"]["claude"]["model"]),
                "max_tokens": _int("DRGT_CLAUDE_MAX_TOKENS", 1024),
                "effort": _str("DRGT_CLAUDE_EFFORT", "auto"),
                "refusal_fallback": _str("DRGT_CLAUDE_REFUSAL_FALLBACK", "auto"),
            },
            "openai": {
                "api_key": _str("OPENAI_API_KEY", ""),
                "model": _str("DRGT_OPENAI_MODEL", d["providers"]["openai"]["model"]),
                "base_url": _str("DRGT_OPENAI_BASE_URL", ""),
                "max_tokens": _int("DRGT_OPENAI_MAX_TOKENS", 1024),
            },
        },
        "incoming": {
            "enabled": _bool("DRGT_INCOMING_ENABLED", True),
            "target": _str("DRGT_INCOMING_TARGET", "ja"),
            "skip_languages": _list("DRGT_INCOMING_SKIP_LANGUAGES", ["ja"]),
            "format": _str("DRGT_INCOMING_FORMAT", d["incoming"]["format"]),
            "max_chars": _int("DRGT_INCOMING_MAX_CHARS", 400),
        },
        "outgoing": {
            "enabled": _bool("DRGT_OUTGOING_ENABLED", True),
            "source": _str("DRGT_OUTGOING_SOURCE", "ja"),
            "targets": _list("DRGT_OUTGOING_TARGETS", d["outgoing"]["targets"]),
            "separator": os.environ.get("DRGT_OUTGOING_SEPARATOR") or " / ",
            "include_source": _bool("DRGT_OUTGOING_INCLUDE_SOURCE", False),
            "max_chars": _int("DRGT_OUTGOING_MAX_CHARS", 200),
        },
        "relay": {
            "enabled": _bool("DRGT_RELAY_ENABLED", d["relay"]["enabled"]),
            "targets": _list("DRGT_RELAY_TARGETS", d["relay"]["targets"]),
            "format": _str("DRGT_RELAY_FORMAT", d["relay"]["format"]),
            "max_chars": _int("DRGT_RELAY_MAX_CHARS", d["relay"]["max_chars"]),
            "max_lines": _int("DRGT_RELAY_MAX_LINES", d["relay"]["max_lines"]),
        },
        "cache": {
            "enabled": _bool("DRGT_CACHE_ENABLED", True),
            "max_entries": _int("DRGT_CACHE_MAX_ENTRIES", 5000),
            "path": _str("DRGT_CACHE_PATH", d["cache"]["path"]),
        },
        "glossary": {
            "enabled": _bool("DRGT_GLOSSARY_ENABLED", True),
            "path": _str("DRGT_GLOSSARY_PATH", d["glossary"]["path"]),
        },
        "overlay": {
            "enabled": _bool("DRGT_OVERLAY_ENABLED", False),
            "mode": _str("DRGT_OVERLAY_MODE", "auto"),
            "hide_after": _float("DRGT_OVERLAY_HIDE_AFTER", 12.0),
            "lines": _int("DRGT_OVERLAY_LINES", 8),
            "font_size": _int("DRGT_OVERLAY_FONT_SIZE", 13),
            "opacity": _float("DRGT_OVERLAY_OPACITY", 0.85),
            "x": _int("DRGT_OVERLAY_X", 40),
            "y": _int("DRGT_OVERLAY_Y", 40),
            "width": _int("DRGT_OVERLAY_WIDTH", 520),
            "composer": _bool("DRGT_OVERLAY_COMPOSER", True),
        },
        "network": {
            "timeout_sec": _float("DRGT_TIMEOUT_SEC", 6.0),
            "llm_timeout_sec": _float("DRGT_LLM_TIMEOUT_SEC", 20.0),
            "max_workers": _int("DRGT_MAX_WORKERS", 4),
            "min_interval_sec": _float("DRGT_MIN_INTERVAL_SEC", 0.0),
        },
        "log_level": _str("DRGT_LOG_LEVEL", "info"),
    }


def load_config(env_path: str | None) -> dict:
    path = env_path or os.path.join(APP_DIR, ".env")
    n = load_dotenv(path)
    if n:
        log.info("設定を読み込みました: %s (%d 項目)", path, n)
    elif not os.path.exists(path):
        log.warning(".env がありません: %s", path)
    return build_config()


def resolve_path(cfg_path: str) -> str:
    """相対パスは exe（またはリポジトリルート）基準で解決する。"""
    return cfg_path if os.path.isabs(cfg_path) else os.path.join(APP_DIR, cfg_path)


def resolve_glossary(cfg_path: str) -> str:
    """用語集のパス。

    exe の隣に glossary.json を置けばそれを使う（利用者が編集できる）。
    無ければ exe に同梱したものを使う。
    """
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
    # Windows 以外（開発・テスト用）
    return os.path.join(os.path.expanduser("~"), ".config", "DRGTranslate")


# ---------------------------------------------------------------------------
# 行フォーマット（Lua 側 util.lua と同じ規則）
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# IPC
# ---------------------------------------------------------------------------


class Ipc:
    def __init__(self, directory: str):
        self.dir = directory
        os.makedirs(directory, exist_ok=True)
        self.p_in = os.path.join(directory, "to_bridge.txt")
        self.p_out = os.path.join(directory, "to_game.txt")
        self.p_alive = os.path.join(directory, "bridge.alive")
        self.p_game_alive = os.path.join(directory, "game.alive")
        self._offset = 0
        self._buf = ""
        self._wlock = threading.Lock()
        # 前回のセッションの残骸を消す。to_bridge.txt も消さないと、
        # 落ちたゲームが残した HELLO を読んで「接続済み」と誤認する。
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
        try:
            size = os.path.getsize(self.p_in)
        except OSError:
            return []
        if size < self._offset:
            # mod 側がセッション開始時に切り詰めた
            self._offset = 0
            self._buf = ""
        if size == self._offset:
            return []
        try:
            with open(self.p_in, "rb") as f:
                f.seek(self._offset)
                chunk = f.read()
        except OSError:
            return []
        self._offset += len(chunk)
        self._buf += chunk.decode("utf-8", "replace")

        out = []
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
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
                log.warning("to_game.txt へ書き込めません: %s", exc)

    def heartbeat(self) -> None:
        try:
            with open(self.p_alive, "w", encoding="utf-8") as f:
                f.write(f"{VERSION} {int(time.time())}\n")
        except OSError:
            pass

    def game_alive(self) -> bool:
        """MOD が生きているか。game.alive の更新時刻で判定する。

        MOD は送るものが無ければ何も書かないので、受信の有無で判定すると
        「黙っているだけ」を切断と誤認してしまう。
        """
        try:
            with open(self.p_game_alive, encoding="utf-8") as f:
                content = f.readline()
        except OSError:
            return False
        m = re.search(r"(\d+)\s*$", content.strip())
        if not m:
            return False
        age = time.time() - int(m.group(1))
        # レベルロード中は UE4SS の Lua スレッドが数秒止まることがあるので広めに取る。
        # 実際に落ちたときの検知が数秒遅れる分には困らない。
        return -5.0 <= age <= 20.0

    def cleanup(self) -> None:
        try:
            os.remove(self.p_alive)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# 本体
# ---------------------------------------------------------------------------


class Bridge:
    def __init__(self, cfg: dict, directory: str, fake: bool = False):
        self.cfg = cfg
        self.ipc = Ipc(directory)
        self.stop_event = threading.Event()

        net = cfg["network"]
        provider_name = "stub" if fake else cfg["provider"]
        timeout = float(
            net["llm_timeout_sec"] if provider_name in LLM_PROVIDERS else net["timeout_sec"]
        )
        if fake:
            # テスト用。APIキーもネットワークも無い環境で動かすためのもの
            provider = StubProvider({}, timeout)
        else:
            provider = build_provider(
                provider_name, cfg["providers"].get(provider_name, {}), timeout
            )
        cache = Cache(
            resolve_path(cfg["cache"]["path"]),
            int(cfg["cache"]["max_entries"]),
            bool(cfg["cache"]["enabled"]),
        )
        glossary = Glossary(
            resolve_glossary(cfg["glossary"]["path"]) if cfg["glossary"]["enabled"] else None
        )
        self.translator = Translator(provider, cache, glossary, float(net["min_interval_sec"]))
        self.cache = cache
        self.glossary = glossary
        self.pool = ThreadPoolExecutor(max_workers=int(net["max_workers"]),
                                       thread_name_prefix="tr")

        self.player_name = ""
        self.game_connected = False
        self.last_game_msg = 0.0
        self.ingame_display_ok: bool | None = None

        # オーバーレイ用
        self.overlay_queue: queue.Queue[tuple[str, str]] = queue.Queue()
        self.outbound_from_overlay: queue.Queue[str] = queue.Queue()

        log.info("provider=%s / 受信→%s / 送信→%s",
                 provider_name,
                 cfg["incoming"]["target"],
                 ",".join(cfg["outgoing"]["targets"]))

        # 設定漏れは起動時点で知らせる。ゲーム内で「翻訳が出ない」となってから
        # 原因を探すことになるのを避けるため。
        problem = provider.setup_problem()
        if problem:
            log.warning("=" * 62)
            log.warning("翻訳できる状態になっていません:")
            for line in problem.splitlines():
                log.warning("  %s", line)
            log.warning("=" * 62)

    # -- 翻訳処理 ---------------------------------------------------------

    def relay_targets(self, source_lang: str) -> list[str]:
        """中継先の言語。発言者の言語は除く（訳す意味がないため）。"""
        rel = self.cfg["relay"]
        if not rel["enabled"]:
            return []
        targets = [t for t in rel["targets"] if t != source_lang]
        return targets[: max(0, int(rel["max_lines"]))]

    def translate_incoming(self, text: str, relay: bool = False
                           ) -> tuple[str, str, dict[str, str]]:
        """受信文を訳す。(検出言語, 日本語訳, 中継用の訳) を返す。

        用語集の判定を含む本番と同じ経路。--test からも呼ぶので、
        利用者が試したときに実際に出るものと同じ結果になる。

        relay=True（自分がホストのとき）は、全員に配る用の訳も一緒に作る。
        日本語訳と中継用をまとめて1回の API 呼び出しで取るので、
        中継を入れても呼び出し回数は増えない。
        """
        inc = self.cfg["incoming"]
        if not inc["enabled"]:
            return "", "", {}
        if len(text) > int(inc["max_chars"]) or not is_translatable(text):
            return "", "", {}

        lang = detect_language(text)
        if lang in set(inc["skip_languages"]):
            return lang, "", {}

        target = inc["target"]
        targets = self.relay_targets(lang) if relay else []
        if relay and len(text) > int(self.cfg["relay"]["max_chars"]):
            targets = []

        hit = self.glossary.lookup_incoming(text)

        # 用語集の訳が原文と同じ＝どの言語でもそのまま使う掛け声。
        # 中継しても同じ文字列が並ぶだけなので、API を呼ぶ前に打ち切る
        # （"Rock and Stone!" は連呼されるので、ここを通すと呼び出しが嵩む）
        if hit is not None and same_phrase(hit, text):
            targets = []

        if not targets:
            # 中継しないときは今までどおり1言語だけ。
            # プロバイダ自身の言語判定（DeepL の detected_source_language）も使える。
            if hit is not None:
                return lang, hit, {}
            # 訳文が原文と同じでも表示する。"Rock and Stone!" のような
            # ゲーム固有の掛け声は、そのまま出るのが正しい訳のため。
            translated, detected = self.translator.translate(text, None, target)
            return detected, translated, {}

        pending = list(targets)
        if hit is None and target not in pending:
            pending.append(target)
        results = self.translator.translate_multi(text, None, pending)
        if hit is not None:
            results.setdefault(target, hit)
        # 原文と変わらない訳は中継しない。掛け声のたぐいは訳しても同じ文字列に
        # なることがあり、流すとチャットが荒れるだけになる
        relayed = {t: results[t] for t in targets
                   if results.get(t) and not same_phrase(results[t], text)}
        return lang, results.get(target, ""), relayed

    def relay_lines(self, sender: str, text: str, relayed: dict[str, str]) -> list[str]:
        """中継用の訳を1言語1行に整える。

        1行にまとめるとチャットの文字数制限に引っかかるので分けている。
        """
        fmt = self.cfg["relay"]["format"]
        return [
            fmt.format(lang=LANG_TAGS.get(code, code.upper()),
                       sender=sender, text=value, original=text)
            for code, value in relayed.items()
        ]

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
                self.overlay_queue.put(("in", line))
            log.info("受信 [%s] %s -> %s", sender, text, translated)
            if relay_lines:
                log.info("中継(ホスト) %s", " | ".join(relay_lines))
        except TranslationError as exc:
            log.warning("受信翻訳に失敗: %s", exc)
            self.ipc.write("ERR", req_id, str(exc))
        except Exception as exc:  # noqa: BLE001
            log.exception("受信翻訳で予期しないエラー")
            self.ipc.write("ERR", req_id, str(exc))

    def translate_outgoing(self, text: str) -> str:
        """日本語の発言を設定された言語すべてに訳して 1 行にまとめる。"""
        out = self.cfg["outgoing"]
        source = out["source"] or None
        targets: list[str] = list(out["targets"])

        # 用語集で片付く言語は API に投げない
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
                # LLM プロバイダなら 1 回の呼び出しで全言語ぶん返ってくる
                results.update(self.translator.translate_multi(text, source, pending))
            except TranslationError as exc:
                log.warning("送信翻訳に失敗 (%s): %s", ",".join(pending), exc)

        pieces: list[str] = [text] if out["include_source"] else []
        pieces += [results[t] for t in targets if results.get(t)]
        return out["separator"].join(p for p in pieces if p)

    def _do_outgoing(self, req_id: str, text: str) -> None:
        out = self.cfg["outgoing"]
        try:
            if not out["enabled"] or len(text) > int(out["max_chars"]):
                self.ipc.write("RES", req_id, "out", "", "")
                return
            joined = self.translate_outgoing(text)
            self.ipc.write("RES", req_id, "out", out["source"], joined)
            if joined:
                log.info("送信 %s -> %s", text, joined)
                self.overlay_queue.put(("out", joined))
        except Exception as exc:  # noqa: BLE001
            log.exception("送信翻訳で予期しないエラー")
            self.ipc.write("ERR", req_id, str(exc))

    # -- 受信ループ -------------------------------------------------------

    def handle(self, fields: list[str]) -> None:
        kind = fields[0] if fields else ""
        self.last_game_msg = time.time()
        if not self.game_connected:
            self.game_connected = True
            log.info("ゲーム(mod)と接続しました")

        if kind == "REQ" and len(fields) >= 5:
            req_id, req_kind, sender, text = fields[1], fields[2], fields[3], fields[4]
            # 6番目は「自分がホストか」。ホストかどうかを知っているのは mod 側だけ
            host = len(fields) > 5 and fields[5] == "1"
            if req_kind == "in":
                self.pool.submit(self._do_incoming, req_id, sender, text, host)
            elif req_kind == "out":
                self.pool.submit(self._do_outgoing, req_id, text)
            else:
                self.ipc.write("ERR", req_id, f"未知の種別: {req_kind}")

        elif kind == "HELLO":
            log.info("mod version = %s", fields[1] if len(fields) > 1 else "?")
            self.ipc.write("HELLO", VERSION)

        elif kind == "NAME":
            self.player_name = fields[1] if len(fields) > 1 else ""
            log.info("プレイヤー名: %s", self.player_name)

        elif kind == "DISPLAY":
            ok = (len(fields) > 1 and fields[1] == "ok")
            self.ingame_display_ok = ok
            log.info("ゲーム内表示: %s", "OK" if ok else "失敗（オーバーレイに切替）")

        elif kind == "TOGGLE":
            # F9 の押下。ホストだとゲーム内に出せないので、ここが唯一の反応になる
            state = fields[1] if len(fields) > 1 else "?"
            log.info("翻訳 %s（ゲーム内で F9 が押されました）", state)
            self.overlay_queue.put(("in", f"[DRGTranslate] 翻訳 {state}"))

        elif kind == "PING":
            self.ipc.write("NOTE", "[DRGTranslate] bridge は動作中です")

    def run_loop(self) -> None:
        log.info("待機中: %s", self.ipc.dir)
        last_beat = 0.0
        while not self.stop_event.is_set():
            try:
                for fields in self.ipc.read_lines():
                    self.handle(fields)

                # オーバーレイの入力欄から送られたものをゲームへ流す
                while True:
                    try:
                        text = self.outbound_from_overlay.get_nowait()
                    except queue.Empty:
                        break
                    translated = self.translate_outgoing(text) if text else ""
                    if translated:
                        self.ipc.write("SAY", translated)
                        self.overlay_queue.put(("out", translated))

                now = time.time()
                if now - last_beat >= 1.0:
                    last_beat = now
                    self.ipc.heartbeat()
                    self.cache.maybe_save()
                    # 生死は game.alive の更新で見る。無言＝切断ではない。
                    # 直前に何か受け取っていれば、心拍が遅れていても生きている。
                    alive = (
                        self.ipc.game_alive()
                        or (now - self.last_game_msg) <= 20.0
                    )
                    if alive and not self.game_connected:
                        self.game_connected = True
                        log.info("ゲーム(mod)と接続しました")
                    elif not alive and self.game_connected:
                        self.game_connected = False
                        log.info("ゲーム(mod)からの通信が途絶えました")
            except Exception:  # noqa: BLE001
                log.exception("メインループでエラー")

            self.stop_event.wait(0.05)

        self.cache.maybe_save(force=True)
        self.ipc.cleanup()
        self.pool.shutdown(wait=False)
        log.info("終了しました")

    def stop(self) -> None:
        self.stop_event.set()


# ---------------------------------------------------------------------------
# エントリポイント
# ---------------------------------------------------------------------------


def setup_logging(level: str) -> None:
    """ログの出力先とレベルを設定する。2回目以降の呼び出しも効かせること。

    初回起動はウィザードのあいだ warning にして、終わったら設定の
    log_level（既定 info）に戻す、という2段構えになっている。
    basicConfig は既にハンドラがあると黙って何もしないので、force を
    付けないと warning のまま常駐してしまい、「黒い窓に何も流れない」
    ことになる（初回だけ症状が出て、2回目からは直るので気づきにくい）。
    """
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
        force=True,
    )


def run_test(bridge: Bridge, text: str) -> int:
    print(f"入力      : {text}")
    print(f"言語判定  : {detect_language(text)}")
    try:
        if detect_language(text) == "ja":
            print(f"送信用翻訳: {bridge.translate_outgoing(text)}")
        else:
            # 本番の受信経路と同じもの（用語集の判定を含む）を通す。
            # ホストのときに全員へ配る中継文もここで確認できる
            detected, translated, relayed = bridge.translate_incoming(text, relay=True)
            if translated:
                print(f"受信用翻訳: {translated}  (元言語: {detected or '不明'})")
            else:
                print(f"受信用翻訳: (翻訳しません。元言語: {detected or '判定不能'})")
            for line in bridge.relay_lines("Karl", text, relayed):
                print(f"中継(ホスト): {line}")
    except TranslationError as exc:
        print(f"失敗: {exc}")
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
        f.write(encode_line("HELLO", "selftest"))
        f.write(encode_line("REQ", "1", "in", "Karl", "Rock and Stone!"))
        f.write(encode_line("REQ", "2", "in", "Karl", "watch out, swarm incoming"))
        f.write(encode_line("REQ", "3", "in", "민수", "안녕하세요"))
        f.write(encode_line("REQ", "4", "in", "Someone", "こんにちは"))
        f.write(encode_line("REQ", "5", "out", "Me", "回復お願いします"))
        # 6番目のフィールド "1" = 自分がホスト。訳文に加えて中継用の行も返るはず
        f.write(encode_line("REQ", "6", "in", "Karl", "swarm from the left", "1"))
        f.write(encode_line("DISPLAY", "ok"))

    deadline = time.time() + 25
    seen: dict[str, list[str]] = {}
    offset = 0
    while time.time() < deadline and len(seen) < 7:
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
    print("\n--- selftest 結果 ---")
    for key in ("HELLO", "1", "2", "3", "4", "5", "6"):
        fields = seen.get(key)
        if fields is None:
            print(f"  {key}: 応答なし")
            ok = False
            continue
        print(f"  {key}: {fields}")
    # 6 はホストとしての受信。日本語訳(5番目)に加えて中継行が付いていること
    relay = seen.get("6") or []
    if len(relay) < 6:
        print("  !! 中継行が返っていません")
        ok = False
    print("--- " + ("PASS" if ok else "FAIL") + " ---")
    return 0 if ok else 1


def needs_setup(env_path: str) -> bool:
    """初回起動かどうか。.env が無い、または中身が空同然なら未セットアップ。"""
    if not os.path.exists(env_path):
        return True
    try:
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    if line.split("=", 1)[1].strip():
                        return False
    except OSError:
        return True
    return True


def run_setup(env_path: str, args) -> bool:
    import setup_wizard

    def build_bridge():
        # ウィザードが書いた .env を読み直してから作る
        cfg = load_config(env_path)
        if args.provider:
            cfg["provider"] = args.provider
        return Bridge(cfg, ipc_dir(args.dir))

    return setup_wizard.run(
        env_path=env_path,
        example_path=bundled(".env.example"),
        mod_source=bundled("mod", "DRGTranslate"),
        build_bridge=build_bridge,
    )


def main(argv: list[str] | None = None) -> int:
    # Windows のコンソールでも日本語が化けないようにする
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass

    ap = argparse.ArgumentParser(description="DRGTranslate bridge")
    ap.add_argument("--config", metavar="ENV", help="設定ファイル (既定: .env)")
    ap.add_argument("--dir", help="IPC フォルダ (既定: %%APPDATA%%\\DRGTranslate)")
    ap.add_argument("--test", metavar="TEXT", help="翻訳だけ試す（ゲーム不要）")
    ap.add_argument("--selftest", action="store_true", help="ファイルIPCの疎通確認")
    ap.add_argument("--provider", help="PROVIDER を上書き (deepl/claude/openai)")
    ap.add_argument("--fake", action="store_true",
                    help="テスト用: 翻訳APIを呼ばず目印を付けて返す（APIキー不要）")
    ap.add_argument("--no-overlay", action="store_true", help="オーバーレイを使わない")
    ap.add_argument("--setup", action="store_true", help="セットアップをやり直す")
    ap.add_argument("--no-setup", action="store_true",
                    help="未設定でもウィザードを出さずに起動する")
    args = ap.parse_args(argv)

    env_path = args.config or os.path.join(APP_DIR, ".env")

    # 初回起動、または --setup 明示のときはウィザードを通す。
    # --test / --selftest / --fake は検証用なので邪魔しない。
    interactive = not (args.test or args.selftest or args.fake or args.no_setup)
    if interactive and (args.setup or needs_setup(env_path)):
        setup_logging("warning")
        if not run_setup(env_path, args):
            print("\nセットアップを完了できませんでした。")
            return 1

    cfg = load_config(env_path)
    if args.provider:
        cfg["provider"] = args.provider
    setup_logging(cfg["log_level"])

    directory = ipc_dir(args.dir)
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
        log.info("停止します...")
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
            log.warning("オーバーレイを起動できません (%s)。ログのみで続行します", exc)
            use_overlay = False

    if use_overlay:
        worker = threading.Thread(target=bridge.run_loop, name="ipc", daemon=True)
        worker.start()
        overlay_mod.run(bridge)   # Tk はメインスレッドで動かす必要がある
        bridge.stop()
        worker.join(timeout=3)
    else:
        bridge.run_loop()
    return 0


def cli() -> int:
    """exe のエントリポイント。

    ダブルクリック起動だと、エラーで落ちた瞬間に窓が消えて何も読めない。
    そこで exe のときは最後に入力待ちを入れる。

    ただし --test / --selftest のようにコマンドラインから叩く用途では
    待たれると困る（スクリプトが止まる）ので、引数無しの起動だけにする。
    """
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
            input("\nEnter キーを押すと閉じます...")
        except (EOFError, KeyboardInterrupt):
            pass
    return code


if __name__ == "__main__":
    sys.exit(cli())
