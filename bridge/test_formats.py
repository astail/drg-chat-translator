"""settings.ini の書式指定を起動時に確かめることの回帰テスト。

リポジトリルートから `python3 -m pytest bridge/test_formats.py` で実行する。
"""

from __future__ import annotations

import logging

import pytest

from drg_bridge import DEFAULTS, check_formats


@pytest.mark.parametrize("bad", [
    "[TL] {name}: {text}",   # 使えない差し込み名
    "[TL] {sender: {text}",  # 括弧が閉じていない
    "[TL] {0}: {text}",      # 位置指定
    "[TL] {sender.x}",       # 属性の参照
])
def test_bad_incoming_format_falls_back(bad, caplog, fake_cfg) -> None:
    """壊れた書式は警告を出して既定に戻すこと。"""
    cfg = fake_cfg
    cfg["incoming"]["format"] = bad
    with caplog.at_level(logging.WARNING, logger="drgtl"):
        check_formats(cfg)
    assert cfg["incoming"]["format"] == DEFAULTS["incoming"]["format"]
    assert "DRGT_INCOMING_FORMAT" in caplog.text


def test_relay_formats_are_checked_too(fake_cfg) -> None:
    """中継の書式2つも同じように確かめること。"""
    cfg = fake_cfg
    cfg["relay"]["format"] = "{who}: {text}"
    cfg["relay"]["item_format"] = "[{language}] {text}"
    check_formats(cfg)
    assert cfg["relay"]["format"] == DEFAULTS["relay"]["format"]
    assert cfg["relay"]["item_format"] == DEFAULTS["relay"]["item_format"]


def test_valid_custom_format_is_kept(caplog, fake_cfg) -> None:
    """正しい書式は、既定と違っていてもそのまま使い、警告も出さないこと。"""
    fmt = "<{lang}> {sender} said: {text} ({original})"
    cfg = fake_cfg
    cfg["incoming"]["format"] = fmt
    with caplog.at_level(logging.WARNING, logger="drgtl"):
        check_formats(cfg)
    assert cfg["incoming"]["format"] == fmt
    assert caplog.text == ""


def test_incoming_works_after_bad_format(make_bridge, fake_cfg, read_out) -> None:
    """書式を書き間違えても、受信の翻訳は既定の書式で動き続けること（ERR にならない）。"""
    fake_cfg["incoming"]["format"] = "[TL] {name}: {text}"
    b = make_bridge(fake_cfg)
    b._do_incoming("1", "Karl", "watch out")
    rows = read_out(b)
    assert rows[-1][0] == "RES"
    assert rows[-1][4].startswith("[訳] Karl: ")
