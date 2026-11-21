# ruleset — specification of the ruleset (nmahjong-ruleset 1.0)

Key: MUST = required, MAY = optional, SHOULD = recommended. The container is JSON (UTF-8). See tileset.md for tilesets and wall.md for walls.
The grounds for the items are in ruleset-survey.md (a comparison of the rules of Japanese organisations, online services, a TV programme, parlours and three-player mahjong).

## 1 Purpose
To hold "how this mahjong is played" in one file, in a form a machine can read.

| Division | Item | What it decides |
|---|---|---|
| How the wall is consumed | wall_rules | Which parts of the wall (one sequence) are the deal, the draws, the dead wall, the dora indicators and the replacement tiles |
| Rules of play | game_rules | The meaning of marks, dora, nuki, yaku, flow, scoring, penalties |
| End | end | Going below zero (tobi), cold game, time, extension, the last round |
| Settlement | settlement | (a) points: starting points, return points, uma, oka, ties, chips, yakitori; (b) external points: rank points of a service, league points; (c) final reward: conversion of pt and chips into a reward unit (YEN, in-game points and so on), entry fees by place |

A ruleset is data independent of walls and records. A record refers to its ruleset by `{name, id}`. It is an **executable setting**, intended so that an application can run a game just by being given the ruleset; it is not a text for people to read.

## 2 Form (example: an M.League-type rule)

```json
{
  "format": "nmahjong-ruleset",
  "version": "1.0",
  "name": "jp-4p-hanchan-red3",
  "id": "sha256:…",
  "tileset": {"name": "mpsz", "id": "sha256:…"},
  "players": 4,
  "hand_size": 13,
  "length": "east_south",
  "winds": ["E", "S", "W", "N"],
  "wall_rules": {
    "deal": "N_each_then_1_to_dealer",
    "dead_wall": 14,
    "dora_indicator": [8], "ura_indicator": [9],
    "kan_dora": [6, 4, 2, 0], "kan_ura": [7, 5, 3, 1],
    "rinshan": [12, 13, 10, 11],
    "break": {"by": "dice"}
  },
  "game_rules": {
    "agari_form": "standard",
    "marks": {"red": {"effects": ["dora"]}},
    "mark_overrides": [],
    "dora": {"indicator": true, "ura": true, "kan": true, "kan_ura": true,
             "kan_timing": {"ankan": "immediate", "minkan": "after_discard", "kakan": "after_discard"},
             "values": {"indicator": 1, "ura": 1, "kan": 1, "kan_ura": 1}},
    "nuki": {"enabled": false},
    "yaku": {"base": "riichi-standard", "overrides": {}, "chiitoi_four_of_kind": false},
    "nagashi_mangan": {"enabled": false},
    "pao": {"yakuman": ["daisangen", "daisuushii", "suukantsu"], "tsumo": "full", "ron": "split", "honba_kyotaku": "discarder", "daiminkan_rinshan": false},
    "flow": {
      "open_tanyao": true, "atozuke": "allowed", "kuikae": "forbidden", "chi": true,
      "ippatsu": true,
      "riichi": {"min_points": 1000, "below_min": "forbidden", "without_draw": true, "on_houtei": true,
                 "furiten_riichi": true, "ankan_after": "if_shape_unchanged", "stick_at_end": "stays", "stick_if_ronned": false},
      "open_riichi": {"enabled": false},
      "renchan": {"dealer_win": true, "dealer_tenpai": true, "all_noten": false, "by_bakaze": {}},
      "renchan_on_abort": true,
      "ryukyoku": {"nine_terminals": false, "four_winds": false, "four_kans": false, "four_riichi": false, "three_ron": false},
      "double_ron": false, "triple_ron": "head", "kyotaku_to": "kamicha",
      "wareme": false,
      "kokushi_ankan_chankan": false, "ryuuiisou_requires_hatsu": false, "chuuren_any_suit": true,
      "max_kans": 4
    },
    "scoring": {
      "table": "standard", "honba_points": 300, "kyotaku_points": 1000, "noten_penalty": 3000,
      "mangan_round_up": true, "round_to": 100,
      "fu": {"double_wind_pair": 2, "rinshan_tsumo_fu": 2, "chiitoi": "25fu_2han", "open_pinfu_fu": 30, "menzen_tsumo_pinfu": true, "yakuhai_tanki_fu": 2, "enabled": true},
      "limits": {"sanbaiman_from": 11, "kazoe_from": null, "yakuman_base": 4, "max_multiple": 1, "stack_with_normal": false},
      "shibari": {"from_honba": null, "han": 2, "exclude_dora": true},
      "tsumo_loss": "none", "payment": "standard"
    },
    "penalties": {
      "chombo": {"kind": "rank_points", "value": 20, "replay": true, "honba_increase": false},
      "false_call": {"kind": "agari_houki"},
      "noten_riichi": "chombo"
    }
  },
  "end": {
    "tobi": {"enabled": false},
    "negative_points": "continue",
    "cold_points": null,
    "time_limit_sec": null,
    "extension": {"enabled": false},
    "agari_yame": {"enabled": false},
    "tenpai_yame": {"enabled": false},
    "max_honba": null
  },
  "settlement": {
    "start_points": 25000, "return_points": 30000,
    "unit": {"name": "pt", "points_per_unit": 1000, "decimals": 1},
    "uma": [30, 10, -10, -30], "oka": "to_first", "tie": "split",
    "dealer_takes_all": false,
    "chips": [], "yakitori": {"enabled": false},
    "external_points": [{"system": "mleague-p", "kind": "rank_plus_raw", "raw_base": 30000, "raw_divisor": 1000, "rank_points": [50, 10, -10, -30]}],
    "payout": null
  }
}
```

The numbers of wall_rules above were **checked on 2026-11-15** against one real Tenhou game log (2019051522gm-00a9-0000-8c64c236, 10 rounds, 3 kans): on the wall reproduced from the seed, with dora indicator 8, ura 9, kan dora [6,4,2,0], kan ura [7,5,3,1] and replacement tiles [12,13,10,11], the deals, every draw, the replacement tiles, the dora indicators, the kan dora and the dice agree in every round. Later 1,005 games were checked in the same way (conformance.md §5).

### 2.0 Omission and defaults
- `format` `version` `tileset` `players` `hand_size` `length` `winds` `wall_rules` cannot be omitted
- **Every item** under `game_rules` `end` `settlement` can be omitted. When omitted, the value in the example of §2 is the default (= the common "three red tiles; ippatsu, ura dora and kan dora used; open tanyao and atozuke allowed; 25000/30000; uma 30-10"). MUST in the tables means "the value is defined"; if it is not written, the default is put in
- When reading, the verifier makes the **normal form**, with defaults filled in, and the id is computed from that normal form. So a file that "omitted" an item and a file that "wrote the default explicitly" have the same id
- `unknown` (MAY): an array of paths of items that the source does not state, so that the value is not known (for example `["settlement.uma", "end.tobi"]`). They are completed with the default (or with the value written), and verification lists them as "missing". **unknown is included in the id** ("not known" and "asserting the default" are different settings)
- `meta` (MAY): `{source, note}`. The source and the main points. **Not included in the id**
- The default of uma depends on the number of players: 30-10 for 4 players, 0 for everyone otherwise (there is no source, so no value is invented)
- The han of a yaku can be set to any positive integer with `yaku.overrides`. Examples: tanyao 10 han = `{"tanyao": 10}`; riichi 10 han = `{"riichi": 10}`; lower when open = `{"tanyao": {"closed": 10, "open": 9}}`. There is no upper bound (above limits.kazoe_from it is a counted yakuman; if that is null it stops at sanbaiman)

### 2.1 The whole file

