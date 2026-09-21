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

local MOD_VERSION = "0.6.3"
local LOCAL_SEND_WINDOW_MS = 5000
local OWN_ECHO_TTL_MS = 30000
-- 中継行で訳と訳の間に入る区切り。bridge の DRGT_RELAY_SEPARATOR の既定値と同じ
local RELAY_SEPARATOR = " / "
local SEEN_SENDER_TTL_MS = 120000

local UEHelpers = nil
pcall(function() UEHelpers = require("UEHelpers") end)

local State = {
    enabled        = Cfg.enabled,
    now            = 0,
    pc             = nil,
    gs             = nil,
    hud            = nil,
    player_name    = nil,
    sending        = false,
    own_sent       = {},
    seen_senders   = {},
    last_alive_at  = 0,
    local_sends    = {},
    display_ok     = nil,
    warned_display = false,
    relay_queue    = {},
    last_relay_at  = 0,
    warned_relay   = false,
}

U.set_debug(Cfg.debug)

Cfg.host_relay = Cfg.host_relay or { enabled = true }

local function is_valid(obj)
    if obj == nil then return false end
    local ok, v = pcall(function() return obj:IsValid() end)
    return ok and v == true
end

--- 判定できないものは「自分のではない」とみなす。
local function is_local_controller(pc)
    if not is_valid(pc) then return false end
    local ok, r = pcall(function() return pc:IsLocalController() end)
    return ok and r == true
end

--- チャットを送れる PlayerController か。
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
    if is_chat_capable_pc(State.pc) then return State.pc end
    State.pc = nil

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
local function is_authority(actor)
    if not is_valid(actor) then return true end
    local ok, r = pcall(function() return actor:HasAuthority() end)
    if ok and type(r) == "boolean" then return r end
    return true
end

--- 自分がホストか。上の is_authority と違い、判定できなければ false を返す。
local function is_host()
    local gs = get_gamestate()
    if not is_valid(gs) then return false end
    local ok, r = pcall(function() return gs:HasAuthority() end)
    return ok and r == true
end

