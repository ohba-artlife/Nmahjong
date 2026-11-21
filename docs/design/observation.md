# Showing a position (the "position as seen from one's own seat" given to an AI) — why it follows mjai

Policy: **follow what already exists**. Do not invent a new form.

## 1 Facts: the forms that already exist

| Form | Content | Where it is used | Source |
|---|---|---|---|
| **mjai event sequence** (gimite, from about 2010) | One JSON per line = one event. `start_game{id,names}` `start_kyoku{bakaze,kyoku,honba,kyotaku,oya,dora_marker,tehais}` `tsumo{actor,pai}` `dahai{actor,pai,tsumogiri}` `chi/pon/daiminkan{actor,target,pai,consumed}` `kakan{actor,pai,consumed}` `ankan{actor,consumed}` `reach{actor}` `reach_accepted{actor}` `dora{dora_marker}` `hora` `ryukyoku` `end_kyoku` `end_game`. Tiles are `1m`–`9s`, red `5mr`, honours `E S W N P F C`, an unseen tile `?`. The AI's response is `dahai/chi/pon/daiminkan/kakan/ankan/reach/hora/none` | Mortal, akochan, mjai.app (closed), RiichiLab, many Tenhou→mjai converters, Cryolite's standardisation project (unfinished; aims at a hub format for Mahjong Soul, Tenhou and Ichibangai) | [Cryolite/mjai](https://github.com/Cryolite/mjai), [mjai.app](https://github.com/smly/mjai.app) |
| **RiichiLab request_action** | In addition to the mjai event sequence, only when a decision is needed: `request_action{request_id, time{grace_ms,bank_ms,deadline_ms}, possible_actions[], observation(base64)}`. possible_actions are `dahai{pai}` `chi/pon/daiminkan{pai,consumed}` `ankan{consumed}` `kakan{pai,consumed}` `reach` `hora{actor,target,pai}` `ryukyoku` `none`. The response is in the mjai form + request_id. On a timeout the drawn tile is discarded or a pass is made on the player's behalf; an illegal action is a chombo at mangan | RiichiLab (in operation; OpenSkill; four players, east-south; there is also Observation3P for three players) | [riichi.dev/docs/protocol](https://riichi.dev/docs/protocol) |
| Mjx Observation (protobuf) | For research. Has `legal_actions()`. A converter to mjai exists | Research | [Mjx](https://github.com/mjx-project/mjx) |

What they have in common, seen from the AI: **(1) the sequence of events so far** (what the player cannot see is `?`), **(2) the list of legal actions**, **(3) the time allowance**. A snapshot of the position can be built by the AI from (1), so in RiichiLab too "the snapshot is a convenience; the event sequence is authoritative".

## 2 What was decided for this library
1. **For showing a position, the mjai event sequence is authoritative.** No observation format of our own is made
2. Only what is missing is **extended**, and the extensions follow the mjai manner (one JSON per line, `type` required, unknown fields ignored):
   - `request_action` (the same name and form as RiichiLab) passes `possible_actions` and `time`
   - Tile notation: when the tileset is `mpsz` / `mpsz-x28`, a tile **maps as it is** to an mjai string (`5mr` and so on) (the mapping from number to string is unique from the tileset). For other tilesets (extras `ex`, two red tiles of one kind, small tilesets for 1-tile mahjong) the strings are not enough, so an extension writes `tile` (the number) alongside `pai`. An AI that reads only mjai looks at `pai`; an AI for this library looks at `tile`
   - The number of players M and of tiles N: `ruleset{name,id}` is written in `start_game` (an extension not in the original mjai). AIs for other than four players and 13 tiles read this
3. **Functions the library provides**: `record → mjai event sequences (hidden per seat)`, `legal_actions(ruleset, position)`, `mjai response → an event of the record`. With these, (a) evaluating game records, (b) a game server, and (c) connecting existing AIs (Mortal and others) share the same entrance
4. The game server itself (matching, rating, permanent connections) is **outside the library**. An AI for 13 tiles and four players is mjai-compatible, so it is in a form that can also enter existing mjai game environments (this is the value of mjai compatibility)

The definition of the form decided is in overview.md §6; the implementation is nmahjong/mjai.py and nmahjong/gateway.py (programs/recorder-gateway.md). The survey is as of 2026-11-13.
