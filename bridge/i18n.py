"""利用者向けメッセージの言語切り替え。

セットアップの案内文と、起動後に黒い窓へ出るメッセージをここにまとめてある。
初回セットアップで選んだ言語が settings.ini の DRGT_UI_LANG に書かれ、
2回目以降の起動でもその言語で表示される。

  init()      settings.ini（= os.environ）から表示言語を決める
  set_lang()  言語を直接指定する（セットアップの言語選択で使う）
  t()         キーからその言語の文言を取り出す

対応していない言語や、訳が抜けているキーは英語にフォールバックする。
言語を増やすときは LANGUAGES に1行足し、_M の各キーにその言語を書く
（書き忘れたキーは英語で出るだけで、落ちはしない）。
"""

from __future__ import annotations

import os
import sys

# 表示言語として選べるもの。(コード, その言語での表記)
LANGUAGES: list[tuple[str, str]] = [
    ("ja", "日本語"),
    ("en", "English"),
    ("ko", "한국어"),
    ("zh", "简体中文"),
    ("zh-tw", "繁體中文"),
    ("ru", "Русский"),
]

LANG_CODES = [code for code, _ in LANGUAGES]
FALLBACK = "en"

REPO_URL = "https://github.com/astail/drg-chat-translator"

_lang = FALLBACK


def normalize(code: str | None) -> str | None:
    """`ja_JP` `zh-TW` のような書き方を LANGUAGES のコードに寄せる。無理なら None。"""
    if not code:
        return None
    value = code.strip().lower().replace("_", "-")
    if value in LANG_CODES:
        return value
    base = value.split("-", 1)[0]
    return base if base in LANG_CODES else None


def set_lang(code: str | None) -> str:
    """表示言語を決める。対応していない言語なら英語にする。"""
    global _lang
    _lang = normalize(code) or FALLBACK
    return _lang


def current() -> str:
    return _lang


def label(code: str) -> str:
    """言語コードから、その言語での表記を返す。"""
    return dict(LANGUAGES).get(normalize(code) or "", code)


def readme(code: str | None = None) -> str:
    """その言語の README の場所。

    zip には README を同梱していない（手引きの README.txt だけ）ので、
    ファイル名ではなく GitHub の URL を返す。日本語版だけ接尾辞が付かない。
    """
    lang = normalize(code) if code else _lang
    if lang in (None, "ja"):
        return f"{REPO_URL}/blob/main/README.md"
    name = "zh-TW" if lang == "zh-tw" else lang
    return f"{REPO_URL}/blob/main/README.{name}.md"


def _windows_ui_lang() -> str | None:
    """Windows の表示言語を BCP-47（ja-JP / zh-TW など）で聞く。

    Windows は LANG などの環境変数を持たないので OS に直接聞く。
    locale.getdefaultlocale() は Python 3.15 で消えるため使わない。
    """
    try:
        import ctypes
        lcid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
        buf = ctypes.create_unicode_buffer(85)  # LOCALE_NAME_MAX_LENGTH
        if ctypes.windll.kernel32.LCIDToLocaleName(lcid, buf, len(buf), 0):
            return normalize(buf.value)
    except Exception:  # noqa: BLE001
        pass
    return None


def _os_lang() -> str | None:
    """OS の言語設定。どちらの設定も無い人に、いきなり英語を出さないための保険。"""
    for value in (os.environ.get("LC_ALL"), os.environ.get("LC_MESSAGES"),
                  os.environ.get("LANG")):
        lang = normalize((value or "").split(".")[0])
        if lang:
            return lang
    if sys.platform == "win32":
        return _windows_ui_lang()
    try:
        import locale
        return normalize((locale.getlocale()[0] or "").split(".")[0])
    except Exception:  # noqa: BLE001
        return None


def init() -> str:
    """設定から表示言語を決める。

    DRGT_UI_LANG が最優先。無ければ受信の翻訳先（= その人が読む言語）、
    それも無ければ OS の言語を見る。DRGT_UI_LANG を持たない古い settings.ini
    でも、これまでどおりの言語で出る。

    順に normalize して、最初に解決したものを採る。対応していない言語が
    途中に入っていても（受信を de にしている等）、そこで英語に落ちずに
    次の候補を見る。
    """
    for candidate in (os.environ.get("DRGT_UI_LANG"),
                      os.environ.get("DRGT_INCOMING_TARGET"),
                      _os_lang()):
        if normalize(candidate):
            return set_lang(candidate)
    return set_lang(None)


def t(key: str, /, **kwargs: object) -> str:
    """メッセージを取り出す。kwargs があれば {name} を埋める。

    キーは位置専用。文言側に {key} という差し込みがあるため
    （p.need_key など）、キーワード引数と名前がぶつからないようにしている。
    """
    entry = _M.get(key)
    if entry is None:
        return key
    text = entry.get(_lang) or entry.get(FALLBACK) or key
    return text.format(**kwargs) if kwargs else text


_M: dict[str, dict[str, str]] = {}


# ---------------------------------------------------------------------------
# 初回セットアップ（setup_wizard.py）
# ---------------------------------------------------------------------------

