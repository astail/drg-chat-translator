"""オーバーレイから打った文の送信が IPC のループを止めないことの回帰テスト。

リポジトリルートから `python3 -m pytest bridge/test_overlay_send.py` で実行する。
"""

from __future__ import annotations

import copy
import os
import sys
import threading
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from drg_bridge import DEFAULTS, Bridge, decode_line  # noqa: E402

SLOW = 2.5  # 翻訳にかかる時間。生存通知の間隔（1秒）より十分長くする


@pytest.fixture
def slow_bridge(tmp_path):
    """翻訳に SLOW 秒かかる Bridge。IPC のループを別スレッドで回す。"""
    cfg = copy.deepcopy(DEFAULTS)
    cfg["cache"]["enabled"] = False
    b = Bridge(cfg, str(tmp_path), fake=True)
    real = b.translator.translate_multi

    def slow(text, source, targets):
        time.sleep(SLOW)
        return real(text, source, targets)

    b.translator.translate_multi = slow
    worker = threading.Thread(target=b.run_loop, daemon=True)
    worker.start()
    time.sleep(0.3)
    yield b
    b.stop()
    worker.join(timeout=3)


def _said(b: Bridge) -> list[str]:
    """to_game.txt に書かれた SAY の本文を順に返す。"""
    with open(b.ipc.p_out, encoding="utf-8") as f:
        rows = [decode_line(line.rstrip("\n")) for line in f if line.strip()]
    return [r[1] for r in rows if r[0] == "SAY"]


def test_heartbeat_keeps_running_while_translating(slow_bridge) -> None:
    """翻訳を待っている間も bridge.alive の更新が止まらないこと。"""
    slow_bridge.outbound_from_overlay.put("回復お願いします")
    worst = 0.0
    deadline = time.time() + SLOW + 0.5
    while time.time() < deadline:
        time.sleep(0.1)
        worst = max(worst, time.time() - os.path.getmtime(slow_bridge.ipc.p_alive))
    assert worst < 1.6, f"生存通知が {worst:.1f} 秒止まった"


def test_incoming_is_handled_while_translating(slow_bridge) -> None:
    """オーバーレイの翻訳を待っている間も、ゲームからの要求を読み続けること。"""
    slow_bridge.outbound_from_overlay.put("回復お願いします")
    time.sleep(0.2)
    with open(slow_bridge.ipc.p_in, "a", encoding="utf-8") as f:
        f.write("HELLO\ttest\n")
    time.sleep(0.5)
    with open(slow_bridge.ipc.p_out, encoding="utf-8") as f:
        assert "HELLO\t" in f.read()


def test_overlay_messages_keep_their_order(slow_bridge) -> None:
    """続けて打った文は、打った順に送られること。"""
    slow_bridge.outbound_from_overlay.put("一つ目です")
    slow_bridge.outbound_from_overlay.put("二つ目です")
    deadline = time.time() + SLOW * 2 + 2
    while time.time() < deadline and len(_said(slow_bridge)) < 2:
        time.sleep(0.1)
    said = _said(slow_bridge)
    assert len(said) == 2
    assert "一つ目" in said[0] and "二つ目" in said[1]
