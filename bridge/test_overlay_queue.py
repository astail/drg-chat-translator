"""overlay_queue に読み手がいないときは溜め込まないことの回帰テスト。

リポジトリルートから `python3 -m pytest bridge/test_overlay_queue.py` で実行する。
"""

from __future__ import annotations

import copy
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from drg_bridge import DEFAULTS, Bridge  # noqa: E402


@pytest.fixture
def bridge(tmp_path):
    """API もキャッシュも使わない Bridge。IPC のファイルは tmp_path に置く。"""
    cfg = copy.deepcopy(DEFAULTS)
    cfg["cache"]["enabled"] = False
    cfg["cache"]["path"] = str(tmp_path / "cache.json")
    b = Bridge(cfg, str(tmp_path), fake=True)
    yield b
    b.stop()
    b.pool.shutdown(wait=False)


def _fill(b: Bridge) -> None:
    """overlay_queue に積む側の経路（受信・送信・トグル）をひととおり通す。"""
    b.handle(["TOGGLE", "on"])
    b._do_incoming("1", "Karl", "watch out, swarm incoming")
    b._do_outgoing("2", "回復お願いします")


def test_overlay_is_detached_by_default(bridge) -> None:
    """既定ではオーバーレイは繋がっていないこと。"""
    assert bridge.overlay_attached is False


def test_queue_does_not_grow_without_overlay(bridge) -> None:
    """オーバーレイが無いときは、何度翻訳してもキューが伸びないこと。"""
    for _ in range(20):
        _fill(bridge)
    assert bridge.overlay_queue.qsize() == 0


def test_queue_receives_lines_when_attached(bridge) -> None:
    """オーバーレイが繋がっているときは、これまでどおり積まれること。"""
    bridge.overlay_attached = True
    _fill(bridge)
    kinds = []
    while not bridge.overlay_queue.empty():
        kind, line = bridge.overlay_queue.get_nowait()
        assert line
        kinds.append(kind)
    assert kinds == ["in", "in", "out"]


def test_show_on_overlay_follows_the_flag(bridge) -> None:
    """show_on_overlay はフラグを見て捨てる／積むを切り替えること。"""
    bridge.show_on_overlay("in", "捨てられる行")
    assert bridge.overlay_queue.empty()

    bridge.overlay_attached = True
    bridge.show_on_overlay("in", "積まれる行")
    assert bridge.overlay_queue.get_nowait() == ("in", "積まれる行")

    bridge.overlay_attached = False
    bridge.show_on_overlay("out", "また捨てられる行")
    assert bridge.overlay_queue.empty()


def test_outbound_from_overlay_is_untouched(bridge) -> None:
    """オーバーレイから送る側のキューはフラグに関係なく使えること。"""
    bridge.outbound_from_overlay.put("こんにちは")
    assert bridge.outbound_from_overlay.get_nowait() == "こんにちは"
