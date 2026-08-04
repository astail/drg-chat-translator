-- =====================================================================
--  DRGTranslate  -  Deep Rock Galactic チャット自動翻訳 (UE4SS Lua mod)
--
--  受信: AFSDGameState::ClientNewMessage(FFSDChatMessage&)
--        → 訳文を自分にだけローカル表示する
--  送信: AFSDPlayerController::Server_NewMessage(FString,FString,EChatSenderType)
--        → 原文はそのまま流し、訳文が届いたら2通目として送る
--
--  どちらも UE4SS の RegisterHook（/Script/ 始まりなので pre コールバック）で捕まえる。
--
--  翻訳そのものはローカル常駐プロセス(bridge/drg_bridge.py)が担当し、
--  %APPDATA%\DRGTranslate 配下のテキストファイル経由でやり取りする。
-- =====================================================================

local Cfg = require("config")
local U   = require("util")
local IPC = require("ipc")

local MOD_VERSION = "0.2.7"

local UEHelpers = nil
pcall(function() UEHelpers = require("UEHelpers") end)

local State = {
    enabled        = Cfg.enabled,
    now            = 0,        -- ループで加算する単調増加のミリ秒
    pc             = nil,
    gs             = nil,
    hud            = nil,
    player_name    = nil,
    sending        = false,    -- 自分で Server_NewMessage を呼んでいる最中
    own_sent       = {},       -- [送信文] = 期限。受信側で自分の発言を弾くのに使う
    last_alive_at  = 0,
    display_ok     = nil,      -- ゲーム内表示が成功しているか
    warned_display = false,
}

U.set_debug(Cfg.debug)

-- ---------------------------------------------------------------------
-- UObject 取得ヘルパー
-- ---------------------------------------------------------------------

local function is_valid(obj)
    if obj == nil then return false end
    local ok, v = pcall(function() return obj:IsValid() end)
    return ok and v == true
end

--- 判定できないものは「自分のではない」とみなす。
--- ここで真を返してしまうと、CDO やタイトル画面用のオブジェクトを
--- 自分の PlayerController として掴んでしまい、送信が必ず失敗する。
local function is_local_controller(pc)
    if not is_valid(pc) then return false end
    local ok, r = pcall(function() return pc:IsLocalController() end)
    return ok and r == true
end

--- チャットを送れる PlayerController か。
--- 弾きたいもの:
---   Default__...                    クラスのデフォルトオブジェクト(CDO)
---   Bp_StartMenu_PlayerController_C タイトル画面用。Server_NewMessage を持たない
local function is_chat_capable_pc(o)
    if not is_valid(o) then return false end
    local ok, name = pcall(function() return o:GetFullName() end)
    if ok then
        local s = U.tostr(name)
        if s:find("Default__", 1, true) then return false end
        if s:find("StartMenu", 1, true) then return false end
    end
    local okc, cls = pcall(function() return o:GetClass():GetFullName() end)
    if okc and U.tostr(cls):find("StartMenu", 1, true) then return false end
    return is_local_controller(o)
end

local function get_pc()
    -- キャッシュにも同じ判定をかける。IsValid だけだと、いったん掴んだ
    -- タイトル画面用のオブジェクトを永久に使い続けてしまう。
    if is_chat_capable_pc(State.pc) then return State.pc end
    State.pc = nil

    -- 型で探すほうを先に試す。UEHelpers は「今の PlayerController」を返すだけで、
    -- タイトル画面では別物が返ってくる。
    local ok, all = pcall(FindAllOf, "FSDPlayerController")
    if ok and all then
        for _, o in ipairs(all) do
            if is_chat_capable_pc(o) then
                State.pc = o
                return o
            end
        end
    end

    if UEHelpers and UEHelpers.GetPlayerController then
        local ok2, found = pcall(UEHelpers.GetPlayerController)
        if ok2 and is_chat_capable_pc(found) then
            State.pc = found
            return found
        end
    end
    return nil
end

local function get_gamestate()
    if is_valid(State.gs) then return State.gs end
    State.gs = nil
    local ok, found = pcall(FindFirstOf, "FSDGameState")
    if ok and is_valid(found) then
        State.gs = found
        return found
    end
    return nil
end

