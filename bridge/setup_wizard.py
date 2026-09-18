"""初回セットアップの対話ウィザード。

exe（PyInstaller）から起動される想定で、次を順に案内する。

  1. Deep Rock Galactic を探す
  2. UE4SS を導入する
  3. MOD をコピーして mods.txt に登録する
  4. 自分の言語を選んでもらう
  5. 翻訳サービスを選んで APIキーを入力してもらう
  6. 実際に1回翻訳して疎通を確認する

ソースから `python bridge/drg_bridge.py --setup` でも同じものが動く。
"""

from __future__ import annotations

import io
import os
import shutil
import sys
import urllib.request
import zipfile

UE4SS_VERSION = "v3.0.1"
UE4SS_URL = (
    "https://github.com/UE4SS-RE/RE-UE4SS/releases/download/"
    f"{UE4SS_VERSION}/UE4SS_{UE4SS_VERSION}.zip"
)
MOD_NAME = "DRGTranslate"

# 自分の言語の候補。ラベルはゲームの言語設定の表記に寄せた
# （そのまま設定してもらうため）。
#
# ここに並べるのは translate.detect_language が文字種で見分けられる言語だけ。
# 一覧に無い言語（ドイツ語など）を選ばせると、受信は訳せても送信が動かない
# （ラテン文字は en と判定されるので DRGT_OUTGOING_SOURCE=de に一致しない）。
# そういう設定は README の「言語を変える」を読んで手で書いてもらう。
LANGUAGES = [
    ("ja", "日本語"),
    ("en", "English"),
    ("ko", "한국어"),
    ("zh", "简体中文"),
    ("zh-tw", "繁體中文"),
    ("ru", "Русский"),
]

# 送信・中継の既定に使う言語。DRG のチャットの大半がこの4つに収まる
BASE_LANGUAGES = ["ja", "en", "ko", "zh"]

PROVIDERS = [
    ("deepl", "DeepL", "DEEPL_AUTH_KEY", "https://www.deepl.com/pro-api",
     "機械翻訳。無料のお試し枠あり"),
    ("openai", "OpenAI", "OPENAI_API_KEY", "https://platform.openai.com/api-keys",
     "スラングや誤字に強い。従量課金"),
    ("claude", "Claude", "ANTHROPIC_API_KEY", "https://platform.claude.com/settings/keys",
     "スラングや誤字に強い。従量課金。既定は最安の Haiku"),
]


# ---------------------------------------------------------------------------
# 表示まわり
# ---------------------------------------------------------------------------

def title(text: str) -> None:
    print()
    print("=" * 64)
    print(f"  {text}")
    print("=" * 64)


def step(n: int, text: str) -> None:
    print(f"\n[{n}] {text}")


def ok(text: str) -> None:
    print(f"    OK  {text}")


def warn(text: str) -> None:
    print(f"    !!  {text}")


def ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    try:
        answer = input(f"    {prompt}{suffix}: ").strip()
    except EOFError:
        return default
    return answer or default


def ask_yes(prompt: str, default: bool = True) -> bool:
    hint = "Y/n" if default else "y/N"
    answer = ask(f"{prompt} ({hint})").lower()
    if not answer:
        return default
    return answer.startswith("y")


# ---------------------------------------------------------------------------
# 1. ゲームを探す
# ---------------------------------------------------------------------------