| Item | Required | Content |
|---|---|---|
| format | MUST | Fixed: `"nmahjong-ruleset"` |
| version | MUST | `"1.0"` |
| name | MUST | For display. `[a-z0-9-]+`. Do not put the name of a parlour or a table in it (parlours and tables are in the register of the application) |
| id | MUST | `"sha256:"` + the 64 hexadecimal digits of SHA-256( the canonical JSON of the normal form **without `id`, `name` and `meta`** ). Canonical = keys in dictionary order, no whitespace at `,` and `:`, UTF-8, `ensure_ascii=false`. The settings themselves are the seed, so **the same settings give the same id even under a different name**, and a difference in one item gives a different id. **The id is authoritative**; the name is for display (the same idea as for tilesets: the id of a tileset is also made from tiles alone) |
| tileset | MUST | `{name, id}`. The id is authoritative |
| players | MUST | The number of players M. An integer, **M ≥ 1** |
| hand_size | MUST | The number of tiles in a hand N. An integer, N ≥ 1 |
| length | MUST | `one` / `east` / `east_south` / `full` / `custom` (with `rounds_total`) / `endless` (no division into winds; the game ends by one of end.tobi, end.time_limit_sec, end.cold_points. Toutenkou) |
| winds | MUST | The list of seat winds. Length M. Vocabulary `E S W N` |
| wall_rules | MUST | See 2.2 |
| game_rules | MUST | See 2.3 |
| end | MUST | See 2.4 |
| settlement | MUST | See 2.5 |

### 2.2 wall_rules — how the wall is consumed

The wall is **consumed from the head** in the order of wall.md (deal → draws → dead wall). The dead wall is the last `dead_wall` tiles. A position inside the dead wall is an offset with the head of the dead wall as 0.

| Item | Required | Content |
|---|---|---|
| deal | MUST | The only word in 1.0 is `N_each_then_1_to_dealer`. Meaning: `order[0..N-1]` → the dealer of the round, `order[N..2N-1]` → the player after the dealer, …, `order[(M-1)N..MN-1]` → the player before the dealer, `order[MN]` → the dealer's first draw (**in turn order from the dealer**, not by seat number). N×M+1 tiles in total. **The procedure of a physical table, "taking four tiles at a time", is not reproduced** (tables that deal automatically have no taking procedure at all: AMOS ULTIMA 2005, Shoryu 2003, S-tellar 2022 and AMOS REXX 3 2021 raise the walls with the hands already dealt. [Wikipedia: automatic mahjong table (Japanese)](https://ja.wikipedia.org/wiki/%E5%85%A8%E8%87%AA%E5%8B%95%E9%BA%BB%E9%9B%80%E5%8D%93)). A rule under which N tiles cannot be dealt to M players (N×M+1+dead_wall > K) is a verification error |
| dead_wall | MUST | The number of tiles of the dead wall. 0 means no dead wall. 14 (common), 16 (Wareme: two dora indicators at all times) |
| dora_indicator | MAY | The array of offsets of the dora indicators. Several if several are turned from the start |
| ura_indicator | MAY | The array of ura dora indicators. The same length as dora_indicator |
| kan_dora | MAY | The positions turned additionally at each kan. An array, in the order of turning. **A negative value is on the side of the end of the live wall** (each time a replacement tile is used the dead wall takes in one tile from the end of the live wall; −1 is the original last tile, −2 the one before it). Tenhou three-player is `[2, 0, -2, -4]` (confirmed on real logs) |
| kan_ura | MAY | The ura indicators that correspond to kan_dora. The same length |
| rinshan | MAY | The positions of the replacement tiles. An array (offsets inside the dead wall, in the order of taking; length ≥ flow.max_kans + the maximum number of nuki) **or** the string `"live"` (a replacement tile is taken from the live wall as the next draw; for N-tile mahjong with a small dead wall). **A negative value is on the side of the end of the live wall** (counted as for kan_dora; −1 is the original last tile). 4-tile mahjong (nm-2p-4-*) is `[3, -1]`: the first is the fourth tile of the dead wall, the second is the original last live tile, which entered the dead wall at the first kan |
| break | MUST | `{"by": "dice" \| "fixed" \| "none"}`. The wall is already in the order of consumption, so dice means **the roll is recorded in the record**. Wareme (flow.wareme) uses this player |

- When dead_wall = 0, the position items are not written. An offset is 0 or more and less than dead_wall (only kan_dora / kan_ura / rinshan may also be negative), and no two items use the same position
- Each time a replacement tile is used, the tiles that can be drawn decrease by one (the last live tile enters the dead wall). A replacement tile after the rinshan array is used up is the tile on the side of the end of the live wall
- A round ends when the `K − dead_wall`-th tile has been consumed (it ends earlier by the number of replacement tiles taken for kans and nuki)
- `rinshan_reserved` (MAY; only `true` can be written, and only when rinshan is an array of positions): a rule in which the tiles for replacement are set aside in the dead wall (Toutenkou: "draw up to the tile next to the dora indicator"). While the tiles listed in rinshan are being used, taking a replacement does not shorten the round. A replacement after the listed tiles are used up is taken from the end of the live wall and the round ends earlier by that much. If it is not written, the behaviour is as before, and the id does not change

### 2.3 game_rules — rules of play

#### 2.3.1 Winning shape, marks, dora, nuki

| Item | Required | Content |
|---|---|---|
| agari_form | MUST | `standard` = (N−1)/3 sets + 1 pair (N mod 3 = 1 is required). `custom:<name>` is defined by the implementation (1-tile mahjong and the like) |
| marks | MUST | The meaning of each mark of the tileset. Key = the value of mark; value = a **mark rule** (below) |
| mark_overrides | MAY | An array. `{"tile_kind": "5p", "mark": "red", …mark rule}` or `{"tile_id": 52, …mark rule}`. Takes precedence over marks ("only the red five of dots is a one-han yaku" and the like) |
| dora.indicator / ura / kan / kan_ura | MUST | Each a bool |
| dora.kan_timing | MAY | By kind of kan. `{"ankan": …, "minkan": …, "kakan": …}`, each `immediate` / `after_discard` / `after_rinshan`. MUST when kan=true |
| dora.values | MAY | Han per tile. Default 1 for all |
| nuki | MUST | Nuki dora. `{"enabled": false}` or `{"enabled": true, "tiles": ["N"] \| ["ex"], "value": 1, "as_yakuhai": "none" \| "common" \| "seat", "chan_nuki": false, "win_with_nuki_in_hand": true, "pao": false, "forbid_keep": false}`. tiles are kinds (`ex` is all the extras of the tileset). as_yakuhai=common means "North is always a yakuhai". chan_nuki is the yaku for robbing a nuki of North. win_with_nuki_in_hand=false means a player cannot win while a nuki tile remains in the hand or in a meld (only the yakuman that cannot be made without those tiles — kokushi musou, chinroutou, tsuuiisou, shousuushii, daisuushii — can be won; Toutenkou). For forbid_keep and pao the game runner has no behaviour yet (dealer.md §4) |

**Mark rule** (a value of marks, and the content of mark_overrides)

| Item | Required | Content |
|---|---|---|
| effects | MUST | An array. `dora` (a dora worth one han) / `yaku` (a yaku worth one han; separate from dora) / `almighty` (can be used as any tile) / `reverse` (the win stands, but points and chips are paid by the winner; the reverse pocchi) / `none`. **They can be combined** ("dora and almighty" = `["dora","almighty"]`) |
| when | MAY | The condition under which the effect works. `{"state": "any" \| "riichi", "how": "any" \| "tsumo" \| "ron", "ippatsu_only": false, "rinshan_ok": true, "haitei_ok": true, "menzen_only": false}`. The white pocchi = `{"state":"riichi","how":"tsumo"}`. The default is unconditional. **A mark whose how is tsumo / ron has an effect "when the win is on that tile", and works on the winning tile only** (held in the hand it is an ordinary tile). A mark whose how is any works on any tile in the hand |
| forced_high | MAY | An almighty tile always wins with the highest value (a forced win). Default true |
| value | MAY | The han of dora / yaku. Default 1 |
| as_ura_indicator | MAY | The treatment when it appears as an ura dora indicator. `normal` / `choose_any` (if the white pocchi is the ura indicator, any tile may be made the dora) |

#### 2.3.2 Yaku

