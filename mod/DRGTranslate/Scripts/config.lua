-- DRGTranslate : ゲーム内側(UE4SS Lua)の設定
--
-- 言語・翻訳先・表示フォーマットなどの「翻訳まわりの設定」は
-- bridge/config.json 側にあります。ここはゲーム内の挙動だけ。

local M = {}

-- MOD 全体の有効/無効（F9 でゲーム中に切り替え可）
M.enabled = true

-- UE4SS コンソールに詳細ログを出す
M.debug = false

-- 受信チャットの翻訳
M.incoming = {
    enabled = true,
    -- 自分の発言は翻訳しない
    skip_own = true,
    -- ゲームシステムメッセージ(EChatMessageType::ES_Game)も翻訳するか
    translate_game_messages = false,
}

-- 自分の発言の翻訳送信
--
-- 打った日本語はそのまま送られ、翻訳が届いたら2通目として送られる。
--   You: 回復お願いします
--   You: Please heal me / 회복 부탁드립니다
M.outgoing = {
    enabled = true,

    -- この接頭辞で始まる発言は翻訳しない（コマンド類）
    ignore_prefixes = { "/", "!", "." },

    -- この文字数未満は翻訳しない
    min_length = 2,
}

-- 翻訳結果をどこに表示するか
M.display = {
    -- "auto"      : クライアントなら GameState:PostGameMessage、ホストならチャットWidget直叩き
    -- "gamestate" : 常に GameState:PostGameMessage を使う
    -- "widget"    : 常に HUD_Chat ウィジェットを直接叩く
    --               （構造体引数を渡すため落ちる可能性がある。自己責任）
    -- "off"       : ゲーム内には出さない（bridge のオーバーレイのみ）
    strategy = "auto",

    -- ホスト(リッスンサーバ)でウィジェット表示に失敗したとき、
    -- PostGameMessage にフォールバックするか。
    -- true にすると「全員に」翻訳文が見えてしまうので既定は false。
    host_broadcast_fallback = false,
}

-- ローカルプロセス(bridge)との通信
M.ipc = {
    -- 受信ポーリング間隔(ms)
    poll_ms = 100,
    -- 通信フォルダ。既定は %APPDATA%\DRGTranslate
    dir = nil,
}

-- ゲーム中に MOD をON/OFFするキー
M.hotkey = {
    toggle = "F9",
}

return M
