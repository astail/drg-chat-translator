"""用語集を言語ごとに引くことの回帰テスト（日本語だけの特別扱いをやめた）。

リポジトリルートから `python3 -m pytest bridge/test_glossary_languages.py` で実行する。
"""

from __future__ import annotations

import copy
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from drg_bridge import DEFAULTS, Bridge  # noqa: E402
from translate import Glossary  # noqa: E402


def _glossary(tmp_path, incoming: dict) -> str:
    path = tmp_path / "glossary.json"
    path.write_text(json.dumps({"incoming": incoming, "outgoing": {}}, ensure_ascii=False),
                    encoding="utf-8")
    return str(path)


def test_lookup_by_language(tmp_path) -> None:
    g = Glossary(_glossary(tmp_path, {"gg": {"ja": "お疲れさま！", "ko": "수고했어!"}}))
    assert g.lookup_incoming("gg", "ja") == "お疲れさま！"
    assert g.lookup_incoming("GG!", "ko") == "수고했어!"
    assert g.lookup_incoming("gg", "zh") is None


def test_star_applies_to_every_language(tmp_path) -> None:
    g = Glossary(_glossary(tmp_path, {"rock and stone": {"*": "Rock and Stone!"}}))
    for lang in ("ja", "en", "ko", "zh", "zh-tw", "ru"):
        assert g.lookup_incoming("rock and stone", lang) == "Rock and Stone!"


def test_old_format_keeps_its_meaning(tmp_path) -> None:
    """以前の形（値が文字列）でも、掛け声はどの言語でも、訳は日本語として読むこと。"""
    g = Glossary(_glossary(tmp_path, {"rock and stone": "Rock and Stone!", "gg": "お疲れさま！"}))
    assert g.lookup_incoming("rock and stone", "ru") == "Rock and Stone!"
    assert g.lookup_incoming("gg", "ja") == "お疲れさま！"
    assert g.lookup_incoming("gg", "ko") is None


def test_shipped_glossary_is_in_the_new_format() -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, "glossary.json"), encoding="utf-8") as f:
        data = json.load(f)
    assert all(isinstance(v, dict) and v for v in data["incoming"].values())


@pytest.fixture
def bridge_for(tmp_path):
    made = []

    def make(target: str, incoming: dict) -> Bridge:
        cfg = copy.deepcopy(DEFAULTS)
        cfg["cache"]["enabled"] = False
        cfg["incoming"]["target"] = target
        cfg["incoming"]["skip_languages"] = [target]
        cfg["glossary"]["path"] = _glossary(tmp_path, incoming)
        b = Bridge(cfg, str(tmp_path / f"ipc-{target}"), fake=True)
        made.append(b)
        return b

    yield make
    for b in made:
        b.pool.shutdown(wait=True)


def test_glossary_reaches_non_japanese_users(bridge_for) -> None:
    """韓国語の訳を用語集に足せば、韓国語で読む人にも API を呼ばずに届くこと。"""
    b = bridge_for("ko", {"gg": {"ja": "お疲れさま！", "ko": "수고했어!"}})
    assert b.translate_incoming("gg")[1] == "수고했어!"


def test_japanese_only_entry_is_not_used_for_other_languages(bridge_for) -> None:
    """日本語の訳しか無ければ、ほかの言語の人には使わず翻訳に回すこと（従来どおり）。"""
    b = bridge_for("ko", {"gg": {"ja": "お疲れさま！"}})
    assert b.translate_incoming("gg")[1] == "[ko] gg"


def test_chants_are_kept_and_not_relayed_for_everyone(bridge_for) -> None:
    """掛け声はどの言語の人にもそのまま出し、中継もしないこと。"""
    b = bridge_for("zh", {"rock and stone": {"*": "Rock and Stone!"}})
    _, shown, relayed = b.translate_incoming("rock and stone", relay=True)
    assert shown == "Rock and Stone!"
    assert relayed == {}