_M.update({
    "w.title": {
        "ja": "DRGTranslate セットアップ",
        "en": "DRGTranslate setup",
        "ko": "DRGTranslate 설치",
        "zh": "DRGTranslate 安装设置",
        "zh-tw": "DRGTranslate 安裝設定",
        "ru": "Установка DRGTranslate",
    },
    "w.intro": {
        "ja": "Deep Rock Galactic のチャットを自動翻訳する MOD を導入します。",
        "en": "This installs a mod that translates Deep Rock Galactic chat for you.",
        "ko": "Deep Rock Galactic 채팅을 자동 번역하는 모드를 설치합니다.",
        "zh": "将安装一个自动翻译 Deep Rock Galactic 聊天的 MOD。",
        "zh-tw": "將安裝一個自動翻譯 Deep Rock Galactic 聊天的 MOD。",
        "ru": "Будет установлен мод, который переводит чат Deep Rock Galactic.",
    },
    "w.intro.cancel": {
        "ja": "途中でやめたい場合は、質問に空欄のまま Enter を押してください。",
        "en": "To stop at any point, leave an answer blank and press Enter.",
        "ko": "도중에 그만두려면 질문에 아무것도 입력하지 말고 Enter 를 누르세요.",
        "zh": "想中途退出时，在提问处直接按 Enter 留空即可。",
        "zh-tw": "想中途退出時，在提問處直接按 Enter 留空即可。",
        "ru": "Чтобы прервать установку, оставьте ответ пустым и нажмите Enter.",
    },
    "w.prompt.number": {
        "ja": "番号", "en": "number", "ko": "번호",
        "zh": "编号", "zh-tw": "編號", "ru": "номер",
    },
    "w.err.number": {
        "ja": "1〜{n} の数字を入れてください。",
        "en": "Enter a number from 1 to {n}.",
        "ko": "1 부터 {n} 까지의 숫자를 입력하세요.",
        "zh": "请输入 1 到 {n} 之间的数字。",
        "zh-tw": "請輸入 1 到 {n} 之間的數字。",
        "ru": "Введите число от 1 до {n}.",
    },
    "w.failed": {
        "ja": "失敗しました: {err}",
        "en": "Failed: {err}",
        "ko": "실패했습니다: {err}",
        "zh": "失败: {err}",
        "zh-tw": "失敗: {err}",
        "ru": "Ошибка: {err}",
    },
    "w.saved": {
        "ja": "保存しました: {path}",
        "en": "Saved: {path}",
        "ko": "저장했습니다: {path}",
        "zh": "已保存: {path}",
        "zh-tw": "已儲存: {path}",
        "ru": "Сохранено: {path}",
    },

    # --- 言語選択 ---
    "w.lang.ok": {
        "ja": "{label} にします（受信→{lang} / 送信→{targets}）",
        "en": "Using {label} (incoming -> {lang} / outgoing -> {targets})",
        "ko": "{label} 로 설정합니다 (수신 -> {lang} / 송신 -> {targets})",
        "zh": "将使用 {label}（接收 -> {lang} / 发送 -> {targets}）",
        "zh-tw": "將使用 {label}（接收 -> {lang} / 發送 -> {targets}）",
        "ru": "Выбран {label} (входящие -> {lang} / исходящие -> {targets})",
    },
    "w.lang.note": {
        "ja": "一覧に無い言語は、あとで settings.ini で変えられます（README の「言語を変える」）。",
        "en": "Languages that are not listed can be set later in settings.ini"
              " (\"Change the language\" in the README).",
        "ko": "목록에 없는 언어는 나중에 settings.ini 에서 바꿀 수 있습니다"
              " (README 의 \"언어 바꾸기\").",
        "zh": "列表中没有的语言，之后可以在 settings.ini 中修改（见 README 的“更改语言”）。",
        "zh-tw": "清單中沒有的語言，之後可以在 settings.ini 中修改（見 README 的「變更語言」）。",
        "ru": "Языки, которых нет в списке, можно задать позже в settings.ini"
              " (раздел «Смена языка» в README).",
    },

    # --- ゲームを探す ---
    "w.step.game": {
        "ja": "Deep Rock Galactic を探しています",
        "en": "Looking for Deep Rock Galactic",
        "ko": "Deep Rock Galactic 을 찾는 중입니다",
        "zh": "正在查找 Deep Rock Galactic",
        "zh-tw": "正在尋找 Deep Rock Galactic",
        "ru": "Поиск Deep Rock Galactic",
    },
    "w.game.use_this": {
        "ja": "このフォルダで進めますか？",
        "en": "Continue with this folder?",
        "ko": "이 폴더로 진행할까요?",
        "zh": "使用这个文件夹继续吗？",
        "zh-tw": "使用這個資料夾繼續嗎？",
        "ru": "Продолжить с этой папкой?",
    },
    "w.game.not_found": {
        "ja": "見つかりませんでした。",
        "en": "Not found.",
        "ko": "찾지 못했습니다.",
        "zh": "没有找到。",
        "zh-tw": "沒有找到。",
        "ru": "Не найдено.",
    },
    "w.game.steam_hint": {
        "ja": "Steam のライブラリで「管理 → ローカルファイルを閲覧」すると分かります。",
        "en": "In your Steam library, use \"Manage -> Browse local files\" to find it.",
        "ko": "Steam 라이브러리에서 \"관리 -> 로컬 파일 보기\" 로 확인할 수 있습니다.",
        "zh": "在 Steam 库中通过“管理 -> 浏览本地文件”可以找到。",
        "zh-tw": "在 Steam 程式庫中透過「管理 -> 瀏覽本機檔案」即可找到。",
        "ru": "В библиотеке Steam: «Управление -> Посмотреть локальные файлы».",
    },
    "w.game.ask_path": {
        "ja": "Deep Rock Galactic のフォルダを貼り付けてください（空欄で中止）",
        "en": "Paste the Deep Rock Galactic folder (blank to cancel)",
        "ko": "Deep Rock Galactic 폴더를 붙여넣으세요 (비워 두면 취소)",
        "zh": "请粘贴 Deep Rock Galactic 文件夹的路径（留空则取消）",
        "zh-tw": "請貼上 Deep Rock Galactic 資料夾的路徑（留空則取消）",
        "ru": "Вставьте путь к папке Deep Rock Galactic (пусто — отмена)",
    },
    "w.game.no_exe": {
        "ja": "そのフォルダに FSD-Win64-Shipping.exe が見つかりません。",
        "en": "FSD-Win64-Shipping.exe is not in that folder.",
        "ko": "그 폴더에 FSD-Win64-Shipping.exe 가 없습니다.",
        "zh": "该文件夹中没有 FSD-Win64-Shipping.exe。",
        "zh-tw": "該資料夾中沒有 FSD-Win64-Shipping.exe。",
        "ru": "В этой папке нет FSD-Win64-Shipping.exe.",
    },

    # --- UE4SS ---
    "w.step.ue4ss": {
        "ja": "UE4SS を確認しています",
        "en": "Checking UE4SS",
        "ko": "UE4SS 를 확인하는 중입니다",
        "zh": "正在检查 UE4SS",
        "zh-tw": "正在檢查 UE4SS",
        "ru": "Проверка UE4SS",
    },
    "w.ue4ss.found": {
        "ja": "導入済み: {path}",
        "en": "Already installed: {path}",
        "ko": "이미 설치됨: {path}",
        "zh": "已安装: {path}",
        "zh-tw": "已安裝: {path}",
        "ru": "Уже установлен: {path}",
    },
    "w.ue4ss.missing": {
        "ja": "UE4SS が入っていません。MOD の動作に必要です。",
        "en": "UE4SS is not installed. The mod needs it to run.",
        "ko": "UE4SS 가 설치되어 있지 않습니다. 모드 동작에 필요합니다.",
        "zh": "尚未安装 UE4SS。MOD 需要它才能运行。",
        "zh-tw": "尚未安裝 UE4SS。MOD 需要它才能運作。",
        "ru": "UE4SS не установлен. Он нужен для работы мода.",
    },
    "w.ue4ss.source": {
        "ja": "取得元: {url}",
        "en": "Source: {url}",
        "ko": "다운로드 주소: {url}",
        "zh": "下载地址: {url}",
        "zh-tw": "下載網址: {url}",
        "ru": "Источник: {url}",
    },
    "w.ue4ss.ask": {
        "ja": "今すぐダウンロードして導入しますか？",
        "en": "Download and install it now?",
        "ko": "지금 다운로드해서 설치할까요?",
        "zh": "现在下载并安装吗？",
        "zh-tw": "現在下載並安裝嗎？",
        "ru": "Скачать и установить сейчас?",
    },
    "w.ue4ss.cancel": {
        "ja": "中止しました。手動で導入してから、もう一度実行してください。",
        "en": "Cancelled. Install it yourself, then run this again.",
        "ko": "중단했습니다. 직접 설치한 뒤 다시 실행하세요.",
        "zh": "已中止。请手动安装后再次运行。",
        "zh-tw": "已中止。請手動安裝後再次執行。",
        "ru": "Отменено. Установите его вручную и запустите снова.",
    },
    "w.ue4ss.downloading": {
        "ja": "ダウンロード中...",
        "en": "Downloading...",
        "ko": "다운로드 중...",
        "zh": "正在下载...",
        "zh-tw": "正在下載...",
        "ru": "Загрузка...",
    },
    "w.ue4ss.extracting": {
        "ja": "展開中... ({kb} KB)",
        "en": "Extracting... ({kb} KB)",
        "ko": "압축을 푸는 중... ({kb} KB)",
        "zh": "正在解压... ({kb} KB)",
        "zh-tw": "正在解壓縮... ({kb} KB)",
        "ru": "Распаковка... ({kb} KB)",
    },
    "w.ue4ss.manual": {
        "ja": "次のURLから手動でダウンロードし、中身を下記へ展開してください。",
        "en": "Download it manually from this URL and extract the contents here.",
        "ko": "아래 주소에서 직접 내려받아 다음 위치에 풀어 주세요.",
        "zh": "请从下面的地址手动下载，并把内容解压到下面的位置。",
        "zh-tw": "請從下面的網址手動下載，並把內容解壓縮到下面的位置。",
        "ru": "Скачайте его вручную по этой ссылке и распакуйте содержимое сюда.",
    },
    "w.ue4ss.done": {
        "ja": "導入しました: {path}",
        "en": "Installed: {path}",
        "ko": "설치했습니다: {path}",
        "zh": "已安装: {path}",
        "zh-tw": "已安裝: {path}",
        "ru": "Установлено: {path}",
    },
    "w.ue4ss.read_failed": {
        "ja": "UE4SS-settings.ini を読めませんでした: {err}",
        "en": "Could not read UE4SS-settings.ini: {err}",
        "ko": "UE4SS-settings.ini 를 읽지 못했습니다: {err}",
        "zh": "无法读取 UE4SS-settings.ini: {err}",
        "zh-tw": "無法讀取 UE4SS-settings.ini: {err}",
        "ru": "Не удалось прочитать UE4SS-settings.ini: {err}",
    },
    "w.ue4ss.hardened": {
        "ja": "UE4SS を安全な設定にしました（{changed}）",
        "en": "Set UE4SS to safer values ({changed})",
        "ko": "UE4SS 를 안전한 설정으로 바꿨습니다 ({changed})",
        "zh": "已把 UE4SS 调整为更安全的设置（{changed}）",
        "zh-tw": "已把 UE4SS 調整為更安全的設定（{changed}）",
        "ru": "UE4SS переведён на безопасные настройки ({changed})",
    },
    "w.ue4ss.write_failed": {
        "ja": "UE4SS-settings.ini を更新できませんでした: {err}",
        "en": "Could not update UE4SS-settings.ini: {err}",
        "ko": "UE4SS-settings.ini 를 수정하지 못했습니다: {err}",
        "zh": "无法更新 UE4SS-settings.ini: {err}",
        "zh-tw": "無法更新 UE4SS-settings.ini: {err}",
        "ru": "Не удалось обновить UE4SS-settings.ini: {err}",
    },

    # --- MOD のコピー ---
    "w.step.mod": {
        "ja": "MOD をコピーしています",
        "en": "Copying the mod",
        "ko": "모드를 복사하는 중입니다",
        "zh": "正在复制 MOD",
        "zh-tw": "正在複製 MOD",
        "ru": "Копирование мода",
    },
    "w.mod.source_missing": {
        "ja": "MOD の元ファイルが見つかりません: {path}",
        "en": "The mod files are missing: {path}",
        "ko": "모드 원본 파일을 찾을 수 없습니다: {path}",
        "zh": "找不到 MOD 的源文件: {path}",
        "zh-tw": "找不到 MOD 的原始檔案: {path}",
        "ru": "Файлы мода не найдены: {path}",
    },
    "w.mod.backup": {
        "ja": "既存の MOD は {name}.bak に退避しました",
        "en": "The existing mod was moved to {name}.bak",
        "ko": "기존 모드는 {name}.bak 으로 옮겼습니다",
        "zh": "已把原有的 MOD 移动到 {name}.bak",
        "zh-tw": "已把原有的 MOD 移動到 {name}.bak",
        "ru": "Прежний мод перемещён в {name}.bak",
    },
    "w.mod.copy_failed": {
        "ja": "コピーに失敗しました: {err}",
        "en": "Copy failed: {err}",
        "ko": "복사에 실패했습니다: {err}",
        "zh": "复制失败: {err}",
        "zh-tw": "複製失敗: {err}",
        "ru": "Не удалось скопировать: {err}",
    },
    "w.mod.close_game": {
        "ja": "ゲームを終了してから、もう一度実行してください。",
        "en": "Close the game, then run this again.",
        "ko": "게임을 종료한 뒤 다시 실행하세요.",
        "zh": "请先退出游戏，然后再次运行。",
        "zh-tw": "請先關閉遊戲，然後再次執行。",
        "ru": "Закройте игру и запустите снова.",
    },
    "w.mod.registered": {
        "ja": "mods.txt に登録しました（{entry}）",
        "en": "Registered in mods.txt ({entry})",
        "ko": "mods.txt 에 등록했습니다 ({entry})",
        "zh": "已写入 mods.txt（{entry}）",
        "zh-tw": "已寫入 mods.txt（{entry}）",
        "ru": "Записано в mods.txt ({entry})",
    },
    "w.mod.samples_off": {
        "ja": "同梱サンプル MOD を無効化しました（{names}）",
        "en": "Disabled the sample mods bundled with UE4SS ({names})",
        "ko": "UE4SS 에 들어 있는 예제 모드를 껐습니다 ({names})",
        "zh": "已禁用 UE4SS 自带的示例 MOD（{names}）",
        "zh-tw": "已停用 UE4SS 內建的範例 MOD（{names}）",
        "ru": "Отключены примеры модов из UE4SS ({names})",
    },
    "w.mod.modstxt_failed": {
        "ja": "mods.txt を更新できませんでした: {err}",
        "en": "Could not update mods.txt: {err}",
        "ko": "mods.txt 를 수정하지 못했습니다: {err}",
        "zh": "无法更新 mods.txt: {err}",
        "zh-tw": "無法更新 mods.txt: {err}",
        "ru": "Не удалось обновить mods.txt: {err}",
    },
})

