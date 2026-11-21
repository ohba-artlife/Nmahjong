# record — specification of the record (nmahjong-record 1.0)

Key: MUST = required, MAY = optional, SHOULD = recommended. The container is JSON (UTF-8). See tileset.md for tilesets, wall.md for walls and ruleset.md for rulesets.

## 1 Purpose
To hold everything that **happened** in one game (a single round, an east-only game, an east-south game, a full game; extensions included), as numbers and structure. It does not hold the text of the rules (the ruleset is referred to by id). It does not hold the order of the walls (a wall is referred to by id for each round). It does not hold evaluations or comments (annotations hold them separately).

**One game = one file.** Rounds are `rounds[]`. A replay (playing again from any turn) is a **separate file** that points to the original with `parent`.

## 2 Form

```json
{
  "format": "nmahjong-record",
  "version": "1.0",
  "id": "sha256:…",
  "source": {"kind": "played", "from": "my-app", "ref": "game-20261113-0001"},
  "ruleset": {"name": "jp-4p-hanchan-red3", "id": "sha256:…"},
  "venue": {"id": "v-001", "name": null, "table_no": 3},
  "device": {"id": "dev-7f3a", "maker": null, "model": null},
  "event": null,
  "players": [
    {"seat": 0, "user": "u-1001", "name": "A", "external": [{"system": "tenhou", "id": "NoName"}], "ranks": [], "rating": null, "ai": null},
    {"seat": 1, "user": "u-1002", "name": "B"},
    {"seat": 2, "user": "u-1003", "name": "C"},
    {"seat": 3, "user": "u-1004", "name": "D"}
  ],
  "started_at": "2026-11-13T10:00:00+09:00",
  "ended_at": "2026-11-13T10:52:10+09:00",
  "end": "finished",
  "parent": null,
  "rounds": [
    {
      "index": 0,
      "wall": {"id": "sha256:…"},
      "state": {"bakaze": "E", "kyoku": 1, "honba": 0, "kyotaku": 0, "oya": 0,
                "scores": [25000, 25000, 25000, 25000], "dice": [3, 5], "wareme": null},
      "events": [
        {"t": "deal"},
        {"t": "dora", "tile": 77},
        {"t": "draw", "who": 0, "tile": 53},
        {"t": "discard", "who": 0, "tile": 108, "tsumogiri": false, "riichi": false},
        {"t": "draw", "who": 1, "tile": 54},
        {"t": "discard", "who": 1, "tile": 131, "tsumogiri": true},
        {"t": "pon", "who": 2, "from": 1, "tiles": [129, 130, 131]},
        {"t": "discard", "who": 2, "tile": 4},
        {"t": "riichi", "who": 3},
        {"t": "discard", "who": 3, "tile": 23, "riichi": true},
        {"t": "kan", "who": 0, "kind": "ankan", "tiles": [16, 17, 18, 19]},
        {"t": "dora", "tile": 90},
        {"t": "nuki", "who": 1, "tile": 120},
        {"t": "win", "who": 3, "from": 2, "tile": 61}
      ],
      "result": {
        "wins": [{
          "who": 3, "from": 2, "tile": 61,
          "hand": [0, 1, 2, 40, 41, 42, 61, 62, 100, 101, 102, 120, 121],
          "melds": [],
          "yaku": [{"name": "riichi", "han": 1}, {"name": "ippatsu", "han": 1}, {"name": "dora", "han": 2}],
          "fu": 40, "han": 4, "points": 8000,
          "ura_indicators": [91],
          "deltas": [0, 0, -8300, 8300], "chips": [0, 0, -2, 2]
        }],
        "draw": null,
        "scores": [25000, 25000, 16700, 33300]
      }
    }
  ],
  "final": {
    "scores": [25000, 25000, 16700, 33300],
    "rank": [2, 3, 4, 1],
    "settled": [-5.0, -15.0, -43.3, 63.3],
    "chips": [0, 0, -2, 2],
    "external_points": [{"system": "mleague-p", "values": [-5.0, -15.0, -43.3, 63.3]}],
    "payout": null,
    "yakitori": [false, false, true, false]
  }
}
```

### 2.1 The whole file

