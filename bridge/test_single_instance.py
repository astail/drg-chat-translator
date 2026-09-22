"""bridge を同じ通信フォルダで2つ動かさないことの回帰テスト。

リポジトリルートから `python3 -m pytest bridge/test_single_instance.py` で実行する。
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
from drg_bridge import DEFAULTS, AlreadyRunning, Bridge, Ipc  # noqa: E402


def test_second_ipc_in_the_same_folder_is_refused(tmp_path) -> None:
    """同じ通信フォルダで2つ目は起動しないこと（2つとも同じ要求を読み、API を二重に呼ぶため）。"""
    first = Ipc(str(tmp_path))
    with pytest.raises(AlreadyRunning):
        Ipc(str(tmp_path))
    first.cleanup()


def test_next_bridge_can_start_after_the_first_stops(tmp_path) -> None:
    Ipc(str(tmp_path)).cleanup()
    Ipc(str(tmp_path)).cleanup()


def test_refused_bridge_does_not_touch_the_files(tmp_path) -> None:
    """断られた2つ目は、動いている bridge のファイルを空にしないこと。"""
    first = Ipc(str(tmp_path))
    with open(first.p_in, "w", encoding="utf-8") as f:
        f.write("REQ\t1\tin\tKarl\thello\t0\n")
    with pytest.raises(AlreadyRunning):
        Ipc(str(tmp_path))
    with open(first.p_in, encoding="utf-8") as f:
        assert f.read() == "REQ\t1\tin\tKarl\thello\t0\n"
    first.cleanup()


def test_bridge_without_ipc_leaves_the_folder_alone(tmp_path) -> None:
    """--test とウィザードの疎通確認は、動いている bridge とゲームのファイルに触らないこと。"""
    running = Ipc(str(tmp_path))
    with open(running.p_out, "w", encoding="utf-8") as f:
        f.write("RES\t1\tin\ten\tpending\n")
    with open(running.p_game_alive, "w", encoding="utf-8") as f:
        f.write("0.7.0 123\n")
    cfg = copy.deepcopy(DEFAULTS)
    cfg["cache"]["enabled"] = False
    b = Bridge(cfg, str(tmp_path), fake=True, ipc=False)
    try:
        assert b.ipc is None
        assert b.translate_incoming("watch out")[1]
    finally:
        b.pool.shutdown(wait=True)
    with open(running.p_out, encoding="utf-8") as f:
        assert f.read() == "RES\t1\tin\ten\tpending\n"
    assert os.path.exists(running.p_game_alive)
    running.cleanup()


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    """main() を走らせても、環境変数・表示言語・ログの設定がほかのテストに残らないようにする。"""
    clean = {k: v for k, v in os.environ.items()
             if not k.startswith(("DRGT_",) + drg_bridge.SECRET_ENV_NAMES)}
    clean["DRGT_UI_LANG"] = "en"
    monkeypatch.setattr(os, "environ", clean)
    monkeypatch.setattr(i18n, "_lang", i18n._lang)
    yield tmp_path
    root = logging.getLogger()
    for h in list(root.handlers):
        h.close()
        root.removeHandler(h)
    drg_bridge.log.setLevel(logging.NOTSET)


def test_main_refuses_to_start_twice(isolated, capsys) -> None:
    """2つ目の起動は、すでに動いていると伝えて 0 以外で終わること（exe なら窓が閉じずに読める）。"""
    running = Ipc(str(isolated / "ipc"))
    try:
        code = drg_bridge.main(["--fake", "--config", str(isolated / "none.ini"),
                                "--dir", str(isolated / "ipc")])
    finally:
        running.cleanup()
    assert code != 0
    assert "already running" in capsys.readouterr().err


def test_main_test_runs_while_a_bridge_is_running(isolated) -> None:
    """--test は通信フォルダを使わないので、bridge が動いていても試せること。"""
    running = Ipc(str(isolated / "ipc"))
    try:
        assert drg_bridge.main(["--fake", "--test", "hello", "--config",
                                str(isolated / "none.ini"), "--dir", str(isolated / "ipc")]) == 0
    finally:
        running.cleanup()
