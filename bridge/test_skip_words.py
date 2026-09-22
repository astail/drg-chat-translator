"""訳さない発言の扱いと、それを利用者に分かるように出すことのテスト。

- 用語集の「訳さない語」（r? / nt など）は API を呼ばず、表示も中継もしない
- 訳さなかった自分の発言も、理由つきで画面に出す（何も出ないと認識されなかったように見える）
- 同僚がいるホストでゲーム内に出さないのは設計どおりで、「失敗」とは出さない
- セットアップの直後でも、どの settings.ini を読んだかを出す

リポジトリルートから `python3 -m pytest bridge/test_skip_words.py` で実行する。
"""

from __future__ import annotations

import json
import logging
import os

import pytest

import drg_bridge
from i18n import t
from translate import Glossary


def _spy(b) -> list[list[str]]:
    calls: list[list[str]] = []
    real = b.translator.translate_multi

    def spy(text, source, targets):
        calls.append(list(targets))
        return real(text, source, targets)

    b.translator.translate_multi = spy
    real_single = b.translator.translate

    def spy_single(text, source, target):
        calls.append([target])
        return real_single(text, source, target)

    b.translator.translate = spy_single
    return calls


@pytest.mark.parametrize("text", ["gg", "GG!", "gg?", "GG!!", "ggs", "GGS", "GGs!", "gg wp", "GG WP!", "ggwp",
                                  "glhf", "r", "r?", "R?", "rdy?", "nt", "NT!"])
@pytest.mark.parametrize("host", [False, True])
def test_skip_words_are_not_translated_or_relayed(bridge, text, host) -> None:
    """同梱の用語集の「訳さない語」は、API を呼ばず、表示も中継もしないこと。"""
    calls = _spy(bridge)
    _, shown, relayed = bridge.translate_incoming(text, relay=host)
    assert (shown, relayed, calls) == ("", {}, [])


@pytest.mark.parametrize("text", ["bugs from the left side", "gg go again"])
def test_ordinary_short_words_are_still_translated(bridge, text) -> None:
    """用語集に無い語は、これまでどおり訳す（訳さない語を広げすぎていない。文の一部に gg があっても訳す）。"""
    calls = _spy(bridge)
    assert bridge.translate_incoming(text)[1] == f"[ja] {text}"
    assert calls


def test_empty_translation_for_one_language(tmp_path) -> None:
    """言語ごとの空文字も「訳さない語」として引けること（`or` で次の候補に流れない）。"""
    path = tmp_path / "glossary.json"
    path.write_text(json.dumps({"incoming": {"gg": {"ja": "", "*": "GG"}}, "outgoing": {}}),
                    encoding="utf-8")
    g = Glossary(str(path))
    assert g.lookup_incoming("gg", "ja") == ""
    assert g.skips_incoming("gg", "ja") and not g.skips_incoming("gg", "ko")


def test_skip_word_is_logged_on_screen_only(bridge, read_out, caplog) -> None:
    """訳さない語が届いたことは画面に出す（本文を含むので、ファイルには残さない印を付ける）。"""
    with caplog.at_level(logging.INFO, logger="drgtl"):
        bridge._do_incoming("1", "themuffin252", "r?", host=True)
    assert read_out(bridge)[-1][:2] == ["RES", "1"] and read_out(bridge)[-1][4] == ""
    records = [r for r in caplog.records if "themuffin252" in r.getMessage()]
    assert records and all(getattr(r, "chat", False) for r in records)


@pytest.mark.parametrize("text, reason_key", [
    ("GG", "b.out.skip.language"),       # 翻訳元（日本語）で打っていない
    ("あ", "b.out.skip.short"),
    ("/help これはコマンド", "b.out.skip.prefix"),
])
def test_untranslated_own_message_is_logged_with_reason(bridge, read_out, caplog,
                                                        text, reason_key) -> None:
    """訳さなかった自分の発言も、理由つきで画面に出すこと（何も出ないと認識されなかったように見える）。"""
    with caplog.at_level(logging.INFO, logger="drgtl"):
        bridge._do_outgoing("3", text)
    assert read_out(bridge)[-1] == ["RES", "3", "out", "", ""]
    reason = bridge.outgoing_skip_reason(text)
    expected = t(reason_key, lang="ja") if reason_key.endswith("language") else t(reason_key)
    assert reason == expected
    line = [r for r in caplog.records if text in r.getMessage()]
    assert line and reason in line[0].getMessage() and getattr(line[0], "chat", False)


def test_disabled_outgoing_reason(bridge) -> None:
    bridge.cfg["outgoing"]["enabled"] = False
    assert bridge.outgoing_skip_reason("回復お願いします") == t("b.out.skip.disabled")


def test_host_display_is_not_called_a_failure(bridge, caplog) -> None:
    """同僚がいるホストで出さないのは設計どおりなので、「失敗」とは出さないこと。"""
    with caplog.at_level(logging.INFO, logger="drgtl"):
        bridge.handle(["DISPLAY", "fail", "host"])
    assert t("b.display.host") in caplog.text
    assert bridge.ingame_display_ok is False  # オーバーレイ（auto）はこれを見て出す


def test_real_display_failure_is_still_a_failure(bridge, caplog) -> None:
    """理由の無い fail（以前の MOD も含む）は、これまでどおり失敗と出すこと。"""
    with caplog.at_level(logging.INFO, logger="drgtl"):
        bridge.handle(["DISPLAY", "fail"])
    assert t("b.display.failed") in caplog.text


def test_settings_path_is_logged_right_after_setup(isolated, caplog) -> None:
    """セットアップの直後（書いた値がもう環境変数にある）でも、どの settings.ini を読んだかを出すこと。"""
    ini = isolated / "settings.ini"
    ini.write_text("DRGT_PROVIDER=claude\nDRGT_UI_LANG=ja\n", encoding="utf-8")
    os.environ.update({"DRGT_PROVIDER": "claude", "DRGT_UI_LANG": "ja"})  # ウィザードが入れた状態
    with caplog.at_level(logging.INFO, logger="drgtl"):
        drg_bridge.load_config(str(ini))
    assert str(ini) in caplog.text


def test_load_dotenv_counts_every_setting_in_the_file(isolated) -> None:
    ini = isolated / "settings.ini"
    ini.write_text("# comment\nDRGT_PROVIDER=claude\n\nDRGT_UI_LANG=ja\n", encoding="utf-8")
    os.environ["DRGT_PROVIDER"] = "deepl"
    assert drg_bridge.load_dotenv(str(ini)) == 2
    assert os.environ["DRGT_PROVIDER"] == "deepl"  # すでにある値は上書きしない（これまでどおり）
