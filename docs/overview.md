# Overview of Nmahjong

Nmahjong is a library that brings together **storage formats for mahjong (five layers)** and **programs that create, verify and run them**. It does not include a screen for playing mahjong, nor a strong AI.
The reference implementation is in Python (standard library only); the second implementation is in JavaScript (browser and Node.js, no dependencies).

## 0. The whole picture

```
  [Formats (what is stored)]      [Programs]
 ─────────────────────────────────────────────────────────────
  1 tileset                      choose a bundled one / make one by giving suits, red tiles and removed tiles (command, page)
        │
        ▼
  2 ruleset                      choose a bundled one / make one by changing items (command, page)
        │
        ▼
  3 wall                         make from a seed / make from the order read by a physical table / reproduce from a Tenhou seed
        │
        ▼
  A situation (table → player)   take out what is visible from that seat. List the actions that can be taken
  A action (player → table)      check the action that came back and turn it into an event of the record (gateway)
        │                        the form follows mjai
        ▼
  4 record                       deal the wall and run the rounds (game runner)
                                 receive events one by one and build the record (recorder)
                                 judge yaku and fu of a win / compute scores and settlement
                                 convert records from elsewhere (Tenhou)
        │
        ▼
  5 annotation                   evaluate a finished game / evaluate each time an action arrives
                                 let players play many games against each other and report results (arena)
```

- Under a chosen ruleset (hand of 1, 4, 7, 10 or 13 tiles; 2 to 4 players), human and AI players can play each other, and every game is kept as a verified record.
- Outside the library: the game server itself (matching, rating, permanent connections), the AI engine itself, registers of parlours, tables and users, and screens.

## 1. Design ideas
1. Mahjong is determined by the set of tiles, the hand size N and the number of players M (1 or more). 136 tiles, 13 tiles and 4 players are one instance
2. Tiles are handled as numbers. Only the tileset holds the meaning of a number (kind, marks); walls and records hold numbers only
3. A wall holds only the order. The dead wall, the dora and the way of dealing are decided by the ruleset (wall_rules)
4. A wall always states how much of it is fact (generated / observed / filled, with the observed range)
5. A ruleset is data independent of records. A record refers to its ruleset and walls by id. However many games are played under one ruleset, there is one ruleset file
6. An annotation is not embedded in a record; it is a separate layer that points to the record by id. There can be several, one per evaluator. The evaluator declares the names of its values
7. The container is JSON. Tile names are for display; storage uses numbers. An id is the SHA-256 of the canonical JSON of the content (for a wall: the bytes of tileset id ‖ order). It is computed on the normal form, in which omitted items are filled with their defaults
8. A verifier decides mechanically what a "correct file" is. Specifications, JSON Schemas, test vectors and default data are bundled, so that the formats can be implemented in other languages
9. Import is one-way (external format → Nmahjong). Export is limited to Tenhou JSON and mjai, for verification and interoperation
10. A position is shown to an AI **in an existing form (mjai)**. No new format is invented (design/observation.md)

## 2. The five layers
| Layer | Name | Version | Content | Specification |
|---|---|---|---|---|
| 1 | tileset | 1.0 | which tiles, how many, which number is which, marks | spec/tileset.md |
| 2 | ruleset | 1.0 | how the wall is consumed, the rules of play, the end, the settlement (points / external points / final reward) | spec/ruleset.md (grounds for the items: design/ruleset-survey.md) |
| 3 | wall | 1.0 | order, source, generation data, range of fact | spec/wall.md |
| 4 | record | 1.0 | source, players, rounds, events, results, settlement results | spec/record.md |
| 5 | annotation | 1.0 | candidates and values at each decision point (declared by the evaluator) | spec/annotation.md (ideas: design/evaluation.md) |

References: 5 → 4 → 2 → 1, and 4 → 3 → 1. A lower layer does not know the layers above it. Each layer has its own version.
**A position (observation) is not a layer.** It is derived from a record by a function (§6). It is not stored as a file.

## 3. Main points of each layer
- Tileset: the id is authoritative; the name is for display. Numbers run from 0 to K−1, K ≤ 256. kind is `1m`–`9s` / `E S W N P F C` / `ex`. mark is a physical mark only; its meaning is given by the ruleset
- Wall: order is a permutation of length K. source is generated / observed / filled. Generation uses `fy-sha256-v1`; reproduction of Tenhou uses `tenhou-mt19937ar-sha512-n288-nm1`. Consumption is from the head: N tiles to seat 0, …, N tiles to seat M−1, one tile to the dealer, then draws; the last dead_wall tiles are the dead wall
- Ruleset: the name is for display; the id is the hash of the normal form without id, name and meta (the same settings give the same id). game_rules / end / settlement may be omitted and have defaults. A survey confirmed that the rules of Japanese organisations, online services, a TV programme, parlours and three-player mahjong can be written (design/ruleset-survey.md). 46 rulesets are bundled (spec/ruleset.md §7; N-tile mahjong in rules/nm-defaults.md)
- Record: one game = one file. ruleset and wall are referred to by id; the tileset is ruleset.tileset. The deal is not written; it is derived from the wall and compared. A replay from a branch point is a separate file with parent. All events use numbers
- Annotation: a separate file per evaluator. metrics[] declares the name, type and scope of each value; one primary metric gives best and loss. Candidates are a subset of the legal actions. Aggregates (agreement rate and so on) are not stored

