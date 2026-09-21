"""HELLO で版の食い違いを知らせることの回帰テスト。

リポジトリルートから `python3 -m pytest bridge/test_version_check.py` で実行する。
"""

from __future__ import annotations

import copy
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from drg_bridge import DEFAULTS, VERSION, Bridge, decode_line  # noqa: E402


@pytest.fixture
def bridge(tmp_path):
    cfg = copy.deepcopy(DEFAULTS)
    cfg["cache"]["enabled"] = False
    b = Bridge(cfg, str(tmp_path), fake=True)
    yield b
    b.pool.shutdown(wait=True)


def _rows(b: Bridge) -> list[list[str]]:
    with open(b.ipc.p_out, encoding="utf-8") as f:
        return [decode_line(line.rstrip("\n")) for line in f if line.strip()]


def test_same_version_sends_only_hello(bridge) -> None:
    """版が同じなら HELLO を返すだけで、案内は出さないこと。"""
    bridge.handle(["HELLO", VERSION])
    assert _rows(bridge) == [["HELLO", VERSION]]


def test_mismatch_notifies_in_game(bridge) -> None:
    """版が違えば、ゲーム内に英数字だけの案内を NOTE で出すこと。"""
    bridge.handle(["HELLO", "0.0.1"])
    rows = _rows(bridge)
    assert rows[0] == ["HELLO", VERSION]
    notes = [r[1] for r in rows if r[0] == "NOTE"]
    assert len(notes) == 1
    assert "0.0.1" in notes[0] and VERSION in notes[0]
    assert notes[0].isascii()


def test_missing_version_is_mismatch(bridge) -> None:
    """版が付いていない HELLO も食い違いとして扱うこと。"""
    bridge.handle(["HELLO"])
    assert any(r[0] == "NOTE" for r in _rows(bridge))
