-- UE4SS のグローバル API と DRG のオブジェクトを模したテスト用スタブ。
-- 実機を起動せずに mod のロジック（hook・翻訳の往復・表示先の切替）を確認するためのもの。
--
--   lua5.4 tools/mock_test.lua
--
-- 本番の動作には不要なので、ゲームへは配布されない。

local M = {}

M.hooks = {}          -- [path] = { pre = fn, post = fn }
M.loops = {}          -- { {interval = ms, fn = fn} }
M.keybinds = {}
M.sent = {}           -- Server_NewMessage で送られたもの
M.displayed = {}      -- PostGameMessage / ウィジェットに出たもの
M.displayed_widget_attempts = 0   -- ウィジェット直叩きを試みた回数
M.log = {}

-- ---------------------------------------------------------------------
-- UE の値を模したラッパー
-- ---------------------------------------------------------------------

local function FString(v)
    return setmetatable({ __v = v }, {
        __index = { ToString = function(self) return self.__v end },
        __tostring = function(self) return self.__v end,
    })
end
M.FString = FString

--- RemoteUnrealParam 相当（:get() / :set()）
local function Param(v)
    local p = { __v = v }
    function p:get() return self.__v end
    function p:set(nv) self.__v = nv; M.log[#M.log + 1] = "param:set " .. tostring(nv) end
    return p
end
M.Param = Param

-- ---------------------------------------------------------------------
-- 偽のゲームオブジェクト
-- ---------------------------------------------------------------------

local function make_obj(fields)
    local o = fields or {}
    o.__valid = true
    function o:IsValid() return self.__valid end
    function o:GetFullName() return self.__name or "MockObject" end
    return o
end

function M.make_world(opts)
    opts = opts or {}

    local player_state = make_obj({ __name = "FSDPlayerState_0" })
    function player_state:GetPlayerName() return FString(opts.player_name or "Kiyo") end

    local pc = make_obj({ __name = "FSDPlayerController_0", PlayerState = player_state })
    function pc:IsLocalController() return true end
    function pc:Server_NewMessage(sender, text, sender_type)
        M.sent[#M.sent + 1] = { sender = sender, text = text, type = sender_type }
    end

    -- ロビーの人数。TArray の代わりに Lua の配列を持たせる（#arr で数えられる）
    local players = {}
    for i = 1, (opts.players or 1) do players[i] = make_obj({ __name = "PlayerState_" .. i }) end

    local gs = make_obj({ __name = "FSDGameState_0", PlayerArray = players })
    function gs:HasAuthority() return opts.is_host == true end
    function gs:PostGameMessage(text)
        -- ホストが呼ぶと全員に配信される。ただしロビーに自分しかいなければ
        -- 配信先も自分だけなので問題ない。他の隊員がいるのに呼んだら異常とする。
        if opts.is_host and #players > 1 then
            error("他の隊員がいるのにホストが PostGameMessage を呼んだ（全員に見えてしまう）")
        end
        M.displayed[#M.displayed + 1] = { via = "gamestate", text = text }
    end

    local hud = make_obj({ __name = "HUD_Chat_C_0" })
    hud["Add Chat Message"] = function(_self, msg)
        -- 実機ではここが構造体引数になり、UE4SS が組み立てに失敗すると
        -- プロセスごと落ちる。何回試みたかを数えておく。
        M.displayed_widget_attempts = M.displayed_widget_attempts + 1
        M.displayed[#M.displayed + 1] = { via = "widget", text = msg.Msg }
    end

    M.pc, M.gs, M.hud = pc, gs, hud
    return { pc = pc, gs = gs, hud = hud }
end

-- ---------------------------------------------------------------------
-- UE4SS のグローバル関数
-- ---------------------------------------------------------------------

function M.install()
    _G.RegisterHook = function(path, pre, post)
        M.hooks[path] = { pre = pre, post = post }
        return 1, 2
    end

    _G.LoopAsync = function(interval, fn)
        M.loops[#M.loops + 1] = { interval = interval, fn = fn }
    end

    _G.ExecuteInGameThread = function(fn) fn() end

    _G.FindFirstOf = function(name)
        if name == "FSDGameState" then return M.gs end
        if name == "HUD_Chat_C" then return M.hud end
        if name == "FSDPlayerController" then return M.pc end
        return nil
    end

    _G.FindAllOf = function(name)
        if name == "FSDPlayerController" then return { M.pc } end
        return nil
    end

    _G.RegisterKeyBind = function(key, fn) M.keybinds[key] = fn end
    _G.Key = { F9 = "F9" }
end

--- ループを1回分進める
function M.tick()
    for _, l in ipairs(M.loops) do l.fn() end
end

--- 実時間を待つ（bridge の応答を待つため）
function M.sleep(sec)
    local t = os.clock() + sec
    while os.clock() < t do end
end

--- 受信チャットを1件流し込む
function M.receive(sender, text, msg_type)
    local h = M.hooks["/Script/FSD.FSDGameState:ClientNewMessage"]
    assert(h and h.pre, "ClientNewMessage の hook が登録されていない")
    local msg = {
        Sender = FString(sender),
        Msg = FString(text),
        MsgType = msg_type or 0,
    }
    h.pre(Param(M.gs), Param(msg))
end

--- 自分がチャットを送信する（戻り値: 実際に送信された本文）
---
--- 実機では Server_NewMessage のあと、その発言が ClientNewMessage として
--- 全員（自分を含む）に配信される。MOD は本文をそちら側で受け取るので、
--- ここでも同じ順序で両方のフックを呼ぶ。
function M.send(sender, text, sender_type)
    local h = M.hooks["/Script/FSD.FSDPlayerController:Server_NewMessage"]
    assert(h and h.pre, "Server_NewMessage の hook が登録されていない")
    local p_sender = Param(FString(sender))
    local p_text = Param(FString(text))
    local p_type = Param(sender_type or 0)
    h.pre(Param(M.pc), p_sender, p_text, p_type)

    M.receive(sender, text, 0)

    local v = p_text:get()
    return type(v) == "string" and v or v:ToString()
end

return M
