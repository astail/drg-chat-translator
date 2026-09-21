"""settings.ini の書式指定を起動時に確かめることの回帰テスト。

リポジトリルートから `python3 -m pytest bridge/test_formats.py` で実行する。
"""

from __future__ import annotations

import copy
import logging
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from drg_bridge import DEFAULTS, Bridge, check_formats, decode_line  # noqa: E402


def _cfg(overrides: dict | None = None) -> dict:
    cfg = copy.deepcopy(DEFAULTS)
    cfg["cache"]["enabled"] = False
    for (section, key), value in (overrides or {}).items():
        cfg[section][key] = value
    return cfg


@pytest.mark.parametrize("bad", [
    "[TL] {name}: {text}",   # 使えない差し込み名
    "[TL] {sender: {text}",  # 括弧が閉じていない
    "[TL] {0}: {text}",      # 位置指定
    "[TL] {sender.x}",       # 属性の参照
])
def test_bad_incoming_format_falls_back(bad, caplog) -> None:
    """壊れた書式は警告を出して既定に戻すこと。"""
    cfg = _cfg({("incoming", "format"): bad})
    with caplog.at_level(logging.WARNING, logger="drgtl"):
        check_formats(cfg)
    assert cfg["incoming"]["format"] == DEFAULTS["incoming"]["format"]
    assert "DRGT_INCOMING_FORMAT" in caplog.text


def test_relay_formats_are_checked_too() -> None:
    """中継の書式2つも同じように確かめること。"""
    cfg = _cfg({("relay", "format"): "{who}: {text}",
                  ("relay", "item_format"): "[{language}] {text}"})
    check_formats(cfg)
    assert cfg["relay"]["format"] == DEFAULTS["relay"]["format"]
    assert cfg["relay"]["item_format"] == DEFAULTS["relay"]["item_format"]


def test_valid_custom_format_is_kept(caplog) -> None:
    """正しい書式は、既定と違っていてもそのまま使い、警告も出さないこと。"""
    fmt = "<{lang}> {sender} said: {text} ({original})"
    cfg = _cfg({("incoming", "format"): fmt})
    with caplog.at_level(logging.WARNING, logger="drgtl"):
        check_formats(cfg)
    assert cfg["incoming"]["format"] == fmt
    assert caplog.text == ""


def test_incoming_works_after_bad_format(tmp_path) -> None:
    """書式を書き間違えても、受信の翻訳は既定の書式で動き続けること（ERR にならない）。"""
    b = Bridge(_cfg({("incoming", "format"): "[TL] {name}: {text}"}), str(tmp_path), fake=True)
    try:
        b._do_incoming("1", "Karl", "watch out")
    finally:
        b.pool.shutdown(wait=True)
    with open(b.ipc.p_out, encoding="utf-8") as f:
        rows = [decode_line(line.rstrip("\n")) for line in f if line.strip()]
    assert rows[-1][0] == "RES"
    assert rows[-1][4].startswith("[訳] Karl: ")