local function get_hud_chat()
    if is_valid(State.hud) then return State.hud end
    State.hud = nil
    local ok, found = pcall(FindFirstOf, "HUD_Chat_C")
    if ok and is_valid(found) then
        State.hud = found
        return found
    end
    return nil
end

--- ホスト(リッスンサーバ)かどうか。判定できない場合はホスト扱いにする
--- （クライアント専用の PostGameMessage を誤って全員に配信しないため）
local function is_authority(actor)
    if not is_valid(actor) then return true end
    local ok, r = pcall(function() return actor:HasAuthority() end)
    if ok and type(r) == "boolean" then return r end
    return true
end

--- 自分の名前。キャッシュを読むだけで UObject には触らない。
---
--- 名前は送信フック(on_outgoing)の引数から受け取る。PlayerState を辿って
--- 取りに行くこともできるが、それをやると
---   ・フックの中でやれば、チャットのたびに落ちる可能性がある
---   ・ループから定期的にやれば、レベルロード中の不安定な時間帯を
---     毎秒なぞることになり、起動直後に落ちる
--- ので取りに行かない。自分が一度発言すれば埋まるし、埋まるまでの間に
--- 困るのは「自分の発言を自分で翻訳してしまう」程度で実害がない。
local function get_player_name()
    return State.player_name or ""
end

-- ---------------------------------------------------------------------
-- 翻訳結果の表示（すべてローカル限定でなければならない）
-- ---------------------------------------------------------------------

--- クライアントから NetMulticast を呼ぶとローカルでしか実行されないため、
--- 「クライアントのとき限定で」安全に使える。
local function display_via_gamestate(text)
    local gs = get_gamestate()
    if not gs then return false end
    U.dbg("PostGameMessage: %s", text)
    local ok, err = pcall(function() gs:PostGameMessage(text) end)
    if not ok then U.dbg("PostGameMessage 失敗: %s", tostring(err)) end
    return ok
end

--- チャットウィジェットを直接叩く（表示はローカル限定になる）
---
--- ⚠ この関数は Lua のテーブルを FFSDChatMessage 構造体として渡している。
--- UE4SS は構造体引数を Lua テーブルから組み立てられないことがあり、
--- 失敗するとゲームごと落ちる（pcall では防げない）。
--- そのため strategy = "widget" を明示したときだけ使う。
local function display_via_widget(text)
    local hud = get_hud_chat()
    if not hud then return false end
    U.dbg("widget 表示を試みます（構造体引数のため危険）")
    local payload = { MsgType = 1, Sender = "", SenderType = 0, Msg = text }
    for _, fname in ipairs({ "Add Chat Message", "NewMesssage", "NewMessage" }) do
        local ok = pcall(function()
            local fn = hud[fname]
            if fn == nil then error("no such UFunction") end
            fn(hud, payload)
        end)
        if ok then
            U.dbg("widget 表示に成功: %s", fname)
            return true
        end
    end
    U.dbg("HUD_Chat への直接表示に失敗")
    return false
end

local function report_display(ok)
    if State.display_ok ~= ok then
        State.display_ok = ok
        IPC.send("DISPLAY", ok and "ok" or "fail")
    end
end

local function display_line(text)
    if text == nil or text == "" then return false end

    local mode = Cfg.display.strategy
    if mode == "off" then
        report_display(false)
        return true
    end
    if mode == "gamestate" then
        local ok = display_via_gamestate(text)
        report_display(ok)
        return ok
    end
    if mode == "widget" then
        local ok = display_via_widget(text)
        report_display(ok)
        return ok
    end

    -- auto : クライアントなら PostGameMessage（引数が FString だけなので安全）。
    --        ホストは PostGameMessage が全員に配信されてしまい、
    --        widget 直叩きは構造体引数で落ちる危険があるので、
    --        既定ではゲーム内に出さず bridge のオーバーレイに任せる。
    local gs = get_gamestate()
    local host = true
    if gs then host = is_authority(gs) end
    U.dbg("display auto: gamestate=%s host=%s", tostring(gs ~= nil), tostring(host))

    if gs and not host then
        if display_via_gamestate(text) then
            report_display(true)
            return true
        end
    end

    if host and Cfg.display.host_broadcast_fallback then
        if display_via_gamestate(text) then
            report_display(true)
            return true
        end
    end

    report_display(false)
    if host and not State.warned_display then
        State.warned_display = true
        U.log("ホストなのでゲーム内チャットには出しません（他の隊員に見えてしまうため）。"
              .. ".env の DRGT_OVERLAY_ENABLED=true で小窓に出せます")
    end
    return false
