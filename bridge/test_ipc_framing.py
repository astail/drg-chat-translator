"""IPC の行フレーミングまわりの回帰テスト。

リポジトリルートから `python3 -m pytest bridge/test_ipc_framing.py` で実行する。
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from drg_bridge import Ipc, decode_line, encode_line, esc, unesc  # noqa: E402

FIELDS = ("REQ", "1", "in", "Karl", "こんにちは")
PAYLOAD = encode_line(*FIELDS).encode("utf-8")


def _append(ipc: Ipc, data: bytes) -> None:
    """Lua 側の書き込みを模して to_bridge.txt にバイト列を追記する。"""
    with open(ipc.p_in, "ab") as f:
        f.write(data)


@pytest.mark.parametrize("cut", range(1, len(PAYLOAD)))
def test_read_lines_split_mid_character(tmp_path, cut: int) -> None:
    """どの位置で分割して届いてもマルチバイト文字が壊れないこと。"""
    ipc = Ipc(str(tmp_path))
    _append(ipc, PAYLOAD[:cut])
    first = ipc.read_lines()
    _append(ipc, PAYLOAD[cut:])
    second = ipc.read_lines()
    assert first + second == [list(FIELDS)]


def test_read_lines_holds_incomplete_line(tmp_path) -> None:
    """改行が来るまでは行を返さず、次の読み出しに持ち越すこと。"""
    ipc = Ipc(str(tmp_path))
    _append(ipc, PAYLOAD[:-1])
    assert ipc.read_lines() == []
    _append(ipc, PAYLOAD[-1:])
    assert ipc.read_lines() == [list(FIELDS)]


def test_read_lines_multiple_lines_at_once(tmp_path) -> None:
    """1回の読み出しで複数行が届いても順番どおりに返すこと。"""
    ipc = Ipc(str(tmp_path))
    second = ("RES", "2", "ja", "Bosco", "やあ、相棒")
    _append(ipc, PAYLOAD + encode_line(*second).encode("utf-8"))
    assert ipc.read_lines() == [list(FIELDS), list(second)]


def test_read_lines_resets_when_file_truncated(tmp_path) -> None:
    """ファイルが切り詰められたら（Lua 側と同じく）読み直すこと。

    半端なバイト列を持ち越した状態で切り詰められても、次の内容と混ざらない。
    """
    short = ("ACK", "9")
    ipc = Ipc(str(tmp_path))
    _append(ipc, PAYLOAD[:-3])  # 末尾のマルチバイト文字が欠けた状態
    assert ipc.read_lines() == []
    with open(ipc.p_in, "wb"):
        pass
    _append(ipc, encode_line(*short).encode("utf-8"))
    assert ipc.read_lines() == [list(short)]


@pytest.mark.parametrize(
    "value",
    [
        "",
        "plain",
        "タブ\tあり",
        "改行\nあり",
        "復帰\rあり",
        "バックスラッシュ\\あり",
        "\\t は文字列としての \\t",
        "\\",
        "\\\\n",
        "混在\t\\\r\n終わり",
    ],
)
def test_esc_unesc_roundtrip(value: str) -> None:
    """esc した文字列は unesc で元に戻り、区切り文字を含まないこと。"""
    escaped = esc(value)
    assert "\t" not in escaped
    assert "\n" not in escaped
    assert "\r" not in escaped
    assert unesc(escaped) == value


def test_encode_decode_line_roundtrip() -> None:
    """タブ・改行・バックスラッシュを含むフィールドも欠けずに往復すること。"""
    fields = ["REQ", "7", "ja", "Karl\tJr.", "1行目\n2行目\\末尾"]
    line = encode_line(*fields)
    assert line.endswith("\n")
    assert line.count("\n") == 1
    assert decode_line(line.rstrip("\n")) == fields


def test_encode_decode_line_through_ipc(tmp_path) -> None:
    """エスケープを含む行が IPC 経由でもそのまま復元されること。"""
    fields = ["REQ", "7", "ja", "Karl\tJr.", "1行目\n2行目\\末尾"]
    ipc = Ipc(str(tmp_path))
    _append(ipc, encode_line(*fields).encode("utf-8"))
    assert ipc.read_lines() == [fields]
