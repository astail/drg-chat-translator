"""用語集・中継行のまとめ方・設定の読み込みのテスト。

リポジトリルートから `python3 -m pytest bridge/test_bridge_units.py` で実行する。
"""

from __future__ import annotations

import json
import os

from drg_bridge import build_config
from translate import Glossary

GLOSSARY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "glossary.json")


def test_glossary_lookups_ignore_case_and_punctuation() -> None:
    g = Glossary(GLOSSARY)
    assert g.lookup_incoming("Rock and Stone!!", "ko") == "Rock and Stone!"
    assert g.lookup_outgoing("弾がない", "en") == "I'm out of ammo"
    assert g.lookup_outgoing("弾がない", "xx") is None
    assert g.lookup_incoming("no such phrase here", "ja") is None


def test_broken_glossary_does_not_crash(tmp_path) -> None:
    """壊れた用語集は、落ちずに空として扱うこと。"""
    path = tmp_path / "glossary.json"
    path.write_text("{ not json", encoding="utf-8")
    g = Glossary(str(path))
    assert g.incoming == {} and g.outgoing == {}


def test_missing_glossary_is_empty() -> None:
    assert Glossary(None).lookup_incoming("gg", "ja") is None


def test_relay_lines_fit_on_one_line_by_default(bridge) -> None:
    lines = bridge.relay_lines("Karl", "watch out", {"ja": "気をつけろ", "ko": "조심해", "zh": "小心"})
    assert lines == ["Karl: 気をつけろ / 조심해 / 小心"]


def test_relay_lines_split_at_max_line_chars(make_bridge, fake_cfg) -> None:
    """max_line_chars を超えるときだけ、言語の切れ目で行を分けること。"""
    fake_cfg["relay"]["max_line_chars"] = 20
    lines = make_bridge(fake_cfg).relay_lines(
        "Karl", "watch out", {"ja": "気をつけろ、左から来る", "ko": "조심해, 왼쪽이야", "zh": "小心左边"})
    assert len(lines) >= 2
    assert lines[0].startswith("Karl: ")
    assert all(len(line) <= 20 or " / " not in line for line in lines)


def test_skip_languages_follow_incoming_target(clean_env) -> None:
    """DRGT_INCOMING_SKIP_LANGUAGES を書かなければ、受信の訳す先に追従すること。"""
    clean_env(DRGT_INCOMING_TARGET="en")
    assert build_config()["incoming"]["skip_languages"] == ["en"]
    clean_env(DRGT_INCOMING_TARGET="en", DRGT_INCOMING_SKIP_LANGUAGES="ja, en")
    assert build_config()["incoming"]["skip_languages"] == ["ja", "en"]


def test_bad_numbers_fall_back_to_defaults(clean_env) -> None:
    """数値の書き間違いは、既定に戻して動くこと。"""
    clean_env(DRGT_CLAUDE_MAX_TOKENS="lots", DRGT_TIMEOUT_SEC="soon")
    cfg = build_config()
    assert cfg["providers"]["claude"]["max_tokens"] == 1024
    assert cfg["network"]["timeout_sec"] == 6.0


def test_booleans(clean_env) -> None:
    clean_env(DRGT_OVERLAY_ENABLED="yes", DRGT_RELAY_ENABLED="off")
    cfg = build_config()
    assert cfg["overlay"]["enabled"] is True
    assert cfg["relay"]["enabled"] is False
    assert json.dumps(cfg)  # 設定は JSON にできる形のまま
