"""翻訳プロバイダが送る引数の回帰テスト（APIキー・ネットワーク不要）。

リポジトリルートから `python3 -m pytest bridge/test_provider_params.py` で実行する。
"""

from __future__ import annotations

import logging
import threading
from types import SimpleNamespace

import pytest

from translate import (
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


def _with(model: str, **opts) -> dict:
    return ClaudeProvider({"model": model, **opts})._build_params("system", "user", None)


@pytest.mark.parametrize("value", ["false", "False", "off", "0", "no", False])
@pytest.mark.parametrize("model", ["claude-opus-5", "claude-haiku-4-5"])
def test_fallback_can_be_turned_off(model, value) -> None:
    """settings.ini の文字列 "false" などで、フォールバックを止められること（bool("false") は真）。"""
    params = _with(model, refusal_fallback=value)
    assert "fallbacks" not in params and "betas" not in params


@pytest.mark.parametrize("value", ["true", "on", "1", "yes", True])
def test_fallback_can_be_forced_on(value) -> None:
    assert _with("claude-haiku-4-5", refusal_fallback=value)["fallbacks"] == "default"


@pytest.mark.parametrize("value", ["auto", "", None])
def test_fallback_auto_follows_the_model(value) -> None:
    assert "fallbacks" in _with("claude-opus-5", refusal_fallback=value)
    assert "fallbacks" not in _with("claude-haiku-4-5", refusal_fallback=value)


def test_unreadable_fallback_warns_and_uses_auto(caplog) -> None:
    with caplog.at_level(logging.WARNING, logger="drgtl"):
        params = _with("claude-haiku-4-5", refusal_fallback="maybe")
    assert "DRGT_CLAUDE_REFUSAL_FALLBACK" in caplog.text
    assert "fallbacks" not in params


def test_fallback_setting_from_settings_ini(monkeypatch) -> None:
    """build_config（settings.ini の読み込み）を通しても false が効くこと。"""
    from drg_bridge import build_config

    monkeypatch.setenv("DRGT_CLAUDE_REFUSAL_FALLBACK", "false")
    monkeypatch.setenv("DRGT_CLAUDE_MODEL", "claude-opus-5")
    params = ClaudeProvider(build_config()["providers"]["claude"])._build_params("s", "u", None)
    assert "fallbacks" not in params


@pytest.mark.parametrize("model, effort", [
    ("claude-sonnet-5", "hgh"),        # 書き間違い
    ("claude-opus-4-6", "xhigh"),      # 4.6 の世代は xhigh を受け付けない
    ("claude-sonnet-4-6", "xhigh"),
])
def test_unusable_effort_warns_and_uses_auto(model, effort, caplog) -> None:
    """モデルが受け付けない effort は、起動時に警告して auto（low）に戻すこと（毎回 400 にしない）。"""
    with caplog.at_level(logging.WARNING, logger="drgtl"):
        params = _with(model, effort=effort)
    assert "DRGT_CLAUDE_EFFORT" in caplog.text
    assert params["output_config"]["effort"] == "low"


@pytest.mark.parametrize("model, effort", [
    ("claude-opus-5", "max"), ("claude-opus-5", "xhigh"),
    ("claude-sonnet-5", "xhigh"), ("claude-opus-4-8", "max"), ("claude-opus-4-6", "max"),
])
def test_valid_effort_is_sent_as_written(model, effort) -> None:
    assert _with(model, effort=effort.upper())["output_config"]["effort"] == effort


@pytest.mark.parametrize("effort, thinking", [
    ("low", True), ("medium", True), ("high", True), ("xhigh", False), ("max", False),
])
def test_opus_5_disables_thinking_only_up_to_high(effort, thinking) -> None:
    """Opus 5 は effort が xhigh / max のとき thinking: disabled を 400 にするので、そのときは送らないこと。"""
    params = _with("claude-opus-5", effort=effort)
    assert ("thinking" in params) is thinking


@pytest.mark.parametrize("model", ["claude-sonnet-5", "claude-opus-4-8"])
def test_other_models_disable_thinking_at_any_effort(model) -> None:
    assert _with(model, effort="max")["thinking"] == {"type": "disabled"}


def test_effort_on_legacy_model_is_ignored_with_a_warning(caplog) -> None:
    with caplog.at_level(logging.WARNING, logger="drgtl"):
        params = _with("claude-haiku-4-5", effort="medium")
    assert "claude-haiku-4-5" in caplog.text
    assert "effort" not in params.get("output_config", {})


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


def test_failure_counter_is_thread_safe(tmp_path, caplog) -> None:
    """失敗の数え上げが、複数のワーカから同時に呼ばれても欠けないこと。"""
    # 5回目以降の失敗ごとに「30秒待機します」が出るので、8000回分の警告を取り込まない
    caplog.set_level(logging.ERROR, logger="drgtl.translate")
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


@pytest.mark.parametrize("model", ["claude-haiku-4-5", "claude-sonnet-5", "claude-opus-5",
                                   "claude-fable-5-1"])
def test_system_prompt_is_marked_for_caching(model) -> None:
    """システムプロンプトにキャッシュの印を付けること（Sonnet 5 / Opus 5 では続けて翻訳すると1割の料金）。"""
    p = ClaudeProvider({"model": model})
    system = p.system_prompt(None, ["ja"], False)
    params = p._build_params(system, "watch out", None)
    assert params["system"] == [
        {"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}
    ]
