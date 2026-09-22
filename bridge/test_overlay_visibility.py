"""オーバーレイの窓を出すかどうかの決まりのテスト。

リポジトリルートから `python3 -m pytest bridge/test_overlay_visibility.py` で実行する。
"""

from __future__ import annotations


import pytest

pytest.importorskip("tkinter")

from overlay import should_show


def test_dismissed_window_stays_hidden_until_next_translation() -> None:
    """✕ / Esc で隠したら、always でも次の翻訳が届くまで出さないこと（bridge は止めない）。"""
    assert should_show("always", None, 12, 0, False, dismissed=True) is False
    assert should_show("auto", False, 12, 0, True, dismissed=True) is False
    assert should_show("always", None, 12, 0, False, dismissed=False) is True


@pytest.mark.parametrize("display_ok, idle, busy, want", [
    (True, 0, False, False),     # ゲーム内に出せているなら出さない
    (False, 3, False, True),     # 出せていない・最後の翻訳から間もない
    (None, 30, False, False),    # 最後の翻訳から hide_after を過ぎた
    (False, 30, True, True),     # 入力欄を使っている間は引っ込めない
])
def test_auto_mode(display_ok, idle, busy, want) -> None:
    assert should_show("auto", display_ok, 12, idle, busy, dismissed=False) is want


def test_off_and_no_hide() -> None:
    assert should_show("off", False, 12, 0, False, dismissed=False) is False
    assert should_show("auto", False, 0, 999, False, dismissed=False) is True
