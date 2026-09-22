"""リリースで食い違ってはいけない値が、ソースの中でそろっていることのテスト。

以前は release.yml（タグを打ったとき）でしか確かめておらず、食い違いに気づくのが
リリースを切った瞬間だった。pytest に置いて、push と PR のたびに走らせる。
タグ名とソースの版の照合だけは、タグがあるときにしかできないので release.yml に残す。

リポジトリルートから `python3 -m pytest bridge/test_release_consistency.py` で実行する。
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _read(path: str, pattern: str) -> str:
    text = (ROOT / path).read_text(encoding="utf-8-sig")
    m = re.search(pattern, text, re.M)
    assert m, f"{path} から {pattern} を読み取れなかった（変数名が変わっていないか）"
    return m.group(1)


def test_bridge_and_mod_have_the_same_version() -> None:
    """バージョンはアプリ全体で1つ。bridge と MOD の番号がそろっていること。"""
    bridge = _read("bridge/drg_bridge.py", r'^VERSION\s*=\s*"([^"]+)"')
    mod = _read("mod/DRGTranslate/Scripts/main.lua", r'^local MOD_VERSION\s*=\s*"([^"]+)"')
    assert bridge == mod


def test_both_installers_install_the_same_ue4ss() -> None:
    """exe のウィザードと install.ps1 が同じ版の UE4SS を入れること。"""
    wizard = _read("bridge/setup_wizard.py", r'^UE4SS_VERSION\s*=\s*"([^"]+)"')
    ps1 = _read("install.ps1", r'\$UE4SSVersion\s*=\s*"([^"]+)"')
    assert wizard == ps1


def test_both_installers_check_the_same_ue4ss_hash() -> None:
    """展開する前に照合する UE4SS の zip の SHA-256 が、2つのインストーラでそろっていること。"""
    version = _read("bridge/setup_wizard.py", r'^UE4SS_VERSION\s*=\s*"([^"]+)"')
    wizard = _read("bridge/setup_wizard.py", r'^UE4SS_SHA256\s*=\s*"([0-9a-f]{64})"')
    ps1 = _read("install.ps1", r'"' + re.escape(version) + r'"\s*=\s*"([0-9a-f]{64})"')
    assert wizard == ps1


def test_requirements_files_declare_utf8() -> None:
    """日本語を含む requirements*.txt は、先頭で utf-8 を宣言していること。

    pip は宣言が無いと OS の既定の文字コードで読むので、日本語の Windows（cp932）では
    build.bat の pip install が UnicodeDecodeError で止まる（Python 3.11 付属の pip 24.0 で確認）。
    """
    for path in sorted(ROOT.glob("requirements*.txt")):
        raw = path.read_bytes()
        if raw.isascii():
            continue
        head = raw.splitlines()[0]
        assert b"coding: utf-8" in head, f"{path.name} の1行目に # -*- coding: utf-8 -*- が無い"
