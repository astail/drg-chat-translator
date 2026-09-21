"""表示文言のカタログ（bridge/i18n.py）の機械的な検査。

TESTING.md に「112キー × 6言語を機械的に検査した」と書いていた内容を、再現できる形にしたもの。
キーを足したときに、言語の抜けや差し込みの食い違いがあれば落ちる。
リポジトリルートから `python3 -m pytest bridge/test_i18n_catalog.py` で実行する。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import i18n  # noqa: E402

CODES = [code for code, _ in i18n.LANGUAGES]
KEYS = sorted(i18n._M)
NAMED = re.compile(r"\{(\w+)\}")
PERCENT = re.compile(r"%[sd]")
SOURCES = [p for p in HERE.glob("*.py") if p.name != "i18n.py" and not p.name.startswith("test_")]


@pytest.mark.parametrize("key", KEYS)
def test_every_language_is_present(key) -> None:
    """どのキーも6言語すべての文言を持つこと（抜けると英語に落ちる）。"""
    entry = i18n._M[key]
    missing = [c for c in CODES if not entry.get(c, "").strip()]
    assert not missing, f"{key}: {missing}"


@pytest.mark.parametrize("key", KEYS)
def test_placeholders_agree_across_languages(key) -> None:
    """{name} の集合と、%s / %d の並びが言語間で一致すること（ずれると実行時に落ちる）。"""
    entry = i18n._M[key]
    named = {c: sorted(NAMED.findall(entry[c])) for c in CODES}
    percent = {c: PERCENT.findall(entry[c]) for c in CODES}
    assert len({tuple(v) for v in named.values()}) == 1, f"{key}: {named}"
    assert len({tuple(v) for v in percent.values()}) == 1, f"{key}: {percent}"


def _code() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in SOURCES)


def test_every_key_used_in_code_exists() -> None:
    """コードから t("...") で呼んでいるキーが、すべてカタログにあること。"""
    used = set(re.findall(r"""\bt\(\s*["']([\w.\-]+)["']""", _code()))
    assert not sorted(used - set(KEYS))


def test_no_unused_keys() -> None:
    """カタログのキーが、どれもコードのどこかで使われていること（文字列で持つものも含む）。"""
    code = _code()
    unused = [k for k in KEYS if f'"{k}"' not in code and f"'{k}'" not in code]
    assert not unused
