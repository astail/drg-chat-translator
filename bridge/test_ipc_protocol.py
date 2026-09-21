"""IPC のやり取りで、bridge が要求に必ず返事をすることの回帰テスト。

リポジトリルートから `python3 -m pytest bridge/test_ipc_protocol.py` で実行する。
"""

from __future__ import annotations

import copy
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from drg_bridge import DEFAULTS, Bridge, decode_line  # noqa: E402


@pytest.fixture
def bridge(tmp_path):
    cfg = copy.deepcopy(DEFAULTS)
    cfg["cache"]["enabled"] = False
    b = Bridge(cfg, str(tmp_path), fake=True)
    yield b
    b.pool.shutdown(wait=True)


def _replies(b: Bridge, timeout: float = 3.0) -> list[list[str]]:
    """to_game.txt に書かれた行を返す。ワーカの書き込みを少し待つ。"""
    deadline = time.time() + timeout
    rows: list[list[str]] = []
    while time.time() < deadline:
        with open(b.ipc.p_out, encoding="utf-8") as f:
            rows = [decode_line(line.rstrip("\n")) for line in f if line.strip()]
        if rows:
            return rows
        time.sleep(0.05)
    return rows


@pytest.mark.parametrize("fields", [
    ["REQ", "7"],
    ["REQ", "7", "in"],
    ["REQ", "7", "in", "Karl"],
])
def test_malformed_req_gets_err(bridge, fields) -> None:
    """項目が足りない要求にも ERR で返事をすること（MOD 側が待ち続けないように）。"""
    bridge.handle(fields)
    rows = _replies(bridge)
    assert rows and rows[-1][0] == "ERR" and rows[-1][1] == "7"


def test_req_without_id_still_gets_err(bridge) -> None:
    """id すら無い要求にも返事はすること。"""
    bridge.handle(["REQ"])
    rows = _replies(bridge)
    assert rows and rows[-1][0] == "ERR"


def test_unknown_req_kind_gets_err(bridge) -> None:
    """知らない種別の要求にも ERR で返すこと（従来どおり）。"""
    bridge.handle(["REQ", "8", "what", "Karl", "hello"])
    rows = _replies(bridge)
    assert rows and rows[-1][:2] == ["ERR", "8"]


def test_valid_req_gets_res(bridge) -> None:
    """正しい要求には RES で返すこと（従来どおり）。"""
    bridge.handle(["REQ", "9", "in", "Karl", "watch out"])
    rows = _replies(bridge)
    assert rows and rows[-1][:3] == ["RES", "9", "in"]