| Item | Required | Content |
|---|---|---|
| format | MUST | `"nmahjong-record"` |
| version | MUST | `"1.0"` |
| id | MUST | `"sha256:"` + SHA-256( the canonical JSON of all items except `id` ). Canonicalisation is the same as in ruleset.md. **The id is authoritative** |
| source | MUST | `{"kind": "played" \| "imported" \| "replayed" \| "generated", "from": string, "ref": string \| null}`. played = actually played (an application, a physical table); imported = from another format (Tenhou, Mahjong Soul); replayed = a replay; generated = AI against AI and the like. from is the name of the original system (`my-app`, `tenhou`, `jantama`, the device.id of a table). ref is the original ID (a Tenhou log ID and the like) |
| ruleset | MUST | `{name, id}`. The id is authoritative. **The tileset is not written**: the tileset is decided by ruleset.tileset (writing the same information in two places leads to mismatches). Below, "the tileset of the record" means ruleset.tileset |
| venue | MAY | `{"id": string, "name": string \| null, "table_no": integer \| null}`. The register of parlours and venues belongs to the application. The id alone is enough here |
| device | MAY | The same form as device in wall.md. For a physical table. A warning if it does not agree with wall.device of each round |
| event | MAY | `{"name", "stage", "match", "teams": [{"name", "seats": [..]}]}`. A league or a tournament. null if there is none |
| players[] | MUST | Length M (ruleset.players). See 2.2 |
| started_at / ended_at | MAY | ISO 8601, with time zone |
| end | MUST | `finished` (ended as prescribed) / `aborted` (interrupted) / `tobi` / `cold` / `time_limit` / `in_progress` (still going on when saved) |
| parent | MAY | `{"record": "sha256:…", "round": integer, "at": integer}`. The id of the game replayed from, and the round and position in events where it branched. null for an original |
| rounds[] | MUST | See 2.3. Length ≥ 1 (up to the current point if in_progress) |
| final | MUST (when end ≠ in_progress) | See 2.5 |

### 2.2 players[]

| Item | Required | Content |
|---|---|---|
| seat | MUST | 0 to M−1. The first dealer is 0. `ruleset.winds[seat]` is the initial seat wind |
| user | MAY | The user id on the application side. null if anonymous |
| name | MAY | Display name |
| external[] | MAY | `{"system": "tenhou" \| "jantama" \| …, "id": string}`. The id in another system |
| ranks[] | MAY | `{"system", "value", "level"}`. Tenhou "七段", Mahjong Soul "雀豪2", and so on. system matches the system of ruleset.external_points |
| rating | MAY | `{"system", "value"}` |
| ai | MAY | `{"name", "version"}`. When an AI played. null for a person |

### 2.3 rounds[]

| Item | Required | Content |
|---|---|---|
| index | MUST | Consecutive numbers starting at 0 |
| wall | MUST | `{"id": "sha256:…"}`. The wall of this round (a wall file). **The order is not held here.** For an import without a wall (Tenhou without SHUFFLE and the like) it is `null`, and verification gives a warning |
| state | MUST | The state at the start of the round. See 2.3.1 |
| snapshots[] | MAY | Save points of intermediate states. `{"at": position in events, "hands": [[..],..], "scores": [..]}`. An optional item so that a replay screen can restore quickly. Without it, the state can be replayed from events |
| events[] | MUST | See 2.4 |
| result | MUST | See 2.3.2 |

#### 2.3.1 state

| Item | Required | Content |
|---|---|---|
| bakaze | MUST | `E S W N` (the round wind) |
| kyoku | MUST | 1 to M (the number of the round within the wind) |
| honba | MUST | The honba count |
| kyotaku | MUST | Riichi sticks on the table (count) |
| oya | MUST | The seat of the dealer |
| scores[] | MUST | Scores at the start, length M |
| dice | MAY | `[a, b]`. MUST when ruleset.wall_rules.break.by=dice (a record of the roll; it does not affect the order) |
| wareme | MAY | The seat of the wareme. MUST when ruleset.flow.wareme is used |

#### 2.3.2 result

