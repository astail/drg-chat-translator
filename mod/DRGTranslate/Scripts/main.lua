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

-- bridge/drg_bridge.py の VERSION と同じ番号にする（アプリ全体で1つの番号）。
-- MOD を変えていないリリースでも上げる。食い違っているとリリースの CI が止まる
local MOD_VERSION = "0.5.7"

-- 自分の Server_NewMessage の直後に来た発言を「自分のもの」とみなす猶予(ms)。
-- ホストなら同期実行なので即座、クライアントでもサーバ往復ぶんで足りる。
local LOCAL_SEND_WINDOW_MS = 5000

-- 「最近チャットで見かけた人」として名前を覚えておく時間(ms)。
-- 中継行かどうかの判定に使う。中継は元の発言の直後に流れるので短くて足りるが、
-- 翻訳の往復ぶんの余裕を見て長めにしている。
local SEEN_SENDER_TTL_MS = 120000

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
    seen_senders   = {},       -- [発言者名] = 期限。中継行の判定に使う
    last_alive_at  = 0,
    local_sent_at  = 0,       -- 自分が最後に Server_NewMessage を通した時刻
    display_ok     = nil,      -- ゲーム内表示が成功しているか
    warned_display = false,
    relay_queue    = {},       -- ホストとして全員に流す順番待ちの行
    last_relay_at  = 0,
    warned_relay   = false,
}

U.set_debug(Cfg.debug)

-- 古い config.lua のまま MOD だけ更新された場合でも動くようにしておく
Cfg.host_relay = Cfg.host_relay or { enabled = true }

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

--- 自分がホストか。上の is_authority と違い、判定できなければ false を返す。
--- どちらも「確信が持てないなら他人に見せない」方向へ倒すための既定値で、
--- 中継はホストだと確認できたときだけ行う。
local function is_host()
    local gs = get_gamestate()
    if not is_valid(gs) then return false end
    local ok, r = pcall(function() return gs:HasAuthority() end)
    return ok and r == true
end

