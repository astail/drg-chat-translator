"""セットアップウィザードのファイル書き込みの回帰テスト。

リポジトリルートから `python3 -m pytest bridge/test_setup_wizard_io.py` で実行する。
"""

from __future__ import annotations

import os

import pytest

import setup_wizard
from setup_wizard import MOD_NAME, install_mod, write_env, write_text_atomic


def _fail_replace(monkeypatch) -> None:
    """os.replace を失敗させる（書き込みの途中で止まった状態を作る）。"""
    def boom(src, dst):
        raise OSError("interrupted")
    monkeypatch.setattr(setup_wizard.os, "replace", boom)


def test_atomic_write_keeps_original_on_failure(tmp_path, monkeypatch) -> None:
    """書き込みに失敗しても元のファイルはそのまま残り、.tmp も残らないこと。"""
    path = tmp_path / "settings.ini"
    path.write_text("DEEPL_AUTH_KEY=secret\n", encoding="utf-8")
    _fail_replace(monkeypatch)
    with pytest.raises(OSError):
        write_text_atomic(str(path), "")
    assert path.read_text(encoding="utf-8") == "DEEPL_AUTH_KEY=secret\n"
    assert not (tmp_path / "settings.ini.tmp").exists()


def test_atomic_write_replaces_content(tmp_path) -> None:
    """成功すれば中身が置き換わり、.tmp は残らないこと。"""
    path = tmp_path / "a.txt"
    path.write_text("old\n", encoding="utf-8")
    write_text_atomic(str(path), "new\n")
    assert path.read_text(encoding="utf-8") == "new\n"
    assert not (tmp_path / "a.txt.tmp").exists()


def test_write_env_keeps_key_when_interrupted(tmp_path, monkeypatch) -> None:
    """settings.ini の書き換えが途中で止まっても APIキーが消えないこと。"""
    path = tmp_path / "settings.ini"
    path.write_text("# comment\nANTHROPIC_API_KEY=sk-test\n", encoding="utf-8")
    _fail_replace(monkeypatch)
    with pytest.raises(OSError):
        write_env(str(path), {"DRGT_PROVIDER": "claude"})
    assert "ANTHROPIC_API_KEY=sk-test" in path.read_text(encoding="utf-8")


def test_write_env_upserts_and_keeps_comments(tmp_path) -> None:
    """既存の項目は書き換え、無い項目は足し、説明のコメントは残すこと。"""
    path = tmp_path / "settings.ini"
    path.write_text("# 説明\n#DRGT_PROVIDER=deepl\nOTHER=1\n", encoding="utf-8")
    write_env(str(path), {"DRGT_PROVIDER": "claude", "NEW_KEY": "x"})
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines == ["# 説明", "DRGT_PROVIDER=claude", "OTHER=1", "NEW_KEY=x"]


@pytest.fixture
def game(tmp_path):
    """install_mod が期待するゲームフォルダの形を作る。"""
    mods = tmp_path / "game" / "FSD" / "Binaries" / "Win64" / "Mods"
    mods.mkdir(parents=True)
    src = tmp_path / "src" / MOD_NAME
    (src / "Scripts").mkdir(parents=True)
    (src / "Scripts" / "main.lua").write_text("-- mod\n", encoding="utf-8")
    return tmp_path / "game", src, mods


def test_install_mod_backs_up_mods_txt(game) -> None:
    """mods.txt を書き換える前に控えを取り、利用者の MOD の行は残すこと。"""
    game_dir, src, mods = game
    original = "MyOwnMod : 1\nKeybinds : 1\nConsoleCommandsMod : 1\n; comment\n"
    (mods / "mods.txt").write_text(original, encoding="utf-8")

    assert install_mod(str(game_dir), str(src)) is True

    assert (mods / "mods.txt.bak").read_text(encoding="utf-8") == original
    lines = (mods / "mods.txt").read_text(encoding="utf-8").splitlines()
    assert "MyOwnMod : 1" in lines
    assert "Keybinds : 1" in lines
    assert "; comment" in lines
    assert "ConsoleCommandsMod : 0" in lines
    assert f"{MOD_NAME} : 1" in lines
    assert not (mods / "mods.txt.tmp").exists()


def test_install_mod_keeps_mods_txt_when_write_fails(game, monkeypatch) -> None:
    """mods.txt の書き込みに失敗しても、他の MOD の一覧は壊れないこと。"""
    game_dir, src, mods = game
    original = "MyOwnMod : 1\n"
    (mods / "mods.txt").write_text(original, encoding="utf-8")

    real_replace = os.replace

    def fail_only_mods_txt(a, b):
        if str(b).endswith("mods.txt"):
            raise OSError("interrupted")
        return real_replace(a, b)

    monkeypatch.setattr(setup_wizard.os, "replace", fail_only_mods_txt)
    assert install_mod(str(game_dir), str(src)) is False
    assert (mods / "mods.txt").read_text(encoding="utf-8") == original
