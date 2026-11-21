# Comparison with the rules of Tenhou (the bundled tenhou-*)

A table in which the rule text published by Tenhou (the manual at https://tenhou.net/man/: "段位戦 4人打ち" (ranked games, four players), "3人打ち" (three players), "役一覧" (list of yaku), and the question "どういう場合にゲームが終了になりますか？" (when does a game end?); retrieved on 2026-11-18) is taken item by item and compared with the values of the bundled rulesets `tenhou-4p-hanchan-red`, `tenhou-4p-tonpu-red` and `tenhou-3p` (and the two `-exact` rulesets that do not round the settlement), and with the behaviour of the game runner and the judgement.

The sentences in the column "Tenhou's text" are our English translations. The original Japanese sentences are quoted in the Japanese version of this document.

The column "How it was checked":
- **Real games**: on 1,005 Tenhou games (a collection of 1,002 public logs and 3 others), the results of the library agreed with Tenhou's results (conformance.md §5). Items whose situation appears in the real games
- **Constructed round**: a situation that does not appear in the real games. The game runner ran a round with a chosen wall and a chosen sequence of actions, and the outcome was compared with the result computed from Tenhou's text (tests/test_tenhou_rules.py; the parts for constructing a wall are in tests/scripted.py). The JavaScript version also runs the same games again (js/test_game.js)
- **Value**: it was confirmed that the value in the ruleset file is as the text says

The name Tenhou belongs to its owner. This document is a comparison made by us from reading the published text; it has not been confirmed by Tenhou.

## 1. Ranked games, four players

| # | Tenhou's text | Item of the ruleset | How it was checked |
|---|---|---|---|
| 1 | Start with 25000 points, return 30000 | settlement.start_points 25000, return_points 30000, oka to_first | Real games (final results) |
| 2 | Uma 10-20 | settlement.uma [20, 10, −10, −20] | Real games |
| 3 | Atozuke allowed | flow.atozuke allowed | Real games |
| 4 | No kuikae | flow.kuikae forbidden | Real games (the 16,913 actual chi and pon remain among the legal actions), tests/test_annotation.py T7-11 |
| 5 | Open tanyao: off / on, selectable | flow.open_tanyao (the bundled rulesets are the "on" tables) | Real games |
| 6 | Number of red tiles under the rule with red tiles: one of each | Tileset `mpsz` (the mark red on one tile each of 5m, 5p, 5s) | Real games |
| 7 | The dealer passes when noten and continues when tenpai | flow.renchan {dealer_win, dealer_tenpai} | Real games (the next round) |
| 8 | An east-only game may enter the south wind and an east-south game the west wind; after that it ends by the sudden-death rule | end.extension {enabled, until_points 30000} | Real games (games that enter the west wind and games that do not), constructed round TR08 |
| 9 | Under the sudden-death rule the game ends when someone reaches 30000 points or more (not counting riichi sticks on the table); however, if the dealer continues, continuing takes precedence | end.extension.renchan_first true | TR08 (it goes on when the dealer continues and is not first) |
| 10 | Sudden death lasts at most to the south wind for an east-only game and to the west wind for an east-south game | end.extension {max_rounds 4, once true} | TR08 |
| 11 | The game ends by tobi. It ends when points are negative; negative points are counted; 0 points continues | end.tobi {at 0, exact_zero_is_tobi false} | Real games, TR11 |
| 12 | Automatic agari-yame and automatic tenpai-yame for a last dealer in first place | end.agari_yame and tenpai_yame {enabled, forced} | Real games, TR12 |
| 13 | Riichi sticks at the end go to the first place | flow.riichi.stick_at_end to_first | Real games (final points) |
| 14 | When points are equal at the end, the places are decided by the order of winds in East 1 | settlement.tie seat_order | Real games |
| 15 | A pair of the double wind is 4 fu | scoring.fu.double_wind_pair 4 | Real games (fu) |
| 16 | 2 fu are also added for a rinshan tsumo | scoring.fu.rinshan_tsumo_fu 2 | Real games |
| 17 | No two-han minimum / always a one-han minimum | scoring.shibari.from_honba null | Real games |
| 18 | Abortive draws (nine terminals and honours / four riichi / three rons / four kans / four winds) are used. The dealer continues in all of them | The five items of flow.ryukyoku, triple_ron draw, renchan_on_abort true | Constructed round TR18 (all five kinds; the dealer stays, 1 honba, riichi sticks stay on the table) |
| 19 | Nine terminals and honours: nine or more kinds of terminals and honours at a first draw with no pon / kan / chi / concealed kan | (a condition of the legal actions) | TR18 (it cannot be declared after a pon) |
| 20 | Nagashi mangan is used. A mangan settlement replaces the tenpai settlement. The dealer continues when tenpai | nagashi_mangan {enabled, as tenpai_settlement, renchan_if_dealer_tenpai} | TR20 (two players at once; the dealer passes when noten and continues when tenpai) |
| 21 | Nagashi mangan stands when none of the player's discards has been called. It stands even if the player has called | (a condition of the game runner) | TR21 |
| 22 | Double ron is allowed. Honba and riichi sticks go to the nearest winner | flow.double_ron true, kyotaku_to kamicha | TR22 |
| 23 | On a double ron the dealer continues if the dealer is among the winners | flow.renchan.dealer_win | TR22 |
| 24 | Pao for daisangen / daisuushii. The points, including combined yakuman, are paid in full on a tsumo and split on a ron. Honba is paid by the liable player | pao {yakuman [daisangen, daisuushii], tsumo full, ron split_all, honba_kyotaku liable} | TR24 (tsumo, ron, combined yakuman, honba) |
| 25 | No pao for suukantsu | suukantsu is not in pao.yakuman | TR25 (value) |
| 26 | Tenpai in shape counts. A tenpai waiting for a fifth tile counts (it stands unless the concealed part of the hand, taking hand = concealed hand + melds, uses all four) | (how tenpai is counted; observe.tenpai_waits) | TR26 |
| 27 | Riichi can be declared with 1000 points or more and a draw remaining | flow.riichi {min_points 1000, below_min forbidden, without_draw false} | Real games, TR27 |
| 28 | When the riichi declaration tile deals in, no riichi stick is paid | flow.riichi.stick_if_ronned false | Real games, TR28 |
| 29 | Riichi while furiten is allowed | flow.riichi.furiten_riichi true | TR29 |
| 30 | Passing a winning tile after riichi makes the player furiten from then on | (a condition of the legal actions) | TR30 |
| 31 | After riichi, a tile that gives a winning shape not meeting the minimum is always passed, and the player is furiten from then on (under a minimum of two han or more) | — | Does not apply: the bundled tables have a one-han minimum |
| 32 | A concealed kan after riichi only when the waits do not change. A kan that changes which tiles are used is not allowed; changes in the shape of the hand or in yaku do not matter | flow.riichi.ankan_after if_shape_unchanged | Real games (the actual concealed kans remain among the legal actions) |
| 33 | Kan dora and kan ura are used | dora {kan, kan_ura} | Real games |
| 34 | A kan dora is turned at once for a concealed kan, and later for an open or added kan (right before the discard or the following replacement draw) | dora.kan_timing {ankan immediate, minkan and kakan after_discard} | Real games (the moment the dora is turned) |
| 35 | Ippatsu is cancelled after the call and the offer to win (added kan only), before the replacement draw (ippatsu does not apply to the second of consecutive added kans) | (judgement) | Constructed round TR35 (riichi → an added kan is robbed: riichi, ippatsu and chankan apply) |
| 36 | No selective ron within the same turn (the tile of an added kan included) | (a condition of the legal actions) | TR36 |
| 37 | Furiten of the same turn is cleared at the player's discard; it is not cleared by a call that reverses the turn order | (a condition of the legal actions) | TR36, TR37 |
| 38 | The last tile cannot be called | (a condition of the legal actions) | TR38 |
| 39 | No paarenchan / renhou / sanrenkou / isshoku sanjun / shiisan puutaa / … | yaku.overrides (no local yaku are added) | TR39 (value), real games (the yaku of every win agree) |
| 40 | "The player who caught up has the advantage" is not used | — | Does not concern how a game is run |
| 41 | Furiten is judged only by tiles discarded to the river (excluding tiles exposed by an added kan or a nuki, which are not part of the concealed hand) | (a condition of the legal actions) | Constructed round TS07 (three-player: a North the player set aside does not make them furiten) |
| 42 | After giving up a win (chankan included) the player is furiten for the same turn and cannot ron until their next draw | (a condition of the legal actions) | TR36 |

## 2. Ranked games, three players (differences from four players)

| # | Tenhou's text | Item of the ruleset | How it was checked |
|---|---|---|---|
| 1 | Start with 35000, return 40000 | settlement {start_points 35000, return_points 40000}, end.extension.until_points 40000 | Real games (278 three-player games) |
| 2 | Place uma +20, 0, −20 (the same for east-only and east-south) | settlement.uma [20, 0, −20] | Real games |
| 3 | There are 8 replacement tiles | wall_rules.rinshan (8 entries) | Real games (the positions of the replacement tiles) |
| 4 | 2m to 8m are not used | Tileset `mpsz-x28` (108 tiles) | Real games (reproduction of the wall) |
| 5 | The dora for the indicator 1m is 9m, and for 9m it is 1m | (the tile after the indicator goes round among the tiles in the tileset) | Real games (the number of dora) |
| 6 | Chi is not possible | flow.chi false | Value, real games |
| 7 | North is a nuki dora | nuki {enabled, tiles [N], value 1} | Real games (the 6,531 actual nuki remain among the legal actions) |
| 8 | A nuki is not possible right after a pon | (a condition of the legal actions) | Constructed round TS08 |
| 9 | A nuki is treated like a call (ippatsu / chiihou / nine terminals / double riichi are cancelled) | (legal actions and judgement) | Real games (ippatsu), constructed round TS09 (nine terminals, double riichi) |
| 10 | A North set aside can be won on, not only by a yakuman | (legal actions: a North set aside by another player can be ronned; not limited to yakuman) | Real games (6 rons on the tile of a nuki) |
| 11 | When North is used in a set it is a guest wind | nuki.as_yakuhai none, nuki.win_with_nuki_in_hand true (a hand can win while using North in the hand) | Real games |
| 12 | Ippatsu is cancelled after the call and the offer to win (added kan / nuki), before the replacement draw | (judgement) | Real games (6 rons on the tile of a nuki) |

## 3. Notes in the list of yaku

| Tenhou's text | Item of the ruleset | How it was checked |
|---|---|---|
| Yakuman combine; suuankou tanki, the 13-sided kokushi and the like are all single yakuman | scoring.limits.max_multiple 6 (meaning no limit). There is no setting that doubles a single-tile wait, a 13-sided wait and the like | Constructed round TR24 (daisangen + tsuuiisou = 64000) |
| A counted yakuman is 13 han or more | scoring.limits.kazoe_from 13 | Value |
| Kokushi musou cannot win on a tile another player used for a concealed kan | flow.kokushi_ankan_chankan false | tests/test_dealer.py D7 |
| Ippatsu and chankan (the first of consecutive kans) combine | (judgement) | TR35 |
| Tenhou / chiihou is a win on the first draw with no pon / kan / chi / concealed kan before it | (judgement) | tests/test_judge.py |

## 4. What this comparison fixed (2026-11-18)

These were situations that never appear in the 1,005 real games, so the comparison with real games had not found them.

| What was fixed | Tenhou's text |
|---|---|
| An east-south game went on to the north wind when it was not decided in the west wind → up to the west wind | #10 |
| After an extension had started, the game ended when someone had 30000 or more even though the dealer continued → the dealer continues unless first | #9 |
| On a ron under pao, the player who dealt in was made to pay the honba part → the liable player | #24 "honba is paid by the liable player" |
| On a ron under pao, only the part of the yakuman under pao in a combined yakuman was split → everything is split (`split_all` was added to `pao.ron`) | #24 |
| Yakuman did not combine (daisangen + tsuuiisou was 32000) → they combine | Notes in the list of yaku |
| Suukantsu was among the pao of three-player games → daisangen and daisuushii only | #25 |
| In three-player games, nine terminals could be declared at the first draw even after another player had set aside a North → it cannot | Three players #9 |
| A shape waiting only for tiles of which the player's own hand uses all four was counted as tenpai → not counted | #26 |
| A three-ron draw could not be run again from the record (who had declared ron was not read from the record) → it can | #18 |

## 5. What Tenhou's text did not decide

- A supplementary note says "agari-yame if the dealer is first with the starting-return points or more", and the Q&A says "becomes first above the starting-return points". The treatment of a first place with exactly 30000 points can be read in two ways. The library stops at "30000 points or more"
- The moment of the four-kans draw (right after the fourth kan, or after its discard has passed) is not in the text. The library uses "after the discard has passed"
