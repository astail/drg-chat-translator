"""自分の発言を訳すかどうかを bridge（settings.ini）だけで決めることのテスト。

リポジトリルートから `python3 -m pytest bridge/test_outgoing_policy.py` で実行する。
"""

from __future__ import annotations

import pytest


@pytest.mark.parametrize("text, wanted", [
    ("回復お願いします", True),
    ("了解", True),               # 漢字だけでも日本語として訳す
    ("あ", False),                # min_length（既定 2）未満
    ("/help これはコマンド", False),
    ("!ping 反応して", False),
    (".。。そうだね", False),
    ("  ", False),
    ("hello everyone", False),    # 翻訳元（既定 ja）でない
])
def test_defaults(bridge, text, wanted) -> None:
    assert bridge.outgoing_wanted(text) is wanted


def test_prefixes_and_length_come_from_settings(bridge) -> None:
    """前置きと最短の長さは settings.ini の値で変えられること。"""
    bridge.cfg["outgoing"]["ignore_prefixes"] = ["#"]
    bridge.cfg["outgoing"]["min_length"] = 5
    assert bridge.outgoing_wanted("/これは訳す発言です") is True
    assert bridge.outgoing_wanted("#これは訳さない発言") is False
    assert bridge.outgoing_wanted("短いです") is False


def test_disabled(bridge) -> None:
    bridge.cfg["outgoing"]["enabled"] = False
    assert bridge.outgoing_wanted("回復お願いします") is False
