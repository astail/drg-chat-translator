"""--fake / --selftest が利用者の環境を汚さないことの回帰テスト。

リポジトリルートから `python3 -m pytest bridge/test_selftest_isolation.py` で実行する。
"""

from __future__ import annotations

import copy
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import drg_bridge  # noqa: E402
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
