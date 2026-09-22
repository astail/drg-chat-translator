"""--fake / --selftest が利用者の環境を汚さないことの回帰テスト。

リポジトリルートから `python3 -m pytest bridge/test_selftest_isolation.py` で実行する。
"""

from __future__ import annotations

import copy
import logging
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import drg_bridge  # noqa: E402
import i18n  # noqa: E402
from drg_bridge import DEFAULTS, Bridge  # noqa: E402


def test_fake_does_not_write_cache(tmp_path) -> None:
    """--fake の目印つきの訳は、キャッシュが有効でも書き出さないこと。"""
    cfg = copy.deepcopy(DEFAULTS)
    cfg["cache"]["enabled"] = True
    cfg["cache"]["path"] = str(tmp_path / "cache.json")
    b = Bridge(cfg, str(tmp_path / "ipc"), fake=True)
    try:
        b.translate_outgoing("回復お願いします")
        b.cache.maybe_save(force=True)
    finally:
        b.pool.shutdown(wait=True)
    assert not (tmp_path / "cache.json").exists()


def test_selftest_says_when_sdk_check_is_skipped(tmp_path, monkeypatch, capsys) -> None:
    """anthropic が無いときは、引数の確認を省いたことを出力すること（PASS のまま）。"""
    monkeypatch.setitem(sys.modules, "anthropic", None)  # import すると ImportError になる
    cfg = copy.deepcopy(DEFAULTS)
    cfg["cache"]["enabled"] = False
    b = Bridge(cfg, str(tmp_path / "ipc"), fake=True)
    assert drg_bridge.run_selftest(b) == 0
    out = capsys.readouterr().out
    assert "anthropic is not installed" in out
    assert "--- PASS ---" in out


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    """main() を走らせても、環境変数・表示言語・ログの設定がほかのテストに残らないようにする。"""
    clean = {k: v for k, v in os.environ.items()
             if not k.startswith(("DRGT_",) + drg_bridge.SECRET_ENV_NAMES)}
    monkeypatch.setattr(os, "environ", clean)
    monkeypatch.setattr(i18n, "_lang", i18n._lang)
    yield tmp_path
    root = logging.getLogger()
    for h in list(root.handlers):
        h.close()
        root.removeHandler(h)
    drg_bridge.log.setLevel(logging.NOTSET)


def _main(tmp_path, settings: str, *args: str) -> int:
    ini = tmp_path / "settings.ini"
    ini.write_text(settings, encoding="utf-8")
    return drg_bridge.main(["--fake", "--config", str(ini), "--dir", str(tmp_path / "ipc"), *args])


@pytest.mark.parametrize("settings", [
    "DRGT_INCOMING_TARGET=en\n",          # 英語で読む人
    "DRGT_OUTGOING_SOURCE=auto\n",        # 翻訳元を決めない人
    "DRGT_OUTGOING_SOURCE=en\nDRGT_INCOMING_TARGET=en\n",
])
def test_selftest_does_not_depend_on_the_users_languages(isolated, capsys, settings) -> None:
    """--selftest の合否は既定の設定が前提なので、利用者の言語の設定では FAIL しないこと。"""
    assert _main(isolated, settings, "--selftest") == 0
    assert "--- PASS ---" in capsys.readouterr().out


def test_defaults_flag_ignores_languages_in_settings(isolated, capsys) -> None:
    """--defaults なら settings.ini の言語を使わない（モックのテスト用の bridge）。"""
    assert _main(isolated, "DRGT_INCOMING_TARGET=en\n", "--defaults", "--test",
                 "bugs from the left side") == 0
    assert "incoming    : [ja] bugs from the left side" in capsys.readouterr().out


def test_defaults_keep_the_translation_service() -> None:
    """既定に戻すのは言語などで、翻訳サービスの設定（provider・APIキー・待ち時間など）は残すこと。"""
    cfg = copy.deepcopy(DEFAULTS)
    cfg["provider"] = "claude"
    cfg["providers"]["claude"]["api_key"] = "sk-ant-kept"
    cfg["incoming"]["target"] = "en"
    cfg["network"]["llm_timeout_sec"] = 60.0
    out = drg_bridge.with_default_settings(cfg)
    assert out["provider"] == "claude"
    assert out["providers"]["claude"]["api_key"] == "sk-ant-kept"
    assert out["network"]["llm_timeout_sec"] == 60.0
    assert out["incoming"]["target"] == DEFAULTS["incoming"]["target"]


def test_test_shows_both_directions_with_auto_source(isolated, capsys) -> None:
    """翻訳元が auto のとき、--test は送信の訳と受信の訳の両方を出すこと。"""
    assert _main(isolated, "DRGT_OUTGOING_SOURCE=auto\n", "--test", "watch out, swarm incoming") == 0
    out = capsys.readouterr().out
    assert "outgoing    :" in out and "incoming    : [ja]" in out


def test_test_with_fixed_source_shows_one_direction(isolated, capsys) -> None:
    """翻訳元を決めているときは、これまでどおり片方だけ出すこと。"""
    assert _main(isolated, "", "--test", "回復お願いします") == 0
    out = capsys.readouterr().out
    assert "outgoing    :" in out and "incoming    :" not in out