| Item | Required | Content |
|---|---|---|
| yaku.base | MUST | `riichi-standard` (the bundled yaku-riichi-standard.json) / `none` |
| yaku.overrides | MAY | Yaku name → `false` (not used) / an integer (the same for concealed and open) / `{"closed": n, "open": n}`. Local yaku go in the same place (`daisharin`, `suurenkou`, `sanrenkou`, `shousharin`, `sanpuu`, `renhou`, `manzu_honitsu`, `tsuuiisou_chiitoi`, `open_riichi`, `nagashi_mangan`). A yakuman is given as `"yakuman"` / `"yakuman:2"` |
| yaku.wheel | MAY | The shape of daisharin. `2to8` (default: seven pairs of 2 to 8 in one suit) / `any_suit` (any seven pairs that are a full flush; three-player mahjong in Kansai). Shousharin (`shousharin`) is seven pairs that are a half flush, in any suit. When it is used, only the han of shousharin is counted, without adding chiitoitsu and honitsu. If not written it is the default, and writing the same value as the default does not change the id |
| yaku.chiitoi_four_of_kind | MUST | Whether seven pairs may use four of the same tile |
| nagashi_mangan | MUST | `{"enabled": false}` or `{"enabled": true, "as": "tenpai_settlement" \| "draw_mangan" \| "win" \| "yakuman", "noten_penalty": false, "renchan_if_dealer_tenpai": true}`. as: `tenpai_settlement` and `draw_mangan` = treated as a draw, and the amount of a mangan tsumo is paid (honba and riichi sticks do not move) / `win` = treated as a win (the amount of a mangan tsumo plus honba, and the riichi sticks are taken too; when two or more players have it, the first counting from the dealer takes the honba and the sticks; if the dealer has nagashi mangan the dealer continues, otherwise the dealer passes and honba becomes 0) / `yakuman` = treated as a draw, with the amount of a yakuman tsumo. noten_penalty=true means the noten penalty is paid in addition to the mangan (yakuman) payment (not paid when as=win). renchan_if_dealer_tenpai=false means that in a round with nagashi mangan the dealer passes even when tenpai |
| pao | MUST | Pao (liability payment). `{"yakuman": [], …}` means no pao. `yakuman` is an array of yakuman names. `tsumo`: `full` (the liable player pays everything, including the part of other yakuman in a combined yakuman). `ron`: `split` (the part of the yakuman under pao is split with the player who dealt in; the part of other yakuman is paid by the player who dealt in) / `split_all` (everything, combined yakuman included, is split; Tenhou) / `full` (the liable player pays all of the part under pao). `honba_kyotaku`: who pays the honba part: `discarder` (the player who dealt in) / `liable` (the liable player; Tenhou). `daiminkan_rinshan`: whether a rinshan kaihou after an open kan is treated as pao |

#### 2.3.3 Flow

| Item | Required | Content |
|---|---|---|
| open_tanyao | MUST | Open tanyao |
| atozuke | MUST | `allowed` (atozuke allowed) / `kanzen_sakizuke` (complete sakizuke = no win on one side only: if even one of the waiting tiles of a tenpai hand gives no yaku, the player cannot win even on a tile that does give a yaku. Yaku are counted as if the win were on that tile in the same way; chance yaku (ippatsu, haitei, houtei, rinshan, chankan) and dora are not counted. After riichi every wait has a yaku. A concealed tsumo can be won because menzen tsumo applies. Yakuman are not restricted) / `forbidden` (sakizuke. There is no source for how "a win on one side is allowed" is decided, so the game runner reports it as a setting it cannot follow) |
| kuikae | MUST | `allowed` / `no_same_tile` (only the same tile is forbidden) / `forbidden` |
| chi | MUST | Whether chi is allowed (often false in three-player mahjong) |
| pon | MUST | Whether pon is allowed. Default true. false in N-tile mahjong (nm-*; the only call is a concealed kan) |
| ippatsu | MUST | Ippatsu |
| riichi.min_points | MUST | The points needed to declare riichi (often 1000; 0 means no restriction) |
| riichi.below_min | MUST | Below min: `forbidden` / `allowed` (allowed even if the stick cannot be paid). "Allowed with exactly 1000 points" is expressed by min_points=1000 |
| riichi.without_draw | MUST | Whether riichi is allowed when the player has no draw left |
| riichi.on_houtei | MUST | Whether riichi is allowed on the last discard |
| riichi.furiten_riichi | MUST | Riichi while furiten |
| riichi.stick_if_ronned | MUST | Whether the riichi stick is put out when the declaration tile is ronned. false (common: the riichi does not stand and no stick is put out) / true (the stick is put out at the moment of declaration; the winner takes it. The variants whose name ends in -ronstick; nm-defaults.md §2.1) |
| riichi.ankan_after | MUST | A concealed kan after riichi. `if_shape_unchanged` (allowed if the waits and the composition do not change; the great majority today) / `none` (not allowed; μ) / `any` (**a kan that changes the waits is also allowed**; old rules and some private groups. It hardly exists today but is kept as a setting) |
| riichi.stick_at_end | MUST | Riichi sticks left at the end of the game. `stays` (they stay on the table) / `to_first` (to the first place) |
| open_riichi | MUST | `{"enabled": false}` or `{"enabled": true, "han_total": 2, "deal_in": "yakuman" \| "normal", "exempt_prior_riichi": true, "chaser_pays": true, "with_double_riichi_han": 3}`. han_total = the han of an open riichi (the total, riichi included). deal_in = `yakuman`: dealing in by ron to an open riichi pays the points of a yakuman (the yaku of the win is the single `open_riichi_deal_in`; if the hand is a yakuman it stays that yakuman). exempt_prior_riichi=true: a deal-in by a player who was in riichi before the open riichi is not paid as a yakuman. chaser_pays=false: a deal-in by a player who declared riichi afterwards (including the declaration tile) is not paid as a yakuman either. A tsumo is paid at ordinary points |
| renchan | MUST | Conditions for the dealer to continue. `dealer_win` (the dealer won), `dealer_tenpai` (the dealer is tenpai), `all_noten` (the dealer continues if everyone is noten), `draw` (on a draw the dealer continues whether tenpai or not; takes precedence over dealer_tenpai), each a bool. `by_bakaze` overrides by round wind (Kansai three-player "in the south round the dealer continues even when noten" = `{"S": {"dealer_tenpai": true, "all_noten": true, "dealer_noten": true}}`) |
| renchan_on_abort | MUST | Whether the dealer continues on an abortive draw |
| ryukyoku | MUST | Which abortive draws are used. `nine_terminals` `four_winds` `four_kans` `four_riichi` `three_ron`, each a bool |
| double_ron | MUST | Double ron (false means only the player nearest to the discarder wins) |
| triple_ron | MUST | `allow` / `draw` / `head` |
| kyotaku_to | MUST | Riichi sticks and honba when several players win. `kamicha` (only the winner nearest to the discarder takes them) / `split` (each winner takes the honba, and the sticks are divided equally; a remainder goes to the winner nearest to the discarder) |
| wareme | MUST | Wareme. When the player at the break (the wareme seat) wins, every payer pays double. When the wareme seat pays, that payment is doubled. Honba, riichi sticks, the noten penalty and the tobi penalty are not doubled. The wareme seat is written in state.wareme of the record: if break.by=dice it is the player found by counting the sum of the dice anticlockwise from the dealer (5, 9 = the dealer; 2, 6, 10 = the next player; 3, 7, 11 = the player opposite; 4, 8, 12 = the previous player); if fixed, the dealer. Used with four players |
| next_dealer | MAY | How the next dealer is decided. `rotate` (default: when the dealer passes, the next seat) / `winner` (the player who won is the next dealer. The wind and the round number do not advance. If the dealer wins, honba increases by one; if a non-dealer wins, it returns to 0. On a draw the dealer continues or passes to the next seat by the renchan rules, and honba does not increase = honba is the number of consecutive wins of the dealer. With several winners, the one nearest to the discarder. Toutenkou). If not written it is the default, and writing the same value as the default does not change the id |
| kokushi_ankan_chankan | MUST | Whether, for kokushi musou only, a tile of a concealed kan can be ronned. Default false. Even under a rule where it is true, shapes other than kokushi musou cannot ron a tile of a concealed kan. A ron on the tile of an added kan (chankan) is possible regardless of this item |
| ryuuiisou_requires_hatsu | MUST | Whether ryuuiisou requires the green dragon |
| chuuren_any_suit | MUST | Whether chuuren poutou is allowed in any suit |
| max_kans | MUST | The limit on kans in one round (4; a fifth is not possible) |
| kan_kinds | MUST | The array of kinds of kan allowed. Default `["ankan", "minkan", "kakan"]`. If `kakan` is included, pon=true. 4-tile mahjong (nm-2p-4-*) is `["ankan"]` |
| max_kans_per_player | MUST | The limit on kans one player can make in one round. An integer or null (no limit, default). 4-tile mahjong (nm-2p-4-*) is 1 (max_kans is 2, the total for the round) |

#### 2.3.4 Scoring

