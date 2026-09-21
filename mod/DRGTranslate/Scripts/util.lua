-- DRGTranslate : 共通ユーティリティ

local M = {}

local PREFIX = "[DRGTranslate] "
local debug_enabled = false

function M.set_debug(v)
    debug_enabled = v and true or false
end

function M.log(fmt, ...)
    local ok, s = pcall(string.format, fmt, ...)
    print(PREFIX .. (ok and s or tostring(fmt)) .. "\n")
end

function M.dbg(fmt, ...)
    if debug_enabled then M.log("(dbg) " .. fmt, ...) end
end

local logged_once = {}

--- key ごとに最初の1回だけログに出す。同じ案内を毎回出さないため。
function M.log_once(key, fmt, ...)
    if logged_once[key] then return end
    logged_once[key] = true
    M.log(fmt, ...)
end

--- UE4SS が返す FString / FText / RemoteUnrealParam / 素の string をすべて Lua の string に落とす。
function M.tostr(v)
    if v == nil then return "" end
    local t = type(v)
    if t == "string" then return v end
    if t == "number" or t == "boolean" then return tostring(v) end

    local ok, inner = pcall(function() return v:get() end)
    if ok and inner ~= nil and inner ~= v then
        return M.tostr(inner)
    end

    local ok2, s = pcall(function() return v:ToString() end)
    if ok2 and type(s) == "string" then return s end

    return tostring(v)
end

function M.esc(s)
    s = tostring(s or "")
    s = s:gsub("\\", "\\\\")
    s = s:gsub("\t", "\\t")
    s = s:gsub("\r", "\\r")
    s = s:gsub("\n", "\\n")
    return s
end

function M.unesc(s)
    local out = (tostring(s or ""):gsub("\\(.)", function(c)
        if c == "t" then return "\t" end
        if c == "n" then return "\n" end
        if c == "r" then return "\r" end
        if c == "\\" then return "\\" end
        return "\\" .. c
    end))
    return out
end

function M.split_tab(line)
    local out = {}
    for field in (line .. "\t"):gmatch("([^\t]*)\t") do
        out[#out + 1] = field
    end
    return out
end

function M.trim(s)
    return (tostring(s or ""):gsub("^%s+", ""):gsub("%s+$", ""))
end

function M.starts_with(s, p)
    return s:sub(1, #p) == p
end

--- UTF-8 としての文字数（おおよそ）。バイト数だと日本語で誤判定するため。
function M.utf8_len(s)
    local n = 0
    for _ in tostring(s or ""):gmatch("[^\128-\191]") do n = n + 1 end
    return n
end

--- interval_ms ごとに fn を呼ぶ。fn はゲームスレッド外で実行されるので UObject に触る処理は ExecuteInGameThread で包むこと。
function M.loop(interval_ms, fn)
    if type(LoopAsync) == "function" then
        LoopAsync(interval_ms, function()
            local ok, err = pcall(fn)
            if not ok then M.log("loop error: %s", tostring(err)) end
            return false
        end)
        return true
    end

    if type(ExecuteInGameThreadWithDelay) == "function" then
        local function step()
            local ok, err = pcall(fn)
            if not ok then M.log("loop error: %s", tostring(err)) end
            ExecuteInGameThreadWithDelay(interval_ms, step)
        end
        ExecuteInGameThreadWithDelay(interval_ms, step)
        return true
    end

    M.log("!! Neither LoopAsync nor ExecuteInGameThreadWithDelay is available. Check your UE4SS version")
    return false
end

--- ゲームスレッドで実行
function M.in_game_thread(fn)
    if type(ExecuteInGameThread) == "function" then
        ExecuteInGameThread(function()
            local ok, err = pcall(fn)
            if not ok then M.log("game-thread error: %s", tostring(err)) end
        end)
    else
        local ok, err = pcall(fn)
        if not ok then M.log("error: %s", tostring(err)) end
    end
end

return M
