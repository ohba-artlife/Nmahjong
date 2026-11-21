# The game runner (nmahjong/dealer.py)

A part of layer 4 (record). It holds the walls, runs one game from beginning to end, and makes the record.
In these documents the program is called the "game runner"; its module and class are named `dealer` / `Dealer`. The player in the east seat of a round is called the "dealer".

```
Table side                                    Player side
┌──────────────────────────────┐
│ game runner (dealer)          │   situation (mjai events + request_action)
│   draws, replacement tiles,   │ ──────────────────────────→  a person or an AI
│   kan dora from the wall      │   action (an mjai response)   (a function / another program)
│   whom to ask what            │ ←──────────────────────────
│   priority of reactions, draws│        ↑ gateway (A)
│   result, next round, end,    │
│   settlement                  │
│        │ events               │
│        ▼                      │
│ recorder (checks and builds)  │
│ judge (yaku and fu)           │
│ scoring (points, settlement)  │
└──────────────────────────────┘
        │
        ▼
   record + walls (the formats of layers 4 and 3)
```

```python
from nmahjong import dealer, gateway, bots, ruleset, tileset, wall
rs = ruleset.find(name="nm-2p-4-mps"); ts = tileset.find(id=rs["tileset"]["id"])
d = dealer.Dealer(rs, ts, players={0: gateway.FunctionPlayer(bots.simple), 1: gateway.ProcessPlayer(["python3", "my_ai.py"])})
rec = d.play(lambda k, state: wall.build(ts, f"seed-{k}"))     # a function that returns the wall of round k. A list of walls also works
d.walls        # the walls used {id: wall}
d.log          # the reason for the end
```

**Where the ruleset says "may choose", and the clock** (neither needs to be passed)

| Argument | When it is asked | When it is not passed |
|---|---|---|
| `choose(kind, seat, scores) -> bool` (`opt.choose` in JavaScript) | kind = `agari_yame` / `tenpai_yame`: a dealer in first place who would continue in the last round is asked whether to stop (rules with forced=false). `agari_yame_not_top`: a dealer in second or third place is asked whether to stop (rules with others_may_continue). True stops | A dealer in first place stops. A dealer in second or third place goes on |
| `clock() -> seconds` (`opt.clock` in JavaScript) | Under a rule with a time limit (end.time_limit_sec), each time a round ends | The real clock (time elapsed since the start) |

Command: `python3 -m nmahjong play RULESET [--seed S] [--bot simple|tsumogiri] [--player SEAT=COMMAND] [--out DIR] [--loose] [--allow-unsupported]`

## 1. What the game runner decides (all of it follows the settings of the ruleset)

| What | Setting |
|---|---|
| The deal, draws, replacement tiles, dora indicators, and when a kan dora is turned | wall_rules, dora.kan, dora.kan_timing (immediate / after_discard / after_rinshan) |
| Whom to ask what: declarations after a draw (A) → the discard (B) → the reactions of the other players (C). A seat that can only pass is not asked | The legal actions (observe.legal_actions). A win only when there is a yaku (and the minimum-han requirement is met) |
| Priority of reactions: ron > pon and open kan > chi. Several rons | flow.double_ron, flow.triple_ron (head / draw / allow) |
| Chankan (a ron on the tile of an added kan or of a nuki; a ron on the tile of a concealed kan only for kokushi musou where the rule allows it). The recorder also checks it against the legal actions | flow.kokushi_ankan_chankan, nuki.chan_nuki |
| Furiten: one's own discards / a tile passed in the same turn / a tile passed after riichi | — |
| The riichi stick: one stick when the declaration tile passes. When the declaration tile is ronned | flow.riichi.stick_if_ronned (false = not put out; true = put out and taken by the winner: the variants whose name ends in -ronstick; nm-defaults.md §2.1) |
| Draws: exhaustive draw, nine terminals and honours, four winds, four riichi, four kans, three rons | flow.ryukyoku |
| The points of a win: yaku and fu (judge) → score table → payments. The payments of a three-player tsumo; units of 1000 points | scoring.*, scoring.payment, scoring.tsumo_loss, scoring.round_to, scoring.honba_points, scoring.kyotaku_points |
| Additive scoring: han are added as points as they are; for a ron the player who dealt in, for a tsumo every other player, pays the same points. Honba is inside the formula. Karasu points | scoring.table = additive, scoring.additive.* |
| The winner is the next dealer. A game with no division into winds | flow.next_dealer, length = endless |
| Honba and riichi sticks when several players win: to the nearest winner / each winner and equal division | flow.kyotaku_to |
| Pao (daisangen, daisuushii, suukantsu) | pao.yakuman, pao.ron (split / full), pao.honba_kyotaku |
| Wareme: the wareme seat is decided from the dice (5, 9 = the dealer; 2, 6, 10 = the next player; 3, 7, 11 = the player opposite; 4, 8, 12 = the previous player); when that seat wins, everyone's payment is doubled, and that seat's own payments are doubled. Honba, riichi sticks, the noten penalty and the tobi penalty are not doubled | flow.wareme, wall_rules.break |
| A yakuman payment for dealing in to an open riichi (a player already in riichi is exempt / a player who declared afterwards pays) | flow.open_riichi (deal_in, exempt_prior_riichi, chaser_pays) |
| The noten penalty; nagashi mangan (treated as a draw / as a win / as a yakuman) | scoring.noten_penalty, nagashi_mangan (as, noten_penalty, renchan_if_dealer_tenpai) |
| The tobi penalty (to the winner who put the player out; to a tenpai player when the player went out by the noten penalty) | end.tobi (penalty_points, penalty_to, on_noten_penalty) |
| The next round: whether the dealer continues, honba, carrying over riichi sticks | flow.renchan (dealer_win, dealer_tenpai, all_noten, draw, by_bakaze), flow.renchan_on_abort |
| The end of the game: the prescribed number of rounds, tobi, extension (a west round and so on), agari-yame and tenpai-yame, cold game, the upper limit of honba, the time limit | length, end.tobi, end.extension, end.agari_yame, end.tenpai_yame, end.cold_points, end.max_honba, end.time_limit_sec |
| The final: remaining riichi sticks, places, settlement | flow.riichi.stick_at_end, settlement |

