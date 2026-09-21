"""UE4SS の zip を展開する前に SHA-256 を照合することの回帰テスト。

リポジトリルートから `python3 -m pytest bridge/test_ue4ss_download.py` で実行する。
"""

from __future__ import annotations

import hashlib
import io
import os
import sys
import zipfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import setup_wizard  # noqa: E402


def _zip_bytes() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("UE4SS.dll", b"dummy")
    return buf.getvalue()


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.fixture
def game(tmp_path, monkeypatch):
    """UE4SS がまだ入っていないゲームフォルダ。導入するかの質問には「はい」と答える。"""
    (tmp_path / "FSD" / "Binaries" / "Win64").mkdir(parents=True)
    monkeypatch.setattr(setup_wizard, "ask_yes", lambda *a, **k: True)
    return tmp_path


def _serve(monkeypatch, data: bytes) -> None:
    monkeypatch.setattr(setup_wizard.urllib.request, "urlopen", lambda *a, **k: _Resp(data))


def test_known_hash_matches_pinned_release() -> None:
    """照合に使う値が SHA-256 の形をしていること（書き間違いの防止）。"""
    assert len(setup_wizard.UE4SS_SHA256) == 64
    int(setup_wizard.UE4SS_SHA256, 16)


def test_mismatch_is_not_extracted(game, monkeypatch) -> None:
    """SHA-256 が一致しない zip は展開せずに止めること。"""
    _serve(monkeypatch, _zip_bytes())
    assert setup_wizard.install_ue4ss(str(game)) is False
    assert not (game / "FSD" / "Binaries" / "Win64" / "UE4SS.dll").exists()


def test_match_is_extracted(game, monkeypatch) -> None:
    """SHA-256 が一致すれば、これまでどおり展開すること。"""
    data = _zip_bytes()
    monkeypatch.setattr(setup_wizard, "UE4SS_SHA256", hashlib.sha256(data).hexdigest())
    _serve(monkeypatch, data)
    assert setup_wizard.install_ue4ss(str(game)) is True
    assert (game / "FSD" / "Binaries" / "Win64" / "UE4SS.dll").exists()
