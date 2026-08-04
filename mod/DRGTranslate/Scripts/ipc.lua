-- DRGTranslate : ローカル常駐プロセス(bridge)とのファイルIPC
--
-- UE4SS の Lua にはソケットが無いため、追記専用の2本のテキストファイルで
-- 双方向通信する。各ファイルの書き手は片側だけなので競合しない。
--
--   <dir>/to_bridge.txt   ゲーム -> bridge   (ゲームが追記 / bridge が読む)
--   <dir>/to_game.txt     bridge -> ゲーム   (bridge が追記 / ゲームが読む)
--   <dir>/bridge.alive    bridge の生存確認用
--
-- 行フォーマット: <TYPE>\t<field>\t<field>... \n （フィールドは util.esc 済み）

local U = require("util")

local M = {}

M.dir = nil
M.connected = false

local path_to_bridge, path_to_game, path_alive, path_game_alive
local read_offset = 0
local next_id = 1
local pending = {}      -- [id] = { on_result = fn, on_error = fn }
local handlers = {}     -- [TYPE] = fn(fields)
local outbox = {}       -- 送信待ちの行
local alive_miss = 0

-- Windows なら "\"、それ以外は "/"
local SEP = package.config:sub(1, 1)

local function join(dir, name)
    return dir .. SEP .. name
end

local function file_size(path)
    local f = io.open(path, "rb")
    if not f then return nil end
    local size = f:seek("end")
    f:close()
    return size
end

local function truncate(path)
    local f = io.open(path, "wb")
    if f then f:close() end
end

--- 通信フォルダを決定して初期化する
function M.init(dir_override)
    local dir = dir_override
    if not dir or dir == "" then
        local appdata = os.getenv("APPDATA")
        if not appdata or appdata == "" then
            appdata = os.getenv("TEMP") or "."
        end
        dir = appdata .. SEP .. "DRGTranslate"
    end
    M.dir = dir

    -- フォルダの存在確認。書けなければ mkdir を一度だけ呼ぶ
    -- （毎回 os.execute すると cmd ウィンドウが一瞬出るため）
    local probe = io.open(join(dir, ".probe"), "wb")
    if probe then
        probe:close()
        os.remove(join(dir, ".probe"))
    elseif SEP == "\\" then
        os.execute(string.format('mkdir "%s" 2>nul', dir))
    else
        os.execute(string.format('mkdir -p "%s" 2>/dev/null', dir))
    end

    path_to_bridge = join(dir, "to_bridge.txt")
    path_to_game   = join(dir, "to_game.txt")
    path_alive     = join(dir, "bridge.alive")
    path_game_alive = join(dir, "game.alive")

    -- セッション開始時に両方リセットする。
    -- bridge 側もファイルが縮んだらオフセットを 0 に戻すよう実装してある。
    truncate(path_to_bridge)
    truncate(path_to_game)
    read_offset = 0
    pending = {}
    outbox = {}
    M.connected = false

    U.log("IPC dir: %s", dir)
    return true
end

--- 生の行を送信キューに積む。
--- 実際の書き込みは flush() でまとめて行う（複数スレッドからの
--- 追記が混ざらないようにするため）。
function M.send(...)
    if not path_to_bridge then return false end
    local parts = { ... }
    for i = 1, #parts do parts[i] = U.esc(parts[i]) end
    outbox[#outbox + 1] = table.concat(parts, "\t") .. "\n"
    return true
end

--- 溜まった送信キューを書き出す。ポーリングループからのみ呼ぶこと。
function M.flush()
    if #outbox == 0 or not path_to_bridge then return end
    local payload = table.concat(outbox)
    local f = io.open(path_to_bridge, "ab")
    if not f then
        U.dbg("to_bridge.txt を開けませんでした（次回に再試行）")
        return
    end
    f:write(payload)
    f:close()
    U.dbg("-> %d line(s)", #outbox)
    outbox = {}
end

--- 翻訳リクエスト
--- kind: "in" (受信文を日本語へ) / "out" (自分の発言を外国語へ)
function M.request(kind, sender, text, on_result, on_error)
    local id = next_id
    next_id = next_id + 1
    pending[id] = { on_result = on_result, on_error = on_error, kind = kind, text = text }
    M.send("REQ", tostring(id), kind, sender or "", text or "")
    return id
end

function M.on(msg_type, fn)
    handlers[msg_type] = fn
end

local function dispatch(fields)
    local t = fields[1]
    if t == "RES" then
        local id = tonumber(fields[2] or "")
        local p = id and pending[id]
        if p then
            pending[id] = nil
            if p.on_result then
                p.on_result(fields[4] or "", fields[5] or "", p)
            end
        end
        return
    end

    if t == "ERR" then
        local id = tonumber(fields[2] or "")
        local p = id and pending[id]
        if p then
            pending[id] = nil
            if p.on_error then p.on_error(fields[3] or "") end
        end
        U.dbg("bridge error: %s", fields[3] or "")
        return
    end

    local h = handlers[t]
    if h then h(fields) end
end

--- to_game.txt の未読分を読んで処理する。ゲームスレッド外から呼ばれる想定。
function M.poll()
    if not path_to_game then return end

    local size = file_size(path_to_game)
    if size == nil then return end
    if size < read_offset then
        -- bridge 側が作り直した
        read_offset = 0
    end
    if size == read_offset then return end

    local f = io.open(path_to_game, "rb")
    if not f then return end
    f:seek("set", read_offset)
    local chunk = f:read("a") or ""
    f:close()

    -- 完全な行だけ処理し、途中で切れている分は次回に回す
    local last_nl = chunk:match("^.*()\n")
    if not last_nl then return end
    local complete = chunk:sub(1, last_nl)
    read_offset = read_offset + #complete

    for line in complete:gmatch("([^\n]*)\n") do
        if line ~= "" then
            local raw = U.split_tab(line)
            local fields = {}
            for i, v in ipairs(raw) do fields[i] = U.unesc(v) end
            local ok, err = pcall(dispatch, fields)
            if not ok then U.log("dispatch error: %s", tostring(err)) end
        end
    end
end

--- こちらの生存を bridge に知らせる。bridge.alive と対称。
---
--- MOD は送るものが無ければ何も書かないので、送信の有無で生死を判定すると
--- 「黙っているだけ」を切断と誤認する。そのため専用の心拍ファイルを持つ。
function M.beat(version)
    if not path_game_alive then return end
    local f = io.open(path_game_alive, "wb")
    if not f then return end
    f:write(string.format("%s %d\n", tostring(version or "?"), os.time()))
    f:close()
end

--- bridge が動いているか。
--- bridge.alive には "<version> <unixtime>" が毎秒書き込まれるので、
--- ファイルの有無ではなく更新時刻で判定する（強制終了された場合に
--- ファイルだけ残るため）。
function M.check_alive()
    local fresh = false
    local f = path_alive and io.open(path_alive, "rb")
    if f then
        local content = f:read("l") or ""
        f:close()
        local ts = tonumber(content:match("(%d+)%s*$") or "")
        if ts then
            local age = os.time() - ts
            fresh = (age >= -5 and age <= 10)
        end
    end

    if fresh then
        alive_miss = 0
        if not M.connected then
            M.connected = true
            U.log("bridge に接続しました")
        end
        return true
    end

    alive_miss = alive_miss + 1
    if M.connected and alive_miss > 3 then
        M.connected = false
        U.log("bridge との接続が切れました（run_bridge.bat は動いていますか？）")
    end
    return false
end

function M.pending_count()
    local n = 0
    for _ in pairs(pending) do n = n + 1 end
    return n
end

return M
