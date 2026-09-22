"""セットアップのやり直しまわりの回帰テスト。

リポジトリルートから `python3 -m pytest bridge/test_wizard_rerun.py` で実行する。
"""

from __future__ import annotations

import copy
import logging
import os

import pytest

import i18n
import setup_wizard
from drg_bridge import DEFAULTS, build_config, check_relay_limit, load_dotenv
from setup_wizard import (
    LANGUAGE_SETTING_KEYS,
    language_settings,
    read_env_value,
    write_env,
)

CODES = [code for code, _ in i18n.LANGUAGES]
EXAMPLE = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                            "settings.example.ini"), encoding="utf-8").read()


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
        # None は「書かない（コメントに戻す）」なので、読むと空になる
        assert read_env_value(str(path), key) == (expected[key] or ""), key


def _load(path) -> dict:
    """その settings.ini だけを読んだときの設定。isolated の中で呼ぶ（環境変数を後で戻すため）。"""
    load_dotenv(str(path))
    return build_config()


@pytest.mark.parametrize("lang", [c for c in CODES if c != "zh-tw"])
def test_following_settings_are_not_pinned(lang) -> None:
    """「書かなければ追従する」2項目は書かない（中継の上限・訳さない言語）。"""
    values = language_settings(lang)
    assert values["DRGT_RELAY_MAX_LANGS"] is None
    assert values["DRGT_INCOMING_SKIP_LANGUAGES"] is None


def test_zh_tw_still_writes_skip_languages() -> None:
    """繁体字は言語判定で zh と見分けられないので、訳さない言語に zh を書く。"""
    assert language_settings("zh-tw")["DRGT_INCOMING_SKIP_LANGUAGES"] == "zh"


def test_changing_language_by_hand_after_setup(isolated) -> None:
    """日本語でセットアップしたあと README の手順で英語に直すと、日本語の発言が英語に訳されること。"""
    path = isolated / "settings.ini"
    path.write_text(EXAMPLE, encoding="utf-8")
    write_env(str(path), language_settings("ja"))
    write_env(str(path), {"DRGT_INCOMING_TARGET": "en", "DRGT_RELAY_TARGETS": "en,ja,ko,ru,zh"})
    cfg = _load(path)
    assert cfg["incoming"]["skip_languages"] == ["en"]
    assert cfg["relay"]["max_langs"] == 5


def test_rerun_fixes_lines_pinned_by_older_setup(isolated) -> None:
    """以前のセットアップが書いた2項目は、やり直せばコメントに戻ること。"""
    path = isolated / "settings.ini"
    path.write_text(EXAMPLE + "DRGT_INCOMING_SKIP_LANGUAGES=ja\nexport DRGT_RELAY_MAX_LANGS=4\n",
                    encoding="utf-8")
    write_env(str(path), language_settings("en"))
    text = path.read_text(encoding="utf-8")
    assert "#DRGT_INCOMING_SKIP_LANGUAGES=ja" in text
    assert "#export DRGT_RELAY_MAX_LANGS=4" in text
    cfg = _load(path)
    assert cfg["incoming"]["skip_languages"] == ["en"]
    assert cfg["relay"]["max_langs"] == len(cfg["relay"]["targets"])


def test_zh_tw_then_ja_comments_skip_languages_out(tmp_path) -> None:
    path = tmp_path / "settings.ini"
    path.write_text(EXAMPLE, encoding="utf-8")
    write_env(str(path), language_settings("zh-tw"))
    assert read_env_value(str(path), "DRGT_INCOMING_SKIP_LANGUAGES") == "zh"
    write_env(str(path), language_settings("ja"))
    assert read_env_value(str(path), "DRGT_INCOMING_SKIP_LANGUAGES") == ""


def test_max_langs_defaults_to_number_of_targets(clean_env) -> None:
    """DRGT_RELAY_MAX_LANGS を書いていなければ、中継先の数が上限になること。"""
    clean_env(DRGT_RELAY_TARGETS="zh-tw,ja,en,ko,zh")
    assert build_config()["relay"]["max_langs"] == 5


def test_explicit_max_langs_wins(clean_env) -> None:
    """明示した値はそのまま使うこと。"""
    clean_env(DRGT_RELAY_TARGETS="ja,en,ko,zh", DRGT_RELAY_MAX_LANGS="2")
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
