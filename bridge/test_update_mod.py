"""起動時にゲームフォルダの古い MOD を入れ替えることの回帰テスト。

zip を展開して settings.ini だけ前のフォルダから持ってくると、セットアップが走らず、
ゲームフォルダの MOD が古いまま残っていた。

リポジトリルートから `python3 -m pytest bridge/test_update_mod.py` で実行する。
"""

from __future__ import annotations

import logging

import pytest

import drg_bridge
import setup_wizard
from drg_bridge import VERSION, update_mod
from setup_wizard import MOD_NAME


def _main_lua(version: str) -> str:
    return f'local Cfg = require("config")\nlocal MOD_VERSION = "{version}"\n'


@pytest.fixture
def game(tmp_path, monkeypatch):
    """前の版の MOD が入っているゲームフォルダと、exe に同梱の MOD。"""
    game_dir = tmp_path / "game"
    mods = game_dir / "FSD" / "Binaries" / "Win64" / "Mods"
    src = tmp_path / "bundle" / "mod" / MOD_NAME
    (src / "Scripts").mkdir(parents=True)
    (src / "enabled.txt").write_text("", encoding="utf-8")
    (src / "Scripts" / "main.lua").write_text(_main_lua(VERSION), encoding="utf-8")
    monkeypatch.setattr(setup_wizard, "find_game", lambda: str(game_dir))
    monkeypatch.setattr(drg_bridge, "bundled", lambda *p: str(tmp_path / "bundle" / "/".join(p)))
    return game_dir, mods


def _install(mods, version: str) -> None:
    scripts = mods / MOD_NAME / "Scripts"
    scripts.mkdir(parents=True)
    (mods / MOD_NAME / "enabled.txt").write_text("", encoding="utf-8")
    (scripts / "main.lua").write_text(_main_lua(version), encoding="utf-8")


def test_old_mod_is_replaced(game, caplog) -> None:
    game_dir, mods = game
    _install(mods, "0.0.1")
    with caplog.at_level(logging.INFO, logger="drgtl"):
        update_mod()
    assert setup_wizard.installed_mod_version(str(game_dir)) == VERSION
    backup = mods / f"{MOD_NAME}.bak"
    assert "0.0.1" in (backup / "Scripts" / "main.lua").read_text(encoding="utf-8")
    assert not (backup / "enabled.txt").exists()  # 退避した方は UE4SS に読ませない
    assert any("0.0.1" in r.getMessage() and VERSION in r.getMessage() for r in caplog.records)


def test_same_version_is_left_alone(game) -> None:
    _, mods = game
    _install(mods, VERSION)
    update_mod()
    assert not (mods / f"{MOD_NAME}.bak").exists()


def test_nothing_is_installed_without_a_mod(game) -> None:
    """MOD を入れていない（セットアップしていない）ゲームフォルダには何も入れないこと。"""
    _, mods = game
    update_mod()
    assert not (mods / MOD_NAME).exists()


def test_game_not_found_does_nothing() -> None:
    update_mod()  # conftest で find_game は None。例外にならないこと


def test_failed_copy_keeps_old_mod_and_warns(game, monkeypatch, caplog) -> None:
    game_dir, mods = game
    _install(mods, "0.0.1")

    def boom(*a, **k):
        raise OSError("locked")

    monkeypatch.setattr(setup_wizard.shutil, "copytree", boom)
    with caplog.at_level(logging.WARNING, logger="drgtl"):
        update_mod()
    assert setup_wizard.installed_mod_version(str(game_dir)) == "0.0.1"
    assert (mods / MOD_NAME / "enabled.txt").exists()
    assert any("locked" in r.getMessage() for r in caplog.records)