| Item | Required | Content |
|---|---|---|
| table | MUST | `standard` (fu × han, with the two base han; the bundled scoring-standard.json) / `additive` (additive scoring; see "Additive scoring" below) / `custom:<name>` (a bundled table. `custom:nm1-limits` = han → haneman (up to 7), baiman 8, sanbaiman 11, counted yakuman 13, with haneman as the minimum. 1-tile mahjong nm-2p-1-*) |
| honba_points | MUST | The points added from one player per honba (300 / 1000 / 1500) |
| kyotaku_points | MUST | One riichi stick |
| noten_penalty | MUST | The noten penalty (0 means none). With four players it is the total on the table (3000: one tenpai player receives 3000; one noten player pays 3000). With three players, one third of this value is one unit: one tenpai player receives 2 units (1 unit from each), and two tenpai players receive 1 unit each (the noten player pays 2 units). For three players, "2000 points on the table" is written as 3000, and "20 points on the table" as 30 |
| tsumo_table | MAY | Decides the payments of a non-dealer's tsumo in three-player mahjong by the parlour's table. `{"8000": [5000, 3000], …}` (key = the ron points of the same hand; value = [the dealer's payment, the non-dealer's payment]). Points not in the table are paid by the formula of tsumo_loss. Not used for the dealer's tsumo. Example of the Kansai "marudori": mangan 5000-3000, haneman 8000-4000, baiman 10000-6000, sanbaiman 16000-8000, yakuman 20000-12000 |
| additive | MAY | Only when table = `additive`. `{"per_han": 1, "base": 2, "dealer": 1, "honba": 1, "honba_dealer_only": true, "multiplier": 1, "round_to": 1, "yakuman": 50, "karasu": {"menzen": 0, "open": 0}}` (items not written are filled with these defaults) |
| mangan_round_up | MUST | Rounding up to mangan (kiriage mangan) |
| round_to | MUST | The smallest unit of points. 100 (common) / 1000 (Kansai three-player: anything below 1000 is rounded up. For a ron the total, for a tsumo each payment, is rounded up to 1000) |
| fu.enabled | MUST | Whether fu is counted (false means han only; ZOO three-player) |
| fu.double_wind_pair | MUST | The fu of a pair of the double wind. 2 / 4 |
| fu.rinshan_tsumo_fu | MUST | The tsumo fu of rinshan kaihou. 2 / 0 |
| fu.chiitoi | MUST | `25fu_2han` / `50fu_1han` |
| fu.open_pinfu_fu | MUST | The fu of an open hand in the pinfu shape. 30 (common, Sports Mahjong) / 20 |
| fu.menzen_tsumo_pinfu | MUST | Whether pinfu with tsumo is allowed |
| fu.yakuhai_tanki_fu | MAY | Extra fu for a single wait on a yakuhai tile (ZOO: 2 fu). Default 0 |
| limits.sanbaiman_from | MUST | The han for sanbaiman (11) |
| limits.kazoe_from | MUST | The han for a counted yakuman. `null` (none = stops at sanbaiman) / 13 / 14 |
| limits.yakuman_base | MUST | A yakuman as a multiple of mangan. 4 (common). Also 4 in Kenko Mahjong and Sports Mahjong |
| limits.max_multiple | MUST | The upper limit of the multiple when yakuman combine. 1 (they do not combine) / 2 / 6 (meaning no limit; Tenhou, Mahjong Soul). Whether a single-tile wait, a thirteen-sided wait and the like are double on their own is decided by `"yakuman:2"` in yaku.overrides |
| limits.stack_with_normal | MUST | Combining yakuman with ordinary yaku (normally false) |
| shibari | MUST | A minimum-han requirement. `{"from_honba": null \| 5, "han": 2, "exclude_dora": true}` |
| tsumo_loss | MUST | The payments of a tsumo in three-player mahjong (it does not concern four or two players). `loss` (tsumo loss: the four-player formula as it is; nobody pays the north player's part) / `add_1000` (1000 points are added to each of the two payments) / `marudori` (the ron points are divided. For a non-dealer's tsumo: the non-dealer pays ron ÷ 3 rounded down to 100, the dealer pays the rest. For the dealer's tsumo: the two players each pay ron ÷ 2 rounded up) / `north_split` (the north player's part is split: for a non-dealer's tsumo, the non-dealer pays the non-dealer payment × 1.5 rounded down, the dealer pays the dealer payment + half the non-dealer payment rounded up. The dealer's tsumo is the same as marudori) / `none` (no tsumo loss, with no method stated: paid as marudori. Used for rules whose source says only "no tsumo loss", and listed in `unknown`). The amounts were compared with the score table of りゅ～く.net "三麻の点数表と点数計算" (tests/test_rule_options.py O1–O3) |
| payment | MUST | How payments are decided. `standard` (each of the M players pays their share) / `4p_total_from_opponent` (the single opponent pays the whole of the four-player total. The other version of 4-tile mahjong, nm-2p-4-room) / `4p_child_half_from_opponent` (a ron is the whole four-player amount; for a tsumo the opponent pays half of the non-dealers' total. 1-tile mahjong nm-2p-1-*) / `4p_dealer_share_from_opponent` (a ron is the whole four-player amount; for a tsumo the single opponent pays the dealer's share in four-player mahjong = basic points × 2 rounded up to 100. 4-tile mahjong nm-2p-4-*). Default standard. Anything other than standard when M ≠ 2 is an error |

**Additive scoring (table = `additive`)** — fu and the score table are not used; han are added as points as they are (common in three-player mahjong in the Kanto region, such as Toutenkou).

```
points one player pays = round_up( ( han × per_han + yakuman points + base + dealer (if the winner is the dealer) + honba count × honba ) × multiplier , round_to ) + karasu points
```

- For a ron the player who dealt in pays these points. For a tsumo every other player pays these points each (payments are not divided between dealer and non-dealer)
- han: the sum of yaku, dora and nuki dora (han of the judgement). yakuman points: `yakuman` × the multiple of the yakuman (up to limits.max_multiple). To add dora and the like to a yakuman, set limits.stack_with_normal=true
- base: points added to every win. dealer: points added to a win by the dealer. honba: points per honba (if honba_dealer_only=true, counted only when the dealer wins)
- multiplier and round_to: the number the total is multiplied by, and the unit it is rounded up to (for example ×4, to units of 10)
- karasu: points added to a win in which no nuki tile (nuki.tiles) was set aside and none is held in the hand. `menzen` = concealed, `open` = with calls. 0 means none
- In this case honba_points is not used (honba is inside the formula). The riichi sticks (kyotaku_points) are taken by the winner. fu, mangan_round_up, limits.kazoe_from, tsumo_loss and round_to are not used
- In a record, the breakdown `additive` is written for every win (record.md)

| Example (values of the source) | Setting | Calculation |
|---|---|---|
| 1 han = 1 point, base 2, dealer 1, honba 1 (dealer only), yakuman 50, karasu 20 and open karasu 10 (LAG) | defaults + `karasu: {menzen: 20, open: 10}` | Dealer, 2 honba, tsumo with 11 han: 11+2+1+2 = 16 points from each. A ron with the same hand (10 han): 15 points |
| (base points: non-dealer 1, dealer 2; + han + nuki dora + honba) × 4, rounded up to units of 10 (麻雀ぽんと。) | `base: 1, dealer: 1, multiplier: 4, round_to: 10, honba_dealer_only: false` | Non-dealer, ron, 8 han, 0 honba: (1+8)×4 = 36 → 40 points. Dealer, tsumo, 5 han, 2 honba: (2+5+2)×4 = 36 → 40 points from each of the two |

#### 2.3.5 Penalties

| Item | Required | Content |
|---|---|---|
| chombo | MUST | `{"kind": "points" \| "rank_points" \| "kyotaku", "value": integer, "replay": bool, "honba_increase": bool}`. points: a mangan payment = 8000 (dealer 12000), a baiman payment = 16000, 8000 from everyone = `"value": 8000, "all": true`. rank_points is taken from the results (20 = −20P). kyotaku is placed on the table (Saikyosen: 12000) |
| false_call | MUST | An empty pon, an empty chi and the like. `{"kind": "agari_houki"}` / `{"kind": "kyotaku", "value": 1000}` / `{"kind": "chombo"}` |
| noten_riichi | MUST | A riichi found to be noten at a draw. `chombo` / `agari_houki` |

