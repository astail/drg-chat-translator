"""ログファイルの回帰テスト。発言の本文を残さないこと、APIキーを伏せること。

リポジトリルートから `python3 -m pytest bridge/test_log_file.py` で実行する。
"""

from __future__ import annotations

import copy
import logging
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import drg_bridge  # noqa: E402
from drg_bridge import CHAT, DEFAULTS, Bridge, setup_logging  # noqa: E402

KEY = "sk-ant-secret-key-1234567890"


@pytest.fixture
def log_file(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", KEY)
    path = tmp_path / "bridge.log"
    setup_logging("info", str(path))
    yield path
    logging.getLogger().handlers.clear()


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


def test_bridge_chat_logs_are_marked(tmp_path, log_file) -> None:
    """実際の受信・送信の処理でも、本文がファイルに残らないこと。"""
    cfg = copy.deepcopy(DEFAULTS)
    cfg["cache"]["enabled"] = False
    b = Bridge(cfg, str(tmp_path / "ipc"), fake=True)
    try:
        b._do_incoming("1", "Karl", "hidden incoming words", host=True)
        b._do_outgoing("2", "ないしょの発言です")
    finally:
        b.pool.shutdown(wait=True)
    text = _read(log_file)
    assert "hidden incoming words" not in text
    assert "ないしょの発言です" not in text