--- ロビーの人数。読めなければ -1。
local function player_count()
    local gs = get_gamestate()
    if not is_valid(gs) then return -1 end
    local ok, arr = pcall(function() return gs.PlayerArray end)
    if not ok or arr == nil then return -1 end
    local ok2, n = pcall(function() return #arr end)
    if not ok2 or type(n) ~= "number" then
        ok2, n = pcall(function() return arr:GetArrayNum() end)
    end
    if ok2 and type(n) == "number" then return n end
    return -1
end

--- 自分の名前。キャッシュを読むだけで UObject には触らない。
local function get_player_name()
    return State.player_name or ""
end

--- クライアントから NetMulticast を呼ぶとローカルでしか実行されないため、クライアントのとき限定で安全に使える。
local function display_via_gamestate(text)
    local gs = get_gamestate()
    if not gs then return false end
    U.dbg("PostGameMessage: %s", text)
    local ok, err = pcall(function() gs:PostGameMessage(text) end)
    if not ok then U.dbg("PostGameMessage failed: %s", tostring(err)) end
    return ok
end

--- チャットウィジェットを直接叩く（表示はローカル限定になる）
local function display_via_widget(text)
    local hud = get_hud_chat()
    if not hud then return false end
    U.dbg("trying the widget path (risky: it passes a struct argument)")
    local payload = { MsgType = 1, Sender = "", SenderType = 0, Msg = text }
    for _, fname in ipairs({ "Add Chat Message", "NewMesssage", "NewMessage" }) do
        local ok = pcall(function()
            local fn = hud[fname]
            if fn == nil then error("no such UFunction") end
            fn(hud, payload)
        end)
        if ok then
            U.dbg("widget display worked: %s", fname)
            return true
        end
    end
    U.dbg("could not drive HUD_Chat directly")
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

    if host and gs and player_count() == 1 then
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
        U.log("You are hosting with other dwarves around, so incoming translations are "
              .. "not shown in the incoming format (anything a host puts in the chat box "
              .. "reaches everyone, so the translations go out together as relay lines "
              .. "instead). Your own language is among the relay targets by default, so "
              .. "you can read them there. If you turned the relay off, or dropped your "
              .. "language from DRGT_RELAY_TARGETS, set DRGT_OVERLAY_ENABLED=true in "
              .. "settings.ini to show them in the small overlay window")
    end
    return false
end

--- MOD が送った発言を覚えておく。サーバを経由して自分にも戻ってくるので、それを弾くため。
--- 同じ文面を何度送っても区別できるよう、1回の送信ごとに1件ずつ持つ。
local function remember_own(text, sender)
    if text == nil or text == "" then return end
    local list = State.own_sent[text] or {}
    list[#list + 1] = { sender = sender or "", expires_at = State.now + OWN_ECHO_TTL_MS }
    State.own_sent[text] = list
end

--- 送信に失敗したので、直前に覚えた1件を取り消す。
local function forget_own(text)
    local list = State.own_sent[text]
    if not list then return end
    table.remove(list)
    if #list == 0 then State.own_sent[text] = nil end
end

--- MOD が送った発言の戻りか。当たったら1件を消費する（1回の送信で戻りは1回だけ）。
--- 文面が同じでも、送信者が別の隊員なら戻りではない（その人の発言として扱う）。
local function take_own_echo(sender, text)
    local list = State.own_sent[text]
    if not list then return false end
    local me = get_player_name()
    for i, e in ipairs(list) do
        if e.expires_at > State.now
                and (e.sender == "" or e.sender == sender or (me ~= "" and sender == me)) then
            table.remove(list, i)
            if #list == 0 then State.own_sent[text] = nil end
            return true
        end
    end
    return false
end

--- 自分が打った合図（on_outgoing）が残っていれば、古いものから1つ消費して true を返す。
local function take_local_send()
    while #State.local_sends > 0 do
        local at = table.remove(State.local_sends, 1)
        if (State.now - at) <= LOCAL_SEND_WINDOW_MS then return true end
    end
    return false
end

local function send_chat(sender, text, sender_type)
    if text == nil or text == "" then return false end
    local pc = get_pc()
    if not pc then
        U.log("Could not send: no PlayerController found")
        return false
    end
    if sender == nil or sender == "" then sender = get_player_name() end

    U.dbg("send: calling Server_NewMessage sender=%s text=%s", sender, text)
    remember_own(text, sender)
    State.sending = true
    local ok, err = pcall(function()
        pc:Server_NewMessage(sender, text, sender_type or 0)
    end)
    State.sending = false
    U.dbg("send: returned from the call")

    if not ok then
        U.log("Server_NewMessage call failed (err type=%s): %s", type(err), tostring(err))
        local okc, cls = pcall(function() return pc:GetClass():GetFullName() end)
        U.log("  called on: %s", okc and U.tostr(cls) or "unknown class")
        U.log("  arguments: sender=%q text=%q type=%s",
              tostring(sender), tostring(text), tostring(sender_type or 0))
        forget_own(text)
        return false
    end
    U.dbg("sent: %s", text)
    return true
end

--- 行頭の "Karl: " から名前を取り出す。無ければ nil。
local function quoted_sender(text)
    local name = text:match("^([^:]+):%s")
    if name == nil then return nil end
    name = U.trim(name)
    if name == "" or U.utf8_len(name) > 32 then return nil end
    return name
end

--- 1行を全員に流す。ゲームスレッドから呼ぶこと。
local function broadcast_relay(text)
    if text == nil or text == "" then return false end

    if Cfg.host_relay.method == "gamemsg" then
        remember_own(text, "")
        return display_via_gamestate(text)
    end

    local original = quoted_sender(text)
    local sender = get_player_name()
    if original and (Cfg.host_relay.sender == "original" or sender == "") then
        sender = original
        text = text:gsub("^[^:]+:%s*", "", 1)
    end
    return send_chat(sender, text, 0)
end

--- 他人（別のホスト）が流した中継行か。
--- 中継行は「発言者名: 訳 / 訳 / 訳」の形でホストの名前で届く。行頭の名前が少し前に
--- 喋った人で、かつ本文が複数の訳を区切りでつないだものだけを中継行とみなす。
--- 区切りを見ないと「Karl: 了解」のような普通の返事まで捨ててしまう。
local function is_relay_line(sender, text)
    local original = quoted_sender(text)
    if original == nil or original == sender then return false end
    local expires_at = State.seen_senders[original]
    if expires_at == nil or expires_at <= State.now then return false end
    return text:find(RELAY_SEPARATOR, 1, true) ~= nil
end

--- 中継行を順番待ちに入れる。1行ずつ間隔を空けて送るため、ここでは送らない。
local function queue_relay(lines)
    if not Cfg.host_relay.enabled or not State.enabled then return end
    local max_queue = Cfg.host_relay.max_queue or 12
    for _, line in ipairs(lines) do
        if line ~= "" then
            State.relay_queue[#State.relay_queue + 1] = line
        end
    end
    while #State.relay_queue > max_queue do
        table.remove(State.relay_queue, 1)
    end
end

local function pump_relay()
    if #State.relay_queue == 0 then return end
    if not State.enabled then
        State.relay_queue = {}
        return
    end
    local interval = Cfg.host_relay.interval_ms or 700
    if (State.now - State.last_relay_at) < interval then return end
    State.last_relay_at = State.now
    local line = table.remove(State.relay_queue, 1)
    U.in_game_thread(function() broadcast_relay(line) end)
end

local function should_translate_outgoing(text)
    text = U.trim(text)
    if text == "" then return false end
    if U.utf8_len(text) < (Cfg.outgoing.min_length or 2) then return false end
    for _, p in ipairs(Cfg.outgoing.ignore_prefixes or {}) do
        if p ~= "" and U.starts_with(text, p) then return false end
    end
    return true
end

local function on_incoming(Context, MsgParam)
    if not State.enabled then return end
    if not IPC.connected then return end

    local ok, err = pcall(function()
        local msg    = MsgParam:get()
        local text   = U.trim(U.tostr(msg.Msg))
        local sender = U.tostr(msg.Sender)
        local mtype  = tonumber(msg.MsgType) or 0

        if text == "" then return end
        if mtype ~= 0 and not Cfg.incoming.translate_game_messages then return end

        if take_own_echo(sender, text) then return end

        if is_relay_line(sender, text) then
            U.dbg("relay line, not translating: %s", text)
            return
        end
        if sender ~= "" then
            State.seen_senders[sender] = State.now + SEEN_SENDER_TTL_MS
        end

        -- 自分の発言かどうかは、実際に自分が打った合図（on_outgoing）が残っているかで決める。
        -- 名前だけで決めると、同じ名前の隊員の発言まで自分の発言として訳して送ってしまう。
        local me = get_player_name()
        local mine = false
        if me == "" or sender == me then
            mine = take_local_send()
            if not mine and sender == me then
                -- 自分の名前なのに合図が無い: 同じ名前の隊員か、合図の期限を過ぎて届いた
                -- 自分の発言。どちらか決められないので何もしない
                U.dbg("same name as you but you did not just send, ignoring: %s", text)
                return
            end
        end
        if mine and me == "" and sender ~= "" then
            State.player_name = sender
            IPC.send("NAME", sender)
            U.dbg("your name: %s", sender)
        end

        if mine then
            if not Cfg.outgoing.enabled then return end
            if not should_translate_outgoing(text) then return end
            U.dbg("outgoing detected: %s", text)
            IPC.request("out", sender, text, function(_, outtext)
                if outtext == "" then return end
                U.in_game_thread(function() send_chat(sender, outtext, 0) end)
            end)
            return
        end

        if not Cfg.incoming.enabled then return end
        local relay = Cfg.host_relay.enabled and is_host() and player_count() ~= 1
        if relay and not State.warned_relay then
            State.warned_relay = true
            U.log("Relaying as host (translations of what others say go to everyone's chat). "
                  .. "To stop, set DRGT_RELAY_ENABLED=false in settings.ini")
        end
        U.dbg("incoming: [%s] %s (relay=%s)", sender, text, tostring(relay))
        IPC.request("in", sender, text, function(_, outtext, relay_lines)
            U.in_game_thread(function()
                if outtext ~= "" then display_line(outtext) end
            end)
            if relay_lines and #relay_lines > 0 then queue_relay(relay_lines) end
        end, nil, relay)
    end)

    if not ok then U.dbg("on_incoming error: %s", tostring(err)) end
end

--- ⚠ このフックでは FString 引数(Sender/Text)に絶対に触らないこと。
local function on_outgoing(Context)
    if State.sending then return end
    if not State.enabled or not Cfg.outgoing.enabled then return end

    local ok, err = pcall(function()
        local pc = Context:get()
        if not is_local_controller(pc) then return end
        State.pc = pc
        State.local_sends[#State.local_sends + 1] = State.now
    end)

    if not ok then U.dbg("on_outgoing error: %s", tostring(err)) end
end

--- 期限切れの「自分が送った文」と「最近見かけた発言者」を捨てる
local function gc_own_sent()
    for text, list in pairs(State.own_sent) do
        for i = #list, 1, -1 do
            if State.now > list[i].expires_at then table.remove(list, i) end
        end
        if #list == 0 then State.own_sent[text] = nil end
    end
    while #State.local_sends > 0
            and (State.now - State.local_sends[1]) > LOCAL_SEND_WINDOW_MS do
        table.remove(State.local_sends, 1)
    end
    for name, expires_at in pairs(State.seen_senders) do
        if State.now > expires_at then State.seen_senders[name] = nil end
    end
end

IPC.on("SAY", function(fields)
    local text = fields[2] or ""
    if text == "" then return end
    U.in_game_thread(function() send_chat(get_player_name(), text, 0) end)
end)

IPC.on("NOTE", function(fields)
    local text = fields[2] or ""
    if text ~= "" then
        U.in_game_thread(function() display_line(text) end)
    end
end)

IPC.on("HELLO", function(fields)
    U.log("bridge version = %s", fields[2] or "?")
end)

--- 診断用。いまの状態をログに出す。config.lua の debug が真のときだけ動く。
IPC.on("DIAG", function()
    if not Cfg.debug then return end
    U.in_game_thread(function()
        local gs = get_gamestate()
        local pc = get_pc()
        U.log("DIAG: gamestate=%s pc=%s host=%s players=%s name=%q enabled=%s queue=%d",
              tostring(is_valid(gs)), tostring(pc ~= nil), tostring(is_host()),
              tostring(player_count()), get_player_name(),
              tostring(State.enabled), #State.relay_queue)
    end)
end)

--- 診断用。Server_NewMessage を「自分で呼んだ」印を付けずに叩くので、実際にチャットを打ったときと同じ経路(on_outgoing)を通る。
IPC.on("SIMSAY", function(fields)
    if not Cfg.debug then return end
    local text = fields[2] or ""
    if text == "" then return end
    local sender = fields[3]
    if sender == nil or sender == "" then sender = get_player_name() end
    U.in_game_thread(function()
        local pc = get_pc()
        if not pc then
            U.log("SIMSAY: no PlayerController found")
            return
        end
        U.log("SIMSAY: sender=%q text=%q", sender, text)
        local ok, err = pcall(function()
            pc:Server_NewMessage(sender, text, 0)
        end)
        if not ok then U.log("SIMSAY failed: %s", tostring(err)) end
    end)
end)

local function safe_hook(path, pre_cb, post_cb)
    local ok, a = pcall(RegisterHook, path, pre_cb, post_cb)
    if ok then
        U.log("hook registered: %s", path)
        return true
    end
    U.log("!! hook registration failed: %s (%s)", path, tostring(a))
    return false
end

local function init()
    U.log("DRGTranslate v%s started", MOD_VERSION)

    IPC.init(Cfg.ipc.dir)
    IPC.send("HELLO", MOD_VERSION)

    safe_hook("/Script/FSD.FSDGameState:ClientNewMessage", on_incoming)
    safe_hook("/Script/FSD.FSDPlayerController:Server_NewMessage", on_outgoing)

    if type(RegisterKeyBind) == "function" and Key and Cfg.hotkey and Key[Cfg.hotkey.toggle] then
        RegisterKeyBind(Key[Cfg.hotkey.toggle], function()
            State.enabled = not State.enabled
            local s = State.enabled and "ON" or "OFF"
            U.log("Translation %s", s)
            IPC.send("TOGGLE", s)
            U.in_game_thread(function()
                display_line("[DRGTranslate] Translation " .. s)
            end)
        end)
        U.log("Press %s to toggle translation on and off", Cfg.hotkey.toggle)
    end

    local poll_ms = Cfg.ipc.poll_ms or 100
    U.loop(poll_ms, function()
        State.now = State.now + poll_ms

        IPC.poll()
        IPC.flush()
        pump_relay()

        if (State.now - State.last_alive_at) >= 1000 then
            State.last_alive_at = State.now
            IPC.check_alive()
            IPC.beat(MOD_VERSION)
            gc_own_sent()
        end
    end)
end

init()
