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
from translate import TranslationError  # noqa: E402

SLOW = 4.0  # 翻訳にかかる時間。生存通知の間隔（1秒）より十分長くする


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
    # 生存通知は1秒ごと。ファイル時刻の反映が遅い環境もあるので、SLOW より十分短い値で見る
    assert worst < 2.5, f"生存通知が {worst:.1f} 秒止まった"


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
    """続けて打った文は、打った順に（それぞれ原文 → 訳の順で）送られること。"""
    slow_bridge.outbound_from_overlay.put("一つ目です")
    slow_bridge.outbound_from_overlay.put("二つ目です")
    deadline = time.time() + SLOW * 2 + 2
    while time.time() < deadline and len(_said(slow_bridge)) < 4:
        time.sleep(0.1)
    said = _said(slow_bridge)
    assert said[0] == "一つ目です" and said[2] == "二つ目です"
    assert "[en] 一つ目です" in said[1] and "[en] 二つ目です" in said[3]


@pytest.fixture
def bridge(tmp_path):
    cfg = copy.deepcopy(DEFAULTS)
    cfg["cache"]["enabled"] = False
    b = Bridge(cfg, str(tmp_path), fake=True)
    b.overlay_attached = True
    yield b
    b.pool.shutdown(wait=True)


def _shown(b: Bridge) -> list[tuple[str, str]]:
    out = []
    while not b.overlay_queue.empty():
        out.append(b.overlay_queue.get_nowait())
    return out


def test_overlay_sends_original_then_translation(bridge) -> None:
    """チャット欄から打ったときと同じく、原文を送ってから訳を2通目として送ること。"""
    bridge._do_overlay_outgoing("回復お願いします")
    said = _said(bridge)
    assert said[0] == "回復お願いします"
    assert said[1].startswith("[en] 回復お願いします")


@pytest.mark.parametrize("setting, value, text", [
    ("enabled", False, "回復お願いします"),        # 送信の翻訳を切っている
    ("source", "ja", "hello everyone"),             # 翻訳元の言語でない
    ("ignore_prefixes", ["/"], "/help これはコマンド"),  # 訳さない前置き
])
def test_overlay_follows_outgoing_settings(bridge, setting, value, text) -> None:
    """入力欄の文も、チャット欄と同じ設定で訳すかを決めること。訳さない文は原文だけ送る。"""
    bridge.cfg["outgoing"][setting] = value
    bridge._do_overlay_outgoing(text)
    assert _said(bridge) == [text]


def test_overlay_tells_when_translation_failed(bridge) -> None:
    """翻訳に失敗したら原文だけを送り、そのことをオーバーレイに出すこと（黙って消えない）。"""
    def fail(text, source, targets):
        raise TranslationError("down")

    bridge.translator.translate_multi = fail
    bridge._do_overlay_outgoing("回復お願いします")
    assert _said(bridge) == ["回復お願いします"]
    assert any(kind == "sys" for kind, _ in _shown(bridge))


def test_failed_translation_is_not_the_original_again(bridge) -> None:
    """原文を付ける設定でも、訳が1つも無ければ原文をもう一度送らないこと。"""
    def fail(text, source, targets):
        raise TranslationError("down")

    bridge.cfg["outgoing"]["include_source"] = True
    bridge.translator.translate_multi = fail
    assert bridge.translate_outgoing("回復お願いします") == ""
    bridge._do_overlay_outgoing("回復お願いします")
    assert _said(bridge) == ["回復お願いします"]
    assert any(kind == "sys" for kind, _ in _shown(bridge))


def test_include_source_still_puts_the_original_first(bridge) -> None:
    bridge.cfg["outgoing"]["include_source"] = True
    joined = bridge.translate_outgoing("回復お願いします")
    assert joined.startswith("回復お願いします / [en] 回復お願いします")