--- ロビーの人数。読めなければ -1。
--- 自分ひとりなら、ホストでも PostGameMessage を使ってよい
--- （全員に配信されるが、その「全員」が自分だけなので実質ローカル表示）。
local function player_count()
    local gs = get_gamestate()
    if not is_valid(gs) then return -1 end
    local ok, arr = pcall(function() return gs.PlayerArray end)
    if not ok or arr == nil then return -1 end
    -- UE4SS のバージョンで TArray の数え方が違うので両方試す
    local ok2, n = pcall(function() return #arr end)
    if not ok2 or type(n) ~= "number" then
        ok2, n = pcall(function() return arr:GetArrayNum() end)
    end
    if ok2 and type(n) == "number" then return n end
    return -1
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
--- 実機(UE4SS 3.x / DRG 1.40)で試したところ、候補の3つの関数名すべてで
--- 失敗した（落ちはせず pcall で捕まる）。つまり今のところ使えない。
--- 構造体引数の組み立ては環境によっては落ちる可能性も残るため、
--- strategy = "widget" を明示したときだけ使う。
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
    --        ホストは PostGameMessage が全員に配信されてしまうが、
    --        ロビーに自分しかいなければ配信先も自分だけなので使ってよい。
    --        他の隊員がいるときは、ゲーム内には出さずオーバーレイに任せる
    --        （widget 直叩きは実機で動かないことを確認済み）。
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

    -- ホストでも、ロビーに自分しかいなければ PostGameMessage を使ってよい。
    -- 全員に配信されるが、その「全員」が自分だけなので実質ローカル表示になる。
    -- ソロで遊ぶときに何も出ないのが一番不便なので、ここで拾う。
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
        U.log("ホストで他の隊員がいるので、受信の訳は受信用の書式では出しません"
              .. "（ホストのチャット欄に出したものは全員に届くので、訳は中継の行として"
              .. "まとめて流しています）。既定では中継の言語に日本語が含まれるので、"
              .. "その行で読めます。中継を切っている場合や DRGT_RELAY_TARGETS から"
              .. "日本語を外した場合は、settings.ini の DRGT_OVERLAY_ENABLED=true "
              .. "で小窓に出せます")
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
-- 中継（ホストのときだけ、他人の発言の訳を全員に配る）
-- ---------------------------------------------------------------------

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
        -- ホストの PostGameMessage は全員に配信される（クライアントだと自分だけ）。
        -- 自分の受信フックにも戻ってくるので、控えを取ってから流す。
        remember_own(text)
        return display_via_gamestate(text)
    end

    -- 行頭の "Karl: " から元の発言者を拾う
    local original = quoted_sender(text)
    local sender = get_player_name()
    -- 自分の名前は一度発言するまで分からない。その間は元の発言者名で送る
    if original and (Cfg.host_relay.sender == "original" or sender == "") then
        sender = original
        -- 送信者名が元の発言者になるので、本文側の名前は落とす。
        -- そのままだと "Karl: Karl: ..." と二重になる
        text = text:gsub("^[^:]+:%s*", "", 1)
    end
    return send_chat(sender, text, 0)
end

--- 他人（別のホスト）が流した中継行か。
--- ホストが流した訳文を、受け取った側がもう一度翻訳しないようにする。
--- 自分が流したぶんは own_sent で弾けるので、ここで見るのは他人のぶんだけ。
---
--- 中継行は「ホストの名前で送られてくるが、本文は別人の名前で始まる」
--- （"Kiyo: Karl: 気をつけろ …"）。この食い違いを目印にしている。
--- 訳文そのものに目印を入れると全員のチャットに記号が並ぶので入れていない。
---
--- 名前の部分は「少し前にチャットで見かけた人」に限る。中継されるのは
--- 全員が受け取った発言の訳なので、元の発言者は必ず直前に喋っている。
--- これを見ないと "warning: swarm incoming" のような、たまたまコロンで
--- 始まる普通の発言まで中継行と誤判定して翻訳しなくなる。
local function is_relay_line(sender, text)
    local original = quoted_sender(text)
    if original == nil or original == sender then return false end
    local expires_at = State.seen_senders[original]
    return expires_at ~= nil and expires_at > State.now
end

--- 中継行を順番待ちに入れる。1行ずつ間隔を空けて送るため、ここでは送らない。
--- まとめて送るとチャットが一瞬で流れてしまい、
--- 1フレームで Server_NewMessage を連打することにもなる。
local function queue_relay(lines)
    if not Cfg.host_relay.enabled or not State.enabled then return end
    local max_queue = Cfg.host_relay.max_queue or 12
    for _, line in ipairs(lines) do
        if line ~= "" then
            State.relay_queue[#State.relay_queue + 1] = line
        end
    end
    -- 溢れた分は古いものから捨てる。遅れて出る訳文は価値が薄い
    while #State.relay_queue > max_queue do
        table.remove(State.relay_queue, 1)
    end
end

local function pump_relay()
    if #State.relay_queue == 0 then return end
    -- F9 で切ったら、順番待ちの分は捨てる。ここを見ないと OFF にしたあとも
    -- 数秒かけて中継が流れ続け、全員のチャットに出てしまう
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
    -- 何語の発言を訳すかは bridge が settings.ini の DRGT_OUTGOING_SOURCE で決める。
    -- 以前はここで日本語かどうかを見ていたため、英語などで打った発言は
    -- 設定を変えても訳せなかった。訳さない発言には空の訳が返ってくる
    return true
end

-- ---------------------------------------------------------------------
-- フック: 受信
-- ---------------------------------------------------------------------

local function on_incoming(Context, MsgParam)
    if not State.enabled then return end
    if not IPC.connected then return end

    local ok, err = pcall(function()
        local msg    = MsgParam:get()
        local text   = U.trim(U.tostr(msg.Msg))
        local sender = U.tostr(msg.Sender)
        local mtype  = tonumber(msg.MsgType) or 0   -- 0 = ES_Chat, 1 = ES_Game

        if text == "" then return end
        if mtype ~= 0 and not Cfg.incoming.translate_game_messages then return end

        -- 自分が送った訳文が返ってきた分は無視する
        local expires_at = State.own_sent[text]
        if expires_at and expires_at > State.now then return end

        -- ホストが流した中継行は翻訳しない（訳文をさらに訳すことになるため）。
        -- 判定に使うので、この発言より前に誰が喋ったかを覚えておく
        if is_relay_line(sender, text) then
            U.dbg("中継行なので翻訳しません: %s", text)
            return
        end
        if sender ~= "" then
            State.seen_senders[sender] = State.now + SEEN_SENDER_TTL_MS
        end

        -- この発言が自分のものか判定する。
        -- 名前が分かっていればそれで照合し、まだなら「直前に自分の
        -- Server_NewMessage が走ったか」で判定して、そのとき名前を覚える。
        local me = get_player_name()
        local mine
        if me ~= "" then
            mine = (sender == me)
        else
            mine = State.local_sent_at > 0
                and (State.now - State.local_sent_at) <= LOCAL_SEND_WINDOW_MS
            if mine and sender ~= "" then
                State.player_name = sender
                IPC.send("NAME", sender)
                U.dbg("自分の名前: %s", sender)
            end
        end
        if mine then State.local_sent_at = 0 end

        if mine then
            -- 自分の発言。訳す言語なら訳文を2通目として送る
            if not Cfg.outgoing.enabled then return end
            if not should_translate_outgoing(text) then return end
            U.dbg("送信を検出: %s", text)
            IPC.request("out", sender, text, function(_, outtext)
                if outtext == "" then return end
                U.in_game_thread(function() send_chat(sender, outtext, 0) end)
            end)
            return
        end

        -- 他人の発言。訳文を自分にだけ出す。
        -- 自分がホストのときは、全員に配る用の訳も一緒に作ってもらう
        -- （同じ1回の API 呼び出しで返ってくる）。
        if not Cfg.incoming.enabled then return end
        -- ロビーに自分しかいないなら中継しない。読む相手がいないのに
        -- 4言語ぶん訳すのは無駄だし、チャットも埋まる。
        -- 人数が読めない(-1)ときは今までどおり中継する。
        local relay = Cfg.host_relay.enabled and is_host() and player_count() ~= 1
        if relay and not State.warned_relay then
            State.warned_relay = true
            U.log("ホストとして中継します（他人の発言の訳を全員のチャットに流します）。"
                  .. "止めるときは settings.ini の DRGT_RELAY_ENABLED=false")
        end
        U.dbg("受信: [%s] %s (中継=%s)", sender, text, tostring(relay))
        IPC.request("in", sender, text, function(_, outtext, relay_lines)
            U.in_game_thread(function()
                if outtext ~= "" then display_line(outtext) end
            end)
            if relay_lines and #relay_lines > 0 then queue_relay(relay_lines) end
        end, nil, relay)
    end)

    if not ok then U.dbg("on_incoming error: %s", tostring(err)) end
end

-- ---------------------------------------------------------------------
-- フック: 送信
-- ---------------------------------------------------------------------

--- ⚠ このフックでは FString 引数(Sender/Text)に絶対に触らないこと。
---
--- 実際のチャット欄から送信すると Server_NewMessage は Blueprint 側から
--- 呼ばれる。そのとき引数を :get() で読むとプロセスごと落ちる
--- (pcall では止められない)。Lua から同じ関数を呼んだ場合は UE4SS が
--- 自前で引数バッファを用意するため読めてしまい、これが原因の特定を
--- 長引かせた。
---
--- Context だけは安全に読めるので、ここでは「自分が今チャットを送った」
--- という合図を立てるだけにして、本文は ClientNewMessage 側で受け取る。
--- ホストの場合は他プレイヤーの送信もここを通るため、
--- IsLocalController で自分の分だけに絞る。
local function on_outgoing(Context)
    if State.sending then return end
    if not State.enabled or not Cfg.outgoing.enabled then return end

    local ok, err = pcall(function()
        local pc = Context:get()
        if not is_local_controller(pc) then return end
        State.pc = pc
        State.local_sent_at = State.now
    end)

    if not ok then U.dbg("on_outgoing error: %s", tostring(err)) end
end

--- 期限切れの「自分が送った文」と「最近見かけた発言者」を捨てる
local function gc_own_sent()
    for text, expires_at in pairs(State.own_sent) do
        if State.now > expires_at then State.own_sent[text] = nil end
    end
    for name, expires_at in pairs(State.seen_senders) do
        if State.now > expires_at then State.seen_senders[name] = nil end
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

-- ゲーム内にローカル表示するだけのお知らせ。
-- 送る側（bridge）は英数字で書くこと。ゲームの言語が日本語以外のときは
-- 日本語フォントが読み込まれず、豆腐（□□□）になる
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
--- 「訳が出ない」「中継されない」の切り分けはここを見るのが早い。
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

--- 診断用。Server_NewMessage を「自分で呼んだ」印を付けずに叩くので、
--- 実際にチャットを打ったときとまったく同じ経路(on_outgoing)を通る。
--- SAY だと State.sending が立つため送信フックを素通りしてしまい、
--- そこの不具合を実機で再現できない。config.lua の debug が真のときだけ動く。
IPC.on("SIMSAY", function(fields)
    if not Cfg.debug then return end
    local text = fields[2] or ""
    if text == "" then return end
    -- 3つ目のフィールドで送信者名を差し替えられる（省略時は実際の自分の名前）
    local sender = fields[3]
    if sender == nil or sender == "" then sender = get_player_name() end
    U.in_game_thread(function()
        local pc = get_pc()
        if not pc then
            U.log("SIMSAY: PlayerController が見つかりません")
            return
        end
        U.log("SIMSAY: sender=%q text=%q", sender, text)
        local ok, err = pcall(function()
            pc:Server_NewMessage(sender, text, 0)
        end)
        if not ok then U.log("SIMSAY 失敗: %s", tostring(err)) end
    end)
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
            -- ホストのときはゲーム内に何も出せない（出すと全員に見える）。
            -- 押しても無反応に見えるので、bridge の窓とオーバーレイに出す
            IPC.send("TOGGLE", s)
            -- キーバインドのコールバックはゲームスレッド外で走るため、
            -- UObject に触る表示処理は必ず包んでから呼ぶ
            -- ゲーム内に出す文字は ASCII にしておく。ゲームの言語が日本語以外だと
            -- 日本語フォントが読み込まれず、「翻訳」が □□ になってしまう
            U.in_game_thread(function()
                display_line("[DRGTranslate] Translation " .. s)
            end)
        end)
        U.log("%s キーで翻訳のON/OFFを切り替えられます", Cfg.hotkey.toggle)
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
