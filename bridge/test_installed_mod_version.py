"""ゲームフォルダの MOD の版を読むこと・ゲームが動いているかを調べることの回帰テスト。

リポジトリルートから `python3 -m pytest bridge/test_installed_mod_version.py` で実行する。
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

import setup_wizard
from setup_wizard import MOD_NAME, install_mod, installed_mod_version

REPO = Path(__file__).resolve().parent.parent


@pytest.fixture
def game(tmp_path):
    mods = tmp_path / "game" / "FSD" / "Binaries" / "Win64" / "Mods"
    mods.mkdir(parents=True)
    return tmp_path / "game", mods


def _put_mod(mods, text: str) -> None:
    scripts = mods / MOD_NAME / "Scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    (scripts / "main.lua").write_text(text, encoding="utf-8")


def test_reads_mod_version(game) -> None:
    game_dir, mods = game
    _put_mod(mods, '-- head\nlocal Cfg = require("config")\n\nlocal MOD_VERSION = "1.2.3"\n')
    assert installed_mod_version(str(game_dir)) == "1.2.3"


def test_bundled_mod_matches_the_exe(monkeypatch) -> None:
    """同梱の main.lua の書き方が変わって、版を読めなくなっていないこと。"""
    from drg_bridge import VERSION
    monkeypatch.setattr(setup_wizard, "existing_mods_dir", lambda game: str(REPO / "mod"))
    assert installed_mod_version("unused") == VERSION


@pytest.mark.parametrize("text", [None, "-- no version here\n"])
def test_unreadable_mod_is_none(game, text) -> None:
    game_dir, mods = game
    if text is not None:
        _put_mod(mods, text)
    assert installed_mod_version(str(game_dir)) is None


def test_no_mods_folder_is_none(tmp_path) -> None:
    assert installed_mod_version(str(tmp_path)) is None


def _tasklist(monkeypatch, stdout: str | None = None, exc: Exception | None = None) -> None:
    def run(*args, **kwargs):
        if exc:
            raise exc
        return subprocess.CompletedProcess(args, 0, stdout=stdout, stderr="")

    monkeypatch.setattr(setup_wizard.subprocess, "run", run)


def test_game_running(monkeypatch) -> None:
    _tasklist(monkeypatch, "FSD-Win64-Shipping.exe  6844 Console  1  2,048,968 K\n")
    assert setup_wizard.game_running() is True


@pytest.mark.parametrize("stdout, exc", [
    ("情報: 指定された条件に一致するタスクは実行されていません。\n", None),
    (None, FileNotFoundError("tasklist")),
    (None, subprocess.TimeoutExpired("tasklist", 10)),
])
def test_game_not_running_or_unknown(monkeypatch, stdout, exc) -> None:
    _tasklist(monkeypatch, stdout, exc)
    assert setup_wizard.game_running() is False


@pytest.mark.parametrize("running", [True, False])
def test_install_mod_asks_for_restart_only_while_game_runs(game, tmp_path, monkeypatch,
                                                            capsys, running) -> None:
    """ゲームが動いているときだけ、MOD を入れたあとに再起動を案内すること。"""
    game_dir, _ = game
    src = tmp_path / "src" / MOD_NAME
    (src / "Scripts").mkdir(parents=True)
    (src / "Scripts" / "main.lua").write_text("-- mod\n", encoding="utf-8")
    monkeypatch.setattr(setup_wizard, "game_running", lambda: running)
    assert install_mod(str(game_dir), str(src)) is True
    shown = setup_wizard.t("w.mod.restart_game") in capsys.readouterr().out
    assert shown is running
