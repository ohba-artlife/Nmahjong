# Default rules of N-tile mahjong (the bundled nm-*)

N-tile mahjong is mahjong played by two players with a hand of N tiles (1, 4, 7, 10 or 13). This library bundles its default rules under the names `nm-2p-{N}-{suits}`.
This document describes the content of those default rules and how they are written in a ruleset (ruleset.md). The rules were set by ohba-artlife. Every item can be changed in a ruleset.

- Where the definition is: `nmahjong/nmrules.py` (`GAME_1`, `GAME_4`, `WALL_1`, `WALL_4`, `ruleset_for(n, suits, length)`). The bundled files are made from it (tools/gen_rulesets.py).
- How it was checked: for 1 and 4 tiles, games played by a game engine made separately from this library are placed in the Nmahjong format in `tests/data/corpus/nm-engine.jsonl`, and tests confirm that yaku, fu, scores, flow and settlement agree with the results of the library (tests/test_corpus.py and others). During development the same comparison was done on 11,254 games, and all agreed.

## 1 1-tile mahjong (nm-2p-1-*)

| Division | Rule | How it is written in the ruleset |
|---|---|---|
| Players and tiles | Two players, a hand of 1 tile, a win = two tiles that are the same | players 2, hand_size 1, agari_form standard (0 sets + a pair) |
| Tiles | Choose the suits to use from characters, dots, bamboo and honours. Four of each. No red tiles | The tileset is the name of the chosen suits (`m`, `mp`, `mpsz`, …). A separate ruleset for each choice (the tileset differs, so the id differs too) |
| Length of the game | A single round / east-only (East 1, East 2) / east-south (East 1, East 2, South 1, South 2) | length one / east / east_south (with two players the east wind = 2 rounds). The name is `nm-2p-1-{suits}` for east-south, `-east` for east-only, `-one` for a single round |
| Dealing | Two tiles to the dealer, one to the non-dealer (N each + 1 to the dealer) | deal N_each_then_1_to_dealer |
| Dead wall | 4 tiles: 1 dora indicator, 1 ura dora indicator, 2 unused. The dora = the tile after the indicator (9→1, North→East, red dragon→white dragon) | dead_wall 4, dora_indicator [0], ura_indicator [1]. No kan |
| Riichi | A 1000-point stick; allowed with 1000 points or more. After declaring, the drawn tile is discarded. Ippatsu lasts until the player's next draw. If the declaration tile is ronned, the riichi does not stand and no stick is put out | riichi {min_points 1000, below_min forbidden, stick_if_ronned false}, ippatsu |
| Condition for a win | A win without a yaku does not occur (if the two tiles are the same, chinitsu or tsuuiisou always applies) | — |
| Yakuman | Tenhou, chiihou, renhou (a ron on the dealer's first discard), tsuuiisou (honours), chinroutou (1 or 9). They multiply when combined (a double yakuman) | yaku.overrides: tenhou / chiihou / renhou / tsuuiisou / chinroutou = "yakuman". limits.max_multiple 2 |
| Ordinary yaku | Chinitsu 6, tanyao 1, riichi 1, ippatsu 1, menzen tsumo 1, dora, ura dora (with riichi) | overrides: chinitsu 6, tanyao 1, riichi 1, ippatsu 1, menzen_tsumo 1. Other yaku are false |
| Fu | Not counted | scoring.fu.enabled false |
| Scores | Decided by han. Haneman (up to 7 han; **haneman even below 6 han**) / baiman 8 / sanbaiman 11 / counted yakuman 13. Dealer 18000 / 24000 / 36000 / 48000; non-dealer 12000 / 16000 / 24000 / 32000. A yakuman is a multiple of 48000 for the dealer and 32000 for the non-dealer | scoring.table `custom:nm1-limits` (a table whose minimum is haneman; bundled) |
| Payment | Ron = the whole amount. Tsumo = the single opponent pays half of the total that non-dealers pay in four-player mahjong (a haneman tsumo → 6000) | scoring.payment `4p_child_half_from_opponent` |
| Honba and riichi sticks | The loser pays 300 per honba. Riichi sticks go to the winner. Sticks left at the end of the game go to the first place | honba_points 300, kyotaku_points 1000, stick_at_end to_first |
| Draw | A draw when the wall runs out. No penalty. The dealer continues (honba +1) | noten_penalty 0, renchan {dealer_win, dealer_tenpai, draw} |
| Dealer continuing | The dealer's win or a draw → honba +1. The non-dealer's win → the next round | Same as above |
| Furiten | A player cannot ron a tile they have discarded | Standard |
| Tobi | The game ends when points are below 0 (exactly 0 continues) | end.tobi {enabled, at 0, exact_zero_is_tobi false} |
| Last round | The non-dealer wins → the game ends. The dealer is ahead on points → the game ends (whether by a win or a draw). The dealer is behind → the game goes on | end.agari_yame {enabled, when last_round, forced}, end.tenpai_yame {enabled, forced, require_tenpai false} |
| Upper limit of honba | The game ends at 50 honba | end.max_honba 50 |
| Settlement | 25000 points, return 30000; the oka of 10000 to the first place; in a tie the first dealer is higher | start 25000, return 30000, oka to_first, tie seat_order, uma [0, 0] |

## 2 4-tile mahjong (nm-2p-4-*)

| Division | Rule | How it is written in the ruleset |
|---|---|---|
| Players and tiles | Two players, a hand of 4 tiles, a win = one set + a pair (after a concealed kan, the kan + a pair) | players 2, hand_size 4, agari_form standard |
| Tiles | Choose the suits to use from characters, dots, bamboo and honours. Four of each. No red tiles | The tileset is the name of the chosen suits (`m`, `mp`, `mpsz`, …). marks {} |
| Length of the game | A single round / east-only / east-south | length one / east / east_south. The name is `nm-2p-4-{suits}` for east-south, `-east` for east-only, `-one` for a single round |
| Winds | Dealer = East, non-dealer = West. The round wind is East in the east wind and South in the south wind | winds ["E", "W"] |
| Dealing and dead wall | Five tiles to the dealer, four to the non-dealer. Dead wall of 4: 1 dora indicator, 1 ura dora indicator, 2 replacement tiles | deal N_each_then_1_to_dealer, dead_wall 4, dora_indicator [0], ura_indicator [1] |
| Concealed kan | The only kan is a concealed kan. Once per player (at most twice in a round); not possible when the wall has 0 tiles. No kan dora. When a replacement tile is taken, one tile from the end of the live wall is moved to the dead wall (the second replacement tile is the original last live tile, which entered the dead wall at the first kan) | max_kans 2, max_kans_per_player 1, kan_kinds ["ankan"], dora.kan false, rinshan [3, -1] (a negative value is on the side of the end of the live wall) |
| Pon and chi | None | flow.pon false, flow.chi false |
| Riichi | A 1000-point stick. Conditions: a discard that makes the hand tenpai, 1000 points or more, and at least one tile in the wall. Allowed while furiten. After declaring, the drawn tile is discarded. On the first discard (before any kan) it is a double riichi. Ippatsu lasts until the player's next draw (and is cancelled by a kan). If the declaration tile is ronned, the riichi does not stand and no stick is put out | riichi {min_points 1000, below_min forbidden, without_draw true, on_houtei false, furiten_riichi true, stick_if_ronned false} |
| Concealed kan after riichi | Only when the tile just drawn makes four and the kan does not change the waits | ankan_after if_shape_unchanged |
| Yaku | Riichi 1, double riichi 2, ippatsu 1, menzen tsumo 1, rinshan kaihou 1, haitei 1, houtei 1, tanyao 1, pinfu 1 (a sequence + a two-sided wait + a pair that is not a yakuhai), yakuhai (white, green, red dragon, round wind, seat wind; 1 each), toitoi 2 (a triplet or a kan), chanta 2, junchan 3, honroutou 2, honitsu 3, chinitsu 6 | yaku.base none + listed in overrides (20 yaku) |
| Yakuman | Tenhou, chiihou, renhou (a ron on the dealer's first discard), tsuuiisou, chinroutou, ryuuiisou. They multiply when combined. With a yakuman, dora and other yaku are not counted | overrides = "yakuman" (6), limits.max_multiple 2 |
| Dora | 1 dora, 1 ura dora (with riichi). The tile after the indicator (9→1, North→East, red dragon→white dragon). All four tiles of a kan are counted | dora {indicator, ura}. No kan |
| No yaku | Without a yaku (other than dora) a ron is not possible. A tsumo win stands on the shape alone, and menzen tsumo applies | Standard |
| Fu | Pinfu tsumo 20 / pinfu ron 30. Otherwise 20 + tsumo 2 / ron 10 + triplet (concealed 4 / 8; a triplet completed by ron is open, 2 / 4) + concealed kan 16 / 32 + a yakuhai pair 2 × (the number of: dragon, round wind, seat wind; the double wind is 4) + single, closed or edge wait 2. Rounded up to units of 10 fu | fu {enabled, double_wind_pair 4, rinshan_tsumo_fu 2, menzen_tsumo_pinfu true, open_pinfu_fu 30} |
| Scores | Basic points = fu × 2^(han+2). Mangan at basic points of 2000 or more, or 5 han (no rounding up to mangan); 6–7 haneman; 8–10 baiman; 11–12 sanbaiman; 13 or more counted yakuman. A yakuman is 8000 × the number | table standard, mangan_round_up false, limits {sanbaiman_from 11, kazoe_from 13, yakuman_base 4} |
| Payment | Ron = basic points × 6 (dealer) / × 4 (non-dealer), rounded up to 100. Tsumo = basic points × 2 rounded up to 100 (the same for dealer and non-dealer; the share the dealer pays in four-player mahjong), paid by the single opponent | scoring.payment `4p_dealer_share_from_opponent` |
| Honba and riichi sticks | The loser pays 300 per honba (300 for a tsumo too). Riichi sticks go to the winner; they carry over on a draw. Sticks left at the end of the game go to the first place (the first dealer in a tie) | honba_points 300, kyotaku_points 1000, stick_at_end to_first |
| Draw | A draw when a player's turn to draw comes with 0 tiles in the wall. No penalty. The dealer continues (honba +1) | noten_penalty 0, renchan.draw true |
| Furiten | A ron is not possible if the player has discarded any of the kinds of tile they are waiting for (judged over all the waits) | Standard |
| Tobi, last round, upper limit of honba, settlement | The same as 1-tile mahjong (§1): the game ends when points are below 0 / the last round ends with the non-dealer's win or with the dealer ahead / the game ends at 50 honba / 25000 points, return 30000, the oka of 10000 to the first place, the first dealer higher in a tie | The same as §1 |

## 2.1 Decisions and their reasons (ohba-artlife)

| # | Decision | Reason and notes | Date |
|---|---|---|---|
| 1 | The payment for a tsumo is "half of the total that non-dealers pay" for 1 tile, and "basic points × 2 (rounded up)" for 4 tiles or more | So that a game does not end at once, the amount is the same as one player pays in four-player mahjong (the opponent in a two-player game is always "the dealer" or "a non-dealer against whom the dealer drew", and both pay basic points × 2). At mangan and above the two methods give the same amount; below mangan they differ (20 fu 2 han: 650 and 700). With 1 tile the minimum is haneman, so no difference arises | 2026-11-16 |
| 2 | Riichi sticks left on the table at the end of the game go to the first place (the first dealer in a tie) | Otherwise the sum of the two players' points would not equal the sum of the points dealt out | 2026-11-16 |
| 3 | The only call is a concealed kan (no pon, chi, open kan or added kan). A concealed kan once per player | With 4 tiles only one set is made | 2026-11-16 |
| 4 | If the riichi declaration tile is ronned, the riichi does not stand and no riichi stick is put out | To treat it the same as in ordinary riichi mahjong | 2026-11-17 |
| 5 | If the dealer wins in the last round and is first, the game ends (the same as when the dealer is first at a draw) | — | 2026-11-17 |

**Variants (not bundled)**: so that games played under the treatment before decisions 2 and 4 can be written as they happened, there are rulesets whose names end in `-stays` (riichi sticks left at the end of the game stay on the table; stick_at_end stays) and `-ronstick` (the riichi stick is put out even when the declaration tile is ronned; stick_if_ronned true). Part of the collection of test games (tests/data/corpus/nm-engine.jsonl) uses them. Their content differs from the bundled rulesets in that one item only.

## 2.2 7-tile, 10-tile and 13-tile mahjong — an extension of 4-tile mahjong (defaults; ohba-artlife, 2026-11-16)

As **defaults**, 4-tile mahjong is simply extended. Every item can be changed in a ruleset (`ruleset new --from nm-2p-7-mps --set item=value`, or the ruleset page).

| Item | Default (the same as 4 tiles) | Items to change it |
|---|---|---|
| Players and hand | Two players; 7 / 10 / 13 tiles (2 / 3 / 4 sets + a pair) | players, hand_size |
| Dead wall | 4 tiles (dora indicator, ura dora indicator, 2 replacement tiles), rinshan [3, -1] | wall_rules.dead_wall, dora_indicator, ura_indicator, rinshan, kan_dora, kan_ura |
| Kan | Concealed kan only, once per player (at most twice in a round), no kan dora | flow.kan_kinds, flow.max_kans_per_player, flow.max_kans, dora.kan |
| Pon and chi | None | flow.pon, flow.chi |
| Yaku | The standard yaku that can be made with sets + a pair (yaku.base riichi-standard). The 20 yaku of 4 tiles are those of this table that can be made with one set. With more sets, iipeikou, sanshoku, ittsu, sanankou, shousangen, daisangen, suuankou and others apply too. Renhou is a yakuman. **Chiitoitsu and kokushi musou are not included** (shapes that are not sets + a pair do not exist with 4 tiles) | yaku.overrides (han, false or "yakuman" for each yaku) |
| Fu, scores, payment, honba, riichi sticks, draws, end, settlement | The same as 4 tiles (§2) | scoring.*, end.*, settlement.* |

Bundled: `nm-2p-7-{m,mps,mpsz}`, `nm-2p-10-{m,mps,mpsz}`, `nm-2p-13-{m,mps,mpsz}` (east-south). Other suits and lengths: `nmrules.ruleset_for(n, suits, length)`.
With characters only (36 tiles) the number of draws is 18 for 7 tiles, 12 for 10 tiles and 6 for 13 tiles.

What was checked: games played between the bundled players (including wins, riichi and concealed kans) run to the end and pass verification of the record (tests/test_dealer.py D4; for the JavaScript version js/test_game.js T14-6). Wall generation and verification of records also pass under rules changed to a dead wall of 14, four kans in a round (two per player), kan dora, pon, and chiitoitsu. There is no check yet with games played by people.

## 3 The other version of 4-tile mahjong (nm-2p-4-room)

4-tile mahjong in the form where two players make a room and play. It is a different rule from §2: characters only, red tiles, no riichi stick, 100000 starting points, and so on.

| Division | Rule | How it is written in the ruleset |
|---|---|---|
| Players and tiles | Two players, a hand of 4 tiles, a win = one set + a pair | players 2, hand_size 4, agari_form standard |
| Tiles | Characters 1–9, four of each (36 tiles). One red tile each of 3, 5 and 7 | tileset `m` (the mark red on one tile each of 3m, 5m and 7m) |
| Length of the game | East 1, East 2, South 1, South 2 | length east_south |
| Dealing | Five tiles to the dealer, four to the non-dealer | deal N_each_then_1_to_dealer |
| Dead wall | 2 tiles: the dora indicator and the ura dora indicator. A replacement tile is not taken from the dead wall; the next tile of the wall is drawn | dead_wall 2, dora_indicator [0], ura_indicator [1], rinshan `"live"` |
| Riichi | Riichi 1, double riichi 2 (the first discard, before any kan), ippatsu 1. No riichi stick is put out | riichi {min_points 0, below_min allowed}, kyotaku_points 0 |
| Kan | Concealed kan only. At most once, before riichi. No kan dora. Rinshan kaihou 1 han | max_kans 1, dora.kan false, ankan_after none |
| Yaku | Renhou 5, rinshan kaihou 1, haitei 1, houtei 1, menzen tsumo 1, chinitsu 2, pinfu 1 (a sequence + a two-sided wait), toitoi 2, tanyao 1, junchan 3. Chinroutou, tenhou and chiihou are yakuman | overrides: renhou 5, rinshan 1, haitei 1, houtei 1, menzen_tsumo 1, chinitsu 2, pinfu 1, toitoi 2, tanyao 1, junchan 3, riichi 1, double_riichi 2, ippatsu 1, chinroutou / tenhou / chiihou "yakuman". The others are false |
| Dora | Dora, red dora, ura dora (with riichi) | marks.red effects [dora], dora.ura true |
| No yaku | Without a yaku the hand cannot win | Standard |
| Fu | Pinfu tsumo 20 / pinfu ron 30. Otherwise 20 + tsumo 2 / ron 10 + triplet (concealed 4 / 8, open 2 / 4) + concealed kan 16 / 32 + single, closed or edge wait 2. Rounded up to units of 10 fu | fu {enabled, menzen_tsumo_pinfu true, open_pinfu_fu 30} |
| Scores | Basic points = fu × 2^(han+2), with an upper limit of 2000. Mangan 5 han, haneman 6, baiman 8, sanbaiman 11, yakuman 13 (8000). Only one yakuman counts, and other yaku are not added | table standard, mangan_round_up false, limits {sanbaiman_from 11, kazoe_from 13, yakuman_base 4, max_multiple 1, stack_with_normal false} |
| Payment | Ron = basic points × 6 (dealer) / × 4 (non-dealer), all from the opponent. Tsumo = the single opponent pays the total of the three players in four-player mahjong | scoring.payment `4p_total_from_opponent` |
| Honba | The loser pays 1000 per honba. No riichi sticks | honba_points 1000 |
| Draw | A draw when the wall runs out; the dealer continues (whether tenpai or not). No penalty | noten_penalty 0, renchan {dealer_tenpai, draw true} |
| Passing a win | A player who passes on a ron cannot ron in that round | Standard furiten |
| Tobi | The game ends when points are 0 or below | end.tobi {at 0, exact_zero_is_tobi true} |
| Last round | The non-dealer wins → the game ends. The dealer is ahead → the game ends. The dealer is behind → the game goes on | end.tenpai_yame {enabled, forced, require_tenpai false} |
| Settlement | 100000 points. The player with more points at the end wins; equal points are a tie. No return points, uma or oka | start 100000, return 100000, uma [0, 0], oka none, tie draw |

## 4 Items provided in the ruleset for N-tile mahjong

Items that ordinary four-player mahjong does not need but that are needed to write N-tile mahjong. They are defined in ruleset.md.

| Item | Values | Rules that use it |
|---|---|---|
| `scoring.payment` | `standard` (each player pays their own share; the usual for four players) / `4p_child_half_from_opponent` (a ron is the whole amount; a tsumo is half of the non-dealers' total in four-player mahjong) / `4p_dealer_share_from_opponent` (a ron is the whole amount; a tsumo is basic points × 2 rounded up) / `4p_total_from_opponent` (the single opponent pays the whole four-player total). Anything other than standard with other than two players is an error | 1 tile / 4 tiles or more / the other version |
| `custom:nm1-limits` in `scoring.table` | han → haneman (up to 7), baiman 8, sanbaiman 11, counted yakuman 13. The minimum is haneman | 1 tile |
| `limits.max_multiple` | The upper limit of the multiple when yakuman combine | 2 for 1 tile and for 4 tiles or more; 1 for the other version |
| A negative value in `wall_rules.rinshan` | A negative position is on the side of the end of the live wall (−1 is the original last tile) | 4 tiles or more (`[3, -1]`) |
| `"live"` in `wall_rules.rinshan` | A replacement tile is taken as the next draw of the wall, not from the dead wall | The other version |
| `flow.pon` | false means no pon | 1 tile, 4 tiles or more |
| `flow.kan_kinds` | The kinds of kan allowed. `["ankan"]` means concealed kan only; `[]` means no kan | 4 tiles or more / 1 tile |
| `flow.max_kans_per_player` | The limit on kans one player can make in a round | 4 tiles or more (1) |
| `flow.riichi.stick_if_ronned` | Whether the riichi stick is put out when the declaration tile is ronned | false in all |
| `flow.riichi.stick_at_end` | Where riichi sticks left on the table at the end of the game go | to_first for 1 tile and for 4 tiles or more |
| `flow.renchan.draw` | Whether, on a draw, the dealer continues whether tenpai or not | true in all |
| `end.max_honba` | The game ends when honba reaches this number | 1 tile, 4 tiles or more (50) |
| `end.tenpai_yame.require_tenpai` | false means "in the last round, if the dealer is ahead the game ends whether tenpai or not" | false in all |
| `draw` in `settlement.tie` | Equal points are a tie (the place is shared) | The other version |

## 5 What is bundled

| name | Content |
|---|---|
| `nm-2p-1-{m,mps,mpsz}` | 1-tile mahjong, east-south (§1) |
| `nm-2p-4-{m,mps,mpsz}` | 4-tile mahjong, east-south (§2) |
| `nm-2p-{7,10,13}-{m,mps,mpsz}` | The extension of 4-tile mahjong (§2.2) |
| `nm-2p-4-room` | The other version of 4-tile mahjong. Tileset `m` (red 3, 5 and 7) (§3) |
| Other suits and lengths | Not bundled. `nmrules.ruleset_for(n, suits, length)` makes them from the same definition (for example `nm-2p-4-z-east`) |
| N-tile mahjong for three or four players | Not bundled. Take one of the above as a template and change players, winds and uma (the ruleset page tools/rulegen.html, or `ruleset new --from`) |