## 2. What was checked

**Running existing games again**: only the walls of the record and the decisions as recorded (the action each seat actually took) were passed in; the draws, the priority of reactions, draws, the result of each round, the next round, the end and the settlement were left to the game runner, and the outcome was compared with the original game (`dealer.replay_with_dealer`, `dealer.differences`).

| Compared with | Games | Result |
|---|---|---|
| Real Tenhou games (four-player east-only and east-south, three-player; public data at hand) | 1,005 | All the same (events, wins, draws, scores, next round, how the game ended, the final) |
| 4-tile N-tile mahjong (games played by the game engine of a separate implementation) | 8,254 | All the same |
| 1-tile N-tile mahjong (as above) | 3,000 | All the same |
| N-tile mahjong played by people | 18 | All the same (two more games, played by a substitute, start in the middle and are outside the scope) |

Not looked at when comparing: the order of the tiles of the winning hand, of the melds and of the yaku; the fu of a yakuman; Tenhou's breakdown of dora (it writes nuki dora inside "dora"). Marks of disconnection and reconnection were put in at their recorded positions as they were.

**The same when decisions are requested through the gateway**: when the list of legal actions is made and each response is confirmed to be in it while running again, the 1,005 Tenhou games and 1,518 games of N-tile mahjong are all the same (one Tenhou game became the same after this check led to fixing a misreading of the response for a ron on a North set aside). The legal actions include furiten in the same turn, furiten after riichi and whether a yaku exists, and every win in the real games was among them.

**One game connected to players**: bundled simple players played each other, two games for each of the 46 bundled rulesets (`python3 tools/selfplay_all.py`). All 92 games of the 46 rulesets run to the end and the resulting records pass verification (1, 4, 7, 10 and 13 tiles; four players; three players). With players that only discard the drawn tile, kansai-3p does not end (in the south round the dealer always continues on a draw and there is no tobi, so nobody wins; it is cut off at 1,000 rounds). The same game results with a player that is another program.

**What this check decided or fixed**
- One item was added to the ruleset: `flow.riichi.stick_if_ronned` (the riichi stick when the declaration tile is ronned). The separate implementation of N-tile mahjong put the stick out at the moment of declaration (the winner takes it). Tenhou does not. **The ids of all bundled rulesets changed**
- Decided on 2026-11-17 (ohba-artlife): in the rules of N-tile mahjong too, "if the declaration tile does not pass, the riichi does not stand and no stick is put out". The bundled nm-* are false. Games played under the earlier treatment that contain a round in which the declaration tile was ronned are written as they happened, with the ruleset made `-ronstick` (true)
- The rules of N-tile mahjong (1, 4, 7, 10, 13 tiles): it was stated explicitly that the game ends if the dealer wins in the last round and is first (`end.agari_yame`)
- Bundled ruleset tenhou-3p: a west round if 40000 is not reached in South 3; agari-yame and tenpai-yame if the dealer is first (how 278 real games ended). It ends in West 3 (one case)
- Legal actions: furiten in the same turn and after riichi was not looked at → it is now

## 3. How situations that do not occur in real games were checked

Situations that never appear in the real games (1,005 Tenhou games) were checked by letting the game runner run rounds with a chosen wall and a chosen sequence of actions, and comparing with the result computed from the rule text published by Tenhou (rules/tenhou-rules.md, tests/test_tenhou_rules.py).
Payments under pao (tsumo, ron, combined yakuman, honba); the draws by four riichi, four kans, three rons, four winds, and nine terminals and honours; nagashi mangan by two players at once; how an extension ends (the dealer continuing takes precedence; up to the west round); honba and riichi sticks on a double ron; chankan and ippatsu; the detailed rules of furiten; the rules of nuki in three-player mahjong.

