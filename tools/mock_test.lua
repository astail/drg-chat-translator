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
-- 中継は「ホスト かつ 他に人がいる」ときだけ働く。既定は4人ロビー想定。
-- 人数は環境変数で変えられる（ソロの確認用）
local players = tonumber(os.getenv("MOCK_PLAYERS") or "") or 4
mock.make_world({ player_name = "Kiyo", is_host = (role == "host"), players = players })

-- config を差し替えてから main.lua を読み込む
local Cfg = require("config")
Cfg.ipc.dir = ipc_dir
Cfg.debug = false
package.loaded["config"] = Cfg

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
---
--- 「訳が届く」ような待ちに使う。固定回数だけ回していたころは、
--- bridge の応答が少し遅れるだけで FAIL したり、遅れて届いた訳を
--- 次の「訳さないこと」の確認が拾ってしまったりして不安定だった。
--- 真になったらすぐ戻るので、速いときは待ち時間も増えない。
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
--- こちらは待つしかないので、少し長めに回す。
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

-- bridge の生存確認が通るまで待つ（bridge.alive は1秒ごとに更新される）
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

-- ------------------------------------------------------------------
-- 受信
-- ------------------------------------------------------------------
print("-- 受信 --")

local before = #mock.displayed
mock.receive("Karl", "Rock and Stone!")
if role == "client" or (role == "host" and players == 1) then
    wait_until(function() return #mock.displayed > before end)
else
    settle()   -- 出ないことを確かめるので、待つしかない
end

if role == "client" then
    check(#mock.displayed > before, "英語の発言が翻訳されて表示される", last_display())
    check((last_display() or ""):find("Rock and Stone!", 1, true) ~= nil,
          "用語集がヒットし、掛け声は英語のまま出る", last_display())
    check((last_display() or ""):find("Karl", 1, true) ~= nil, "発言者名が含まれる", last_display())

    -- 訳文が原文と同じでも表示する
    before = #mock.displayed
    mock.receive("Karl", "for karl")
    wait_until(function() return #mock.displayed > before end)
    check(#mock.displayed > before, "原文と同じ訳文でも表示される", last_display())

    check(mock.displayed[#mock.displayed].via == "gamestate",
          "クライアントでは PostGameMessage を使う")
elseif players >= 2 then
    -- 他の隊員がいるホストでは、PostGameMessage が全員に配信されてしまうので
    -- ゲーム内には出さない。ウィジェット直叩きは実機で動かないので試さない。
    check(#mock.displayed == before,
          "他の隊員がいるホストではゲーム内に出さない", last_display())
    check(mock.displayed_widget_attempts == 0,
          "ホストでもウィジェット直叩きは試さない", mock.displayed_widget_attempts)
else
    -- ソロなら配信先が自分だけなので PostGameMessage を使ってよい
    check(#mock.displayed > before, "ソロのホストではゲーム内に出す", last_display())
    check(mock.displayed[#mock.displayed].via == "gamestate",
          "そのとき使うのは PostGameMessage")
end

-- ------------------------------------------------------------------
-- 中継（ホストのときだけ、他人の発言の訳を全員に配る）
-- ------------------------------------------------------------------
print("-- 中継 --")

pump(40, 0.05)   -- 上の受信で溜まった中継行を出し切ってから数える

local relay_before = #mock.sent
mock.receive("Karl", "swarm from the left")
if role == "host" and players >= 2 then
    wait_until(function() return #mock.sent > relay_before end)
    pump(20, 0.05)   -- 2行目が続かないことも見るので、少し余分に回す
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
    -- 訳文の目印は --fake の翻訳器が付けるもの。どの言語を頼んだかを確認できる
    local tags = table.concat(relayed, " ")
    check(tags:find("[ja]", 1, true) ~= nil and tags:find("[ko]", 1, true) ~= nil
          and tags:find("[zh]", 1, true) ~= nil,
          "1行に日本語・韓国語・中国語がすべて入る", tags)
    check(tags:find("[en]", 1, true) == nil, "発言者の言語(EN)は中継しない", tags)
    check(#relayed > 0 and relayed[1]:find(" / ", 1, true) ~= nil,
          "訳どうしは / でつなぐ", relayed[1])
    check(tags:find("[JP]", 1, true) == nil and tags:find("[KR]", 1, true) == nil,
          "言語の目印([JP] など)は付けない", tags)
    -- まだ一度も発言していないので自分の名前が分からない。
    -- そのときは元の発言者名で送り、本文側の名前は落とす（二重表示の防止）
    check(senders[1] == "Karl", "自分の名前が未判明なら元の発言者名で送る", senders[1])
    check(relayed[1]:find("Karl", 1, true) == nil,
          "本文に発言者名が二重に入らない", relayed[1])

    -- 一度発言して名前が分かったあとは、自分の名前で中継する
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

-- 中継行を受け取ってもさらに翻訳しない（ホスト・クライアント共通）。
-- 別のホスト(Hosty)が、少し前に喋った Karl の発言の訳を流してきた形
relay_before = #mock.sent
before = #mock.displayed
mock.receive("Hosty", "Karl: 気をつけろ / 조심해 / 小心")
settle()
check(#mock.displayed == before and #mock.sent == relay_before,
      "中継された行は翻訳も再中継もしない")

-- コロンで始まるだけの普通の発言（"warning: ..."）を中継行と間違えない。
-- 行頭の名前が「最近チャットで見かけた人」でなければ中継行ではない
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

before = #mock.displayed
mock.receive("Someone", "こんにちは")
settle()
check(#mock.displayed == before, "日本語の発言は翻訳しない")

before = #mock.displayed
mock.receive("System", "Mission Control speaking", 1)
settle()
check(#mock.displayed == before, "ゲームメッセージ(ES_Game)は既定で翻訳しない")

-- ------------------------------------------------------------------
-- 送信（原文をそのまま流し、翻訳を2通目として送る）
-- ------------------------------------------------------------------
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

-- 用語集にある定型句は翻訳APIを介さず置き換わる
sent_before = #mock.sent
mock.send("Kiyo", "弾がない")
wait_until(function() return #mock.sent > sent_before end)
check(#mock.sent > sent_before, "用語集の定型句も2通目として送られる")
if #mock.sent > sent_before then
    check(mock.sent[#mock.sent].text == "I'm out of ammo / 탄약이 없어요 / 我没弹药了",
          "送信側の用語集がヒットする", mock.sent[#mock.sent].text)
end

-- ------------------------------------------------------------------
-- 自分の発言の翻訳がエコーバックしても再翻訳しない
-- ------------------------------------------------------------------
print("-- ループ防止 --")

before = #mock.displayed
mock.receive("Kiyo", "please heal me")
settle()
check(#mock.displayed == before, "自分の名前の発言は翻訳しない")

-- ------------------------------------------------------------------
-- F9（翻訳のON/OFF）
-- ------------------------------------------------------------------
print("-- F9 切り替え --")

check(mock.keybinds["F9"] ~= nil, "F9 が登録されている")
mock.keybinds["F9"]()          -- OFF
before, sent_before = #mock.displayed, #mock.sent
mock.receive("Karl", "anyone got nitra")
settle()
check(#mock.displayed == before, "OFF のあとは受信を翻訳しない")
check(#mock.sent == sent_before, "OFF のあとは中継もしない", #mock.sent - sent_before)

sent_before = #mock.sent
mock.send("Kiyo", "テスト、聞こえますか")
settle()
check(#mock.sent == sent_before, "OFF のあとは自分の発言も翻訳しない")

mock.keybinds["F9"]()          -- ON に戻す
before, sent_before = #mock.displayed, #mock.sent
mock.receive("Karl", "nitra right here")
if role == "client" or players == 1 then
    wait_until(function() return #mock.displayed > before end)
else
    wait_until(function() return #mock.sent > sent_before end)
end
if role == "client" or players == 1 then
    -- クライアントとソロのホストは、自分に見える表示で確認する
    check(#mock.displayed > before, "ON に戻すと翻訳が再開する", last_display())
else
    check(#mock.sent > sent_before, "ON に戻すと中継が再開する", #mock.sent - sent_before)
end

-- ------------------------------------------------------------------
print()
if failures == 0 then
    print("ALL PASS")
    os.exit(0)
else
    print(failures .. " 件 FAIL")
    os.exit(1)
end
