"""用語集を言語ごとに引くことの回帰テスト（日本語だけの特別扱いをやめた）。

リポジトリルートから `python3 -m pytest bridge/test_glossary_languages.py` で実行する。
"""

from __future__ import annotations

import copy
import json
import os

import pytest

from drg_bridge import Bridge
from translate import Glossary


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
def bridge_for(tmp_path, make_bridge, fake_cfg):
    """受信の訳す先と用語集を決めた Bridge を作る。"""
    def make(target: str, incoming: dict) -> Bridge:
        cfg = copy.deepcopy(fake_cfg)
        cfg["incoming"]["target"] = target
        cfg["incoming"]["skip_languages"] = [target]
        cfg["glossary"]["path"] = _glossary(tmp_path, incoming)
        return make_bridge(cfg, directory=tmp_path / f"ipc-{target}")

    return make


def test_glossary_reaches_non_japanese_users(bridge_for) -> None:
    """韓国語の訳を用語集に足せば、韓国語で読む人にも API を呼ばずに届くこと。"""
    b = bridge_for("ko", {"gg": {"ja": "お疲れさま！", "ko": "수고했어!"}})
    assert b.translate_incoming("gg")[1] == "수고했어!"


def test_japanese_only_entry_is_not_used_for_other_languages(bridge_for) -> None:
    """日本語の訳しか無ければ、ほかの言語の人には使わず翻訳に回すこと（従来どおり）。"""
    b = bridge_for("ko", {"gg": {"ja": "お疲れさま！"}})
    assert b.translate_incoming("gg")[1] == "[ko] gg"


GG = {"gg": {"ja": "お疲れさま！", "ko": "수고했어!", "zh": "辛苦了！"}}


def _spy(b: Bridge) -> list[list[str]]:
    """translate_multi に頼まれた言語を記録する。"""
    calls: list[list[str]] = []
    real = b.translator.translate_multi

    def spy(text, source, targets):
        calls.append(list(targets))
        return real(text, source, targets)

    b.translator.translate_multi = spy
    return calls


def test_host_uses_glossary_for_every_language(bridge_for) -> None:
    """ホストの中継でも、用語集にある言語は API を呼ばずに用語集の訳を使うこと。"""
    b = bridge_for("ja", GG)
    calls = _spy(b)
    _, shown, relayed = b.translate_incoming("gg", relay=True)
    assert calls == []
    assert shown == "お疲れさま！"
    assert relayed == {"ja": "お疲れさま！", "ko": "수고했어!", "zh": "辛苦了！"}


def test_host_asks_api_only_for_missing_languages(bridge_for) -> None:
    """用語集に無い言語だけを API に頼むこと。"""
    b = bridge_for("ja", {"gg": {"ja": "お疲れさま！"}})
    calls = _spy(b)
    _, shown, relayed = b.translate_incoming("gg", relay=True)
    assert calls == [["ko", "zh"]]
    assert shown == "お疲れさま！"
    assert relayed["ja"] == "お疲れさま！" and relayed["ko"] == "[ko] gg"


def test_client_and_host_show_the_same_translation(bridge_for) -> None:
    """同じ発言なら、クライアントのときとホストのときで自分に見える訳が同じこと。"""
    b = bridge_for("ja", GG)
    assert b.translate_incoming("gg")[1] == b.translate_incoming("gg", relay=True)[1]


def test_chants_are_kept_and_not_relayed_for_everyone(bridge_for) -> None:
    """掛け声はどの言語の人にもそのまま出し、中継もしないこと。"""
    b = bridge_for("zh", {"rock and stone": {"*": "Rock and Stone!"}})
    _, shown, relayed = b.translate_incoming("rock and stone", relay=True)
    assert shown == "Rock and Stone!"
    assert relayed == {}