_M.update({
    # --- 翻訳サービスとAPIキー ---
    "w.step.provider": {
        "ja": "翻訳サービスを選んでください",
        "en": "Choose a translation service",
        "ko": "번역 서비스를 선택하세요",
        "zh": "请选择翻译服务",
        "zh-tw": "請選擇翻譯服務",
        "ru": "Выберите сервис перевода",
    },
    "w.provider.deepl": {
        "ja": "機械翻訳。無料のお試し枠あり",
        "en": "Machine translation. Has a free tier",
        "ko": "기계 번역. 무료 체험 한도 있음",
        "zh": "机器翻译。有免费额度",
        "zh-tw": "機器翻譯。有免費額度",
        "ru": "Машинный перевод. Есть бесплатный тариф",
    },
    "w.provider.openai": {
        "ja": "スラングや誤字に強い。従量課金",
        "en": "Good with slang and typos. Pay as you go",
        "ko": "속어와 오타에 강함. 쓴 만큼 과금",
        "zh": "擅长俚语和错别字。按用量计费",
        "zh-tw": "擅長俚語和錯字。按用量計費",
        "ru": "Хорош со сленгом и опечатками. Оплата по факту",
    },
    "w.provider.claude": {
        "ja": "スラングや誤字に強い。従量課金。既定は最安の Haiku",
        "en": "Good with slang and typos. Pay as you go. Cheapest Haiku by default",
        "ko": "속어와 오타에 강함. 쓴 만큼 과금. 기본값은 가장 저렴한 Haiku",
        "zh": "擅长俚语和错别字。按用量计费。默认用最便宜的 Haiku",
        "zh-tw": "擅長俚語和錯字。按用量計費。預設用最便宜的 Haiku",
        "ru": "Хорош со сленгом и опечатками. Оплата по факту. По умолчанию дешёвый Haiku",
    },
    "w.key.need": {
        "ja": "{label} のAPIキーが必要です。",
        "en": "You need an API key for {label}.",
        "ko": "{label} 의 API 키가 필요합니다.",
        "zh": "需要 {label} 的 API 密钥。",
        "zh-tw": "需要 {label} 的 API 金鑰。",
        "ru": "Нужен API-ключ для {label}.",
    },
    "w.key.where": {
        "ja": "取得先: {url}",
        "en": "Get one at: {url}",
        "ko": "발급 주소: {url}",
        "zh": "获取地址: {url}",
        "zh-tw": "取得網址: {url}",
        "ru": "Получить здесь: {url}",
    },
    "w.key.bundled": {
        "ja": "※ このexeには {pkg} が同梱済みです。追加インストールは不要です。",
        "en": "Note: {pkg} is bundled in this exe. Nothing else to install.",
        "ko": "참고: 이 exe 에 {pkg} 가 들어 있습니다. 따로 설치할 필요 없습니다.",
        "zh": "注意: 该 exe 已内置 {pkg}，无需另外安装。",
        "zh-tw": "注意: 該 exe 已內建 {pkg}，無需另外安裝。",
        "ru": "{pkg} уже встроен в этот exe — ставить ничего не нужно.",
    },
    "w.key.existing": {
        "ja": "既に設定されています: {masked}",
        "en": "Already set: {masked}",
        "ko": "이미 설정되어 있습니다: {masked}",
        "zh": "已经设置: {masked}",
        "zh-tw": "已經設定: {masked}",
        "ru": "Уже задан: {masked}",
    },
    "w.key.reenter": {
        "ja": "入力し直しますか？",
        "en": "Enter it again?",
        "ko": "다시 입력할까요?",
        "zh": "要重新输入吗？",
        "zh-tw": "要重新輸入嗎？",
        "ru": "Ввести заново?",
    },
    "w.key.ask": {
        "ja": "APIキーを貼り付けてください（空欄で中止）",
        "en": "Paste your API key (blank to cancel)",
        "ko": "API 키를 붙여넣으세요 (비워 두면 취소)",
        "zh": "请粘贴 API 密钥（留空则取消）",
        "zh-tw": "請貼上 API 金鑰（留空則取消）",
        "ru": "Вставьте API-ключ (пусто — отмена)",
    },
    "w.key.short": {
        "ja": "短すぎます。キー全体を貼り付けてください。",
        "en": "That is too short. Paste the whole key.",
        "ko": "너무 짧습니다. 키 전체를 붙여넣으세요.",
        "zh": "太短了。请粘贴完整的密钥。",
        "zh-tw": "太短了。請貼上完整的金鑰。",
        "ru": "Слишком короткий. Вставьте ключ целиком.",
    },

    # --- 疎通確認 ---
    "w.step.verify": {
        "ja": "翻訳を1回試します",
        "en": "Testing one translation",
        "ko": "번역을 한 번 시험합니다",
        "zh": "试着翻译一次",
        "zh-tw": "試著翻譯一次",
        "ru": "Пробный перевод",
    },
    "w.verify.missing": {
        "ja": "設定が足りません:",
        "en": "Something is missing:",
        "ko": "설정이 부족합니다:",
        "zh": "设置还不完整:",
        "zh-tw": "設定還不完整:",
        "ru": "Не хватает настроек:",
    },
    "w.verify.check": {
        "ja": "APIキーが正しいか、ネットワークに繋がっているか確認してください。",
        "en": "Check that the API key is correct and that you are online.",
        "ko": "API 키가 맞는지, 인터넷에 연결되어 있는지 확인하세요.",
        "zh": "请确认 API 密钥是否正确、网络是否连通。",
        "zh-tw": "請確認 API 金鑰是否正確、網路是否連通。",
        "ru": "Проверьте, верен ли API-ключ и есть ли подключение к сети.",
    },
    "w.verify.ok": {
        "ja": "翻訳できました",
        "en": "Translation works",
        "ko": "번역에 성공했습니다",
        "zh": "翻译成功",
        "zh-tw": "翻譯成功",
        "ru": "Перевод работает",
    },
    "w.verify.saved_anyway": {
        "ja": "翻訳の確認に失敗しましたが、設定自体は保存されています。",
        "en": "The test translation failed, but your settings were saved.",
        "ko": "번역 확인에는 실패했지만 설정은 저장되었습니다.",
        "zh": "翻译测试失败，但设置已经保存。",
        "zh-tw": "翻譯測試失敗，但設定已經儲存。",
        "ru": "Пробный перевод не удался, но настройки сохранены.",
    },
    "w.verify.fix_restart": {
        "ja": "{path} を直してから、もう一度起動してください。",
        "en": "Fix {path}, then start the program again.",
        "ko": "{path} 를 고친 뒤 다시 실행하세요.",
        "zh": "请修改 {path} 后重新启动。",
        "zh-tw": "請修改 {path} 後重新啟動。",
        "ru": "Исправьте {path} и запустите программу снова.",
    },

    # --- 完了 ---
    "w.done.title": {
        "ja": "セットアップ完了",
        "en": "Setup complete",
        "ko": "설치 완료",
        "zh": "设置完成",
        "zh-tw": "設定完成",
        "ru": "Установка завершена",
    },
    "w.done.starting": {
        "ja": "このあと翻訳プロセスが起動します。",
        "en": "The translator starts next.",
        "ko": "이제 번역 프로세스가 시작됩니다.",
        "zh": "接下来将启动翻译程序。",
        "zh-tw": "接下來將啟動翻譯程式。",
        "ru": "Сейчас запустится процесс перевода.",
    },
    "w.done.keep_open": {
        "ja": "この窓を開いたまま Deep Rock Galactic を起動してください。",
        "en": "Leave this window open and start Deep Rock Galactic.",
        "ko": "이 창을 열어 둔 채로 Deep Rock Galactic 을 실행하세요.",
        "zh": "请保持这个窗口打开，然后启动 Deep Rock Galactic。",
        "zh-tw": "請保持這個視窗開啟，然後啟動 Deep Rock Galactic。",
        "ru": "Оставьте это окно открытым и запустите Deep Rock Galactic.",
    },
    "w.done.game_lang": {
        "ja": "・ゲームの言語設定を「{lang}」にしてください"
              "（そのままだとフォントが読み込まれず、訳文が □□□ になります）",
        "en": "- Set the game language to \"{lang}\", or the font will not load"
              " and translations will show up as boxes.",
        "ko": "- 게임 언어 설정을 \"{lang}\" 로 바꾸세요."
              " 그대로 두면 글꼴이 없어 번역문이 □□□ 로 보입니다.",
        "zh": "- 请把游戏语言设置为“{lang}”，否则字体不会加载，译文会显示成 □□□。",
        "zh-tw": "- 請把遊戲語言設定為「{lang}」，否則字型不會載入，譯文會顯示成 □□□。",
        "ru": "- Поставьте в игре язык «{lang}», иначе шрифт не загрузится"
              " и перевод будет показан квадратами.",
    },
    "w.done.f9": {
        "ja": "・ゲーム中は F9 で翻訳の ON/OFF を切り替えられます",
        "en": "- Press F9 in game to turn translation on and off.",
        "ko": "- 게임 중 F9 로 번역을 켜고 끌 수 있습니다.",
        "zh": "- 游戏中按 F9 可以开关翻译。",
        "zh-tw": "- 遊戲中按 F9 可以開關翻譯。",
        "ru": "- В игре нажмите F9, чтобы включить или выключить перевод.",
    },
    "w.done.settings": {
        "ja": "・設定は {ini} をメモ帳で開いて変えられます",
        "en": "- Open {ini} in Notepad to change settings.",
        "ko": "- {ini} 를 메모장으로 열면 설정을 바꿀 수 있습니다.",
        "zh": "- 用记事本打开 {ini} 即可修改设置。",
        "zh-tw": "- 用記事本開啟 {ini} 即可修改設定。",
        "ru": "- Настройки меняются в {ini} (откройте его в Блокноте).",
    },
    "w.done.redo": {
        "ja": "・セットアップをやり直したいときは、{ini} を削除してからもう一度起動してください",
        "en": "- To redo this setup, delete {ini} and start the program again.",
        "ko": "- 설치를 처음부터 다시 하려면 {ini} 를 지우고 다시 실행하세요.",
        "zh": "- 想重新进行设置时，删除 {ini} 后再次启动。",
        "zh-tw": "- 想重新進行設定時，刪除 {ini} 後再次啟動。",
        "ru": "- Чтобы пройти установку заново, удалите {ini} и запустите программу снова.",
    },
    "w.done.readme": {
        "ja": "・詳しい説明: {readme}",
        "en": "- The full documentation is at {readme}",
        "ko": "- 자세한 설명: {readme}",
        "zh": "- 详细说明: {readme}",
        "zh-tw": "- 詳細說明: {readme}",
        "ru": "- Полное описание: {readme}",
    },
    "w.incomplete": {
        "ja": "セットアップを完了できませんでした。",
        "en": "Setup did not finish.",
        "ko": "설치를 끝내지 못했습니다.",
        "zh": "设置没有完成。",
        "zh-tw": "設定沒有完成。",
        "ru": "Установка не завершена.",
    },
})


