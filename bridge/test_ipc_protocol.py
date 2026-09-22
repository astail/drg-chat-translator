"""IPC のやり取りで、bridge が要求に必ず返事をすることの回帰テスト。

リポジトリルートから `python3 -m pytest bridge/test_ipc_protocol.py` で実行する。
"""

from __future__ import annotations

import pytest


@pytest.mark.parametrize("fields", [
    ["REQ", "7"],
    ["REQ", "7", "in"],
    ["REQ", "7", "in", "Karl"],
])
def test_malformed_req_gets_err(bridge, fields, read_out) -> None:
    """項目が足りない要求にも ERR で返事をすること（MOD 側が待ち続けないように）。"""
    bridge.handle(fields)
    rows = read_out(bridge, timeout=3)
    assert rows and rows[-1][0] == "ERR" and rows[-1][1] == "7"


def test_req_without_id_still_gets_err(bridge, read_out) -> None:
    """id すら無い要求にも返事はすること。"""
    bridge.handle(["REQ"])
    rows = read_out(bridge, timeout=3)
    assert rows and rows[-1][0] == "ERR"


def test_unknown_req_kind_gets_err(bridge, read_out) -> None:
    """知らない種別の要求にも ERR で返すこと（従来どおり）。"""
    bridge.handle(["REQ", "8", "what", "Karl", "hello"])
    rows = read_out(bridge, timeout=3)
    assert rows and rows[-1][:2] == ["ERR", "8"]


def test_valid_req_gets_res(bridge, read_out) -> None:
    """正しい要求には RES で返すこと（従来どおり）。"""
    bridge.handle(["REQ", "9", "in", "Karl", "watch out"])
    rows = read_out(bridge, timeout=3)
    assert rows and rows[-1][:3] == ["RES", "9", "in"]
