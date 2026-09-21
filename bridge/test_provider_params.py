"""翻訳プロバイダが送る引数の回帰テスト（APIキー・ネットワーク不要）。

リポジトリルートから `python3 -m pytest bridge/test_provider_params.py` で実行する。
"""

from __future__ import annotations

import logging
import os
import sys
import threading
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from translate import (  # noqa: E402
    Cache,
    ClaudeProvider,
    Glossary,
    OpenAIProvider,
    StubProvider,
    Translator,
)


def _params(model: str) -> dict:
    return ClaudeProvider({"model": model})._build_params("system", "user", ["ja"])


@pytest.mark.parametrize("model", [
    "claude-haiku-4-5", "claude-sonnet-5", "claude-opus-5", "claude-opus-4-8",
    "claude-fable-5", "claude-fable-5-1", "claude-some-future-model",
])
def test_temperature_is_never_sent_to_claude(model) -> None:
    """Claude にはどのモデルにも temperature を送らないこと（0.5.7 でやめた）。"""
    assert "temperature" not in _params(model)


def test_legacy_model_gets_no_effort_or_thinking() -> None:
    params = _params("claude-haiku-4-5")
    assert "thinking" not in params
    assert "effort" not in params.get("output_config", {})


@pytest.mark.parametrize("model", ["claude-sonnet-5", "claude-opus-5", "claude-opus-4-8"])
def test_modern_model_disables_thinking_with_low_effort(model) -> None:
    params = _params(model)
    assert params["thinking"] == {"type": "disabled"}
    assert params["output_config"]["effort"] == "low"


@pytest.mark.parametrize("model", ["claude-fable-5", "claude-fable-5-1", "claude-mythos-5-1"])
def test_thinking_is_omitted_where_it_cannot_be_disabled(model) -> None:
    """Fable / Mythos は thinking を送ると 400 になるので、送らないこと（effort は送る）。"""
    params = _params(model)
    assert "thinking" not in params
    assert params["output_config"]["effort"] == "low"


@pytest.mark.parametrize("model", ["claude-opus-5", "claude-fable-5-1"])
def test_fallbacks_are_requested(model) -> None:
    params = _params(model)
    assert params["betas"] == ["server-side-fallback-2026-07-01"]
    assert params["fallbacks"] == "default"


def test_unknown_model_warns_once(caplog) -> None:
    """知らないモデルは旧世代として扱い、最初の1回だけ警告すること。"""
    p = ClaudeProvider({"model": "claude-some-future-model"})
    with caplog.at_level(logging.WARNING, logger="drgtl"):
        first = p._build_params("s", "u", None)
        p._build_params("s", "u", None)
    assert caplog.text.count("claude-some-future-model") == 1
    assert "thinking" not in first


class _Rejected(Exception):
    status_code = 400


class _FakeCompletions:
    def __init__(self, reject: list[str]):
        self.reject = reject
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        for name in self.reject:
            if name in kwargs:
                other = "max_completion_tokens" if name == "max_tokens" else name
                raise _Rejected(f"Unsupported parameter: '{name}'. Use '{other}' instead.")
        msg = SimpleNamespace(content='{"ja": "こんにちは"}')
        return SimpleNamespace(choices=[SimpleNamespace(message=msg, finish_reason="stop")])


def _openai(reject: list[str]) -> tuple[OpenAIProvider, _FakeCompletions]:
    p = OpenAIProvider({"model": "some-reasoning-model", "api_key": "sk-test"})
    fake = _FakeCompletions(reject)
    p._client = SimpleNamespace(chat=SimpleNamespace(completions=fake))
    return p, fake


def test_openai_adapts_once_and_remembers() -> None:
    """断られた引数を差し替えて通したら、次からは最初からその組み合わせで送ること。"""
    p, fake = _openai(["max_tokens", "temperature"])
    p._complete("system", "hello", None)
    first_round = len(fake.calls)
    assert first_round == 3
    p._complete("system", "hello again", None)
    assert len(fake.calls) == first_round + 1
    last = fake.calls[-1]
    assert "max_tokens" not in last and "temperature" not in last
    assert last["max_completion_tokens"] == p.max_tokens


def test_openai_does_not_retry_other_errors() -> None:
    """引数と関係のない失敗は、差し替えて送り直さないこと。"""
    p, fake = _openai([])
    fake.create = lambda **k: (_ for _ in ()).throw(RuntimeError("connection reset"))
    with pytest.raises(Exception, match="connection reset"):
        p._complete("system", "hello", None)


def test_failure_counter_is_thread_safe(tmp_path) -> None:
    """失敗の数え上げが、複数のワーカから同時に呼ばれても欠けないこと。"""
    tr = Translator(StubProvider({}), Cache(str(tmp_path / "c.json"), enabled=False), Glossary(None))

    def hammer():
        for _ in range(2000):
            tr._note_failure()

    threads = [threading.Thread(target=hammer) for _ in range(4)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    assert tr._fail_streak == 8000
    tr._note_success()
    assert tr._fail_streak == 0
