"""セットアップのやり直しまわりの回帰テスト。

リポジトリルートから `python3 -m pytest bridge/test_wizard_rerun.py` で実行する。
"""

from __future__ import annotations

import copy
import logging
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import i18n  # noqa: E402
import setup_wizard  # noqa: E402
from drg_bridge import DEFAULTS, build_config, check_relay_limit  # noqa: E402
from setup_wizard import (  # noqa: E402
    LANGUAGE_SETTING_KEYS,
    language_settings,
    read_env_value,
    write_env,
)

CODES = [code for code, _ in i18n.LANGUAGES]


@pytest.mark.parametrize("lang", CODES)
def test_language_settings_returns_every_key(lang) -> None:
    """どの言語でも、言語から決まる設定を過不足なく全部返すこと（条件つきで省かない）。"""
    assert set(language_settings(lang)) == set(LANGUAGE_SETTING_KEYS)


@pytest.mark.parametrize("first", CODES)
@pytest.mark.parametrize("second", CODES)
def test_rerun_leaves_nothing_from_previous_language(tmp_path, first, second) -> None:
    """別の言語でやり直したら、言語まわりの設定がすべて新しい言語のものになること。"""
    path = tmp_path / "settings.ini"
    path.write_text("# comment\n", encoding="utf-8")
    write_env(str(path), language_settings(first))
    write_env(str(path), language_settings(second))
    expected = language_settings(second)
    for key in LANGUAGE_SETTING_KEYS:
        assert read_env_value(str(path), key) == expected[key], key


def _env(monkeypatch, **values) -> None:
    for key in [k for k in os.environ if k.startswith("DRGT_")]:
        monkeypatch.delenv(key, raising=False)
    for key, value in values.items():
        monkeypatch.setenv(key, value)


def test_max_langs_defaults_to_number_of_targets(monkeypatch) -> None:
    """DRGT_RELAY_MAX_LANGS を書いていなければ、中継先の数が上限になること。"""
    _env(monkeypatch, DRGT_RELAY_TARGETS="zh-tw,ja,en,ko,zh")
    assert build_config()["relay"]["max_langs"] == 5


def test_explicit_max_langs_wins(monkeypatch) -> None:
    """明示した値はそのまま使うこと。"""
    _env(monkeypatch, DRGT_RELAY_TARGETS="ja,en,ko,zh", DRGT_RELAY_MAX_LANGS="2")
    assert build_config()["relay"]["max_langs"] == 2


def test_too_small_limit_is_warned(caplog) -> None:
    """上限が中継先の数より小さければ、落ちる言語を起動時に知らせること。"""
    cfg = copy.deepcopy(DEFAULTS)
    cfg["relay"]["targets"] = ["zh-tw", "ja", "en", "ko", "zh"]
    cfg["relay"]["max_langs"] = 4
    with caplog.at_level(logging.WARNING, logger="drgtl"):
        check_relay_limit(cfg)
    assert "DRGT_RELAY_MAX_LANGS" in caplog.text and "zh" in caplog.text


def test_enough_limit_is_quiet(caplog) -> None:
    cfg = copy.deepcopy(DEFAULTS)
    with caplog.at_level(logging.WARNING, logger="drgtl"):
        check_relay_limit(cfg)
    assert caplog.text == ""


def test_setup_offers_key_saved_in_settings(tmp_path, monkeypatch) -> None:
    """やり直しのとき、settings.ini に保存済みの APIキーを使い回せること。"""
    path = tmp_path / "settings.ini"
    path.write_text("#ANTHROPIC_API_KEY=\nANTHROPIC_API_KEY=sk-ant-saved-0123456789\n",
                    encoding="utf-8")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(setup_wizard, "choose_provider",
                        lambda: ("claude", "Claude", "ANTHROPIC_API_KEY", "https://example"))
    asked = []
    monkeypatch.setattr(setup_wizard, "ask_yes",
                        lambda prompt, default=True: asked.append(prompt) or False)
    monkeypatch.setattr(setup_wizard, "ask",
                        lambda *a, **k: pytest.fail("should not ask for the key again"))
    assert setup_wizard.configure(str(path), str(path)) == ("claude", "ANTHROPIC_API_KEY")
    assert asked, "saved key was not offered for reuse"
    text = path.read_text(encoding="utf-8")
    assert "ANTHROPIC_API_KEY=sk-ant-saved-0123456789" in text
    assert "DRGT_PROVIDER=claude" in text