Ways of paying and ending that a ruleset can choose were checked in the same way (O1–O59 in tests/test_rule_options.py; for the JavaScript version, the same rounds are run with the same decisions and the same results are confirmed: js/test_game.js T14-11).
The payments of a three-player tsumo (tsumo loss, adding 1000, marudori, splitting the north player's part) were compared cell by cell with a published score table; equal division of riichi sticks among several winners; the tobi penalty (by a win, by a tsumo, by dealing in to two players, by the noten penalty); the treatments of nagashi mangan (draw, win, yakuman, with the noten penalty, the dealer passing); the choice of agari-yame and tenpai-yame; the time limit; wareme (the dice and the seat; doubling on ron and tsumo; honba and riichi sticks not doubled); dealing in to an open riichi (yakuman payment, a player already in riichi, a player who declared afterwards, tsumo).
For additive scoring (Toutenkou), a published worked example was run on a constructed wall and gave the same points (dealer, 2 honba, riichi, ittsu, pinfu, one red tile, two dora, three nuki dora: tsumo 16 points from each, ron 15 points). The formula also agrees with the examples of two other sources (36 points in total; ×4 and rounded up to units of 10, 40 points). Karasu (concealed, open, and when a tile was set aside), yakuman, a non-dealer's win not counting honba, the winner becoming the next dealer (how honba increases), and the bundled Toutenkou running until it ends by tobi.
Chips and the white and reverse pocchi were checked on constructed rounds: five chips for red tiles, ippatsu and ura dora (from the player who dealt in on a ron, from the three on a tsumo); red 5p in an open hand (yaku and chip); chips for tobi; drawing the white pocchi after riichi and winning with the higher value (two gold tiles + one white pocchi); with the reverse pocchi the winner pays points and chips; a white pocchi held in the hand is an ordinary white dragon.
Kansai three-player was checked against the text and the table of the source: complete sakizuke (if there is a wait without a yaku, a ron is not possible even on a tile with a yaku; possible if that tile is the only wait; possible after riichi; a concealed tsumo is possible); shousharin 6 han; daisharin as full-flush seven pairs; the table of payments for a non-dealer's tsumo (mangan 5000-3000 up to yakuman 20000-12000; the dealer's tsumo is half the ron each); the ura dora indicator being the white pocchi.

How tenpai is counted: when the only waiting tiles are tiles of which the player's own hand (melds excluded) already uses all four, the hand is not counted as tenpai (`observe.tenpai_waits`; used for tenpai at a draw and for the conditions of riichi).

Things not decided by the text and set as conventions: agari-yame for a first place with exactly 30000 points (stops); the moment of a four-kans draw (when the discard after the fourth kan passes).

## 4. Settings it cannot follow yet

`dealer.unsupported(rs)` returns the list. A ruleset that has any of them is not started unless `allow_unsupported=True` is given (`--allow-unsupported` for the command). With it, the game is run with the substitute treatment written below.

| Setting | Substitute treatment | Bundled rulesets affected |
|---|---|---|
| flow.wareme used with other than four players | The sum of the dice is counted from the dealer over the seats that exist (the only source for deciding the player at the break is for four players) | none |
| on in settlement.chips is kan, nuki, call or yakitori | That rule is not counted (only chips for wins and tobi are counted) | none |
| flow.atozuke = forbidden (sakizuke) | Run as if atozuke were allowed (there is no source for how "a win on one side is allowed" is decided) | none |
| nuki.forbid_keep = true | Run as if a nuki tile may be kept in the hand (there is no behaviour that stops it) | none |
| nuki.pao = true | Liability for nuki dora is not counted | none |

None of the 46 bundled rulesets has a setting that cannot be followed.

Also: chombo (penalties) does not occur, because the game runner accepts only legal actions. Chips (settlement.chips) are counted for every win and put into chips of the result (tiles of the winning hand, the kind of win, tobi; from the player who dealt in on a ron, from everyone on a tsumo). In a win with the reverse pocchi (the mark effect reverse), the winner pays both points and chips. A tile such as the white pocchi, which "can be used as anything when drawn after riichi", lets the player choose a tsumo win when it is drawn. A game played by a substitute (a game with parent that starts in the middle) cannot be run.

## 5. Bundled players (nmahjong/bots.py)

| Name | How it plays |
|---|---|
| tsumogiri | Does nothing: discards the drawn tile, passes |
| simple | Wins if it can, declares riichi if it can, discards isolated tiles first. Does not call |

As a separate program: `python3 -m nmahjong.bots simple` (one JSON per line on standard input; it answers a request_action with one line). It serves as a template for a player of your own.
