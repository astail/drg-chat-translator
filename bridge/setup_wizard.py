"""初回セットアップの対話ウィザード。

exe（PyInstaller）から起動される想定で、次を順に案内する。

  1. 自分の言語を選んでもらう（以降の案内はその言語で出す）
  2. Deep Rock Galactic を探す
  3. UE4SS を導入する
  4. MOD をコピーして mods.txt に登録する
  5. 翻訳サービスを選んで APIキーを入力してもらう
  6. 実際に1回翻訳して疎通を確認する

言語を最初に聞くのは、2番目以降の案内文をその言語で出すため。選んだ言語は
settings.ini の DRGT_UI_LANG に残るので、2回目以降の起動でも同じ言語で出る。

ソースから `python bridge/drg_bridge.py --setup` でも同じものが動く。
"""

from __future__ import annotations

import io
import os
import shutil
import urllib.request
import zipfile

import i18n
from i18n import t

UE4SS_VERSION = "v3.0.1"
UE4SS_URL = (
    "https://github.com/UE4SS-RE/RE-UE4SS/releases/download/"
    f"{UE4SS_VERSION}/UE4SS_{UE4SS_VERSION}.zip"
)
MOD_NAME = "DRGTranslate"

LANGUAGES = i18n.LANGUAGES

BASE_LANGUAGES = ["ja", "en", "ko", "zh"]

PROVIDERS = [
    ("deepl", "DeepL", "DEEPL_AUTH_KEY", "https://www.deepl.com/pro-api",
     "w.provider.deepl"),
    ("openai", "OpenAI", "OPENAI_API_KEY", "https://platform.openai.com/api-keys",
     "w.provider.openai"),
    ("claude", "Claude", "ANTHROPIC_API_KEY", "https://platform.claude.com/settings/keys",
     "w.provider.claude"),
]


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


def ask_choice(prompt: str, count: int) -> int:
    """1〜count の番号を聞く。戻り値は 0 始まりの添字。"""
    while True:
        answer = ask(prompt, "1")
        if answer.isdigit() and 1 <= int(answer) <= count:
            return int(answer) - 1
        warn(t("w.err.number", n=count))


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
        pass

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
    step(2, t("w.step.game"))
    path = preset or find_game()
    if path:
        ok(path)
        if ask_yes(t("w.game.use_this")):
            return path
        path = None

    while True:
        warn(t("w.game.not_found"))
        print(f"    {t('w.game.steam_hint')}")
        answer = ask(t("w.game.ask_path"))
        if not answer:
            return None
        answer = answer.strip('"')
        if os.path.exists(os.path.join(answer, "FSD", "Binaries", "Win64",
                                       "FSD-Win64-Shipping.exe")):
            ok(answer)
            return answer
        warn(t("w.game.no_exe"))


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
    step(3, t("w.step.ue4ss"))
    found = find_ue4ss(game)
    if found:
        ok(t("w.ue4ss.found", path=found))
        harden_ue4ss(game)
        return True

    warn(t("w.ue4ss.missing"))
    print(f"    {t('w.ue4ss.source', url=UE4SS_URL)}")
    if not ask_yes(t("w.ue4ss.ask")):
        print(f"    {t('w.ue4ss.cancel')}")
        return False

    target = win64_dir(game)
    try:
        print(f"    {t('w.ue4ss.downloading')}")
        with urllib.request.urlopen(UE4SS_URL, timeout=60) as resp:
            data = resp.read()
        print(f"    {t('w.ue4ss.extracting', kb=len(data) // 1024)}")
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            z.extractall(target)
    except Exception as exc:  # noqa: BLE001
        warn(t("w.failed", err=exc))
        print(f"    {t('w.ue4ss.manual')}")
        print(f"      {UE4SS_URL}")
        print(f"      {target}")
        return False

    ok(t("w.ue4ss.done", path=target))
    harden_ue4ss(game)
    return True


UE4SS_SAFE_SETTINGS = {
    "bUseUObjectArrayCache": "false",
    "GuiConsoleEnabled": "0",
    "EnableDumping": "0",
}

UE4SS_SAMPLE_MODS = {
    "cheatmanagerenablermod",
    "actordumpermod",
    "consolecommandsmod",
    "consoleenablermod",
    "splitscreenmod",
    "linetracemod",
    "bpmodloadermod",
    "bpml_genericfunctions",
    "jsbluaprofilermod",
}