For the vocabulary of yaku names, yakuman names, reasons for a draw, conditions for chips and kinds of win, the bundled `vocab.json` is authoritative. The mapping of Tenhou's yaku numbers is `tenhou-yaku-map.json`.

### 2.4 end — the end

| Item | Required | Content |
|---|---|---|
| tobi | MUST | `{"enabled": false}` or `{"enabled": true, "at": 0, "exact_zero_is_tobi": false, "on_noten_penalty": true, "penalty_points": 0, "penalty_to": "none" \| "tenpai_players" \| "winner"}`. The game ends when a player's points are below at (also exactly at, if exact_zero_is_tobi=true). If on_noten_penalty=false, a player does not go out by the noten penalty (the payment at a draw). penalty_points = the penalty the player who went out pays to the player who put them out. penalty_to: `winner` = to the winner who put the player out by a win (when the player dealt in to two players, the winner nearest to them) / `tenpai_players` = in addition, when the player went out by the noten penalty, to a tenpai player (if two or more, the first tenpai player counting from the seat that went out). The penalty is included in the changes of that round (wins[0].deltas / draw.deltas), and the breakdown is written in result.tobi_penalty [{from, to, points}]. Wareme = penalty_points 10000, penalty_to tenpai_players |
| negative_points | MUST | Points below zero. `continue` (borrow and go on; settle with the negative value) / `zero` (no counting below zero = settle as 0) |
| cold_points | MUST | The points at which a cold game ends. `null` / 55000 / 60000 |
| time_limit_sec | MUST | The time limit. `null` / 3600. When this many seconds have passed since the game started, the round being played is finished and the game ends (no new round is started; end of the record is `time_limit`) |
| extension | MUST | Extension (into the south or west round). `{"enabled": false}` or `{"enabled": true, "until_points": 30000, "max_rounds": 4, "once": true, "renchan_first": false}`. until_points: the game ends in the round in which someone reaches these points. max_rounds: the maximum number of rounds of the extension. once: the extension is one wind only. renchan_first: after the extension has started, if the dealer continues, continuing takes precedence even when the points have been reached, and the game ends by agari-yame or tenpai-yame only when the dealer is in first place (Tenhou) |
| agari_yame | MUST | `{"enabled": false}` or `{"enabled": true, "when": "last_round", "forced": false, "others_may_continue": false}`. When the dealer wins in the last round (rounds of an extension included) and would continue. forced=true: if the dealer is in first place the game always ends (Marchao). forced=false: a dealer in first place chooses whether to stop or go on. others_may_continue=true: a dealer in second or third place (neither first nor last) may choose whether to stop or go on (Marchao: "2着・3着の場合は続行選択自由"). If false, a dealer who is not first goes on |
| tenpai_yame | MUST | `{"enabled": bool, "forced": bool, "require_tenpai": true}`. When, in the last round, the dealer is tenpai at a draw and would continue. forced=true: if the dealer is in first place the game always ends. false: a dealer in first place chooses. require_tenpai=false is "in the last round, if the dealer is ahead the game ends whether tenpai or not" (N-tile mahjong nm-*) |
| max_honba | MUST | The upper limit of honba. `null` or an integer (the game ends when it is reached; 50 in N-tile mahjong nm-*) |

### 2.5 settlement — the settlement

The settlement has three stages. **(a) Settlement of points** (points → return points, uma, oka → pt), **(b) external points** (numbers that move separately from points, such as rank points of Mahjong Soul and Tenhou, or P of M.League), **(c) final reward** (pt and the number of chips → a reward unit; includes entry fees by place; the form is the same whether the unit is YEN or in-game points). (a) exists in every rule; (b) and (c) do not exist in some.

**The unit pt**: uma, oka, chips and external points are all written in `unit` (by default 1 pt = 1000 points). A parlour's "1-1.5-3" or "5-10", M.League's "+50P", and the place points of Tenhou and Mahjong Soul are all in this unit.

#### 2.5.0 (a) Settlement of points

