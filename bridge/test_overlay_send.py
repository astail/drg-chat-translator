"""オーバーレイから打った文の送信が IPC のループを止めないことの回帰テスト。

リポジトリルートから `python3 -m pytest bridge/test_overlay_send.py` で実行する。
"""

from __future__ import annotations

import os
import threading
import time

import pytest

from drg_bridge import Bridge
from translate import TranslationError


def _wait_for(cond, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if cond():
            return True
        time.sleep(0.05)
    return bool(cond())


@pytest.fixture
def gated_bridge(make_bridge):
    """翻訳が gate を開けるまで止まる Bridge。IPC のループを別スレッドで回す。

    以前は翻訳に4秒の sleep を入れていて、テスト全体の時間の大半を使っていた。
    止めておく長さはテストが決め、確かめ終わったら gate を開ける。
    """
    b = make_bridge()
    gate = threading.Event()
    real = b.translator.translate_multi

    def gated(text, source, targets):
        gate.wait(10)
        return real(text, source, targets)

    b.translator.translate_multi = gated
    worker = threading.Thread(target=b.run_loop, daemon=True)
    worker.start()
    assert _wait_for(lambda: os.path.exists(b.ipc.p_alive))
    yield b, gate
    gate.set()
    b.stop()
    worker.join(timeout=3)


@pytest.fixture
def bridge(make_bridge):
    b = make_bridge()
    b.overlay_attached = True
    return b


def _said(b: Bridge) -> list[str]:
    """to_game.txt に書かれた SAY の本文を順に返す。"""
    with open(b.ipc.p_out, encoding="utf-8") as f:
        return [line.rstrip("\n").split("\t", 1)[1] for line in f if line.startswith("SAY\t")]


def _alive_time(b: Bridge) -> int:
    """bridge.alive に書かれた時刻（書きかけで読めなければ -1）。"""
    try:
        with open(b.ipc.p_alive, encoding="utf-8") as f:
            return int(f.read().split()[-1])
    except (OSError, ValueError, IndexError):
        return -1


def test_heartbeat_keeps_running_while_translating(gated_bridge) -> None:
    """翻訳を待っている間も bridge.alive の更新が止まらないこと。"""
    b, _gate = gated_bridge
    b.outbound_from_overlay.put("回復お願いします")
    assert _wait_for(lambda: _alive_time(b) >= 0)
    start = _alive_time(b)
    # 生存通知は1秒ごと。翻訳が止まっている間に、書かれる時刻が進むこと
    assert _wait_for(lambda: _alive_time(b) > start, timeout=3), "翻訳を待つ間に生存通知が止まった"


def test_incoming_is_handled_while_translating(gated_bridge) -> None:
    """オーバーレイの翻訳を待っている間も、ゲームからの要求を読み続けること。"""
    b, _gate = gated_bridge
    b.outbound_from_overlay.put("回復お願いします")
    assert _wait_for(lambda: _said(b) == ["回復お願いします"])  # 原文を送り、訳の途中で止まっている
    with open(b.ipc.p_in, "a", encoding="utf-8") as f:
        f.write("HELLO\ttest\n")

    def replied() -> bool:
        with open(b.ipc.p_out, encoding="utf-8") as f:
            return "HELLO\t" in f.read()

    assert _wait_for(replied, timeout=3)


def test_overlay_messages_keep_their_order(gated_bridge) -> None:
    """続けて打った文は、打った順に（それぞれ原文 → 訳の順で）送られること。"""
    b, gate = gated_bridge
    b.outbound_from_overlay.put("一つ目です")
    b.outbound_from_overlay.put("二つ目です")
    gate.set()
    assert _wait_for(lambda: len(_said(b)) >= 4)
    said = _said(b)
    assert said[0] == "一つ目です" and said[2] == "二つ目です"
    assert "[en] 一つ目です" in said[1] and "[en] 二つ目です" in said[3]


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