## 4. File names
| Kind | Form |
|---|---|
| tileset | `{name}_{id64}.tileset.json` |
| ruleset | `{name}_{id64}.ruleset.json` |
| wall | `{tileset.name}_{id64}.wall.json` |
| record | `{ruleset.tileset.name}_{id64}.record.json` |
| annotation | `{record_id64}_{evaluator.name}.annotation.json` |

- id64 is the 64 hexadecimal digits of SHA-256, as they are. ASCII only. The separator is `_`; the kind comes before the extension
- File names are not meant to be read by people. Search by id or by content
- If a file of the same name already exists and the id of its content differs, saving fails instead of overwriting
- For very large numbers (millions or more), split folders by the first two digits of the id (a recommendation for the place of storage)
- The verifier warns when name and content disagree (the content is authoritative)

## 5. List of cross-layer checks
The checks of each layer alone are written in the specification of that layer (spec/). This list has only the checks that **compare two or more files**.

| # | Compared | Content | On failure |
|---|---|---|---|
| X1 | ruleset ↔ tileset | The tileset of ruleset.tileset.id exists. The keys of marks, mark_overrides and nuki.tiles exist in the tileset. N×M+1+dead_wall ≤ K | error |
| X2 | wall ↔ tileset | The tileset of wall.tileset.id exists. The length of order = K, a permutation of 0 to K−1 | error |
| X3 | wall ↔ generation data | The order regenerated from the generation of a generated / observed wall is the same (fy-sha256-v1, tenhou-…-nm1). For filled, the observed range is the same and the rest is reproduced by fill | error |
| X4 | record ↔ ruleset | ruleset.id exists. The length of players = M. The initial state.scores = start_points. The presence of dice / wareme agrees with break and wareme | error |
| X5 | record ↔ wall ↔ ruleset | The wall.id of each round exists, and wall.tileset.id = ruleset.tileset.id. The deal, the order of draws, the dora indicators and the replacement tiles derived from wall.order and wall_rules agree, in order, with draw / dora / rinshan in events. Tiles consumed ≤ K−dead_wall | error (the position in events is reported) |
| X6 | record ↔ ruleset (flow) | events do not contradict flow: conditions for riichi, chi forbidden, kuikae, maximum number of kans, which abortive draws are used, whether double ron is allowed, kan after riichi that changes the waits, nuki | error |
| X7 | record ↔ ruleset (scores) | wins[].yaku are yaku in use; the sum of han; fu and han → points agree with scoring. The sum of deltas is 0; honba and riichi sticks go in and out correctly; chips can be derived from the chips rules | error |
| X8 | record ↔ ruleset (settlement) | final.settled = recomputed from settlement (return points, uma, oka, tie). The same for external_points and payout | error |
| X9 | record ↔ record (parent) | If parent.record can be read, events up to the branch point are the same | warning if it cannot be read |
| X10 | record ↔ device | record.device.id and the device.id of each wall | warning on mismatch |
| X11 | annotation ↔ record | record.id exists. round and at are in range; the event at `at` fits the phase. actual = the next event of the record | error |
| X12 | annotation ↔ record ↔ ruleset | Every element of candidates is contained in `legal_actions(ruleset, observe(record, round, at, actor))` | error |
| X13 | import ↔ original | Tenhou: the derived deal agrees with INIT.hai0–3, the draws with T–W, the dora indicator with INIT.seed | fails per game |
| X14 | file name ↔ content | name and id64 agree with the content | warning |

## 6. Positions (observation) and the gateway for players
### 6.1 Place in the whole
```
record (everything that happened)
   │ observe(record, round, at, seat)      deterministic. What the seat cannot see is hidden
   ▼
position = a sequence of mjai events (hidden per seat) + request_action{possible_actions, time}
   │ player (a person or an AI)
   ▼
action (the form of annotation.md §2.3.1 = one-to-one with an mjai response)
```
- **Evaluation** (annotation) = a record of the values an evaluator gave to the candidates at the position of each decision point
- **Play** (AI against AI, a person against an AI) = at every turn the game runner sends the situation, receives an action and adds it to the record
- Because the entrance is the same, an AI that plays can be used as an evaluator as it is (and the other way round)

### 6.2 The form of a position: mjai is authoritative
The sequence of mjai events (gimite; used by Mortal, akochan and RiichiLab) is taken as authoritative, and no new format is invented (grounds in design/observation.md). There are only three extensions, all in the mjai manner (one JSON per line, `type` required, unknown fields ignored):
1. `tile`: the tile number, written alongside. When the tileset is `mpsz` / `mpsz-x28`, a tile maps uniquely to an mjai string (`5mr` and so on), so `pai` is written too. For other tilesets (`ex`, two red tiles of one kind, small tilesets) the strings are not enough, so look at `tile`
2. `ruleset{name,id}` in `start_game`: so that the player can read M, N and all the rules
3. `request_action{request_id, time{grace_ms,bank_ms,deadline_ms}, possible_actions[]}`: the same name and form as RiichiLab. possible_actions is the result of `legal_actions`

