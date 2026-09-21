"""LLM プロバイダの応答の扱いと、翻訳のまとめ方のテスト（APIキー不要）。

TESTING.md に「スタブで8項目を検証した」と書いていた内容を、再現できる形にしたもの。
リポジトリルートから `python3 -m pytest bridge/test_llm_logic.py` で実行する。
"""

from __future__ import annotations

import json
import os
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from translate import (  # noqa: E402
    Cache,
    ClaudeProvider,
    Glossary,
    LLMProvider,
    TranslationError,
    Translator,
)


class FakeLLM(LLMProvider):
    """_complete の返事を決め打ちにした LLM。呼ばれた回数と頼まれた言語を覚える。"""

    name = "fake"

    def __init__(self, reply=None):
        super().__init__({"model": "m"})
        self.reply = reply
        self.calls: list[list[str] | None] = []

    def _complete(self, system, user, json_targets):
        self.calls.append(json_targets)
        if self.reply is not None:
            return self.reply
        if json_targets is None:
            return f"<one>{user}"
        return json.dumps({t: f"<{t}>{user}" for t in json_targets})


def test_many_languages_in_one_call() -> None:
    """複数の言語への訳は、1回の呼び出しにまとめること。"""
    p = FakeLLM()
    out = p.translate_multi("hello", None, ["ja", "ko", "zh"])
    assert len(p.calls) == 1
    assert out == {"ja": "<ja>hello", "ko": "<ko>hello", "zh": "<zh>hello"}


def test_json_in_code_fence_is_parsed() -> None:
    """```json のフェンスで囲まれた応答も読めること。"""
    p = FakeLLM('```json\n{"ja": "やあ", "en": " hi "}\n```')
    assert p.translate_multi("hey", None, ["ja", "en"]) == {"ja": "やあ", "en": "hi"}


@pytest.mark.parametrize("raw, clean", [
    ('"hi"', "hi"), ("「こんにちは」", "こんにちは"), ("『やあ』", "やあ"),
    ('"unclosed', '"unclosed'), ("  plain  ", "plain"),
])
def test_quotes_are_stripped(raw, clean) -> None:
    """訳の前後に付いてきた引用符だけを外すこと（片側だけなら外さない）。"""
    assert LLMProvider._clean(raw) == clean


def test_missing_language_is_left_out() -> None:
    """応答に無い言語・空の値は、結果に含めないこと。"""
    p = FakeLLM('{"ja": "やあ", "ko": "  "}')
    assert p.translate_multi("hey", None, ["ja", "ko", "zh"]) == {"ja": "やあ"}


@pytest.mark.parametrize("reply", ["not json at all", "[1, 2, 3]"])
def test_broken_reply_is_an_error(reply) -> None:
    """JSON でない・オブジェクトでない応答は TranslationError にすること。"""
    with pytest.raises(TranslationError):
        FakeLLM(reply).translate_multi("hey", None, ["ja", "ko"])


def test_cached_languages_are_not_asked_again(tmp_path) -> None:
    """キャッシュ済みの言語は問い合わせず、足りない言語だけを頼むこと。"""
    p = FakeLLM()
    tr = Translator(p, Cache(str(tmp_path / "c.json")), Glossary(None))
    tr.translate_multi("hello", None, ["ja", "ko"])
    out = tr.translate_multi("hello", None, ["ja", "ko", "zh"])
    # 2回目は zh だけを頼む（1言語なので JSON ではない単発の呼び出しになる）
    assert p.calls == [["ja", "ko"], None]
    assert out == {"ja": "<ja>hello", "ko": "<ko>hello", "zh": "<one>hello"}


def _claude_with(resp) -> ClaudeProvider:
    p = ClaudeProvider({"model": "claude-haiku-4-5", "api_key": "sk-test"})
    create = lambda **kwargs: resp  # noqa: E731
    p._client = SimpleNamespace(messages=SimpleNamespace(create=create),
                                beta=SimpleNamespace(messages=SimpleNamespace(create=create)))
    return p


def test_claude_refusal_is_an_error() -> None:
    """翻訳を断られたら（stop_reason=refusal）、訳が空のまま進まずエラーにすること。"""
    resp = SimpleNamespace(stop_reason="refusal", stop_details=SimpleNamespace(category="cyber"),
                           content=[])
    with pytest.raises(TranslationError):
        _claude_with(resp).translate("hello", None, "ja")


def test_claude_text_blocks_are_joined() -> None:
    resp = SimpleNamespace(stop_reason="end_turn", stop_details=None,
                           content=[SimpleNamespace(type="text", text="こん"),
                                    SimpleNamespace(type="text", text="にちは")])
    assert _claude_with(resp).translate("hello", None, "ja")[0] == "こんにちは"