end

-- ---------------------------------------------------------------------
-- 送信
-- ---------------------------------------------------------------------

local function remember_own(text)
    if text and text ~= "" then
        State.own_sent[text] = State.now + 30000
    end
end

local function send_chat(sender, text, sender_type)
    if text == nil or text == "" then return false end
    local pc = get_pc()
    if not pc then
        U.log("PlayerController が見つからず送信できませんでした")
        return false
    end
    if sender == nil or sender == "" then sender = get_player_name() end

    U.dbg("send: Server_NewMessage を呼びます sender=%s text=%s", sender, text)
    -- ホスト(リッスンサーバ)では Server_NewMessage が同期的に実行され、
    -- この呼び出しの中で ClientNewMessage まで配信される。つまり受信フックは
    -- 呼び出しから戻る前に走る。記録を後回しにすると自分の発言を弾けず、
    -- 送った訳文をもう一度翻訳してしまうので、呼ぶ前に控えておく。
    remember_own(text)
    State.sending = true
    local ok, err = pcall(function()
        pc:Server_NewMessage(sender, text, sender_type or 0)
    end)
    State.sending = false
    U.dbg("send: 呼び出しから戻りました")

    if not ok then
        U.log("Server_NewMessage 呼び出し失敗 (err type=%s): %s", type(err), tostring(err))
        local okc, cls = pcall(function() return pc:GetClass():GetFullName() end)
        U.log("  呼び出した相手: %s", okc and U.tostr(cls) or "クラス不明")
        U.log("  引数: sender=%q text=%q type=%s",
              tostring(sender), tostring(text), tostring(sender_type or 0))
        State.own_sent[text] = nil   -- 送れていないので控えを取り消す
        return false
    end
    U.dbg("送信: %s", text)
    return true
end

-- ---------------------------------------------------------------------
-- 自分の発言を翻訳するか判定
-- ---------------------------------------------------------------------

local function should_translate_outgoing(text)
    text = U.trim(text)
    if text == "" then return false end
    if U.utf8_len(text) < (Cfg.outgoing.min_length or 2) then return false end
    for _, p in ipairs(Cfg.outgoing.ignore_prefixes or {}) do
        if p ~= "" and U.starts_with(text, p) then return false end
    end
    -- 日本語が入っていなければ既に英語などで書いているとみなす
    if not U.has_japanese(text) then return false end
    return true
end

-- ---------------------------------------------------------------------
-- フック: 受信
-- ---------------------------------------------------------------------

local function on_incoming(Context, MsgParam)
    if not State.enabled or not Cfg.incoming.enabled then return end
    if not IPC.connected then return end

    local ok, err = pcall(function()
        U.dbg("in: フック開始")
        local msg = MsgParam:get()
        U.dbg("in: 構造体を取得")
        local text   = U.trim(U.tostr(msg.Msg))
        U.dbg("in: Msg=%s", text)
        local sender = U.tostr(msg.Sender)
        U.dbg("in: Sender=%s", sender)
        local mtype  = tonumber(msg.MsgType) or 0   -- 0 = ES_Chat, 1 = ES_Game
        U.dbg("in: MsgType=%d", mtype)

        if text == "" then return end
        if mtype ~= 0 and not Cfg.incoming.translate_game_messages then return end

        -- 自分の発言・自分が送った翻訳文はスキップ
        if Cfg.incoming.skip_own then
            local me = get_player_name()   -- キャッシュのみ。UObject には触らない
            if me ~= "" and sender == me then return end
        end
        local expires_at = State.own_sent[text]
        if expires_at and expires_at > State.now then return end

        U.dbg("受信: [%s] %s", sender, text)
        IPC.request("in", sender, text, function(_, outtext)
            if outtext == "" then return end
            U.in_game_thread(function() display_line(outtext) end)
        end)
    end)

    if not ok then U.dbg("on_incoming error: %s", tostring(err)) end
end

