-- ipc.lua の接続判定の単体テスト。bridge を起動せずに走る。
--
--   lua5.4 tools/ipc_test.lua
--
-- bridge.alive を手で書き換えて、つながったとき・つながり直したとき・bridge が
-- 入れ替わったとき（起動番号が変わったとき）に HELLO を送り直す合図が出ることを確かめる。

local here = (arg[0]:match("^(.*)[/\\]") or ".")
package.path = here .. "/../mod/DRGTranslate/Scripts/?.lua;" .. package.path

local U = require("util")
U.log = function() end  -- テストの出力を汚さない

local IPC = require("ipc")

local dir = os.tmpname()
os.remove(dir)
os.execute(string.format('mkdir -p "%s"', dir))
IPC.init(dir)

local connects = 0
IPC.set_on_connect(function() connects = connects + 1 end)

local failures = 0
local function check(cond, label, detail)
    if cond then
        print("  ok   " .. label)
    else
        failures = failures + 1
        print("  FAIL " .. label .. (detail and ("  -> " .. tostring(detail)) or ""))
    end
end

local function write_alive(content)
    local f = assert(io.open(dir .. "/bridge.alive", "wb"))
    f:write(content)
    f:close()
end

local function lose()
    os.remove(dir .. "/bridge.alive")
    for _ = 1, 5 do IPC.check_alive() end
end

print("== ipc test ==")

IPC.check_alive()
check(not IPC.connected and connects == 0, "bridge.alive が無ければつながらない")

write_alive(string.format("0.7.1 1000 %d\n", os.time()))
IPC.check_alive()
check(IPC.connected and connects == 1, "つながったら合図が出る", connects)

IPC.check_alive()
IPC.check_alive()
check(connects == 1, "同じ bridge のままなら合図は1回だけ", connects)

write_alive(string.format("0.7.1 2000 %d\n", os.time()))
IPC.check_alive()
check(IPC.connected and connects == 2,
      "切断に気づく前に bridge が入れ替わっても（起動番号が変わる）合図が出る", connects)

lose()
check(not IPC.connected, "bridge.alive が消えて4回続けば切断とみなす")
write_alive(string.format("0.7.1 2000 %d\n", os.time()))
IPC.check_alive()
check(IPC.connected and connects == 3, "つながり直したら合図が出る", connects)

-- 起動番号を書かない古い bridge（「<版> <時刻>」）
lose()
write_alive(string.format("0.7.0 %d\n", os.time()))
IPC.check_alive()
check(IPC.connected and connects == 4, "古い形の bridge.alive でもつながる", connects)
-- 版の末尾の数字（0.7.0 の 0 と 0.6.9 の 9）を起動番号と読むと、入れ替わったと誤判定する
write_alive(string.format("0.6.9 %d\n", os.time()))
IPC.check_alive()
check(connects == 4, "古い形では版の数字を起動番号と取り違えない", connects)

write_alive(string.format("0.7.1 3000 %d\n", os.time() - 60))
for _ = 1, 5 do IPC.check_alive() end
check(not IPC.connected, "時刻が古い bridge.alive は生きているとみなさない")

os.remove(dir .. "/bridge.alive")
os.remove(dir .. "/to_bridge.txt")
os.remove(dir .. "/to_game.txt")
os.remove(dir)

print()
if failures == 0 then
    print("ALL PASS")
    os.exit(0)
end
print(failures .. " 件 FAIL")
os.exit(1)