| Item | Required | Content |
|---|---|---|
| start_points | MUST | Starting points |
| return_points | MUST | Return points |
| unit | MAY | `{"name": "pt", "points_per_unit": 1000, "decimals": 1}`. This is the default. name is for display (`P`, `pt`, `千点`) |
| uma | MUST | Place points (pt). **An array** (length M, from first place) **or** `{"by_floating": {"1": [...], "2": [...], "3": [...]}, "threshold": "return" \| "start" \| integer, "includes_threshold": true}`. By the number of players above the threshold (JPML, Sports Mahjong, Kenko Mahjong). **threshold=start** is the parlour rule "A-top: if second place is below 25,000, second place pays" (Sakae Shibuya) |
| oka | MUST | `to_first` / `none` / `split` |
| rounding | MAY | Rounding of the settlement. `{"score_to_1000": "none" \| "half_up_600" \| "half_up_500", "remainder_to_top": false}`. The **points themselves** are rounded to units of 1000 (round the absolute value and restore the sign), and then the return points are subtracted. Rounding the difference would give 28500 → −1.5 → −2, which does not agree with real data. half_up_500 = .5 rounds up; half_up_600 = .5 rounds down and .6 rounds up. Tenhou is half_up_500 (28500→29 = −1 pt, 36500→37, −500→−1), the first place absorbs the remainder, and ties are seat_order (confirmed on owari of 1,002 public logs; Tenhou's written explanation says ".5 rounds down" but the real data round .5 up). Default none / false |
| tie | MUST | Ties. `split` (the place points are divided) / `seat_order` (the player nearer to the first dealer is higher) / `draw` (a tie; the place is shared) |
| dealer_takes_all | MUST | The dealer takes all |
| chips | MUST | An array of rules for chips (empty = none). See 2.5.1. Counted in chips |
| yakitori | MUST | `{"enabled": false}` or see 2.5.2 |

#### 2.5.3 (b) external_points[] — external points (MAY; may be an empty array)

Numbers that move by place (and raw points), separately from the settlement of points. Games (Mahjong Soul, Tenhou) and leagues (M.League) have them.

| Item | Required | Content |
|---|---|---|
| system | MUST | The name. Any string, such as `jantama-rank`, `tenhou-rank`, `tenhou-rate`, `mleague-p` |
| kind | MUST | `rank_only` (place only; Tenhou rank points) / `rank_plus_raw` (place points + raw points converted; Mahjong Soul rank points, M.League P) / `formula` (decided by a formula; Tenhou Rate. This specification holds only the name and does not compute it) |
| raw_base | MAY | The base points for converting raw points. Mahjong Soul = 25000 (starting points), M.League = 30000 (return points) |
| raw_divisor | MAY | 1000 |
| rank_points | MUST (except formula) | An array (length M) **or** `{"by_player_rank": {"初心": [25,10,-5,-15], "雀聖3": [75,35,-5,-125], …}}`. In Mahjong Soul and Tenhou the deduction for fourth place changes with **the player's own rank**, hence by_player_rank. The names of ranks are the vocabulary of the system |
| rounding | MAY | `none` / `ceil_0.01` and so on. Tenhou Rate rounds up at the third decimal place |

Mahjong Soul: `{"system":"jantama-rank","kind":"rank_plus_raw","raw_base":25000,"raw_divisor":1000,"rank_points":{"by_player_rank":{…room × rank…}}}` ([game8](https://game8.jp/jantama/631616)). Tenhou: `{"system":"tenhou-rank","kind":"rank_only","rank_points":{"by_player_rank":{"初段":[30,15,0,-45],…}}}`; Rate is `{"system":"tenhou-rate","kind":"formula"}` ([Tenhou manual](https://tenhou.net/man/)). M.League: `{"system":"mleague-p","kind":"rank_plus_raw","raw_base":30000,"raw_divisor":1000,"rank_points":[50,10,-10,-30]}` (uma and oka included).

#### 2.5.4 (c) payout — final reward (MAY; may be null)

The rule for converting pt and the number of chips into a **reward unit**. The unit can be anything (a currency such as `JPY`, in-game `COIN` or `PT`, a tournament's `P`). This specification only holds the coefficients of the conversion; what the unit is, is decided by `unit.code`.

| Item | Required | Content |
|---|---|---|
| unit | MUST | `{"code": "JPY" \| "COIN" \| "PT" \| …, "name": "display name"}`. code is the three letters of ISO 4217, or otherwise 2 to 8 capital letters (an in-game unit) |
| per_pt | MUST | Reward units per 1 pt. Examples: 50 / 100 / 30 ([doramahjong](https://doramahjong.org/freejyannsou/01/0003.html)); anything for an in-game unit |
| chip_value | MUST (when chips exist) | Reward units per chip. Examples: 100 / 500 |
| rounding | MAY | `none` / `round_100`. Default none |
| fees | MAY | Entry fees. `{"by_rank": [700, 500, 500, 500], "collect": "each" \| "top_pays_all"}`. by_rank is **the amount for each place, from first** (length M). If everyone pays the same, repeat the value. "Only the first place 700, the others 500" and "600 for everyone, plus 300 for the first place only" (= [900,600,600,600]) both take this form. collect=top_pays_all is the practice in which "the first place pays the parlour for everyone and the others are deducted in the settlement". If `unit` is omitted it is the same unit as payout.unit (JPY for a parlour, COIN for Mahjong Soul). If only the entry fee is in another unit (tickets and so on), write `"unit": {"code": "TICKET"}` alongside. In Mahjong Soul, entering needs coins according to the room (the bronze room is free), entry is refused if they are insufficient, and the reward is also coins according to the points ([game8](https://game8.jp/jantama/615786)) → `payout{unit COIN, per_pt …, fees{by_rank [c,c,c,c]}}`. Deposits are a practice of the parlour and are not held |

**Reproducing Sakae Shibuya** ([じゃんラボ](https://media.jannavi.net/sakae/), [doramahjong さかえ](https://doramahjong.org/freejyannsou/08/0040.html), [旅打ち記録](https://jangoro46.hatenablog.com/entry/2020/01/13/230000)): Uma 1-1.5-3 with A-top → `uma.by_floating` with `threshold: start`. Red 5p = a yaku, with chips even when the hand is open → `mark_overrides[{tile_kind 5p, effects ["yaku"]}]` + `chips[{on win_with_mark, tile_kind 5p, when always, count 1}]`. Red 5m and 5s = dora + chips. One chip each for ippatsu and ura dora → `chips[{on win_kind ippatsu},{on win_kind uradora}]`. A tobi penalty of one chip → `chips[{on tobi, count 1}]`. Honba 1500. The four red tiles used on holidays are a separate ruleset whose tileset is replaced with an `mpsz` containing two red 5p. **Chips for a yakuman are "unknown" in both sources, so they are not written.** Not all patterns of uma (what first and third place receive) are in the sources, so only the corresponding rows of by_floating are filled and the verifier lists the rest as missing.

#### 2.5.1 chips[] — rules for chips

| Item | Required | Content |
|---|---|---|
| on | MUST | `win_with_mark` (the winning hand contains the target tile) / `win_kind` (the kind of win; kind is one of ippatsu, uradora, yakuman, haitei, houtei, rinshan, chankan, tsumo, ron, double_riichi, renhou) / `tobi` (going out: the player who went out pays the winner who put them out) / `kan` / `nuki` / `call` / `yakitori` |
| mark / tile_kind / tile_id | MAY | Narrowing the target |
| when | MAY | `always` / `menzen` / `tsumo` / `ron`. Default always (also given for an open hand) |
| win_tile | MAY | When on=win_with_mark. If true, only the winning tile is looked at (chips for winning on the white pocchi). By default the whole hand and the melds |
| per | MUST | `tile` / `event` |
| count | MUST | The number of chips. A gold tile's "double chips" = a rule with count 2 written for the gold tile |
| payer | MUST | `loser` (for a ron the player who dealt in, for a tsumo every other player, pays count chips each) / `all` (for a ron and for a tsumo alike, every other player pays each) / `kan_target` (when on=kan) |
| kan_kind | MAY | When on=kan: an array of `ankan` / `minkan` / `kakan` |

How they are counted: for win_with_mark, the number of tiles in the winner's hand and melds (tiles set aside by nuki included) that match the target (mark / tile_kind / tile_id). If per=tile, that number × count; if per=event, count if there is at least one. For win_kind, uradora counts the number of ura dora, and yakuman counts the multiple of the yakuman. In a win with the reverse pocchi (the mark effect reverse), the winner is the one who pays the chips too. In a record, the change per seat `chips` is written for every win, and the total `final.chips` at the end of the game (record.md).

The game runner counts win_with_mark, win_kind and tobi. For a ruleset with rules for kan, nuki, call or yakitori, the game runner reports them as "settings it cannot follow" (programs/dealer.md §4).

#### 2.5.2 yakitori

| Item | Required | Content |
|---|---|---|
| enabled | MUST | Whether it is used |
| penalty | MUST | `{"kind": "chips", "count": 1}` / `{"kind": "points", "value": 10000}` |
| revive | MAY | An array of `all_cleared` (phoenix) / `feed_yakitori` / `last_cleared_returns` / `{"time_limit_sec": n}` |

## 3 Bundled data
| File | Content |
|---|---|
| `yaku-riichi-standard.json` | Yaku names, han when concealed, han when open, yakuman flag |
| `scoring-standard.json` | fu × han → points (non-dealer and dealer, ron and tsumo) |
| `vocab.json` | Vocabulary of yaku (local yaku included), yakuman, reasons for a draw, conditions for chips, kinds of win, pao |
| `tenhou-yaku-map.json` | Tenhou's yaku numbers → yaku names |
| `rulesets/*.ruleset.json` | **The collection of default rulesets.** The real rules of §7 (for organisations, all of their several sets such as A / B) and the defaults of N-tile mahjong (§7.1). The ruleset generator reads these as templates and asks only about differences. Items not in the source are not invented as confirmed values |

## 4 Reference
A record refers to it with `"ruleset": {"name", "id"}`. The id is authoritative. The text of the rules is not written inside a record.

## 5 Verification
1. format / version are the fixed values; name is `[a-z0-9-]+`
2. id = the hash of the canonical JSON of the normal form without id, name and meta
3. tileset.id is an existing tileset (when available). K is obtained
4. players ≥ 1, hand_size ≥ 1, the length of winds = players and the winds are in the vocabulary
5. N×M+1 + dead_wall ≤ K
6. Offsets inside the dead wall are in range and not repeated. No position items when dead_wall=0. dora_indicator and ura_indicator, and kan_dora and kan_ura, have the same length
7. The length of rinshan ≥ max_kans (plus the number of tiles that can be set aside, if nuki.enabled)
8. When agari_form=standard, N mod 3 = 1
9. The targets of mark_overrides and chips (mark / tile_kind / tile_id) exist in the tileset (error). A key of marks that is not in the tileset is a **warning** (no effect; when the default red is applied to a tileset without red tiles). effects are in the vocabulary; `none` can be used only alone; `reverse` only together with `almighty`
10. The yaku names in yaku.overrides, pao.yakuman, nagashi and open_riichi are in vocab. A han is an integer of 1 or more, `yakuman[:n]`, or false
11. When nuki.enabled, tiles exist in the tileset. When as_yakuhai=seat, tiles are winds
12. When wareme=true, break.by ≠ none
13. When chi=false, the rules in vocab for reduced han of open hands have no effect (no warning). players=4 with chi=false is a **warning**
14. uma: if an array, length = players. If by_floating, all keys 1 to M−1 exist and each array has length = players; threshold is `return` / `start` / an integer. A **warning** if the sum is not 0
14b. external_points[]: system is required; kind is in the vocabulary; rank_only / rank_plus_raw require rank_points (if an array, length = players; if by_player_rank, each value has length = players); rank_plus_raw requires raw_base and raw_divisor
14c. payout: unit.code is ISO 4217 or 2 to 8 capital letters; per_pt > 0; chip_value is required when chips is not empty; fees.by_rank is non-negative integers of length = players; fees.collect is in the vocabulary
15. chips[]: on is in the vocabulary; per / count / payer are required; the target exists in the tileset; kan_kind only with on=kan; on=yakitori only when yakitori.enabled
16. When yakitori.enabled, penalty is required; revive is checked against the vocabulary
17. unit.points_per_unit > 0
18. When length=custom, rounds_total ≥ 1. When length=endless, one of end.tobi / end.time_limit_sec / end.cold_points exists
19. end: when tobi.enabled, at is an integer, and if penalty_to ≠ none then penalty_points > 0. When extension.enabled, until_points and max_rounds are required
20. scoring: round_to ∈ {100, 1000}; limits.kazoe_from ∈ {null, 13, 14, …} and ≥ sanbaiman_from+1; max_multiple ≥ 1; shibari.from_honba is null or 1 or more. When table = additive, each value of additive is an integer of 0 or more (multiplier and round_to are 1 or more), and payment = standard. additive only when table = additive
21. The required items for each penalties.chombo.kind (points → value, rank_points → value, kyotaku → value)
22. When open_riichi.enabled, `open_riichi` in yaku.overrides is not false (a **warning**: for the han, han_total is authoritative)

## 6 File name
`{name}_{id, 64 digits}.ruleset.json`. The 64 digits as they are, ASCII only (overview.md §4).

## 7 Confirming that real rules can be expressed
The rules surveyed in ruleset-survey.md are written in `rulesets/` and passed through the verifier. An item that the source does not state is set to the most plausible value (or left at the default), and its name is listed in `unknown` of the ruleset; the verifier **lists those item names** as missing. When the organisation, service or parlour tells us the correct value, the ruleset is corrected (CONTRIBUTING.md, "Rule corrections").

An organisation does not have just one rule. **All** the sets that are published are made separate files.

**The names of the companies and organisations belong to their respective owners. The content of each rule was written down by us after checking published material; the source is in the source field (meta.source) of each ruleset file.** These rulesets are not approved by the organisations or companies. For an actual game or tournament, check the latest regulations of the organiser.

| name (46 bundled, of which 16 are the nm-* of N-tile mahjong; items not in the source are listed in unknown of each file) | Origin | Features this example uses |
|---|---|---|
| jpml-official | JPML (Japan Professional Mahjong League), official rule | No ippatsu, ura dora or kan dora; place points by the number of players above the starting points; 2 fu for a pair of the double wind; no kuikae; no abortive draws; the winner nearest to the discarder has priority; no counted yakuman; yakuman combine (suuankou tanki, daisuushii, the 13-sided kokushi and the 9-sided chuuren are not double on their own); pao (daisangen, daisuushii, suukantsu; all on a tsumo, split on a ron); no win on a concealed kan for kokushi; no liability for rinshan after an open kan; no riichi on the last discard; 30 fu 4 han is not rounded up; −20P |
| jpml-wrc | JPML WRC | Ippatsu, ura dora and kan dora; 30000/30000; 15-5; no abortive draws; kokushi can ron a concealed kan; rounding up to mangan; −30P |
| jpml-wrc-r | JPML WRC-R | WRC + three red tiles; 30-10 |
| saikouisen | Saikouisen | 30000 points and no oka; place points 10-30; no abortive draws; no agari-yame or tenpai-yame; no pao; no counted yakuman; yakuman do not combine; no win on a concealed kan for kokushi; −40P |
| saikouisen-classic | Saikouisen Classic | Place points 12-4; no ippatsu, ura dora, kan dora or kan ura (only the first dora); the dealer continues only by winning; no noten penalty; 300 points per honba; no rounding up to mangan; kuikae allowed; no concealed kan after riichi; −16P. Where the source is silent (no abortive draws, no pao, yakuman do not combine) it is made the same as the Saikouisen rule |
| npm | NPM (Japan Professional Mahjong Association) | 25000/30000; place points 50-10 (oka included); no abortive draws; no double or triple ron (the nearest player); no renhou or nagashi mangan; no pao; yakuman combine when the yaku are genuinely combined; play continues when points run out; riichi allowed with no draw left; −40P |
| rmu-a | RMU A | 30000/30000; 15-5; ippatsu, ura dora and kan dora; no abortive draws; the nearest player has priority; play continues below zero; counted yakuman from 13; yakuman combine; no pao |
| rmu-b | RMU B | A without ippatsu, ura dora and kan dora |
| rmu-m | RMU M | A + three red tiles; 25000 points; place points 50-10 (oka included); with pao |
| mu | Mahjong Union (麻将連合) | 30000/30000; place points 12-4; no ippatsu, ura dora, kan dora or red tiles; no abortive draws; only the nearest player wins (also for three rons); no nagashi mangan or renhou; no counted yakuman; yakuman do not combine; kuikae allowed; 2 fu for a pair of the double wind; pao (daisangen, daisuushii; liability on a tsumo, split on a ron); no concealed kan after riichi; 30 fu 4 han is 7700; the game does not end when a player goes below zero; −20P |
| mleague | M.League | Three red tiles; ippatsu, ura dora and kan dora; no abortive draws; only the nearest player wins; no nagashi mangan; no tobi; no agari-yame or tenpai-yame; no counted yakuman (11 han or more is sanbaiman); yakuman combine (no double yakuman from a single yakuman); pao (daisangen, daisuushii, suukantsu); riichi allowed at 0 points or below; rounding up to mangan; place points 50/10/−10/−30 (oka included); chombo −20P |
| sports-mahjong | Sports Mahjong | Dora indicators only; place points by the number of players above (one above +8/▲1/▲2/▲5, two above +5/+3/▲3/▲5, three above +5/+2/+1/▲8; exactly the starting points counts as above); no abortive draws; the nearest player wins; yakuman do not combine; an open pinfu shape is 30 fu; a yakuman is four mangan; renhou is baiman |
| kenko | Kenko Mahjong | Ippatsu, ura dora, kan dora and kan ura (red tiles are not treated as dora); a time limit (60 minutes for team games, 50 for individual games); place points (one winner 12/△2/△4/△6, two winners 8/4/△4/△8, three winners 6/4/2/△12; 30000 points counts as a winner); no abortive draws; only the nearest player wins; a player who runs out of sticks borrows and goes on; 13 han or more is sanbaiman; no double yakuman; pao (daisangen, daisuushii); chombo is 3000 points to each of the three |
| tenhou-4p-hanchan-red | Tenhou | Riichi with 1000 points or more and a draw left; five kinds of abortive draw (the dealer continues); automatic agari-yame; extension into further winds; nagashi mangan (in place of the tenpai settlement); tobi; no rounding up to mangan; settlement rounding half_up_500 and ties in favour of the player nearer to the first dealer (verified on 1,002 public logs) |
| tenhou-4p-tonpu-red | Tenhou | The same as above with length=east (east-only); the south extension is at most 4 rounds |
| tenhou-4p-hanchan-red-exact / tenhou-4p-tonpu-red-exact | Tenhou | **Versions of the two above that do not round the settlement** (settlement.rounding none; units of 0.1 pt). The Tenhou manual: "2022/01/21 終了時の得点の1000点未満の四捨五入を廃止" (rounding of final points below 1000 was abolished on 2022-01-21). Also confirmed on two real logs of November 2026. The versions with rounding are for logs before that date |
| tenhou-3p | Tenhou three-player | 35000/40000; nuki of North (a nuki of North can be ronned); tileset mpsz-x28 |
| jantama-4p / jantama-4p-tonpu | Mahjong Soul (from a note article and Wikipedia; there is no official rule text) | Return points 25000 (no oka); uma 5-15; ties in favour of the player nearer to the first dealer; no riichi below 1000 points; play continues at 0 points; nagashi mangan = treated as a draw, mangan, no noten penalty; yakuman combine up to six times (suuankou tanki, the 13-sided kokushi, junsei chuuren and daisuushii are double); pao (daisangen, daisuushii); kokushi can ron a concealed kan; no rounding up to mangan; kan dora timing by kind of kan; double and triple ron allowed (three rons are not a draw; honba and riichi sticks go to the nearest winner); four kinds of abortive draw (nine terminals and honours, four winds, four kans, four riichi); riichi sticks left when the game ends by a draw go to the first place. Not yet compared with real logs. One west extension |
| wareme-de-pon | Wareme de Pon (TV programme) | East-only (if nobody is a confirmed first place, a return east round; the game ends when someone exceeds 30,000 points); 25000 points, return 30000; oka to the first place; no uma; dead wall of 16 and two dora indicators at all times; wareme (the points of a win are doubled; the noten penalty and honba are not); double ron is decided by nearest player; nagashi mangan; all abortive draws; the dealer continues when tenpai (and when everyone is noten); a right to agari-yame; tobi (exactly 0 points is not tobi; tobi penalty 10000); a two-han minimum from the fifth honba; open riichi |
| sakae-shibuya | Sakae Shibuya (parlour) | A-top (second place pays if below 25000); red 5p is a one-han yaku and gives a chip even in an open hand; one chip each for ippatsu and ura dora; a tobi penalty of one chip; honba 1500; cold game at 60,000 points; the game ends when a player falls below zero (no counting below zero); the dealer continues only by winning; no nine terminals, four winds or four kans draws; four riichi continues; only three rons are a draw; nagashi mangan; double ron; the dealer of the last round may stop after winning; pao is liability on a tsumo and split on a ron; ties by seat order; a yakuman is four mangan (also for 13 han or more) |
| zoo-4p | ZOO, four players (parlour) | The game ends below 0 points or at 55000 or more; 0 fu for rinshan; 2 fu for a pair of the double wind; 2 fu for a single wait on a yakuhai; abortive draws (nine terminals, four winds, triple ron, four kans); nagashi mangan; the dealer continues when tenpai; double ron (honba and the dealership by nearest player). Chips are given even for open hands (what gets how many chips is not in the source, so no rule for chips is written) |
| zoo-3p | ZOO, three players | 35000 points, return 40000; no tsumo loss (the amounts are not in the source; set to marudori, following the example of Marchao, a Tokyo parlour with the same "no tsumo loss"); no fu; tobi at exactly 0 points; agari-yame and tenpai-yame in the last round (the game ends if first); no abortive draws; the dealer continues when tenpai; double ron; 1000 points per honba; pao (daisangen, daisuushii, suukantsu); seven pairs with four of a kind; special yakuman (half flush of characters, daisharin, renhou, nagashi); counted yakuman from 14; no riichi while furiten. The four red 5p and four red 5s are not included because they need a separate tileset |
| marchao-4p | Marchao, four players (parlour) | 25000 points, return 30000; the game ends at 55000 or more; the game ends when a player goes below zero (0 points continues); no kuikae; if the dealer of the last round wins and is first the game ends, and second or third place may choose to go on; the dealer continues only by winning (the body text and the page of the Hiroshima branch; "the dealer continues when tenpai" in the list of adopted rules is a common field of the shop listing); nagashi mangan is a winning yaku; double and triple ron; no abortive draws; riichi while furiten is allowed (tsumo only) |
| marchao-3p | Marchao, three players | 35000 points, return 40000; tobi at exactly 0 points; forced end if first in the last round; the dealer continues when tenpai; no tsumo loss (marudori; the example of the Kawasaki branch: a non-dealer's haneman tsumo is 4000 and 8000); rounding up below 1000 points; 1000 points per honba; double ron (riichi sticks and honba to the nearest winner); yakuman (renhou, half flush of characters, nagashi, daisharin = full-flush seven pairs); counted yakuman from 14; pao on a yakuman is full liability; riichi while furiten is a chombo (8000 from everyone); riichi allowed with 1000 points; four flower tiles (to be expressed with a separate tileset) |
| kansai-3p | Kansai three-player, general | All 5p and 5s are red (the tileset is mpsz-x28 with eight red tiles); eight replacement tiles with the dora indicator next to them; four nuki dora (in the source the majority set aside a flower tile specific to each parlour; here the North-nuki form, which the source also describes, is used. North cannot be used in the hand except for the yakuman that need North or honours); complete sakizuke (no open tanyao, no atozuke, no win on one side only); no chi; no riichi while furiten; units of 1000 points; 1000 points per honba; no tsumo loss (marudori; a non-dealer's tsumo follows the table of the source); in the south round the dealer continues even when noten; daisharin (full-flush seven pairs), suurenkou and nagashi are yakuman; shousharin 6 han; sanrenkou and sanpuu 2 han; seven pairs with four of a kind; counted yakuman from 14 |
| toutenkou-3p | Toutenkou (three-player mahjong of the Kanto region), general form | Additive scoring (1 han = 1 point, base 2, dealer 1, honba 1, yakuman 50, karasu 20 and 10); 1m, 9m and North are set aside; the winner is the next dealer; the noten penalty is 20 points on the table (the noten players pay 20 points in total and the tenpai players receive them); no division into winds (50 points each, ends by tobi); dead wall of 18 (16 tiles for replacement + the dora indicator on the ninth stack); dora and ura dora only; draws go up to the tile next to the dora indicator (taking a replacement does not shorten the round); no win while 1m, 9m or North remains in the hand (except kokushi musou, chinroutou, tsuuiisou and the four-winds yakuman) |
| open-riichi-house | General form of a parlour that uses open riichi | open_riichi (2 han; a deal-in pays a yakuman; a player already in riichi is exempt; a player who declares riichi afterwards pays; 3 han combined with double riichi. The source says "some count 3 han, some 4") |
| pocchi-house | Three red, three gold, white pocchi and reverse pocchi (daisen) | marks: red is dora; gold is dora + two chips; pocchi is almighty (riichi, tsumo) + one chip for winning on the white pocchi (win_tile); reverse_pocchi (the winner pays points and chips); 1500 points per honba; uma 20-50 |
| nm-* | Defaults of N-tile mahjong (§7.1) | — |

### 7.1 Default rules of N-tile mahjong
With a hand of N tiles, `agari_form: standard` holds when N mod 3 = 1: (N−1)/3 sets + 1 pair.

| N | Sets | Pair | Default name | Default yaku |
|---|---|---|---|---|
| 1 | 0 | 1 | nm-2p-1-{suits} (m / mps / mpsz are bundled; other suits and lengths are made with `nmrules.ruleset_for`) | Five yaku such as chinitsu, tanyao and riichi + five yakuman (nm-defaults.md §1) |
| 4 | 1 | 1 | nm-2p-4-{suits} (as above). The other version: nm-2p-4-room | Twenty yaku that can be made with one set + six yakuman (nm-defaults.md §2). The other version is §3 |
| 7, 10, 13 | 2, 3, 4 | 1 | nm-2p-7-{suits}, nm-2p-10-{suits}, nm-2p-13-{suits} | riichi-standard without chiitoitsu and kokushi musou. Renhou is a yakuman (nm-defaults.md §2.2) |

- 1-tile and 4-tile mahjong are for two players and needed: payment (scoring.payment), replacement tiles from the live wall (rinshan "live"), an upper limit of honba (end.max_honba), the dealer continuing on a draw (renchan.draw), ending when the dealer is ahead whether tenpai or not (tenpai_yame.require_tenpai=false), and a tie (tie draw). All have been added to the ruleset
- N mod 3 ≠ 1 (2, 3, 5, …) needs `agari_form: custom:<name>`. No default is made

## 8 The ruleset generator — design
It is included in this library (so as to use vocab, the defaults and the verifier as they are). It has no UI of its own: a command and functions.

| Entrance | What it does |
|---|---|
| `nmahjong ruleset list` | Lists the default rulesets in `rulesets/` with name, id, a one-line description and the source |
| `nmahjong ruleset show <name>` | Shows the normal form (with defaults filled in) |
| `nmahjong ruleset new --from <name> [--set path=value …] [--name <new>]` | Reads a template, applies the differences, verifies, and writes `{name}_{id64}.ruleset.json`. Without `--from`, the defaults of §2 |
| `nmahjong ruleset new --interactive --from <name>` | Asks only about differences from the template (it does not ask every item). Order of questions: number of players and tiles → tileset (number of red tiles) → ippatsu, ura dora, kan dora → open tanyao and atozuke → points, return points, uma → chips → end conditions → reward |
| `nmahjong ruleset diff <a> <b>` | Lists the differences between two rulesets by item name (for showing the difference between an organisation's A and B) |
| `nmahjong ruleset validate <file>` | The verification of §5. Missing MUST items are listed by name, with exit code 1 |

- The generator **does not invent values**. An item not in the template gets the default; if there is no default either, it is left as missing
- The id of the result is computed from the normal form, so the same answers give the same id whoever makes it
- The JavaScript implementation has `validate` and `show` only (the side an application reads with). `new` is in Python only

### 8.1 State of the default rulesets
46 are bundled (`nmahjong/data/rulesets/`; they are made by tools/gen_rulesets.py). All pass verification. Items that the source does not state are listed by name in `unknown` of each file (the ruleset runs with the chosen or default value, but the value was not confirmed from the source). The content of the nm-* of N-tile mahjong is in nm-defaults.md.

## 9 How the version is raised
Additions to the vocabulary are made in version 1.1. The meaning of existing items is not changed. A verifier for 1.0 treats unknown vocabulary as an **error**.
