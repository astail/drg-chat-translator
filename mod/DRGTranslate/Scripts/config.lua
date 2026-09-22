-- DRGTranslate : settings for the in-game side (UE4SS Lua)
--
-- Languages, translation targets, display format and anything else about the
-- translation itself live in settings.ini, next to DRGTranslate.exe.
-- This file only covers how the mod behaves inside the game.
--
-- Restart the game after editing this file.

local M = {}

-- Turn the whole mod on or off (F9 toggles it while you play)
M.enabled = true

-- Write verbose logs to the UE4SS console
M.debug = false

-- Whether to translate incoming or outgoing chat, which languages, and which
-- messages are skipped (too short, starting with / ! . and so on) are all set
-- in settings.ini next to DRGTranslate.exe (DRGT_INCOMING_* / DRGT_OUTGOING_*).
-- This file only covers how the mod behaves inside the game.

-- Incoming chat
M.incoming = {
    -- Also translate system messages (EChatMessageType::ES_Game)
    translate_game_messages = false,
}

-- Relay (only while you host: push translations of others to everyone)
--
-- For an English message it builds Japanese, Korean and Chinese - the
-- speaker's own language is left out - and posts them all as a single chat
-- line. It does nothing while you are a client.
--
-- Which languages, and the format of the line, are decided on the bridge side
-- (DRGT_RELAY_* in settings.ini).
-- (Turn the relay on or off with DRGT_RELAY_ENABLED in settings.ini.)
M.host_relay = {
    -- Delay between relayed lines (ms). Sending them all at once would flood
    -- the chat in an instant
    interval_ms = 700,

    -- Drop the oldest lines once more than this are waiting (keeps the queue
    -- from piling up during a heavy swarm)
    max_queue = 12,

    -- "self"     : send under your own (the host's) name
    -- "original" : send under the original speaker's name. It looks more
    --              natural, but the server may overwrite the name. The
    --              speaker's name also disappears from the text, so other
    --              dwarves running this mod can no longer tell it is a relay
    --              line (they end up seeing the translation twice)
    sender = "self",

    -- "chat"    : send as a normal chat message (same path as your own
    --             translated messages)
    -- "gamemsg" : post as a system message via GameState:PostGameMessage
    method = "chat",
}

-- Where translations are shown
M.display = {
    -- "auto"      : GameState:PostGameMessage as a client and as a solo host.
    --               As a host with other dwarves around nothing is shown in
    --               game, because anything a host posts reaches everyone; read
    --               the relay line instead (or turn on the overlay)
    -- "gamestate" : always use GameState:PostGameMessage
    -- "widget"    : always drive the HUD_Chat widget directly
    --               (this passes a struct argument, so it may crash the game.
    --                It did not work when tried in the real game. Use at your
    --                own risk)
    -- "off"       : show nothing in game (bridge overlay only)
    strategy = "auto",

    -- With "auto", use PostGameMessage even as a host with other dwarves
    -- around. That shows your translations to *everyone*, so it is off by
    -- default.
    host_broadcast_fallback = false,
}

-- Talking to the local process (bridge)
M.ipc = {
    -- How often to poll for incoming lines (ms)
    poll_ms = 100,
    -- Folder used for the exchange. Defaults to %APPDATA%\DRGTranslate
    dir = nil,
}

-- Key that toggles the mod while you play
M.hotkey = {
    toggle = "F9",
}

return M
