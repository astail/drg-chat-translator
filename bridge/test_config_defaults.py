"""設定の既定値が DEFAULTS 1か所にまとまっていることの回帰テスト。

リポジトリルートから `python3 -m pytest bridge/test_config_defaults.py` で実行する。
"""

from __future__ import annotations

import copy
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from drg_bridge import DEFAULTS, Bridge, build_config, decode_line  # noqa: E402

CONFIG_ENV = ("DRGT_", "DEEPL_AUTH_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY")


def _clean_env(monkeypatch, **values) -> None:
    for key in [k for k in os.environ if k.startswith(CONFIG_ENV)]:
        monkeypatch.delenv(key, raising=False)
    for key, value in values.items():
        monkeypatch.setenv(key, value)


def test_build_config_equals_defaults_when_nothing_is_set(monkeypatch) -> None:
    """何も設定していなければ、build_config() は DEFAULTS とまったく同じになること。

    既定値を build_config() に直接書くと、DEFAULTS と食い違ったときにここで落ちる。
    """
    _clean_env(monkeypatch)
    assert build_config() == DEFAULTS


def test_auto_source_translates_whatever_language(monkeypatch, tmp_path) -> None:
    """DRGT_OUTGOING_SOURCE=auto なら、打った発言の言語を判定して訳すこと。"""
    _clean_env(monkeypatch, DRGT_OUTGOING_SOURCE="auto", DRGT_CACHE_ENABLED="false")
    cfg = build_config()
    assert cfg["outgoing"]["source"] == ""
    b = Bridge(cfg, str(tmp_path), fake=True)
    try:
        b._do_outgoing("1", "hello everyone")
        b._do_outgoing("2", "回復お願いします")
    finally:
        b.pool.shutdown(wait=True)
    with open(b.ipc.p_out, encoding="utf-8") as f:
        rows = {r[1]: r for r in (decode_line(x.rstrip("\n")) for x in f if x.strip())}
    # 英語の発言は、英語を除いた訳す先（ko / zh）へ
    assert rows["1"][4] == "[ko] hello everyone / [zh] hello everyone"
    # 日本語の発言は、既定の訳す先すべて（en / ko / zh）へ
    assert rows["2"][4].startswith("[en] 回復お願いします")


def test_fixed_source_skips_other_languages(monkeypatch, tmp_path) -> None:
    """翻訳元を決めているときは、それ以外の言語の発言は訳さないこと（従来どおり）。"""
    _clean_env(monkeypatch, DRGT_CACHE_ENABLED="false")
    b = Bridge(copy.deepcopy(build_config()), str(tmp_path), fake=True)
    try:
        b._do_outgoing("1", "hello everyone")
    finally:
        b.pool.shutdown(wait=True)
    with open(b.ipc.p_out, encoding="utf-8") as f:
        row = decode_line(f.read().rstrip("\n"))
    assert row[:3] == ["RES", "1", "out"] and row[4] == ""
