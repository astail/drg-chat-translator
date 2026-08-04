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
mock.make_world({ player_name = "Kiyo", is_host = (role == "host") })

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
pump(12)

if role == "client" then
    check(#mock.displayed > before, "英語の発言が翻訳されて表示される", last_display())
    check((last_display() or ""):find("Rock and Stone!", 1, true) ~= nil,
          "用語集がヒットし、掛け声は英語のまま出る", last_display())
    check((last_display() or ""):find("Karl", 1, true) ~= nil, "発言者名が含まれる", last_display())

    -- 訳文が原文と同じでも表示する
    before = #mock.displayed
    mock.receive("Karl", "for karl")
    pump(12)
    check(#mock.displayed > before, "原文と同じ訳文でも表示される", last_display())

    check(mock.displayed[#mock.displayed].via == "gamestate",
          "クライアントでは PostGameMessage を使う")
else
    -- ホストは PostGameMessage が全員に配信されてしまい、ウィジェット直叩きは
    -- 構造体引数でゲームごと落ちる危険がある。既定ではゲーム内に出さず、
    -- bridge のオーバーレイに任せる。
    check(#mock.displayed == before,
          "ホストではゲーム内に出さない（全員に見えるのを防ぐ）", last_display())
    check(mock.displayed_widget_attempts == 0,
          "ホストでもウィジェット直叩きは試さない", mock.displayed_widget_attempts)
end

before = #mock.displayed
mock.receive("Someone", "こんにちは")
pump(10)
check(#mock.displayed == before, "日本語の発言は翻訳しない")

before = #mock.displayed
mock.receive("System", "Mission Control speaking", 1)
pump(10)
check(#mock.displayed == before, "ゲームメッセージ(ES_Game)は既定で翻訳しない")

-- ------------------------------------------------------------------
-- 送信（原文をそのまま流し、翻訳を2通目として送る）
-- ------------------------------------------------------------------
print("-- 送信 --")

local sent_before = #mock.sent
local passed_through = mock.send("Kiyo", "回復お願いします")
check(passed_through == "回復お願いします", "原文は書き換えられずそのまま流れる", passed_through)
pump(12)
check(#mock.sent > sent_before, "遅れて翻訳文が2通目として送信される")
if #mock.sent > sent_before then
    local s = mock.sent[#mock.sent]
    check(s.text:find("回復お願いします", 1, true) ~= nil, "翻訳文に元の内容が含まれる", s.text)
    check(s.sender == "Kiyo", "送信者名が引き継がれる", s.sender)
end

sent_before = #mock.sent
mock.send("Kiyo", "hello everyone")
pump(8)
check(#mock.sent == sent_before, "日本語でない発言は翻訳しない")

sent_before = #mock.sent
mock.send("Kiyo", "/help これはコマンド")
pump(8)
check(#mock.sent == sent_before, "/ で始まる発言は翻訳しない")

sent_before = #mock.sent
mock.send("Kiyo", "あ")
pump(8)
check(#mock.sent == sent_before, "min_length 未満の発言は翻訳しない")

-- 用語集にある定型句は翻訳APIを介さず置き換わる
sent_before = #mock.sent
mock.send("Kiyo", "弾がない")
pump(12)
check(#mock.sent > sent_before, "用語集の定型句も2通目として送られる")
if #mock.sent > sent_before then
    check(mock.sent[#mock.sent].text == "I'm out of ammo / 탄약이 없어요",
          "送信側の用語集がヒットする", mock.sent[#mock.sent].text)
end

-- ------------------------------------------------------------------
-- 自分の発言の翻訳がエコーバックしても再翻訳しない
-- ------------------------------------------------------------------
print("-- ループ防止 --")

before = #mock.displayed
mock.receive("Kiyo", "please heal me")
pump(10)
check(#mock.displayed == before, "自分の名前の発言は翻訳しない")

-- ------------------------------------------------------------------
print()
if failures == 0 then
    print("ALL PASS")
    os.exit(0)
else
    print(failures .. " 件 FAIL")
    os.exit(1)
end