### 6.3 Parts the library has
| Part | Place | What it does |
|---|---|---|
| `observe(record, round, at, seat, …)` | nmahjong/observe.py | The position at that moment (hands, melds, discards, dora indicators, scores, remaining draws). Tiles the seat cannot see are hidden |
| `legal_actions(ruleset, tileset, position, phase)` | nmahjong/observe.py | The list of actions that can be taken. Whether chi, pon and kan are possible, kuikae, conditions for riichi, nuki, nine terminals and honours, the limit on kans and furiten are decided from the ruleset |
| conversion to mjai | nmahjong/mjai.py | A record → sequences of mjai events (per seat). An mjai response → an event of the record |
| recorder `Recorder` | nmahjong/recorder.py | Receives events one by one and builds the record, checking each against the legal actions |
| gateway `Gateway` | nmahjong/gateway.py | Sends the situation to a player (a function or another program) and receives an action (programs/recorder-gateway.md) |
| game runner `Dealer` | nmahjong/dealer.py | Deals the wall, runs the rounds, and decides the result, the next round, the end and the settlement (programs/dealer.md) |
| judgement `judge` | nmahjong/judge.py | Yaku, fu and han of a win (programs/judge.md) |
| evaluation and arena | nmahjong/evaluate.py, arena.py | Step-by-step evaluation; games between players and a table of results (programs/layer5.md) |

### 6.4 Transport
- With a player that is another program, JSON Lines are exchanged over standard input and output (the same as mjai)
- What happens when a player does not answer, or answers an action that cannot be taken (discard the drawn tile / pass instead, or disqualification), is a setting of the game runner and the gateway (programs/dealer.md)
- An AI for 13 tiles and 4 players is mjai-compatible, so it is in a form that can also enter existing mjai game environments

## 7. Bundled data (nmahjong/data/)
| Place | Content |
|---|---|
| `tilesets/` | 10 tilesets (`mpsz`, `mpsz-x28`, `mpsz-e8`, the small tilesets `m` and `mps`, and others; separate files by the presence and number of red tiles) |
| `rulesets/` | 46 rulesets (organisations, online services, a TV programme, parlours, three-player mahjong, N-tile mahjong). The source is in meta.source of each file. Items not found in the source are listed in `unknown` |
| `defaults.json` | The defaults of a ruleset (the values filled into omitted items) and the values that can be chosen for each item |
| `yaku-riichi-standard.json` | Names of yaku, han when concealed, han when open, yakuman (local yaku included) |
| `vocab.json` | Vocabulary: yaku, reasons for a draw, conditions for chips, recommended names of evaluation values, and so on |
| `schema/` | JSON Schemas of the five layers (draft 2020-12; for checking the shape. For agreement of ids, cross-layer checks and consistency that depends on the ruleset, `validate` is authoritative) |

Test vectors are in spec/wall.md §3 (wall generation) and in tests/. Example games are in examples/.

## 8. Choice of technology
| Chosen | Reason |
|---|---|
| Reference implementation in Python (standard library only) | Runs without additional packages. Widely used in AI and research |
| Second implementation in JavaScript | To run in a browser. Tests confirm that, with the same test vectors and bundled data, it gives the same ids and the same results as Python (programs/js-game.md). The ruleset page also runs on it |
| JSON | Readable in any language. The shape can be checked with JSON Schema. The same container as mjai |
| Storing numbers | The same formats serve many compositions of tiles just by replacing the tileset. Small. Verification is simple |
| Random numbers by SHA-256 in counter mode | Available in the standard library of any language, and hard to get wrong when porting. No bias. If the seed is published, a third party can reproduce the wall |
| Tile names in the mjai notation | For display, input and AI connection. `1z`–`7z` and `0m` are also accepted on input |

## 9. Compatibility
- Tenhou: with `mpsz`, the tile numbers are the same. The walls of all rounds are reproduced from the seed in the game log (mjlog) and imported. The logs themselves are not bundled (tests/data/tenhou/README.md)
- Tenhou JSON (tenhou.net/6): can be imported as a game without walls. A record can also be exported to it
- mjai: a record can be converted to a sequence of mjai events (§6). There is no import from mjai
- No code of other libraries or AIs has been taken in

## 10. Import
The same input gives the same output (the same id). A game that does not pass verification is not output. The origin, the original ID and the range of fact are always kept.

| Origin | Input | Wall | Program |
|---|---|---|---|
| Tenhou | mjlog (XML). One file = one game | observed, all tiles, with generation data (reproduced from the seed and compared with the deal, the draws and the dora) | nmahjong/tenhou/importer.py, shuffle.py |
| Tenhou JSON | JSON of tenhou.net/6 | none (the deal is written in the record) | nmahjong/tenhou/json6.py |
| Physical table | a sequence of tag ids that were read, and a mapping table | observed | `nmahjong build --tags` |
