"""用語集・中継行のまとめ方・設定の読み込みのテスト。

リポジトリルートから `python3 -m pytest bridge/test_bridge_units.py` で実行する。
"""

from __future__ import annotations

import copy
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from drg_bridge import DEFAULTS, Bridge, build_config  # noqa: E402
from translate import Glossary  # noqa: E402

GLOSSARY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "glossary.json")


def test_glossary_lookups_ignore_case_and_punctuation() -> None:
    g = Glossary(GLOSSARY)
    assert g.lookup_incoming("Rock and Stone!!") == "Rock and Stone!"
    assert g.lookup_outgoing("弾がない", "en") == "I'm out of ammo"
    assert g.lookup_outgoing("弾がない", "xx") is None
    assert g.lookup_incoming("no such phrase here") is None


def test_broken_glossary_does_not_crash(tmp_path) -> None:
    """壊れた用語集は、落ちずに空として扱うこと。"""
    path = tmp_path / "glossary.json"
    path.write_text("{ not json", encoding="utf-8")
    g = Glossary(str(path))
    assert g.incoming == {} and g.outgoing == {}


def test_missing_glossary_is_empty() -> None:
    assert Glossary(None).lookup_incoming("gg") is None


def _bridge(tmp_path, **relay) -> Bridge:
    cfg = copy.deepcopy(DEFAULTS)
    cfg["cache"]["enabled"] = False
    cfg["relay"].update(relay)
    return Bridge(cfg, str(tmp_path), fake=True)


def test_relay_lines_fit_on_one_line_by_default(tmp_path) -> None:
    b = _bridge(tmp_path)
    try:
        lines = b.relay_lines("Karl", "watch out", {"ja": "気をつけろ", "ko": "조심해", "zh": "小心"})
    finally:
        b.pool.shutdown(wait=True)
    assert lines == ["Karl: 気をつけろ / 조심해 / 小心"]


def test_relay_lines_split_at_max_line_chars(tmp_path) -> None:
    """max_line_chars を超えるときだけ、言語の切れ目で行を分けること。"""
    b = _bridge(tmp_path, max_line_chars=20)
    try:
        lines = b.relay_lines("Karl", "watch out",
                              {"ja": "気をつけろ、左から来る", "ko": "조심해, 왼쪽이야", "zh": "小心左边"})
    finally:
        b.pool.shutdown(wait=True)
    assert len(lines) >= 2
    assert lines[0].startswith("Karl: ")
    assert all(len(line) <= 20 or " / " not in line for line in lines)


def _env(monkeypatch, **values) -> None:
    for key in [k for k in os.environ if k.startswith("DRGT_")]:
        monkeypatch.delenv(key, raising=False)
    for key, value in values.items():
        monkeypatch.setenv(key, value)


def test_skip_languages_follow_incoming_target(monkeypatch) -> None:
    """DRGT_INCOMING_SKIP_LANGUAGES を書かなければ、受信の訳す先に追従すること。"""
    _env(monkeypatch, DRGT_INCOMING_TARGET="en")
    assert build_config()["incoming"]["skip_languages"] == ["en"]
    _env(monkeypatch, DRGT_INCOMING_TARGET="en", DRGT_INCOMING_SKIP_LANGUAGES="ja, en")
    assert build_config()["incoming"]["skip_languages"] == ["ja", "en"]


def test_bad_numbers_fall_back_to_defaults(monkeypatch) -> None:
    """数値の書き間違いは、既定に戻して動くこと。"""
    _env(monkeypatch, DRGT_CLAUDE_MAX_TOKENS="lots", DRGT_TIMEOUT_SEC="soon")
    cfg = build_config()
    assert cfg["providers"]["claude"]["max_tokens"] == 1024
    assert cfg["network"]["timeout_sec"] == 6.0


def test_booleans(monkeypatch) -> None:
    _env(monkeypatch, DRGT_OVERLAY_ENABLED="yes", DRGT_RELAY_ENABLED="off")
    cfg = build_config()
    assert cfg["overlay"]["enabled"] is True
    assert cfg["relay"]["enabled"] is False
    assert json.dumps(cfg)  # 設定は JSON にできる形のまま
