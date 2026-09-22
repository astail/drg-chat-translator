"""ログファイルの回帰テスト。発言の本文を残さないこと、APIキーを伏せること。

リポジトリルートから `python3 -m pytest bridge/test_log_file.py` で実行する。
"""

from __future__ import annotations

import logging
import os

import pytest

import drg_bridge
from drg_bridge import CHAT, setup_logging

KEY = "sk-ant-secret-key-1234567890"


@pytest.fixture
def log_file(isolated, monkeypatch):
    """ファイルにも書くログの設定。後始末（ハンドラを閉じて外す）は isolated が行う。"""
    monkeypatch.setenv("ANTHROPIC_API_KEY", KEY)
    path = isolated / "bridge.log"
    setup_logging("info", str(path))
    return path


def _read(path) -> str:
    for h in logging.getLogger().handlers:
        h.flush()
    return path.read_text(encoding="utf-8")


def test_warnings_reach_the_file(log_file) -> None:
    """警告やエラーは、窓を閉じたあとでも読めるようファイルに残ること。"""
    drg_bridge.log.warning("something went wrong")
    assert "something went wrong" in _read(log_file)


def test_chat_text_is_not_written(log_file) -> None:
    """発言の本文（受信・送信・中継の訳）はファイルに残さないこと。"""
    drg_bridge.log.info("in [%s] %s -> %s", "Karl", "secret plan", "ひみつの作戦", extra=CHAT)
    drg_bridge.log.info("connected")
    text = _read(log_file)
    assert "secret plan" not in text and "ひみつの作戦" not in text
    assert "connected" in text


def test_api_key_is_masked(log_file, capsys) -> None:
    """APIキーは画面にもファイルにも、そのままでは出さないこと。"""
    drg_bridge.log.warning("request failed with key %s", KEY)
    try:
        raise RuntimeError(f"auth error for {KEY}")
    except RuntimeError:
        drg_bridge.log.exception("boom")
    text = _read(log_file)
    assert KEY not in text
    assert "sk-a****" in text
    assert KEY not in capsys.readouterr().err


def test_bridge_chat_logs_are_marked(log_file, make_bridge) -> None:
    """実際の受信・送信の処理でも、本文がファイルに残らないこと。"""
    b = make_bridge(directory=log_file.parent / "ipc")
    b._do_incoming("1", "Karl", "hidden incoming words", host=True)
    b._do_outgoing("2", "ないしょの発言です")
    text = _read(log_file)
    assert "hidden incoming words" not in text
    assert "ないしょの発言です" not in text


def _run_main(tmp_path, ini_text: str) -> str:
    ini = tmp_path / "settings.ini"
    ini.write_text(ini_text, encoding="utf-8")
    ipc = tmp_path / "ipc"
    assert drg_bridge.main(["--fake", "--test", "hello", "--config", str(ini),
                            "--dir", str(ipc)]) == 0
    for h in logging.getLogger().handlers:
        h.flush()
    return (ipc / drg_bridge.LOG_FILE_NAME).read_text(encoding="utf-8")


def test_settings_messages_reach_the_file(isolated) -> None:
    """どの settings.ini を読んだか、書き間違いの警告が、ログファイルにも残ること。

    以前はログを設定する前に settings.ini を読んでいたので、どちらもファイルに残らなかった。
    """
    text = _run_main(isolated, "DRGT_UI_LANG=en\nDRGT_MAX_WORKERS=four\n")
    assert "Loaded settings:" in text
    assert "DRGT_MAX_WORKERS is not a whole number" in text


def test_key_from_settings_ini_is_masked(isolated) -> None:
    """ログの設定より後に settings.ini から読んだ APIキーも伏せること。"""
    key = "sk-ant-from-settings-ini-0123456789"
    _run_main(isolated, f"DRGT_UI_LANG=en\nANTHROPIC_API_KEY={key}\n")
    drg_bridge.log.warning("request failed with %s", key)
    path = isolated / "ipc" / drg_bridge.LOG_FILE_NAME
    for h in logging.getLogger().handlers:
        h.flush()
    text = path.read_text(encoding="utf-8")
    assert key not in text and "sk-a****" in text


def test_sdk_http_logs_are_not_written(log_file, capsys) -> None:
    """翻訳 SDK の HTTP ライブラリの INFO（翻訳のたびの "HTTP Request: ..."）は出さないこと。"""
    logging.getLogger("httpx").info('HTTP Request: POST https://api.anthropic.com/v1/messages')
    drg_bridge.log.info("our own info line")
    text = _read(log_file)
    assert "HTTP Request" not in text and "HTTP Request" not in capsys.readouterr().err
    assert "our own info line" in text


def test_log_level_applies_to_our_logs(log_file) -> None:
    drg_bridge.set_log_level("warning")
    drg_bridge.log.info("hidden info")
    drg_bridge.log.warning("shown warning")
    text = _read(log_file)
    assert "hidden info" not in text and "shown warning" in text
    drg_bridge.set_log_level("info")


def test_resolved_paths_use_one_separator() -> None:
    """用語集・キャッシュのパスは OS の区切りにそろえること（Windows で \\ と / が混ざらない）。"""
    path = drg_bridge.resolve_path("bridge/glossary.json")
    assert path == os.path.normpath(path)