# ---------------------------------------------------------------------------
# 起動後の黒い窓（drg_bridge.py / overlay.py）
#
# logging に渡す書式なので、%s / %d はそのまま残すこと。
# ---------------------------------------------------------------------------

_M.update({
    "b.config.loaded": {
        "ja": "設定を読み込みました: %s (%d 項目)",
        "en": "Loaded settings: %s (%d items)",
        "ko": "설정을 읽었습니다: %s (%d 개)",
        "zh": "已读取设置: %s（%d 项）",
        "zh-tw": "已讀取設定: %s（%d 項）",
        "ru": "Настройки загружены: %s (%d шт.)",
    },
    "b.config.missing": {
        "ja": "設定ファイルがありません: %s",
        "en": "No settings file: %s",
        "ko": "설정 파일이 없습니다: %s",
        "zh": "没有设置文件: %s",
        "zh-tw": "沒有設定檔: %s",
        "ru": "Файл настроек не найден: %s",
    },
    "b.config.not_int": {
        "ja": "%s は整数として読めません。既定値 %s を使います",
        "en": "%s is not a whole number. Using the default %s",
        "ko": "%s 를 정수로 읽을 수 없습니다. 기본값 %s 를 사용합니다",
        "zh": "%s 不是整数。将使用默认值 %s",
        "zh-tw": "%s 不是整數。將使用預設值 %s",
        "ru": "%s не является целым числом. Используется значение по умолчанию %s",
    },
    "b.config.not_num": {
        "ja": "%s は数値として読めません。既定値 %s を使います",
        "en": "%s is not a number. Using the default %s",
        "ko": "%s 를 숫자로 읽을 수 없습니다. 기본값 %s 를 사용합니다",
        "zh": "%s 不是数字。将使用默认值 %s",
        "zh-tw": "%s 不是數字。將使用預設值 %s",
        "ru": "%s не является числом. Используется значение по умолчанию %s",
    },
    "b.startup": {
        "ja": "provider=%s / 受信→%s / 送信→%s",
        "en": "provider=%s / incoming -> %s / outgoing -> %s",
        "ko": "provider=%s / 수신 -> %s / 송신 -> %s",
        "zh": "provider=%s / 接收 -> %s / 发送 -> %s",
        "zh-tw": "provider=%s / 接收 -> %s / 發送 -> %s",
        "ru": "provider=%s / входящие -> %s / исходящие -> %s",
    },
    "b.not_ready": {
        "ja": "翻訳できる状態になっていません:",
        "en": "Not ready to translate:",
        "ko": "아직 번역할 수 없는 상태입니다:",
        "zh": "还不能进行翻译:",
        "zh-tw": "還不能進行翻譯:",
        "ru": "Перевод пока не настроен:",
    },
    "b.game.connected": {
        "ja": "ゲーム(mod)と接続しました",
        "en": "Connected to the game (mod)",
        "ko": "게임(모드)과 연결되었습니다",
        "zh": "已与游戏（MOD）连接",
        "zh-tw": "已與遊戲（MOD）連線",
        "ru": "Есть связь с игрой (мод)",
    },
    "b.game.lost": {
        "ja": "ゲーム(mod)からの通信が途絶えました",
        "en": "Lost contact with the game (mod)",
        "ko": "게임(모드)과의 통신이 끊겼습니다",
        "zh": "与游戏（MOD）的通信中断了",
        "zh-tw": "與遊戲（MOD）的通訊中斷了",
        "ru": "Связь с игрой (мод) прервана",
    },
    "b.player": {
        "ja": "プレイヤー名: %s",
        "en": "Player name: %s",
        "ko": "플레이어 이름: %s",
        "zh": "玩家名称: %s",
        "zh-tw": "玩家名稱: %s",
        "ru": "Имя игрока: %s",
    },
    "b.display": {
        "ja": "ゲーム内表示: %s",
        "en": "In-game display: %s",
        "ko": "게임 내 표시: %s",
        "zh": "游戏内显示: %s",
        "zh-tw": "遊戲內顯示: %s",
        "ru": "Показ в игре: %s",
    },
    "b.display.failed": {
        "ja": "失敗",
        "en": "failed",
        "ko": "실패",
        "zh": "失败",
        "zh-tw": "失敗",
        "ru": "не удалось",
    },
    "b.display.failed_overlay": {
        "ja": "失敗（オーバーレイに切替）",
        "en": "failed (switching to the overlay)",
        "ko": "실패 (오버레이로 전환)",
        "zh": "失败（改用小窗）",
        "zh-tw": "失敗（改用小視窗）",
        "ru": "не удалось (переключаюсь на оверлей)",
    },
    "b.toggle": {
        "ja": "翻訳 %s（ゲーム内で F9 が押されました）",
        "en": "Translation %s (F9 pressed in game)",
        "ko": "번역 %s (게임에서 F9 를 눌렀습니다)",
        "zh": "翻译 %s（在游戏中按下了 F9）",
        "zh-tw": "翻譯 %s（在遊戲中按下了 F9）",
        "ru": "Перевод %s (в игре нажата F9)",
    },
    "b.waiting": {
        "ja": "待機中: %s",
        "en": "Waiting: %s",
        "ko": "대기 중: %s",
        "zh": "等待中: %s",
        "zh-tw": "等待中: %s",
        "ru": "Ожидание: %s",
    },
    "b.stopping": {
        "ja": "停止します...",
        "en": "Stopping...",
        "ko": "정지합니다...",
        "zh": "正在停止...",
        "zh-tw": "正在停止...",
        "ru": "Останавливаюсь...",
    },
    "b.already_running": {
        "ja": "DRGTranslate はすでに動いています（通信フォルダ: %s）。先に起動した黒い窓をそのまま使ってください",
        "en": "DRGTranslate is already running (folder: %s). Keep using the console window you opened first",
        "ko": "DRGTranslate 가 이미 실행 중입니다(통신 폴더: %s). 먼저 연 콘솔 창을 그대로 사용하세요",
        "zh": "DRGTranslate 已在运行（通信文件夹：%s）。请继续使用先打开的那个黑色窗口",
        "zh-tw": "DRGTranslate 已在執行（通訊資料夾：%s）。請繼續使用先開啟的那個黑色視窗",
        "ru": "DRGTranslate уже запущен (папка: %s). Пользуйтесь окном консоли, которое открыли первым",
    },
    "b.stopped": {
        "ja": "終了しました",
        "en": "Stopped",
        "ko": "종료했습니다",
        "zh": "已结束",
        "zh-tw": "已結束",
        "ru": "Завершено",
    },
    "b.in": {
        "ja": "受信 [%s] %s -> %s",
        "en": "in [%s] %s -> %s",
        "ko": "수신 [%s] %s -> %s",
        "zh": "接收 [%s] %s -> %s",
        "zh-tw": "接收 [%s] %s -> %s",
        "ru": "входящее [%s] %s -> %s",
    },
    "b.relay": {
        "ja": "中継(ホスト) %s",
        "en": "relay (host) %s",
        "ko": "중계(호스트) %s",
        "zh": "转发（房主）%s",
        "zh-tw": "轉發（房主）%s",
        "ru": "ретрансляция (хост) %s",
    },
    "b.out": {
        "ja": "送信 %s -> %s",
        "en": "out %s -> %s",
        "ko": "송신 %s -> %s",
        "zh": "发送 %s -> %s",
        "zh-tw": "發送 %s -> %s",
        "ru": "исходящее %s -> %s",
    },
    "b.in.failed": {
        "ja": "受信翻訳に失敗: %s",
        "en": "Incoming translation failed: %s",
        "ko": "수신 번역에 실패했습니다: %s",
        "zh": "接收翻译失败: %s",
        "zh-tw": "接收翻譯失敗: %s",
        "ru": "Не удалось перевести входящее: %s",
    },
    "b.out.failed": {
        "ja": "送信翻訳に失敗 (%s): %s",
        "en": "Outgoing translation failed (%s): %s",
        "ko": "송신 번역에 실패했습니다 (%s): %s",
        "zh": "发送翻译失败 (%s): %s",
        "zh-tw": "發送翻譯失敗 (%s): %s",
        "ru": "Не удалось перевести исходящее (%s): %s",
    },
    "b.in.error": {
        "ja": "受信翻訳で予期しないエラー",
        "en": "Unexpected error while translating an incoming message",
        "ko": "수신 번역 중 예기치 않은 오류",
        "zh": "接收翻译时发生意外错误",
        "zh-tw": "接收翻譯時發生非預期的錯誤",
        "ru": "Непредвиденная ошибка при переводе входящего",
    },
    "b.out.error": {
        "ja": "送信翻訳で予期しないエラー",
        "en": "Unexpected error while translating an outgoing message",
        "ko": "송신 번역 중 예기치 않은 오류",
        "zh": "发送翻译时发生意外错误",
        "zh-tw": "發送翻譯時發生非預期的錯誤",
        "ru": "Непредвиденная ошибка при переводе исходящего",
    },
    "b.loop.error": {
        "ja": "メインループでエラー",
        "en": "Error in the main loop",
        "ko": "메인 루프에서 오류",
        "zh": "主循环中出错",
        "zh-tw": "主迴圈中發生錯誤",
        "ru": "Ошибка в основном цикле",
    },
    "b.ipc.write_failed": {
        "ja": "to_game.txt へ書き込めません: %s",
        "en": "Cannot write to to_game.txt: %s",
        "ko": "to_game.txt 에 쓸 수 없습니다: %s",
        "zh": "无法写入 to_game.txt: %s",
        "zh-tw": "無法寫入 to_game.txt: %s",
        "ru": "Не удаётся записать to_game.txt: %s",
    },
    "b.ipc.unknown_kind": {
        "ja": "未知の種別: {kind}",
        "en": "unknown kind: {kind}",
        "ko": "알 수 없는 종류: {kind}",
        "zh": "未知的类型: {kind}",
        "zh-tw": "未知的類型: {kind}",
        "ru": "неизвестный тип: {kind}",
    },
    "b.ipc.bad_req": {
        "ja": "要求の形が正しくありません（項目数 {n}）",
        "en": "malformed request ({n} fields)",
        "ko": "요청 형식이 올바르지 않습니다 (항목 수 {n})",
        "zh": "请求格式不正确（字段数 {n}）",
        "zh-tw": "請求格式不正確（欄位數 {n}）",
        "ru": "неверный формат запроса (полей: {n})",
    },
    "b.mod_version": {
        "ja": "MOD のバージョン: %s",
        "en": "MOD version: %s",
        "ko": "MOD 버전: %s",
        "zh": "MOD 版本: %s",
        "zh-tw": "MOD 版本: %s",
        "ru": "версия MOD: %s",
    },
    "b.version_mismatch": {
        "ja": "exe（%s）とゲームフォルダの MOD（%s）のバージョンが違います。"
              "セットアップをやり直して MOD を入れ直してください",
        "en": "The exe (%s) and the MOD in the game folder (%s) are different versions. "
              "Run the setup again to update the MOD",
        "ko": "exe(%s)와 게임 폴더의 MOD(%s) 버전이 다릅니다. "
              "설정을 다시 실행해 MOD를 다시 설치하세요",
        "zh": "exe（%s）与游戏文件夹中的 MOD（%s）版本不一致。请重新运行设置以更新 MOD",
        "zh-tw": "exe（%s）與遊戲資料夾中的 MOD（%s）版本不一致。請重新執行設定以更新 MOD",
        "ru": "Версии exe (%s) и MOD в папке игры (%s) различаются. "
              "Запустите настройку заново, чтобы обновить MOD",
    },
    "b.config.bad_format": {
        "ja": "settings.ini の %s（%s）が使えません（%s）。使える差し込みは %s です。"
              "既定の「%s」で動かします",
        "en": "%s in settings.ini (%s) cannot be used (%s). The placeholders you can use are %s. "
              "Using the default \"%s\" instead",
        "ko": "settings.ini의 %s(%s)을(를) 사용할 수 없습니다(%s). 사용할 수 있는 자리표시자는 %s입니다. "
              "기본값 \"%s\"(으)로 동작합니다",
        "zh": "settings.ini 中的 %s（%s）无法使用（%s）。可用的占位符为 %s。将使用默认值“%s”",
        "zh-tw": "settings.ini 中的 %s（%s）無法使用（%s）。可用的佔位符為 %s。將使用預設值「%s」",
        "ru": "%s в settings.ini (%s) нельзя использовать (%s). Допустимые подстановки: %s. "
              "Используется значение по умолчанию «%s»",
    },
    "w.ue4ss.checksum": {
        "ja": "ダウンロードした UE4SS の zip が想定のものと違います（SHA-256 が一致しません）。"
              "展開せずに止めました",
        "en": "The downloaded UE4SS zip is not the expected file (SHA-256 does not match). "
              "Stopped without extracting it",
        "ko": "다운로드한 UE4SS zip이 예상한 파일이 아닙니다(SHA-256 불일치). 압축을 풀지 않고 중단했습니다",
        "zh": "下载的 UE4SS zip 与预期的文件不同（SHA-256 不一致）。已停止，未解压",
        "zh-tw": "下載的 UE4SS zip 與預期的檔案不同（SHA-256 不一致）。已停止，未解壓縮",
        "ru": "Загруженный zip UE4SS не совпадает с ожидаемым (SHA-256 не совпадает). "
              "Остановлено без распаковки",
    },
    "b.config.relay_limit": {
        "ja": "DRGT_RELAY_MAX_LANGS（%s）が DRGT_RELAY_TARGETS の数（%s）より小さいので、"
              "発言者の言語が中継先に無いときは末尾の言語（%s）が中継されません",
        "en": "DRGT_RELAY_MAX_LANGS (%s) is smaller than the number of DRGT_RELAY_TARGETS (%s), "
              "so the last languages (%s) are not relayed when the speaker's language is not "
              "among the targets",
        "ko": "DRGT_RELAY_MAX_LANGS(%s)가 DRGT_RELAY_TARGETS의 개수(%s)보다 작아서, "
              "발언자의 언어가 중계 대상에 없으면 마지막 언어(%s)는 중계되지 않습니다",
        "zh": "DRGT_RELAY_MAX_LANGS（%s）小于 DRGT_RELAY_TARGETS 的数量（%s），"
              "发言者的语言不在转发目标中时，末尾的语言（%s）不会被转发",
        "zh-tw": "DRGT_RELAY_MAX_LANGS（%s）小於 DRGT_RELAY_TARGETS 的數量（%s），"
                 "發言者的語言不在轉發目標中時，末尾的語言（%s）不會被轉發",
        "ru": "DRGT_RELAY_MAX_LANGS (%s) меньше числа DRGT_RELAY_TARGETS (%s), поэтому "
              "последние языки (%s) не пересылаются, если языка говорящего нет среди целей",
    },
    "b.relay.dropped": {
        "ja": "中継する訳（%s）が原文と釣り合わないので、流さずに捨てました",
        "en": "The relay translation (%s) did not look like a translation of the message, "
              "so it was not sent",
        "ko": "중계할 번역(%s)이 원문과 맞지 않아 보내지 않고 버렸습니다",
        "zh": "转发的译文（%s）与原文不相称，已丢弃，未发送",
        "zh-tw": "轉發的譯文（%s）與原文不相稱，已捨棄，未送出",
        "ru": "Перевод для пересылки (%s) не похож на перевод сообщения, поэтому он не отправлен",
    },
    "p.unknown_model": {
        "ja": "%s は知らないモデルなので、旧世代のモデルとして送ります（effort は送りません）。"
              "新しいモデルなら translate.py の表に足してください",
        "en": "%s is not a model this version knows, so it is treated as an older model "
              "(effort is not sent). If it is a new model, add it to the table in translate.py",
        "ko": "%s 은(는) 알 수 없는 모델이라 이전 세대 모델로 취급합니다(effort 를 보내지 않음). "
              "새 모델이면 translate.py 의 표에 추가하세요",
        "zh": "%s 是未知的模型，按旧一代模型处理（不发送 effort）。如果是新模型，请加入 translate.py 的表中",
        "zh-tw": "%s 是未知的模型，按舊一代模型處理（不送出 effort）。如果是新模型，請加入 translate.py 的表中",
        "ru": "%s — неизвестная модель, она обрабатывается как модель предыдущего поколения "
              "(effort не отправляется). Если это новая модель, добавьте её в таблицу в translate.py",
    },
    "b.overlay.failed": {
        "ja": "オーバーレイを起動できません (%s)。ログのみで続行します",
        "en": "Cannot start the overlay (%s). Continuing with the log only",
        "ko": "오버레이를 시작할 수 없습니다 (%s). 로그만 남기고 계속합니다",
        "zh": "无法启动小窗 (%s)。仅用日志继续运行",
        "zh-tw": "無法啟動小視窗 (%s)。僅用日誌繼續執行",
        "ru": "Не удалось запустить оверлей (%s). Продолжаю только с логом",
    },
    "b.press_enter": {
        "ja": "Enter キーを押すと閉じます...",
        "en": "Press Enter to close...",
        "ko": "Enter 키를 누르면 닫힙니다...",
        "zh": "按 Enter 键关闭...",
        "zh-tw": "按 Enter 鍵關閉...",
        "ru": "Нажмите Enter, чтобы закрыть...",
    },

    # --- オーバーレイ（小窓） ---
    "o.waiting": {
        "ja": "翻訳待機中です。ゲームを起動してチャットしてください。",
        "en": "Waiting for chat. Start the game and say something.",
        "ko": "번역을 기다리는 중입니다. 게임을 실행하고 채팅해 보세요.",
        "zh": "正在等待翻译。请启动游戏并聊天。",
        "zh-tw": "正在等待翻譯。請啟動遊戲並聊天。",
        "ru": "Жду сообщений. Запустите игру и напишите в чат.",
    },
    "o.toggle": {
        "ja": "[DRGTranslate] 翻訳 {state}",
        "en": "[DRGTranslate] Translation {state}",
        "ko": "[DRGTranslate] 번역 {state}",
        "zh": "[DRGTranslate] 翻译 {state}",
        "zh-tw": "[DRGTranslate] 翻譯 {state}",
        "ru": "[DRGTranslate] Перевод {state}",
    },
    "o.not_connected": {
        "ja": "ゲームと接続していないため送信できません",
        "en": "Not connected to the game, so it cannot be sent",
        "ko": "게임과 연결되어 있지 않아 보낼 수 없습니다",
        "zh": "尚未与游戏连接，无法发送",
        "zh-tw": "尚未與遊戲連線，無法發送",
        "ru": "Нет связи с игрой — отправить нельзя",
    },
    "o.not_translated": {
        "ja": "翻訳できなかったので、原文だけを送りました",
        "en": "Could not translate it, so only the original was sent",
        "ko": "번역하지 못해 원문만 보냈습니다",
        "zh": "未能翻译，只发送了原文",
        "zh-tw": "未能翻譯，只發送了原文",
        "ru": "Перевести не удалось — отправлен только оригинал",
    },
    "o.update_error": {
        "ja": "オーバーレイの更新でエラー",
        "en": "Error while updating the overlay",
        "ko": "오버레이 갱신 중 오류",
        "zh": "更新小窗时出错",
        "zh-tw": "更新小視窗時發生錯誤",
        "ru": "Ошибка при обновлении оверлея",
    },
})


