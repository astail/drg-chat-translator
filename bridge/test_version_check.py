"""HELLO で版の食い違いを知らせることの回帰テスト。

リポジトリルートから `python3 -m pytest bridge/test_version_check.py` で実行する。
"""

from __future__ import annotations

import copy
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from drg_bridge import DEFAULTS, VERSION, Bridge, Ipc, decode_line  # noqa: E402


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


def _alive(ipc: Ipc) -> list[str]:
    ipc.heartbeat()
    with open(ipc.p_alive, encoding="utf-8") as f:
        return f.read().split()


def test_heartbeat_carries_a_boot_id(tmp_path) -> None:
    """bridge.alive は「<版> <起動番号> <時刻>」。起動番号は同じ bridge の間は変わらないこと。

    MOD は起動番号が変わったことで、切断に気づく前に bridge が再起動したと分かり、
    HELLO を送り直す（再起動で to_bridge.txt が空になり、前の HELLO は消えている）。
    """
    ipc = Ipc(str(tmp_path))
    first, second = _alive(ipc), _alive(ipc)
    assert first[0] == VERSION and len(first) == 3
    assert first[1] == second[1]
    assert abs(int(first[2]) - time.time()) < 5  # 時刻は最後（古い MOD は行末の数字を読む）


def test_boot_id_changes_when_the_bridge_restarts(tmp_path) -> None:
    first = _alive(Ipc(str(tmp_path)))
    time.sleep(0.01)
    assert _alive(Ipc(str(tmp_path)))[1] != first[1]