-- ---------------------------------------------------------------------
-- フック: 送信
-- ---------------------------------------------------------------------

local function on_outgoing(Context, SenderP, TextP, SenderTypeP)
    if State.sending then return end            -- 自分で呼んだ分は無視
    if not State.enabled or not Cfg.outgoing.enabled then return end

    local ok, err = pcall(function()
        U.dbg("out: フック開始")
        local pc = Context:get()
        U.dbg("out: PlayerController を取得")
        -- ホストの場合、他プレイヤーの Server_NewMessage もここを通る
        if not is_local_controller(pc) then return end
        State.pc = pc

        local sender = U.tostr(SenderP)
        local text   = U.tostr(TextP)
        U.dbg("out: Sender=%s Text=%s", sender, text)
        if sender ~= "" and State.player_name ~= sender then
            State.player_name = sender
            IPC.send("NAME", sender)
        end

        if not IPC.connected then return end
        if not should_translate_outgoing(text) then return end

        -- 原文はそのまま流れる。翻訳が届いたら2通目として送る
        local sender_type = tonumber(SenderTypeP and SenderTypeP:get()) or 0
        U.dbg("送信を検出: %s", text)
        IPC.request("out", sender, text, function(_, outtext)
            if outtext == "" then return end
            U.in_game_thread(function() send_chat(sender, outtext, sender_type) end)
        end)
    end)

    if not ok then U.dbg("on_outgoing error: %s", tostring(err)) end
end

--- 期限切れの「自分が送った文」を捨てる
local function gc_own_sent()
    for text, expires_at in pairs(State.own_sent) do
        if State.now > expires_at then State.own_sent[text] = nil end
    end
end

-- ---------------------------------------------------------------------
-- bridge からのメッセージ
-- ---------------------------------------------------------------------

-- オーバーレイの入力欄から送信された文（翻訳済み）
IPC.on("SAY", function(fields)
    local text = fields[2] or ""
    if text == "" then return end
    U.in_game_thread(function() send_chat(get_player_name(), text, 0) end)
end)

-- ゲーム内にローカル表示するだけのお知らせ
IPC.on("NOTE", function(fields)
    local text = fields[2] or ""
    if text ~= "" then
        U.in_game_thread(function() display_line(text) end)
    end
end)

IPC.on("HELLO", function(fields)
    U.log("bridge version = %s", fields[2] or "?")
end)

-- ---------------------------------------------------------------------
-- 初期化
-- ---------------------------------------------------------------------

local function safe_hook(path, pre_cb, post_cb)
    local ok, a = pcall(RegisterHook, path, pre_cb, post_cb)
    if ok then
        U.log("hook 登録: %s", path)
        return true
    end
    U.log("!! hook 登録失敗: %s (%s)", path, tostring(a))
    return false
end

local function init()
    U.log("DRGTranslate v%s 起動", MOD_VERSION)

    IPC.init(Cfg.ipc.dir)
    IPC.send("HELLO", MOD_VERSION)

    safe_hook("/Script/FSD.FSDGameState:ClientNewMessage", on_incoming)
    safe_hook("/Script/FSD.FSDPlayerController:Server_NewMessage", on_outgoing)

    if type(RegisterKeyBind) == "function" and Key and Cfg.hotkey and Key[Cfg.hotkey.toggle] then
        RegisterKeyBind(Key[Cfg.hotkey.toggle], function()
            State.enabled = not State.enabled
            local s = State.enabled and "ON" or "OFF"
            U.log("翻訳 %s", s)
            -- キーバインドのコールバックはゲームスレッド外で走るため、
            -- UObject に触る表示処理は必ず包んでから呼ぶ
            U.in_game_thread(function()
                display_line("[DRGTranslate] 翻訳 " .. s)
            end)
        end)
        U.log("%s キーで翻訳のON/OFFを切り替えられます", Cfg.hotkey.toggle)
    end

    local poll_ms = Cfg.ipc.poll_ms or 100
    U.loop(poll_ms, function()
        State.now = State.now + poll_ms

        IPC.poll()
        IPC.flush()

        if (State.now - State.last_alive_at) >= 1000 then
            State.last_alive_at = State.now
            IPC.check_alive()
            IPC.beat(MOD_VERSION)
            gc_own_sent()
        end
    end)
end

init()
