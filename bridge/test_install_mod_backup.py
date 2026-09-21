"""MOD を入れ直すときの退避と復元の回帰テスト。

リポジトリルートから `python3 -m pytest bridge/test_install_mod_backup.py` で実行する。
"""

from __future__ import annotations

import os
import shutil
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import setup_wizard  # noqa: E402
from setup_wizard import MOD_NAME, install_mod  # noqa: E402


@pytest.fixture
def game(tmp_path):
    """前の版の MOD（利用者が config.lua を編集済み）が入っているゲームフォルダ。"""
    mods = tmp_path / "game" / "FSD" / "Binaries" / "Win64" / "Mods"
    old = mods / MOD_NAME
    (old / "Scripts").mkdir(parents=True)
    (old / "enabled.txt").write_text("", encoding="utf-8")
    (old / "Scripts" / "config.lua").write_text("-- edited by user\n", encoding="utf-8")
    src = tmp_path / "src" / MOD_NAME
    (src / "Scripts").mkdir(parents=True)
    (src / "enabled.txt").write_text("", encoding="utf-8")
    (src / "Scripts" / "config.lua").write_text("-- new\n", encoding="utf-8")
    return tmp_path / "game", src, mods


def test_backup_is_not_loaded_by_ue4ss(game) -> None:
    """退避した前の MOD は、UE4SS に2つ目の MOD として読み込まれないこと。"""
    game_dir, src, mods = game
    assert install_mod(str(game_dir), str(src)) is True
    backup = mods / f"{MOD_NAME}.bak"
    assert (backup / "Scripts" / "config.lua").read_text(encoding="utf-8") == "-- edited by user\n"
    assert not (backup / "enabled.txt").exists()
    assert (backup / "enabled.txt.off").exists()
    assert (mods / MOD_NAME / "enabled.txt").exists()
    assert (mods / MOD_NAME / "Scripts" / "config.lua").read_text(encoding="utf-8") == "-- new\n"


def test_failed_copy_restores_previous_mod(game, monkeypatch) -> None:
    """新しい MOD のコピーに失敗したら、前の MOD を元の場所と状態に戻すこと。"""
    game_dir, src, mods = game

    def boom(*a, **k):
        raise OSError("file in use")

    monkeypatch.setattr(setup_wizard.shutil, "copytree", boom)
    assert install_mod(str(game_dir), str(src)) is False
    restored = mods / MOD_NAME
    assert (restored / "enabled.txt").exists()
    assert (restored / "Scripts" / "config.lua").read_text(encoding="utf-8") == "-- edited by user\n"
    assert not (mods / f"{MOD_NAME}.bak").exists()


def test_reinstall_twice_keeps_latest_backup(game) -> None:
    """続けて2回入れ直しても、.bak は1つで、UE4SS に読み込まれない状態のままなこと。"""
    game_dir, src, mods = game
    assert install_mod(str(game_dir), str(src)) is True
    assert install_mod(str(game_dir), str(src)) is True
    backup = mods / f"{MOD_NAME}.bak"
    assert not (backup / "enabled.txt").exists()
    assert sorted(p.name for p in mods.iterdir() if p.is_dir()) == [MOD_NAME, f"{MOD_NAME}.bak"]
    shutil.rmtree(mods)
