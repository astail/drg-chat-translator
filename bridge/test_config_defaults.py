"""設定の既定値が DEFAULTS 1か所にまとまっていることの回帰テスト。

リポジトリルートから `python3 -m pytest bridge/test_config_defaults.py` で実行する。
"""

from __future__ import annotations

from drg_bridge import DEFAULTS, build_config


def test_build_config_equals_defaults_when_nothing_is_set(clean_env) -> None:
    """何も設定していなければ、build_config() は DEFAULTS とまったく同じになること。

    既定値を build_config() に直接書くと、DEFAULTS と食い違ったときにここで落ちる。
    """
    assert build_config() == DEFAULTS


def test_auto_source_translates_whatever_language(clean_env, make_bridge, read_out) -> None:
    """DRGT_OUTGOING_SOURCE=auto なら、打った発言の言語を判定して訳すこと。"""
    clean_env(DRGT_OUTGOING_SOURCE="auto", DRGT_CACHE_ENABLED="false")
    cfg = build_config()
    assert cfg["outgoing"]["source"] == ""
    b = make_bridge(cfg)
    b._do_outgoing("1", "hello everyone")
    b._do_outgoing("2", "回復お願いします")
    rows = {r[1]: r for r in read_out(b)}
    # 英語の発言は、英語を除いた訳す先（ko / zh）へ
    assert rows["1"][4] == "[ko] hello everyone / [zh] hello everyone"
    # 日本語の発言は、既定の訳す先すべて（en / ko / zh）へ
    assert rows["2"][4].startswith("[en] 回復お願いします")


def test_fixed_source_skips_other_languages(clean_env, make_bridge, read_out) -> None:
    """翻訳元を決めているときは、それ以外の言語の発言は訳さないこと（従来どおり）。"""
    clean_env(DRGT_CACHE_ENABLED="false")
    b = make_bridge(build_config())
    b._do_outgoing("1", "hello everyone")
    row = read_out(b)[0]
    assert row[:3] == ["RES", "1", "out"] and row[4] == ""