def _steam_paths() -> list[str]:
    roots: list[str] = []
    try:
        import winreg
        for hive, key in (
            (winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam"),
        ):
            try:
                with winreg.OpenKey(hive, key) as k:
                    roots.append(winreg.QueryValueEx(k, "SteamPath")[0].replace("/", "\\"))
                    break
            except OSError:
                continue
    except ImportError:
        pass  # Windows 以外

    # libraryfolders.vdf に別ドライブのライブラリが書いてある
    extra: list[str] = []
    for root in roots:
        vdf = os.path.join(root, "steamapps", "libraryfolders.vdf")
        if not os.path.exists(vdf):
            continue
        try:
            with open(vdf, encoding="utf-8", errors="replace") as f:
                for line in f:
                    if '"path"' in line:
                        parts = line.split('"')
                        if len(parts) >= 4:
                            extra.append(parts[3].replace("\\\\", "\\"))
        except OSError:
            pass
    roots.extend(extra)

    # X:\SteamLibrary もよくある配置
    for letter in "CDEFGHIJKLMNOPQRSTUVWXYZ":
        roots.append(f"{letter}:\\SteamLibrary")
    return roots


def find_game() -> str | None:
    seen: set[str] = set()
    for root in _steam_paths():
        path = os.path.join(root, "steamapps", "common", "Deep Rock Galactic")
        if path in seen:
            continue
        seen.add(path)
        if os.path.exists(os.path.join(path, "FSD", "Binaries", "Win64",
                                       "FSD-Win64-Shipping.exe")):
            return path
    return None


def resolve_game(preset: str | None = None) -> str | None:
    step(1, "Deep Rock Galactic を探しています")
    path = preset or find_game()
    if path:
        ok(path)
        if ask_yes("このフォルダで進めますか？"):
            return path
        path = None

    while True:
        warn("見つかりませんでした。")
        print("    Steam のライブラリで「管理 → ローカルファイルを閲覧」すると分かります。")
        answer = ask("Deep Rock Galactic のフォルダを貼り付けてください（空欄で中止）")
        if not answer:
            return None
        answer = answer.strip('"')
        if os.path.exists(os.path.join(answer, "FSD", "Binaries", "Win64",
                                       "FSD-Win64-Shipping.exe")):
            ok(answer)
            return answer
        warn("そのフォルダに FSD-Win64-Shipping.exe が見つかりません。")


# ---------------------------------------------------------------------------
# 2. UE4SS
# ---------------------------------------------------------------------------

def win64_dir(game: str) -> str:
    return os.path.join(game, "FSD", "Binaries", "Win64")


def find_ue4ss(game: str) -> str | None:
    base = win64_dir(game)
    for rel in ("UE4SS.dll", os.path.join("ue4ss", "UE4SS.dll")):
        path = os.path.join(base, rel)
        if os.path.exists(path):
            return path
    return None


def install_ue4ss(game: str) -> bool:
    step(2, "UE4SS を確認しています")
    found = find_ue4ss(game)
    if found:
        ok(f"導入済み: {found}")
        harden_ue4ss(game)   # 既存の導入でも設定だけは安全側に直す
        return True

    warn("UE4SS が入っていません。MOD の動作に必要です。")
    print(f"    取得元: {UE4SS_URL}")
    if not ask_yes("今すぐダウンロードして導入しますか？"):
        print("    中止しました。手動で導入してから、もう一度実行してください。")
        return False

    target = win64_dir(game)
    try:
        print("    ダウンロード中...")
        with urllib.request.urlopen(UE4SS_URL, timeout=60) as resp:
            data = resp.read()
        print(f"    展開中... ({len(data) // 1024} KB)")
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            z.extractall(target)
    except Exception as exc:  # noqa: BLE001
        warn(f"失敗しました: {exc}")
        print("    次のURLから手動でダウンロードし、中身を下記へ展開してください。")
        print(f"      {UE4SS_URL}")
        print(f"      {target}")
        return False

    ok(f"導入しました: {target}")
    harden_ue4ss(game)
    return True


# UE4SS の既定値のうち、クラッシュ要因になりうるものを落としておく。
#   bUseUObjectArrayCache : UObject 配列をキャッシュする。GC でオブジェクトが
#                           移動・破棄されると古いポインタを読んで
#                           EXCEPTION_ACCESS_VIOLATION になる（既知の不具合）
#   GuiConsoleEnabled     : 別ウィンドウのコンソール。翻訳には不要
#   EnableDumping         : オブジェクトダンプ。翻訳には不要
UE4SS_SAFE_SETTINGS = {
    "bUseUObjectArrayCache": "false",
    "GuiConsoleEnabled": "0",
    "EnableDumping": "0",
}

# UE4SS に同梱されるサンプル MOD。翻訳には一切不要なうえ、
# エンジン内部を広く書き換えるのでクラッシュ源になりやすい。
# Keybinds は RegisterKeyBind が依存するので残す。
UE4SS_KEEP_MODS = {"keybinds", MOD_NAME.lower()}


def harden_ue4ss(game: str) -> None:
    """UE4SS-settings.ini を安全側に倒す。"""
    path = os.path.join(win64_dir(game), "UE4SS-settings.ini")
    if not os.path.exists(path):
        return
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            lines = f.read().splitlines()
    except OSError as exc:  # noqa: BLE001
        warn(f"UE4SS-settings.ini を読めませんでした: {exc}")
        return

    changed = []
    for i, line in enumerate(lines):
        key = line.split("=", 1)[0].strip()
        if key in UE4SS_SAFE_SETTINGS:
            want = UE4SS_SAFE_SETTINGS[key]
            if line.split("=", 1)[1].strip() != want:
                lines[i] = f"{key} = {want}"
                changed.append(f"{key}={want}")

    if not changed:
        return
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        ok("UE4SS を安全な設定にしました（" + ", ".join(changed) + "）")
    except OSError as exc:  # noqa: BLE001
        warn(f"UE4SS-settings.ini を更新できませんでした: {exc}")


# ---------------------------------------------------------------------------
# 3. MOD のコピー
# ---------------------------------------------------------------------------

def mods_dir(game: str) -> str:
    base = win64_dir(game)
    for rel in ("ue4ss\\Mods", "Mods"):
        path = os.path.join(base, rel)
        if os.path.exists(path):
            return path
    path = os.path.join(base, "Mods")
    os.makedirs(path, exist_ok=True)
    return path


def install_mod(game: str, mod_source: str) -> bool:
    step(3, "MOD をコピーしています")
    if not os.path.isdir(mod_source):
        warn(f"MOD の元ファイルが見つかりません: {mod_source}")
        return False

    mods = mods_dir(game)
    dest = os.path.join(mods, MOD_NAME)
    try:
        if os.path.exists(dest):
            # 利用者が config.lua を編集している可能性があるので退避
            backup = os.path.join(mods, f"{MOD_NAME}.bak")
            shutil.rmtree(backup, ignore_errors=True)
            shutil.move(dest, backup)
            print(f"    既存の MOD は {MOD_NAME}.bak に退避しました")
        shutil.copytree(mod_source, dest)
    except OSError as exc:
        warn(f"コピーに失敗しました: {exc}")
        print("    ゲームを終了してから、もう一度実行してください。")
        return False
    ok(dest)

    # mods.txt に登録（UE4SS 3.x はこれを見る）
    mods_txt = os.path.join(mods, "mods.txt")
    lines: list[str] = []
    if os.path.exists(mods_txt):
        try:
            # UE4SS 同梱の mods.txt は BOM 付きなので utf-8-sig で読む
            with open(mods_txt, encoding="utf-8-sig", errors="replace") as f:
                lines = f.read().splitlines()
        except OSError:
            lines = []
    entry = f"{MOD_NAME} : 1"
    replaced = False
    disabled = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        # コメント行・空行・区切り行はそのまま
        if not stripped or stripped.startswith(";") or ":" not in stripped:
            continue
        name = stripped.split(":", 1)[0].strip()
        if name.lower() == MOD_NAME.lower():
            lines[i] = entry
            replaced = True
        elif name.lower() not in UE4SS_KEEP_MODS:
            # UE4SS 同梱のサンプル MOD は落としておく（翻訳には不要）
            if stripped.split(":", 1)[1].strip() != "0":
                lines[i] = f"{name} : 0"
                disabled.append(name)
    if not replaced:
        lines.append(entry)
    try:
        with open(mods_txt, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        ok(f"mods.txt に登録しました（{entry}）")
        if disabled:
            ok(f"同梱サンプル MOD を無効化しました（{', '.join(disabled)}）")
    except OSError as exc:
        warn(f"mods.txt を更新できませんでした: {exc}")
        return False
    return True


# ---------------------------------------------------------------------------
# 4. 言語 / 5. 翻訳サービスの設定
# ---------------------------------------------------------------------------

def language_settings(lang: str) -> dict[str, str]:
    """自分の言語から、言語まわりの設定をまとめて作る。

    1問で済ませたいのでここで全部決める。手で直すなら4か所
    （受信・送信の元・送信先・中継先）を揃えて書く必要があり、
    書き忘れると「日本語の発言に訳が付かないのに、自分の言語の発言は
    同じ言語へ訳させる」という壊れ方をするため。

    DRGT_INCOMING_SKIP_LANGUAGES は書かない。既定が受信の訳す先と同じに
    なるので、自分が読める言語を増やしたい人だけが足せばよい。
    """
    others = [x for x in BASE_LANGUAGES if x != lang]
    return {
        # 受信: 他の人の発言を自分の言語にする
        "DRGT_INCOMING_TARGET": lang,
        # 送信: 自分の言語で打った発言を訳す
        "DRGT_OUTGOING_SOURCE": lang,
        "DRGT_OUTGOING_TARGETS": ",".join(others),
        # 中継: 自分の言語を先頭に置く。ホスト（マルチ）では自分が読む訳も
        # この行から読むので、外すと自分の画面に何も出なくなる
        "DRGT_RELAY_TARGETS": ",".join([lang] + others),
    }


def choose_language(env_path: str, example_path: str) -> str:
    step(4, "あなたの言語を選んでください")
    print("      他の人の発言をこの言語に訳し、この言語で打った発言を他の言語に訳します。")
    for i, (code, label) in enumerate(LANGUAGES, 1):
        print(f"      {i}) {label} ({code})")
    print("      一覧に無い言語は、あとで settings.ini で変えられます")
    print("      （README の「言語を変える」）。")

    while True:
        answer = ask("番号", "1")
        if answer.isdigit() and 1 <= int(answer) <= len(LANGUAGES):
            lang, label = LANGUAGES[int(answer) - 1]
            break
        warn(f"1〜{len(LANGUAGES)} の数字を入れてください。")

    values = language_settings(lang)
    ensure_env_file(env_path, example_path)
    write_env(env_path, values)
    # このあとの疎通確認も、書いたものと同じ設定で動かす
    os.environ.update(values)
    ok(f"{label} に設定しました（受信→{lang} / 送信→{values['DRGT_OUTGOING_TARGETS']}）")
    return lang


def choose_provider() -> tuple[str, str, str, str]:
    step(5, "翻訳サービスを選んでください")
    for i, (_, label, _, _, note) in enumerate(PROVIDERS, 1):
        print(f"      {i}) {label:<8} {note}")
    while True:
        answer = ask("番号", "1")
        if answer.isdigit() and 1 <= int(answer) <= len(PROVIDERS):
            key, label, env, url, _ = PROVIDERS[int(answer) - 1]
            return key, label, env, url
        warn("1〜3 の数字を入れてください。")


def ensure_env_file(env_path: str, example_path: str) -> None:
    """設定ファイルが無ければ見本から作る。全項目の説明を残したいので上書きはしない。"""
    if not os.path.exists(env_path) and os.path.exists(example_path):
        shutil.copyfile(example_path, env_path)


def write_env(env_path: str, values: dict[str, str]) -> None:
    """既存の設定ファイルを壊さずに、渡された項目だけ書き換える。

    見本はすべてコメントアウトされているので、該当行があれば
    コメントを外した形で置き換える。無ければ末尾に足す。
    """
    lines: list[str] = []
    if os.path.exists(env_path):
        with open(env_path, encoding="utf-8") as f:
            lines = f.read().splitlines()

    def upsert(key: str, value: str) -> None:
        target = f"{key}={value}"
        for i, line in enumerate(lines):
            stripped = line.lstrip("#").strip()
            if stripped.split("=")[0].strip() == key:
                lines[i] = target
                return
        lines.append(target)

    for key, value in values.items():
        upsert(key, value)

    with open(env_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def configure(env_path: str, example_path: str) -> tuple[str, str] | None:
    provider, label, env_name, url = choose_provider()

    print(f"\n    {label} のAPIキーが必要です。")
    print(f"      取得先: {url}")
    if provider in ("openai", "claude"):
        pkg = "openai" if provider == "openai" else "anthropic"
        print(f"      ※ このexeには {pkg} が同梱済みです。追加インストールは不要です。")

    existing = os.environ.get(env_name, "").strip()
    if existing:
        masked = existing[:6] + "..." + existing[-4:] if len(existing) > 12 else "***"
        print(f"    既に設定されています: {masked}")
        if not ask_yes("入力し直しますか？", default=False):
            return provider, env_name

    while True:
        api_key = ask("APIキーを貼り付けてください（空欄で中止）")
        if not api_key:
            return None
        if len(api_key) < 8:
            warn("短すぎます。キー全体を貼り付けてください。")
            continue
        break

    ensure_env_file(env_path, example_path)
    write_env(env_path, {"DRGT_PROVIDER": provider, env_name: api_key})
    os.environ[env_name] = api_key
    os.environ["DRGT_PROVIDER"] = provider
    ok(f"保存しました: {env_path}")
    return provider, env_name


# ---------------------------------------------------------------------------
# 6. 疎通確認
# ---------------------------------------------------------------------------

def verify(build_bridge, lang: str = "ja") -> bool:
    step(6, "翻訳を1回試します")
    # 訳す先と同じ言語の見本だと、訳せたのか見て分からない
    sample = ("気をつけろ、大群が来るぞ" if lang.startswith("en")
              else "watch out, swarm incoming")
    try:
        bridge = build_bridge()
        problem = bridge.translator.provider.setup_problem()
        if problem:
            warn("設定が足りません:")
            for line in problem.splitlines():
                print(f"      {line}")
            return False
        translated, _ = bridge.translator.translate(sample, None, lang)
    except Exception as exc:  # noqa: BLE001
        warn(f"失敗しました: {exc}")
        print("    APIキーが正しいか、ネットワークに繋がっているか確認してください。")
        return False

    print(f"      {sample}")
    print(f"        → {translated}")
    ok("翻訳できました")
    return True


# ---------------------------------------------------------------------------
# 全体の流れ
# ---------------------------------------------------------------------------

def run(*, env_path: str, example_path: str, mod_source: str, build_bridge,
        game_path: str | None = None) -> bool:
    """セットアップを最後まで通す。成功したら True。"""
    title("DRGTranslate セットアップ")
    print("  Deep Rock Galactic のチャットを自動翻訳する MOD を導入します。")
    print("  途中でやめたい場合は、質問に空欄のまま Enter を押してください。")

    game = resolve_game(game_path)
    if not game:
        return False
    if not install_ue4ss(game):
        return False
    if not install_mod(game, mod_source):
        return False
    lang = choose_language(env_path, example_path)
    if not configure(env_path, example_path):
        return False
    if not verify(build_bridge, lang):
        warn("翻訳の確認に失敗しましたが、設定自体は保存されています。")
        print(f"    {env_path} を直してから、もう一度起動してください。")
        return False

    title("セットアップ完了")
    print("  このあと翻訳プロセスが起動します。")
    print("  この窓を開いたまま Deep Rock Galactic を起動してください。")
    print()
    game_lang = dict(LANGUAGES).get(lang, lang)
    print(f"  ・ゲームの言語設定を「{game_lang}」にしてください"
          "（フォントが読み込まれず、訳文が □□□ になります）")
    print("  ・ゲーム中は F9 で翻訳の ON/OFF を切り替えられます")
    print(f"  ・設定は {os.path.basename(env_path)} をメモ帳で開いて変えられます")
    print(f"  ・セットアップからやり直したいときは、{os.path.basename(env_path)} を削除してから")
    print("    もう一度起動してください")
    print()
    return True
