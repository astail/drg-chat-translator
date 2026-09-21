"""翻訳キャッシュまわりの回帰テスト。

リポジトリルートから `python3 -m pytest bridge/test_cache.py` で実行する。
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import translate  # noqa: E402
from translate import Cache, ClaudeProvider, DeepLProvider, OpenAIProvider  # noqa: E402


def test_llm_scope_changes_with_prompt(monkeypatch) -> None:
    """プロンプト（GAME_CONTEXT）を変えると、同じモデルでもスコープが変わること。"""
    before = ClaudeProvider({"model": "claude-haiku-4-5"}).cache_scope()
    monkeypatch.setattr(translate, "GAME_CONTEXT",
                        translate.GAME_CONTEXT.replace("ナイトラ", "ニトラ"))
    after = ClaudeProvider({"model": "claude-haiku-4-5"}).cache_scope()
    assert before != after
    assert before.startswith("claude:claude-haiku-4-5:")


def test_llm_scope_is_stable() -> None:
    """同じ設定なら何度作ってもスコープは同じ（起動のたびにキャッシュが消えない）こと。"""
    a = OpenAIProvider({"model": "gpt-4o-mini"}).cache_scope()
    b = OpenAIProvider({"model": "gpt-4o-mini"}).cache_scope()
    assert a == b


def test_llm_scope_differs_by_model() -> None:
    """モデルが違えばスコープも違うこと（従来どおり）。"""
    a = ClaudeProvider({"model": "claude-haiku-4-5"}).cache_scope()
    b = ClaudeProvider({"model": "claude-sonnet-5"}).cache_scope()
    assert a != b


def test_deepl_scope_is_unchanged() -> None:
    """DeepL はプロンプトを使わないので、スコープは名前だけのままであること。"""
    assert DeepLProvider({}).cache_scope() == "deepl"


def test_cache_separates_scopes(tmp_path) -> None:
    """同じ文でもスコープが違えば別の項目として持つこと。"""
    cache = Cache(str(tmp_path / "cache.json"))
    cache.put("claude:m:aaaa", "hello", "auto", "ja", "こんにちは")
    assert cache.get("claude:m:aaaa", "hello", "auto", "ja") == "こんにちは"
    assert cache.get("claude:m:bbbb", "hello", "auto", "ja") is None


def test_maybe_save_keeps_dirty_on_failure(tmp_path, monkeypatch) -> None:
    """保存に失敗したら次の機会にもう一度書くこと。書きかけの .tmp は残さないこと。"""
    path = tmp_path / "cache.json"
    cache = Cache(str(path))
    cache.put("s", "hello", "auto", "ja", "こんにちは")

    def boom(src, dst):
        raise OSError("disk full")

    monkeypatch.setattr(translate.os, "replace", boom)
    cache.maybe_save(force=True)
    assert not path.exists()
    assert not (tmp_path / "cache.json.tmp").exists()

    monkeypatch.undo()
    cache.maybe_save(force=True)
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "s|auto|ja|hello": "こんにちは",
    }


def test_maybe_save_skips_when_clean(tmp_path) -> None:
    """変更が無ければ書かないこと。"""
    path = tmp_path / "cache.json"
    cache = Cache(str(path))
    cache.maybe_save(force=True)
    assert not path.exists()


def test_eviction_keeps_size_bounded(tmp_path) -> None:
    """max_entries を超えたら古いものから捨てて、上限を守ること。"""
    cache = Cache(str(tmp_path / "cache.json"), max_entries=10)
    for i in range(25):
        cache.put("s", f"text{i}", "auto", "ja", f"訳{i}")
    assert len(cache._data) <= 10
    assert cache.get("s", "text24", "auto", "ja") == "訳24"
    assert cache.get("s", "text0", "auto", "ja") is None