| Item | Required | Content |
|---|---|---|
| wins[] | MUST | The array of wins (0 = a draw; 2 or more = double ron and the like). Each element: `who`, `from` (the same as who for a tsumo), `tile`, `hand` (the tile numbers of the winning hand, including tile; melds are in melds), `melds[]` (`{"kind": chi\|pon\|ankan\|minkan\|kakan\|nuki, "tiles": [..], "from"}`), `yaku[]` (`{"name", "han"}`; a yakuman is `{"name", "yakuman": multiple}`), `fu`, `han`, `points` (the basic points; honba and riichi sticks are not included), `ura_indicators[]`, `deltas[]` (the change of each player **from the scores at the start of the round**; it includes honba, riichi sticks on the table and the riichi stick paid in this round; length M. Tenhou's sc is based on the scores after the riichi stick has been taken away, so it is converted on import), `chips[]` (the change in chips, length M; omitted when there are no chips), `pao` (the seat liable under pao; omitted if none) |
| wins[].chips | MAY | The change in chips per seat (length = number of players, sum 0). When the ruleset has rules for chips |
| wins[].reverse | MAY | true = a win with the reverse pocchi (the mark effect reverse). deltas and chips are in the direction in which the winner pays |
| wins[].additive | MAY | The breakdown when the ruleset uses additive scoring (scoring.table = additive): `{"han", "yakuman", "base", "dealer", "honba", "karasu", "each"}`. each = the points one player pays. points is each for a ron, and each × (number of players − 1) for a tsumo. In this case fu is 0 |
| draw | MUST (when wins is empty) | `{"reason": "exhaustive" \| "nine_terminals" \| "four_winds" \| "four_kans" \| "four_riichi" \| "three_ron" \| "nagashi_mangan", "tenpai": [bool×M], "hands": [[..]×M] (only players who declared tenpai; null for the others), "deltas": [..]}` |
| scores[] | MUST | Scores at the end of the round, length M |
| tobi_penalty[] | MAY | The breakdown of the penalty for going below zero (end.tobi.penalty_points of the ruleset): `{"from": seat, "to": seat, "points": points}`. The amount is already inside wins[0].deltas / draw.deltas (this item explains the breakdown) |
| tobi_chips[] | MAY | The breakdown of the chips for going below zero (on=tobi in settlement.chips of the ruleset): `{"from": seat, "to": seat, "chips": count}`. The count is already inside wins[0].chips |
| end_reason | MAY | Why the game ended in this round. `regular` / `tobi` / `cold` / `agari_yame` / `tenpai_yame` / `time_limit` / `aborted`. Only in the last round |

### 2.4 events[] — what happened in one round

Every event has `t` (the kind). Tiles are always **numbers** (ids of the tileset). `at` (an ISO 8601 time) is MAY and can be attached to any event (the time of a discard on a physical table or in an application).

| t | Required items | Content |
|---|---|---|
| deal | — | The deal. Hands are not written (they can be derived from the wall and ruleset.wall_rules.deal). Only when wall is null, `hands: [[..]×M]` is MUST |
| dora | tile | A dora indicator was turned. Right after the start of the round, and after a kan |
| draw | who, tile | A draw. A replacement tile has `rinshan: true`. A replacement tile after the list in wall_rules.rinshan is used up (nuki of North plus kans in three-player mahjong) is compared as the tile at the end of the live wall (the dead wall takes in the last live tile). A negative offset in rinshan also points to the end of the live wall (−1 is the original last tile) |
| discard | who, tile | A discard. `tsumogiri` (MAY, default false; the drawn tile was discarded), `riichi` (MAY; this discard is the riichi declaration tile), `open` (MAY; the array of tile numbers shown for an open riichi) |
| chi | who, from, tiles | Three tiles. tiles includes the called tile |
| pon | who, from, tiles | Three tiles |
| kan | who, kind, tiles | kind ∈ `ankan` / `minkan` (from is MUST) / `kakan`. tiles is four tiles |
| riichi | who | A riichi declaration (the discard right after it has riichi:true). `open: true` for an open riichi |
| nuki | who, tile | A nuki dora (North, a flower) |
| win | who, from, tile | A win. Details are in result.wins |
| draw_end | reason | A draw. Details are in result.draw |
| abort | reason | An interruption (`disconnect` / `chombo` / `manual`) |
| chombo | who, kind | A foul. kind is from the vocabulary of ruleset.penalties |

Rules of order: `deal` → `dora` (for the first indicators) → then in turn order. `riichi` comes right before the `discard` of the same who. The `dora` after a `kan` is at the position given by ruleset.dora.kan_timing. `win` / `draw_end` / `abort` come last.

### 2.5 final

| Item | Required | Content |
|---|---|---|
| scores[] | MUST | Final scores. The result.scores of the last round, after the riichi sticks left on the table have been handled by ruleset.flow.riichi.stick_at_end (to the first place if to_first). Confirmed on real logs (in Tenhou the 1000 points left go to the first place) |
| rank[] | MUST | The place of each seat (1 to M). Ties follow ruleset.settlement.tie |
| settled[] | MUST | The settlement of points (after return points, uma and oka). Length M, sum 0 (when oka is to_first) |
| chips[] | MAY | The final change in chips (the sum of chips of every win). When the ruleset has rules for chips |
| external_points[] | MAY | `{"system", "values": [..]}`. For each system in ruleset.settlement.external_points |
| payout | MAY | `{"unit": {"code"}, "values": [..], "fees": [..]}`. When ruleset.settlement.payout exists. Otherwise null |
| yakitori[] | MAY | When ruleset.yakitori.enabled. Whether each seat is yakitori (did not win once) |

## 3 Id and canonicalisation
- id = SHA-256 of the canonical JSON of all items except `id`. snapshots is MAY but **is included in the id** (so that "the same game with different ids" does not happen, if snapshots are attached they should always be attached when writing out)
- An import gives the same id for the same input (overview.md §10)

## 4 Verification
### 4.1 Alone
1. format / version; id agrees with the hash
2. source.kind is in the vocabulary; end is in the vocabulary
3. The length of players; seats are consecutive from 0 to M−1
4. rounds[].index are consecutive; state.scores has length M; state.scores of each round = result.scores of the previous round (for index 0: ruleset.start_points × M)
5. The rules of order of events (2.4). who and from are 0 to M−1
6. Either result.wins or draw. The sum of deltas is 0, or a value explained by riichi sticks going in or out (an integer multiple of kyotaku_points). scores = state.scores + deltas
7. final.scores = result.scores of the last round + handling of the remaining riichi sticks. rank = recomputed; settled = the settlement recomputed (X8)

### 4.2 Cross-layer (with tileset, wall and ruleset)
8. The ruleset file can be read. K is taken from the tileset of ruleset.tileset. Tile numbers in events are 0 to K−1
9. When the file of the wall.id of a round exists: wall.tileset.id = ruleset.tileset.id. The deal, the order of draws, the dora indicators and the replacement tiles are derived from wall.order and ruleset.wall_rules, and they **agree, in order**, with draw.tile, dora.tile and rinshan in events. If they do not, it is an error (the position in events is reported)
10. The number of tiles consumed in one round ≤ K − dead_wall
11. The names in wins[].yaku are yaku used by the ruleset (a yaku set to false in overrides does not appear). The sum of han = wins[].han. fu and han → points agree with the table of ruleset.scoring
12. wins[].chips agrees with the count recomputed from the rules in ruleset.settlement.chips (the first win also carries tobi_chips). chips in a record whose ruleset has no rule for chips is an error. final.chips = the sum of chips of every win
13. events do not contradict ruleset.flow: riichi_min_points for riichi, which abortive draws are used, whether double ron is allowed, the maximum number of kans, and so on
14. final.settled agrees with the value recomputed from ruleset.settlement (return points, uma, oka, tie). The same for external_points and payout (when the ruleset has them)
15. When device is present, a **warning** if it does not agree with each wall.device.id
16. When parent is present: if the game of parent.record can be read, events up to the branch point are confirmed to be the same (a warning if it cannot be read)

## 5 File name
`{ruleset.tileset.name}_{id, 64 digits}.record.json` (overview.md §4).

## 6 Correspondence with Tenhou and Mahjong Soul (main points of import; see overview.md §9 and §10)
- Tenhou: INIT → state, T/U/V/W → draw, D/E/F/G → discard, N → chi/pon/kan, REACH → riichi, DORA → dora, AGARI → win + result.wins, RYUUKYOKU → draw_end. hai0–3 are not written in deal; they are derived from the wall and compared (check 9). For GO.type → ruleset, one of the bundled tenhou-*.ruleset.json is chosen
- Mahjong Soul (not implemented yet): its logs have only the kind of each tile, so individual numbers would be assigned in order of appearance. The wall would be filled

## 7 Notes for 1-tile and 4-tile mahjong
- N=1: hand has 2 tiles (1 tile in hand + the winning tile). melds is always empty. chi/pon/kan do not occur (forbidden by ruleset.flow.chi=false and so on)
- N=4: hand has 5 tiles. One set and a pair
- The form is the same in both. Checks 9 and 11 work as they are