# ---------------------------------------------------------------------------
# 翻訳エンジン（translate.py）
#
# ここの文言は例外メッセージにもなり、"受信翻訳に失敗: ..." の形で黒い窓に出る。
# ---------------------------------------------------------------------------

_M.update({
    "p.glossary.loaded": {
        "ja": "用語集を読み込みました: %s (受信 %d / 送信 %d)",
        "en": "Loaded the glossary: %s (incoming %d / outgoing %d)",
        "ko": "용어집을 읽었습니다: %s (수신 %d / 송신 %d)",
        "zh": "已读取术语表: %s（接收 %d / 发送 %d）",
        "zh-tw": "已讀取術語表: %s（接收 %d / 發送 %d）",
        "ru": "Глоссарий загружен: %s (входящие %d / исходящие %d)",
    },
    "p.glossary.failed": {
        "ja": "用語集の読み込みに失敗しました (%s): %s",
        "en": "Could not read the glossary (%s): %s",
        "ko": "용어집을 읽지 못했습니다 (%s): %s",
        "zh": "读取术语表失败 (%s): %s",
        "zh-tw": "讀取術語表失敗 (%s): %s",
        "ru": "Не удалось прочитать глоссарий (%s): %s",
    },
    "p.cache.loaded": {
        "ja": "キャッシュを読み込みました: %d 件",
        "en": "Loaded the cache: %d entries",
        "ko": "캐시를 읽었습니다: %d 건",
        "zh": "已读取缓存: %d 条",
        "zh-tw": "已讀取快取: %d 筆",
        "ru": "Кэш загружен: %d записей",
    },
    "p.cache.load_failed": {
        "ja": "キャッシュの読み込みに失敗しました: %s",
        "en": "Could not read the cache: %s",
        "ko": "캐시를 읽지 못했습니다: %s",
        "zh": "读取缓存失败: %s",
        "zh-tw": "讀取快取失敗: %s",
        "ru": "Не удалось прочитать кэш: %s",
    },
    "p.cache.save_failed": {
        "ja": "キャッシュの保存に失敗しました: %s",
        "en": "Could not save the cache: %s",
        "ko": "캐시를 저장하지 못했습니다: %s",
        "zh": "保存缓存失败: %s",
        "zh-tw": "儲存快取失敗: %s",
        "ru": "Не удалось сохранить кэш: %s",
    },
    "p.conn_failed": {
        "ja": "接続失敗: {reason}",
        "en": "Connection failed: {reason}",
        "ko": "연결 실패: {reason}",
        "zh": "连接失败: {reason}",
        "zh-tw": "連線失敗: {reason}",
        "ru": "Не удалось соединиться: {reason}",
    },
    "p.timeout": {
        "ja": "タイムアウト",
        "en": "Timed out",
        "ko": "시간 초과",
        "zh": "超时",
        "zh-tw": "逾時",
        "ru": "Превышено время ожидания",
    },
    "p.need_key": {
        "ja": "settings.ini に {key} を設定してください（{url}）",
        "en": "Set {key} in settings.ini ({url})",
        "ko": "settings.ini 에 {key} 를 설정하세요 ({url})",
        "zh": "请在 settings.ini 中设置 {key}（{url}）",
        "zh-tw": "請在 settings.ini 中設定 {key}（{url}）",
        "ru": "Задайте {key} в settings.ini ({url})",
    },
    "p.no_key": {
        "ja": "{name} のAPIキーが設定されていません（settings.ini の {key}）",
        "en": "No API key for {name} (set {key} in settings.ini)",
        "ko": "{name} 의 API 키가 설정되어 있지 않습니다 (settings.ini 의 {key})",
        "zh": "没有设置 {name} 的 API 密钥（settings.ini 的 {key}）",
        "zh-tw": "沒有設定 {name} 的 API 金鑰（settings.ini 的 {key}）",
        "ru": "Нет API-ключа для {name} (параметр {key} в settings.ini)",
    },
    "p.missing_sdk": {
        "ja": "{package} パッケージが見つかりません。次のコマンドで入れてください:",
        "en": "The {package} package is missing. Install it with:",
        "ko": "{package} 패키지가 없습니다. 다음 명령으로 설치하세요:",
        "zh": "找不到 {package} 包。请用下面的命令安装:",
        "zh-tw": "找不到 {package} 套件。請用下面的指令安裝:",
        "ru": "Пакет {package} не найден. Установите его командой:",
    },
    "p.bad_json": {
        "ja": "JSON として読めない応答: {raw}",
        "en": "The reply is not valid JSON: {raw}",
        "ko": "JSON 으로 읽을 수 없는 응답: {raw}",
        "zh": "无法按 JSON 解析的响应: {raw}",
        "zh-tw": "無法按 JSON 解析的回應: {raw}",
        "ru": "Ответ не является корректным JSON: {raw}",
    },
    "p.not_object": {
        "ja": "JSON オブジェクトではない応答",
        "en": "The reply is not a JSON object",
        "ko": "JSON 객체가 아닌 응답",
        "zh": "响应不是 JSON 对象",
        "zh-tw": "回應不是 JSON 物件",
        "ru": "Ответ не является объектом JSON",
    },
    "p.empty": {
        "ja": "空の応答",
        "en": "Empty reply",
        "ko": "빈 응답",
        "zh": "空的响应",
        "zh-tw": "空的回應",
        "ru": "Пустой ответ",
    },
    "p.api_failed": {
        "ja": "{name} API 呼び出しに失敗: {err}",
        "en": "The {name} API call failed: {err}",
        "ko": "{name} API 호출에 실패했습니다: {err}",
        "zh": "调用 {name} API 失败: {err}",
        "zh-tw": "呼叫 {name} API 失敗: {err}",
        "ru": "Вызов API {name} не удался: {err}",
    },
    "p.refused": {
        "ja": "翻訳を拒否されました{detail}",
        "en": "The translation was refused{detail}",
        "ko": "번역이 거부되었습니다{detail}",
        "zh": "翻译被拒绝{detail}",
        "zh-tw": "翻譯被拒絕{detail}",
        "ru": "Перевод отклонён{detail}",
    },
    "p.effort_ignored": {
        "ja": "%s では effort を使わないので、DRGT_CLAUDE_EFFORT は無視します",
        "en": "effort is not used with %s, so DRGT_CLAUDE_EFFORT is ignored",
        "ko": "%s 에서는 effort 를 쓰지 않으므로 DRGT_CLAUDE_EFFORT 는 무시합니다",
        "zh": "%s 不使用 effort，将忽略 DRGT_CLAUDE_EFFORT",
        "zh-tw": "%s 不使用 effort，將忽略 DRGT_CLAUDE_EFFORT",
        "ru": "С %s effort не используется, поэтому DRGT_CLAUDE_EFFORT игнорируется",
    },
    "p.effort_invalid": {
        "ja": "DRGT_CLAUDE_EFFORT（%s）は %s では使えません。使えるのは auto / %s です。auto で動かします",
        "en": "DRGT_CLAUDE_EFFORT (%s) cannot be used with %s. Use auto / %s. Using auto",
        "ko": "DRGT_CLAUDE_EFFORT(%s)는 %s 에서 쓸 수 없습니다. 쓸 수 있는 값은 auto / %s 입니다. auto 로 동작합니다",
        "zh": "DRGT_CLAUDE_EFFORT（%s）不能用于 %s。可用的值为 auto / %s。将按 auto 运行",
        "zh-tw": "DRGT_CLAUDE_EFFORT（%s）不能用於 %s。可用的值為 auto / %s。將以 auto 執行",
        "ru": "DRGT_CLAUDE_EFFORT (%s) нельзя использовать с %s. Допустимо: auto / %s. Используется auto",
    },
    "p.fallback_invalid": {
        "ja": "DRGT_CLAUDE_REFUSAL_FALLBACK（%s）が読めません。auto / true / false のどれかにしてください。auto で動かします",
        "en": "Cannot read DRGT_CLAUDE_REFUSAL_FALLBACK (%s). Use auto, true or false. Using auto",
        "ko": "DRGT_CLAUDE_REFUSAL_FALLBACK(%s)를 읽을 수 없습니다. auto / true / false 중 하나로 설정하세요. auto 로 동작합니다",
        "zh": "无法读取 DRGT_CLAUDE_REFUSAL_FALLBACK（%s）。请设为 auto / true / false 之一。将按 auto 运行",
        "zh-tw": "無法讀取 DRGT_CLAUDE_REFUSAL_FALLBACK（%s）。請設為 auto / true / false 之一。將以 auto 執行",
        "ru": "Не удалось прочитать DRGT_CLAUDE_REFUSAL_FALLBACK (%s). Укажите auto, true или false. Используется auto",
    },
    "p.unknown_provider": {
        "ja": "未知の provider '{name}' です。使えるのは: {names}",
        "en": "Unknown provider '{name}'. Available: {names}",
        "ko": "알 수 없는 provider '{name}' 입니다. 사용할 수 있는 값: {names}",
        "zh": "未知的 provider “{name}”。可用的有: {names}",
        "zh-tw": "未知的 provider「{name}」。可用的有: {names}",
        "ru": "Неизвестный provider «{name}». Доступны: {names}",
    },
    "p.cooldown": {
        "ja": "プロバイダが一時的に停止中です（連続失敗によるクールダウン）",
        "en": "The provider is paused for a moment (cooling down after repeated failures)",
        "ko": "프로바이더가 잠시 멈춰 있습니다 (연속 실패로 인한 대기)",
        "zh": "翻译服务暂时停用中（连续失败后的冷却）",
        "zh-tw": "翻譯服務暫時停用中（連續失敗後的冷卻）",
        "ru": "Сервис временно приостановлен (пауза после серии ошибок)",
    },
    "p.cooldown_start": {
        "ja": "翻訳が5回連続で失敗したため30秒待機します",
        "en": "Translation failed 5 times in a row, waiting 30 seconds",
        "ko": "번역이 5회 연속 실패하여 30초 기다립니다",
        "zh": "翻译连续失败 5 次，等待 30 秒",
        "zh-tw": "翻譯連續失敗 5 次，等待 30 秒",
        "ru": "Пять неудач подряд — жду 30 секунд",
    },
})
