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

--- UE4SS が返す FString / FText / RemoteUnrealParam / 素の string を
--- すべて Lua の string に落とす。
function M.tostr(v)
    if v == nil then return "" end
    local t = type(v)
    if t == "string" then return v end
    if t == "number" or t == "boolean" then return tostring(v) end

    -- RemoteUnrealParam の場合は中身を取り出す
    local ok, inner = pcall(function() return v:get() end)
    if ok and inner ~= nil and inner ~= v then
        return M.tostr(inner)
    end

    local ok2, s = pcall(function() return v:ToString() end)
    if ok2 and type(s) == "string" then return s end

    return tostring(v)
end

-- ------------------------------------------------------------------
-- IPC 用の行フォーマット（TAB 区切り + エスケープ）
-- ------------------------------------------------------------------

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

--- UTF-8 文字列のコードポイントを 1 つずつ fn に渡す。
--- fn が true を返したら打ち切る。（不正バイトは読み飛ばす）
function M.each_codepoint(s, fn)
    s = tostring(s or "")
    local i, n = 1, #s
    while i <= n do
        local b = s:byte(i)
        local cp, size
        if b < 0x80 then
            cp, size = b, 1
        elseif b >= 0xC2 and b <= 0xDF then
            cp, size = b - 0xC0, 2
        elseif b >= 0xE0 and b <= 0xEF then
            cp, size = b - 0xE0, 3
        elseif b >= 0xF0 and b <= 0xF4 then
            cp, size = b - 0xF0, 4
        else
            i = i + 1
            goto continue
        end
        if i + size - 1 > n then break end
        for k = 1, size - 1 do
            local cb = s:byte(i + k)
            if not cb or cb < 0x80 or cb > 0xBF then
                cp = nil
                break
            end
            cp = cp * 0x40 + (cb - 0x80)
        end
        if cp and fn(cp) then return end
        i = i + size
        ::continue::
    end
end

--- 日本語(かな/漢字)を含むか
function M.has_japanese(s)
    local found = false
    M.each_codepoint(s, function(cp)
        if (cp >= 0x3040 and cp <= 0x30FF)      -- ひらがな・カタカナ
            or (cp >= 0x4E00 and cp <= 0x9FFF)  -- 漢字
            or (cp >= 0xFF66 and cp <= 0xFF9D)  -- 半角カナ
        then
            found = true
            return true
        end
        return false
    end)
    return found
end

-- ------------------------------------------------------------------
-- スケジューラ（UE4SS のバージョン差を吸収）
-- ------------------------------------------------------------------

--- interval_ms ごとに fn を呼ぶ。fn はゲームスレッド外で実行されるので
--- UObject に触る処理は ExecuteInGameThread で包むこと。
function M.loop(interval_ms, fn)
    if type(LoopAsync) == "function" then
        LoopAsync(interval_ms, function()
            local ok, err = pcall(fn)
            if not ok then M.log("loop error: %s", tostring(err)) end
            return false -- false = ループ継続
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

    M.log("!! LoopAsync も ExecuteInGameThreadWithDelay も見つかりません。UE4SS のバージョンを確認してください")
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
