"""言語判定まわりの純関数のテスト。

リポジトリルートから `python3 -m pytest bridge/test_language.py` で実行する。
"""

from __future__ import annotations


import pytest

from translate import detect_language, is_translatable, is_written_in, same_phrase


@pytest.mark.parametrize("text, lang", [
    ("", "und"), ("123", "und"), ("!!!", "und"),
    ("hello", "en"), ("안녕", "ko"), ("こんにちは", "ja"), ("你好", "zh"), ("привет", "ru"),
    # かなが1文字でもあれば日本語（優先順位: かな > ハングル > 漢字 > キリル > ラテン）
    ("hello 안녕 こんにちは", "ja"),
    # 漢字だけの日本語は中国語と見分けられない（仕様。送信側は is_written_in で拾う）
    ("了解", "zh"),
])
def test_detect_language(text, lang) -> None:
    assert detect_language(text) == lang


def test_is_written_in() -> None:
    assert is_written_in("了解", "ja") is True        # 漢字だけでも日本語の発言として訳す
    assert is_written_in("hello", "ja") is False
    assert is_written_in("안녕하세요", "ko") is True
    # zh と zh-tw は文字では見分けられない（どちらも zh として扱う。仕様）
    assert is_written_in("你好世界", "zh-tw") is True
    assert is_written_in("你好世界", "zh") is True
    # 翻訳元を決めていないときは、判定できる言語なら何でも
    assert is_written_in("hello", "") is True
    assert is_written_in("!!!", "") is False


@pytest.mark.parametrize("text, ok", [
    ("", False), ("   ", False), ("123", False), ("!!!", False), ("https://x.com", False),
    ("gg", True), ("https://x.com look", True), ("了解", True),
])
def test_is_translatable(text, ok) -> None:
    assert is_translatable(text) is ok


def test_same_phrase_ignores_case_and_punctuation() -> None:
    assert same_phrase("Rock and Stone!", "rock and stone")
    assert same_phrase("gg", "gg!")
    assert not same_phrase("gg", "gl")
