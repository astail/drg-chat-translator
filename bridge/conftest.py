"""bridge のテストで共通に使う fixture。

- fake_cfg     … 既定の設定からキャッシュを切ったもの（テストの中で書き換えてよい）
- make_bridge  … --fake の Bridge を作る。スレッドと通信フォルダのロックも後始末する
- bridge       … make_bridge() で作った既定の Bridge
- read_out     … to_game.txt（bridge → MOD）に書かれた行を読む
- clean_env    … 設定に関わる環境変数を消し、渡した値だけを入れる
- isolated     … main() を走らせても、環境変数・表示言語・ログの設定をほかのテストに残さない
"""

from __future__ import annotations

import copy
import logging
import os
import time

import pytest

import drg_bridge
import i18n
from drg_bridge import DEFAULTS, Bridge, decode_line

# 設定に関わる環境変数（利用者の環境や settings.ini の値がテストに混ざらないように消す）
CONFIG_ENV = ("DRGT_",) + drg_bridge.SECRET_ENV_NAMES


@pytest.fixture
def fake_cfg() -> dict:
    cfg = copy.deepcopy(DEFAULTS)
    cfg["cache"]["enabled"] = False
    return cfg


@pytest.fixture
def make_bridge(tmp_path, fake_cfg):
    made: list[Bridge] = []

    def make(cfg: dict | None = None, directory=None, **kwargs) -> Bridge:
        b = Bridge(fake_cfg if cfg is None else cfg, str(directory or tmp_path),
                   fake=True, **kwargs)
        made.append(b)
        return b

    yield make
    for b in made:
        b.stop()
        b.pool.shutdown(wait=True)
        b.overlay_pool.shutdown(wait=True)
        if b.ipc is not None:
            b.ipc.cleanup()


@pytest.fixture
def bridge(make_bridge) -> Bridge:
    return make_bridge()


@pytest.fixture
def read_out():
    def read(b: Bridge, timeout: float = 0.0) -> list[list[str]]:
        """to_game.txt の行。timeout を渡すと、何か書かれるまで最大その秒数だけ待つ。"""
        deadline = time.monotonic() + timeout
        while True:
            with open(b.ipc.p_out, encoding="utf-8") as f:
                rows = [decode_line(line.rstrip("\n")) for line in f if line.strip()]
            if rows or time.monotonic() >= deadline:
                return rows
            time.sleep(0.05)

    return read


@pytest.fixture
def clean_env(monkeypatch):
    def set_env(**values: str) -> None:
        for key in [k for k in os.environ if k.startswith(CONFIG_ENV)]:
            monkeypatch.delenv(key, raising=False)
        for key, value in values.items():
            monkeypatch.setenv(key, value)

    set_env()
    return set_env


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    """main() は settings.ini を os.environ に読み込み、表示言語とログの設定を変える。

    環境変数は丸ごと差し替え、表示言語とログのハンドラ・レベルはテストのあとに戻す。
    """
    clean = {k: v for k, v in os.environ.items() if not k.startswith(CONFIG_ENV)}
    monkeypatch.setattr(os, "environ", clean)
    monkeypatch.setattr(i18n, "_lang", i18n._lang)
    yield tmp_path
    close_log_handlers()


def close_log_handlers() -> None:
    """setup_logging が付けたハンドラを閉じて外す（開いたままだと Windows でファイルを消せない）。"""
    root = logging.getLogger()
    for h in list(root.handlers):
        h.close()
        root.removeHandler(h)
    drg_bridge.log.setLevel(logging.NOTSET)