def harden_ue4ss(game: str) -> None:
    """UE4SS-settings.ini を安全側に倒す。"""
    path = os.path.join(win64_dir(game), "UE4SS-settings.ini")
    if not os.path.exists(path):
        return
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            lines = f.read().splitlines()
    except OSError as exc:  # noqa: BLE001
        warn(t("w.ue4ss.read_failed", err=exc))
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
        ok(t("w.ue4ss.hardened", changed=", ".join(changed)))
    except OSError as exc:  # noqa: BLE001
        warn(t("w.ue4ss.write_failed", err=exc))


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
    step(4, t("w.step.mod"))
    if not os.path.isdir(mod_source):
        warn(t("w.mod.source_missing", path=mod_source))
        return False

    mods = mods_dir(game)
    dest = os.path.join(mods, MOD_NAME)
    try:
        if os.path.exists(dest):
            backup = os.path.join(mods, f"{MOD_NAME}.bak")
            shutil.rmtree(backup, ignore_errors=True)
            shutil.move(dest, backup)
            print(f"    {t('w.mod.backup', name=MOD_NAME)}")
        shutil.copytree(mod_source, dest)
    except OSError as exc:
        warn(t("w.mod.copy_failed", err=exc))
        print(f"    {t('w.mod.close_game')}")
        return False
    ok(dest)

    mods_txt = os.path.join(mods, "mods.txt")
    lines: list[str] = []
    if os.path.exists(mods_txt):
        try:
            with open(mods_txt, encoding="utf-8-sig", errors="replace") as f:
                lines = f.read().splitlines()
        except OSError:
            lines = []
    entry = f"{MOD_NAME} : 1"
    replaced = False
    disabled = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith(";") or ":" not in stripped:
            continue
        name = stripped.split(":", 1)[0].strip()
        if name.lower() == MOD_NAME.lower():
            lines[i] = entry
            replaced = True
        elif name.lower() in UE4SS_SAMPLE_MODS:
            if stripped.split(":", 1)[1].strip() != "0":
                lines[i] = f"{name} : 0"
                disabled.append(name)
    if not replaced:
        lines.append(entry)
    try:
        with open(mods_txt, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        ok(t("w.mod.registered", entry=entry))
        if disabled:
            ok(t("w.mod.samples_off", names=", ".join(disabled)))
    except OSError as exc:
        warn(t("w.mod.modstxt_failed", err=exc))
        return False
    return True


def language_settings(lang: str) -> dict[str, str]:
    """自分の言語から、言語まわりの設定をまとめて作る。"""
    others = [x for x in BASE_LANGUAGES if x != lang]
    relay = [lang] + others
    values = {
        "DRGT_UI_LANG": lang,
        "DRGT_INCOMING_TARGET": lang,
        "DRGT_INCOMING_FORMAT": ("[訳] {sender}: {text}" if lang == "ja"
                                 else "[TL] {sender}: {text}"),
        "DRGT_OUTGOING_SOURCE": lang,
        "DRGT_OUTGOING_TARGETS": ",".join(others),
        "DRGT_RELAY_TARGETS": ",".join(relay),
        "DRGT_RELAY_MAX_LANGS": str(len(relay)),
        # 言語判定は文字の種類で見るので zh-tw のような地域つきの言語は
        # 元の言語（zh）までしか分からない。書かないでおくと、やり直しで
        # 別の言語を選んだときに前の値が残ってしまうので、常に書く
        "DRGT_INCOMING_SKIP_LANGUAGES": lang.split("-")[0],
    }
    return values


def choose_language() -> str:
    """最初の質問。ここから先の案内は選ばれた言語で出す。

    まだ言語が分からない時点の問いかけなので、この節だけ日本語と英語を併記する。
    書き込みは save_language で、APIキーが入ったあとに行う。
    """
    step(1, "言語を選んでください / Choose your language")
    print("      セットアップの案内と、他の人の発言の訳がこの言語になります。")
    print("      Setup and the chat you read are shown in this language.")
    for i, (code, label) in enumerate(LANGUAGES, 1):
        print(f"      {i}) {label} ({code})")

    index = ask_choice("番号 / number", len(LANGUAGES))
    lang, label = LANGUAGES[index]
    i18n.set_lang(lang)

    values = language_settings(lang)
    ok(t("w.lang.ok", label=label, lang=lang, targets=values["DRGT_OUTGOING_TARGETS"]))
    print(f"      {t('w.lang.note')}")
    return lang


def save_language(env_path: str, example_path: str, lang: str) -> None:
    """選んだ言語を設定ファイルへ書く。APIキーが入ったあとに呼ぶ。"""
    values = language_settings(lang)
    ensure_env_file(env_path, example_path)
    write_env(env_path, values)
    os.environ.update(values)


def choose_provider() -> tuple[str, str, str, str]:
    step(5, t("w.step.provider"))
    for i, (_, label, _, _, note_key) in enumerate(PROVIDERS, 1):
        print(f"      {i}) {label:<8} {t(note_key)}")
    key, label, env, url, _ = PROVIDERS[ask_choice(t("w.prompt.number"), len(PROVIDERS))]
    return key, label, env, url


def ensure_env_file(env_path: str, example_path: str) -> None:
    """設定ファイルが無ければ見本から作る。全項目の説明を残したいので上書きはしない。"""
    if not os.path.exists(env_path) and os.path.exists(example_path):
        shutil.copyfile(example_path, env_path)


def write_env(env_path: str, values: dict[str, str]) -> None:
    """既存の設定ファイルを壊さずに、渡された項目だけ書き換える。"""
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

    print(f"\n    {t('w.key.need', label=label)}")
    print(f"      {t('w.key.where', url=url)}")
    if provider in ("openai", "claude"):
        pkg = "openai" if provider == "openai" else "anthropic"
        print(f"      {t('w.key.bundled', pkg=pkg)}")

    existing = os.environ.get(env_name, "").strip()
    reuse = False
    if existing:
        masked = existing[:6] + "..." + existing[-4:] if len(existing) > 12 else "***"
        print(f"    {t('w.key.existing', masked=masked)}")
        reuse = not ask_yes(t("w.key.reenter"), default=False)

    values = {"DRGT_PROVIDER": provider}
    if not reuse:
        # 入力を空欄で終えたら、設定ファイルを作らずに中止する。
        # ここから下の書き込みには進まないこと
        while True:
            api_key = ask(t("w.key.ask"))
            if not api_key:
                return None
            if len(api_key) < 8:
                warn(t("w.key.short"))
                continue
            break
        values[env_name] = api_key
        os.environ[env_name] = api_key

    ensure_env_file(env_path, example_path)
    write_env(env_path, values)
    os.environ["DRGT_PROVIDER"] = provider
    ok(t("w.saved", path=env_path))
    return provider, env_name


def verify(build_bridge, lang: str = "ja") -> bool:
    step(6, t("w.step.verify"))
    sample = ("気をつけろ、大群が来るぞ" if lang.startswith("en")
              else "watch out, swarm incoming")
    try:
        bridge = build_bridge()
        problem = bridge.translator.provider.setup_problem()
        if problem:
            warn(t("w.verify.missing"))
            for line in problem.splitlines():
                print(f"      {line}")
            return False
        translated, _ = bridge.translator.translate(sample, None, lang)
    except Exception as exc:  # noqa: BLE001
        warn(t("w.failed", err=exc))
        print(f"    {t('w.verify.check')}")
        return False

    print(f"      {sample}")
    print(f"        → {translated}")
    ok(t("w.verify.ok"))
    return True


def run(*, env_path: str, example_path: str, mod_source: str, build_bridge,
        game_path: str | None = None) -> bool:
    """セットアップを最後まで通す。成功したら True。"""
    title("DRGTranslate")
    lang = choose_language()

    title(t("w.title"))
    print(f"  {t('w.intro')}")
    print(f"  {t('w.intro.cancel')}")

    game = resolve_game(game_path)
    if not game:
        return False
    if not install_ue4ss(game):
        return False
    if not install_mod(game, mod_source):
        return False
    if not configure(env_path, example_path):
        return False
    save_language(env_path, example_path, lang)
    if not verify(build_bridge, lang):
        warn(t("w.verify.saved_anyway"))
        print(f"    {t('w.verify.fix_restart', path=env_path)}")
        return False

    title(t("w.done.title"))
    print(f"  {t('w.done.starting')}")
    print(f"  {t('w.done.keep_open')}")
    print()
    ini = os.path.basename(env_path)
    print(f"  {t('w.done.game_lang', lang=i18n.label(lang))}")
    print(f"  {t('w.done.f9')}")
    print(f"  {t('w.done.settings', ini=ini)}")
    print(f"  {t('w.done.redo', ini=ini)}")
    print(f"  {t('w.done.readme', readme=i18n.readme(lang))}")
    print()
    return True
