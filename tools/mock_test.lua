-- 実機なしで mod のロジックを確認するテスト。
--
--   1. bridge を別プロセスで起動しておく（--fake 付き。APIキー不要）
--        python3 bridge/drg_bridge.py --fake --dir <IPCフォルダ>
--   2. lua5.4 tools/mock_test.lua <IPCフォルダ> [client|host]
--
-- ゲーム内のフックが呼ばれたときの挙動、翻訳の往復、
-- 表示先の切り替え（クライアント/ホスト）を確認する。

local ipc_dir = arg[1] or error("使い方: lua5.4 tools/mock_test.lua <IPCフォルダ> [client|host]")
local role = arg[2] or "client"

local here = (arg[0]:match("^(.*)[/\\]") or ".")
package.path = table.concat({
    here .. "/?.lua",
    here .. "/../mod/DRGTranslate/Scripts/?.lua",
    package.path,
}, ";")

local mock = require("mock_ue4ss")
mock.install()
local players = tonumber(os.getenv("MOCK_PLAYERS") or "") or 4
mock.make_world({ player_name = "Kiyo", is_host = (role == "host"), players = players })

local Cfg = require("config")
Cfg.ipc.dir = ipc_dir
Cfg.debug = false
package.loaded["config"] = Cfg

-- MOD のログを控えておく（bridge からの返事が届いたかを見るため）
local U = require("util")
local logged = {}
local real_log = U.log
U.log = function(fmt, ...)
    local ok, s = pcall(string.format, fmt, ...)
    logged[#logged + 1] = ok and s or tostring(fmt)
    real_log(fmt, ...)
end
local function logged_line(needle)
    for _, line in ipairs(logged) do
        if line:find(needle, 1, true) then return line end
    end
    return nil
end

local failures = 0
local function check(cond, label, detail)
    if cond then
        print("  ok   " .. label)
    else
        failures = failures + 1
        print("  FAIL " .. label .. (detail and ("  -> " .. tostring(detail)) or ""))
    end
end

local function pump(times, sleep_sec)
    for _ = 1, (times or 1) do
        mock.tick()
        mock.sleep(sleep_sec or 0.06)
    end
end

--- cond が真になるまで回す。最大 timeout 秒（既定15秒）。
local function wait_until(cond, timeout)
    local step = 0.06
    for _ = 1, math.ceil((timeout or 15) / step) do
        if cond() then return true end
        mock.tick()
        mock.sleep(step)
    end
    return cond() == true
end

--- 「何も起きないこと」を確かめる前の待ち。
local function settle()
    pump(25)
end

local function last_display()
    local d = mock.displayed[#mock.displayed]
    return d and d.text or nil
end

print(("== mock test (%s) =="):format(role))

dofile(here .. "/../mod/DRGTranslate/Scripts/main.lua")

check(mock.hooks["/Script/FSD.FSDGameState:ClientNewMessage"] ~= nil, "受信フックが登録される")
check(mock.hooks["/Script/FSD.FSDPlayerController:Server_NewMessage"] ~= nil, "送信フックが登録される")
check(#mock.loops > 0, "ポーリングループが登録される")
check(mock.keybinds["F9"] ~= nil, "F9 のキーバインドが登録される")

local connected = false
for _ = 1, 60 do
    pump(1, 0.05)
    local IPC = require("ipc")
    if IPC.connected then connected = true break end
end
check(connected, "bridge に接続できる")
if not connected then
    print("!! bridge が動いていません。先に drg_bridge.py を起動してください")
    os.exit(1)
end
wait_until(function() return logged_line("bridge version = ") ~= nil end, 5)
check(logged_line("bridge version = ") ~= nil,
      "つながったら HELLO を送り、bridge の版が返ってくる", logged_line("bridge version"))

if role == "client" then
    print("-- 名前が分からないうちの取り違え --")

    -- 自分（Kiyo）が打つと送信フックだけ先に発火し、戻りはサーバを一周してから届く。
    -- その間に他の隊員（Karl）の発言が先に届いても、Karl を自分と取り違えないこと
    local sent_before, disp_before = #mock.sent, #mock.displayed
    local h = mock.hooks["/Script/FSD.FSDPlayerController:Server_NewMessage"]
    h.pre(mock.Param(mock.pc), mock.Param(mock.FString("Kiyo")),
          mock.Param(mock.FString("了解です")), mock.Param(0))
    mock.receive("Karl", "watch out, left side")
    mock.receive("Kiyo", "了解です")
    wait_until(function() return #mock.displayed > disp_before end)
    settle()
    local as_karl = 0
    for i = sent_before + 1, #mock.sent do
        if mock.sent[i].sender == "Karl" then as_karl = as_karl + 1 end
    end
    check(as_karl == 0, "戻りより先に他の隊員の発言が届いても、その人の名前で訳を送らない", as_karl)
    check(#mock.displayed > disp_before and (last_display() or ""):find("Karl", 1, true) ~= nil,
          "そのときの他の隊員の発言は、受信としてふつうに訳す", last_display())
    -- 名前を Karl と覚えていれば、ここで Karl の発言が「同じ名前の隊員」として無視される
    disp_before = #mock.displayed
    mock.receive("Karl", "need ammo over here")
    wait_until(function() return #mock.displayed > disp_before end)
    check(#mock.displayed > disp_before, "そのあとも Karl の発言は訳される（Karl を自分と覚えていない）",
          last_display())
end

print("-- 受信 --")

local before = #mock.displayed
mock.receive("Karl", "Rock and Stone!")
if role == "client" or (role == "host" and players == 1) then
    wait_until(function() return #mock.displayed > before end)
else
    settle()
end

if role == "client" then
    check(#mock.displayed > before, "英語の発言が翻訳されて表示される", last_display())
    check((last_display() or ""):find("Rock and Stone!", 1, true) ~= nil,
          "用語集がヒットし、掛け声は英語のまま出る", last_display())
    check((last_display() or ""):find("Karl", 1, true) ~= nil, "発言者名が含まれる", last_display())

    before = #mock.displayed
    mock.receive("Karl", "for karl")
    wait_until(function() return #mock.displayed > before end)
    check(#mock.displayed > before, "原文と同じ訳文でも表示される", last_display())

    check(mock.displayed[#mock.displayed].via == "gamestate",
          "クライアントでは PostGameMessage を使う")
elseif players >= 2 then
    check(#mock.displayed == before,
          "他の隊員がいるホストではゲーム内に出さない", last_display())
    check(mock.displayed_widget_attempts == 0,
          "ホストでもウィジェット直叩きは試さない", mock.displayed_widget_attempts)
else
    check(#mock.displayed > before, "ソロのホストではゲーム内に出す", last_display())
    check(mock.displayed[#mock.displayed].via == "gamestate",
          "そのとき使うのは PostGameMessage")
end

print("-- 中継 --")

pump(40, 0.05)

local relay_before = #mock.sent
mock.receive("Karl", "swarm from the left")
if role == "host" and players >= 2 then
    wait_until(function() return #mock.sent > relay_before end)
    pump(20, 0.05)
else
    settle()
end
local relayed, senders = {}, {}
for i = relay_before + 1, #mock.sent do
    relayed[#relayed + 1] = mock.sent[i].text
    senders[#senders + 1] = mock.sent[i].sender
end

if role == "host" and players == 1 then
    check(#relayed == 0, "ソロ（自分しかいない）なら中継しない", table.concat(relayed, " | "))
elseif role == "host" then
    check(#relayed == 1, "ホストは発言者以外の3言語ぶんを1行で中継する", #relayed)
    local tags = table.concat(relayed, " ")
    check(tags:find("[ja]", 1, true) ~= nil and tags:find("[ko]", 1, true) ~= nil
          and tags:find("[zh]", 1, true) ~= nil,
          "1行に日本語・韓国語・中国語がすべて入る", tags)
    check(tags:find("[en]", 1, true) == nil, "発言者の言語(EN)は中継しない", tags)
    check(#relayed > 0 and relayed[1]:find(" / ", 1, true) ~= nil,
          "訳どうしは / でつなぐ", relayed[1])
    check(tags:find("[JP]", 1, true) == nil and tags:find("[KR]", 1, true) == nil,
          "言語の目印([JP] など)は付けない", tags)
    check(senders[1] == "Karl", "自分の名前が未判明なら元の発言者名で送る", senders[1])
    check(relayed[1]:find("Karl", 1, true) == nil,
          "本文に発言者名が二重に入らない", relayed[1])

    local before_own = #mock.sent
    mock.send("Kiyo", "了解です")
    wait_until(function() return #mock.sent > before_own end)
    local after = #mock.sent
    mock.receive("Karl", "nitra over here")
    wait_until(function() return #mock.sent > after end)
    check(#mock.sent > after and mock.sent[after + 1].sender == "Kiyo",
          "名前が判明したあとは自分の名前で中継する",
          #mock.sent > after and mock.sent[after + 1].sender or "送信なし")
    check(#mock.sent > after and mock.sent[after + 1].text:find("Karl", 1, true) ~= nil,
          "そのときは本文に元の発言者名が入る",
          #mock.sent > after and mock.sent[after + 1].text or "送信なし")
else
    check(#relayed == 0, "クライアントは中継しない", table.concat(relayed, " | "))
end

relay_before = #mock.sent
before = #mock.displayed
mock.receive("Hosty", "Karl: 気をつけろ / 조심해 / 小心")
settle()
check(#mock.displayed == before and #mock.sent == relay_before,
      "中継された行は翻訳も再中継もしない")

relay_before = #mock.sent
before = #mock.displayed
mock.receive("Karl", "warning: swarm incoming")
if role == "host" and players >= 2 then
    wait_until(function() return #mock.sent > relay_before end)
else
    wait_until(function() return #mock.displayed > before end)
end
if role == "host" and players >= 2 then
    check(#mock.sent > relay_before,
          "コロンを含む発言も中継する（中継行と誤判定しない）")
else
    check(#mock.displayed > before,
          "コロンを含む発言も翻訳する（中継行と誤判定しない）", last_display())
end

-- 直前に喋った人（Karl）の名前で始まる普通の返事は、中継行と誤判定しない
relay_before = #mock.sent
before = #mock.displayed
mock.receive("Scout", "Karl: roger, on my way")
if role == "host" and players >= 2 then
    wait_until(function() return #mock.sent > relay_before end)
    check(#mock.sent > relay_before,
          "直前に喋った人の名前で始まる返事も中継する（中継行と誤判定しない）")
else
    wait_until(function() return #mock.displayed > before end)
    check(#mock.displayed > before,
          "直前に喋った人の名前で始まる返事も翻訳する（中継行と誤判定しない）", last_display())
end

before = #mock.displayed
mock.receive("Someone", "こんにちは")
settle()
check(#mock.displayed == before, "日本語の発言は翻訳しない")

before = #mock.displayed
mock.receive("System", "Mission Control speaking", 1)
settle()
check(#mock.displayed == before, "ゲームメッセージ(ES_Game)は既定で翻訳しない")

print("-- 送信 --")

local sent_before = #mock.sent
local passed_through = mock.send("Kiyo", "回復お願いします")
check(passed_through == "回復お願いします", "原文は書き換えられずそのまま流れる", passed_through)
wait_until(function() return #mock.sent > sent_before end)
check(#mock.sent > sent_before, "遅れて翻訳文が2通目として送信される")
if #mock.sent > sent_before then
    local s = mock.sent[#mock.sent]
    check(s.text:find("回復お願いします", 1, true) ~= nil, "翻訳文に元の内容が含まれる", s.text)
    check(s.sender == "Kiyo", "送信者名が引き継がれる", s.sender)
end

sent_before = #mock.sent
mock.send("Kiyo", "hello everyone")
settle()
check(#mock.sent == sent_before, "翻訳元（既定は日本語）でない発言は翻訳しない")

sent_before = #mock.sent
mock.send("Kiyo", "/help これはコマンド")
settle()
check(#mock.sent == sent_before, "/ で始まる発言は翻訳しない")

sent_before = #mock.sent
mock.send("Kiyo", "あ")
settle()
check(#mock.sent == sent_before, "min_length 未満の発言は翻訳しない")

sent_before = #mock.sent
mock.send("Kiyo", "弾がない")
wait_until(function() return #mock.sent > sent_before end)
check(#mock.sent > sent_before, "用語集の定型句も2通目として送られる")
if #mock.sent > sent_before then
    check(mock.sent[#mock.sent].text == "I'm out of ammo / 탄약이 없어요 / 我没弹药了",
          "送信側の用語集がヒットする", mock.sent[#mock.sent].text)
end

print("-- ループ防止 --")

before = #mock.displayed
mock.receive("Kiyo", "please heal me")
settle()
check(#mock.displayed == before, "自分の名前の発言は翻訳しない")

-- 同じ名前の隊員が喋っても、自分が打っていないなら自分の発言として訳して送らない
sent_before = #mock.sent
mock.receive("Kiyo", "こっちに回復ある？")
settle()
check(#mock.sent == sent_before, "同じ名前の隊員の発言を、自分の発言として訳して送らない",
      #mock.sent - sent_before)

-- MOD が送った訳文と同じ文面を別の隊員が言っても、その人の発言は捨てない
sent_before = #mock.sent
mock.send("Kiyo", "弾がない")
wait_until(function() return #mock.sent > sent_before end)
local own_text = mock.sent[#mock.sent].text
local disp_mid, sent_mid = #mock.displayed, #mock.sent
mock.receive("Karl", own_text)
if role == "client" or players == 1 then
    wait_until(function() return #mock.displayed > disp_mid end)
    check(#mock.displayed > disp_mid, "MOD が送ったのと同じ文面でも、他の隊員の発言は訳して表示する",
          own_text)
else
    wait_until(function() return #mock.sent > sent_mid end)
    check(#mock.sent > sent_mid, "MOD が送ったのと同じ文面でも、他の隊員の発言は中継する", own_text)
end
settle()
local relayed_count = (role == "client" or players == 1) and 0 or 1
check(#mock.sent == sent_mid + relayed_count, "そのあと届く自分の2通目の戻りは、引き続き弾く",
      #mock.sent - sent_mid)

-- MOD が送った2通目（翻訳文）は、実機と同じくサーバを経由して自分にも戻ってくる。
-- その戻りを、また訳したり表示したり中継したりしないこと。
sent_before, before = #mock.sent, #mock.displayed
mock.send("Kiyo", "こっちに来て")
wait_until(function() return #mock.sent > sent_before end)
check(#mock.echo_queue > 0, "MOD が送った2通目は自分にも戻ってくる（モックが実機どおりに返す）",
      #mock.echo_queue)
settle()
check(#mock.echo_queue == 0, "戻りが届いた")
check(#mock.sent == sent_before + 1, "自分の2通目の戻りを、もう一度訳して送らない",
      #mock.sent - sent_before)
check(#mock.displayed == before, "自分の2通目の戻りを表示しない", last_display())

print("-- F9 切り替え --")

check(mock.keybinds["F9"] ~= nil, "F9 が登録されている")
mock.keybinds["F9"]()
before, sent_before = #mock.displayed, #mock.sent
mock.receive("Karl", "anyone got nitra")
settle()
check(#mock.displayed == before, "OFF のあとは受信を翻訳しない")
check(#mock.sent == sent_before, "OFF のあとは中継もしない", #mock.sent - sent_before)

sent_before = #mock.sent
mock.send("Kiyo", "テスト、聞こえますか")
settle()
check(#mock.sent == sent_before, "OFF のあとは自分の発言も翻訳しない")

mock.keybinds["F9"]()
before, sent_before = #mock.displayed, #mock.sent
mock.receive("Karl", "nitra right here")
if role == "client" or players == 1 then
    wait_until(function() return #mock.displayed > before end)
else
    wait_until(function() return #mock.sent > sent_before end)
end
if role == "client" or players == 1 then
    check(#mock.displayed > before, "ON に戻すと翻訳が再開する", last_display())
else
    check(#mock.sent > sent_before, "ON に戻すと中継が再開する", #mock.sent - sent_before)
end

print("-- 返事の来ない要求 --")

-- bridge が落ちた・再起動でファイルが空になった、などで返事が来ない要求は、
-- 期限を過ぎたら捨てて on_error を呼ぶこと（いつまでも待ち続けない）
do
    local IPC = require("ipc")
    local errored = nil
    local before_pending = IPC.pending_count()
    IPC.request("in", "Karl", "no reply expected", function() end,
                function(msg) errored = msg end, false)
    check(IPC.pending_count() == before_pending + 1, "要求は返事を待つ一覧に入る")
    -- 最後に進めた時刻から 61 秒後まで一気に進める（実時間は待たない）
    IPC.expire_pending(10 ^ 9)
    check(errored == "timeout", "期限を過ぎた要求は on_error(\"timeout\") で知らされる",
          tostring(errored))
    check(IPC.pending_count() == 0, "期限を過ぎた要求は一覧から消える", IPC.pending_count())
end

print()
if failures == 0 then
    print("ALL PASS")
    os.exit(0)
else
    print(failures .. " 件 FAIL")
    os.exit(1)
end
