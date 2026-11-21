# Ruleset survey — can the major Japanese rules be written? (2026-11-13)

Purpose: to confirm, from published primary and secondary material, whether the items of ruleset.md can express the rules actually used in Japan **without anything missing**. Items that could not be expressed were added to ruleset.md.

The column "Earlier draft" refers to the draft of the ruleset specification before this survey.

## 1 What was surveyed, and the sources

| Division | Rule | Source |
|---|---|---|
| Organisation | JPML, Japan Professional Mahjong League (official, WRC, WRC-R) | [JPML official rules](https://www.ma-jan.or.jp/column_other/115081.html) |
| Organisation | Saikouisen | [Saikouisen rules](https://saikouisen.com/_rule.php), [competition regulations (PDF)](https://saikouisen.com/wordpress/wp-content/uploads/fe9d1f2e3f4994352345f3eb5245e586.pdf) |
| Organisation | NPM, Japan Professional Mahjong Association | [NPM official rules](https://npm2001.com/about/rule/) |
| Organisation | RMU (A, B, M) | [RMU rules](https://rmu.jp/rule) |
| Organisation | Mahjong Union μ | [comparison table](https://mj.maku.blog/p/triuood/) (the official regulations through the comparison table) |
| Organisation | Japan Sports Mahjong Association | [official competition regulations](https://sportsmahjong.com/page/rule01.html) |
| Organisation | Official competition regulations of Kenko Mahjong (Tokyo Mahjong Business Cooperative) | [competition regulations](https://tojankyo.com/kenma-rule/) |
| League | M.League | [janten commentary (with article numbers of the official regulations)](https://janten.net/guide/m-league-rules), [comparison table](https://mj.maku.blog/p/triuood/) |
| Tournament | Mahjong Saikyosen | [comparison table](https://mj.maku.blog/p/triuood/) |
| Online | Tenhou | [Tenhou wiki: basic rules](https://wikiwiki.jp/tenhou-chat/%E5%A4%A9%E9%B3%B3%E9%BA%BB%E9%9B%80%E3%81%AE%E5%9F%BA%E6%9C%AC%E3%83%AB%E3%83%BC%E3%83%AB) |
| Online | Mahjong Soul | [note article by クァル](https://note.com/qar13ktk20/n/nf9c7cf0eb025) (the article itself states that **the official site has no rule text**; what the game shows is authoritative) |
| TV | THE Wareme de Pon | [Wikipedia](https://ja.wikipedia.org/wiki/THE%E3%82%8F%E3%82%8C%E3%82%81DE%E3%83%9D%E3%83%B3) |
| Parlour | Riichi Mahjong Sakae (Shibuya) | [jan39 rules](https://jan39.com/shop/11686/rule/), [じゃんラボ](https://media.jannavi.net/sakae/) |
| Parlour | Mahjong ZOO (four and three players) | [ZOO rules](https://mj-zoo.jp/rule.html), [Yokohama non-smoking branch](https://jan39.com/shop/12399/rule/) |
| Parlour | Marchao α Kyoto Shijo Karasuma (four and three players) | [麻雀王国](https://mj-king.net/tempos/rule/8362) |
| Parlour | Kansai three-player, general | [Peculiar rules of Kansai three-player](https://ameblo.jp/kansai3mj/entry-12100946684.html), [Wikipedia: three-player mahjong](https://ja.wikipedia.org/wiki/%E4%B8%89%E4%BA%BA%E9%BA%BB%E9%9B%80) |
| Local | Open riichi | [じゃんラボ](https://media.jannavi.net/open-reach/) |
| Local | White pocchi, gold tiles, reverse pocchi | [mahjong-press: white pocchi](https://www.mahjong-press.com/mahjong-strategy/white-tile-almighty/), [daisen note: three red, three gold, white pocchi](https://note.com/daisen/n/n66fdb6489afb) |

Many parlours do not publish their number of chips, uma or number of red tiles on the web (both Sakae Shibuya and ZOO Yokohama: "not stated"). A parlour's rule is something **the parlour writes as a ruleset**; it is not something this library can settle. The purpose of this survey is to confirm that "the container can express it".

## 2 Facts found, and what the earlier draft could not express

| # | Fact (source) | Earlier draft | What was done |
|---|---|---|---|
| 1 | White pocchi: almighty on a tsumo after riichi. Variants: ippatsu tsumo only / rinshan and haitei too. One chip. Forced highest value (mahjong-press, daisen) | marks was a single value with no condition | marks became `{effects[], when, forced_high}` |
| 2 | Gold tile: treated as dora + double chips (daisen) | No multiplier for chips | Expressed with chips.count (a rule is written per mark) |
| 3 | Reverse pocchi: the hand can win, but points and chips are **paid** (daisen) | None | `reverse` in marks.effects |
| 4 | The red five of dots is a one-han yaku; the red fives of characters and bamboo are dora (Sakae) | Possible with mark_overrides | Kept |
| 5 | Red tiles are dora even in an open hand / only when concealed (ZOO three-player: "treated as dora even when called") | No condition | `menzen_only` in marks.when |
| 6 | Place points change with the number of players above the starting points (JPML official, Sports Mahjong, Kenko Mahjong) | uma was a fixed array | uma is an array **or** `by_floating` |
| 7 | Ties: divided equally (JPML, RMU, M.League) / the player nearer to the first dealer is higher (Saikyosen, Sakae, Marchao) | None | settlement.tie |
| 8 | Exactly the starting points counts as "above" (Sports Mahjong) | None | includes_threshold in uma.by_floating |
| 9 | Cold game at 55,000 / 60,000 points or more (ZOO, Marchao, Sakae) | None | end.cold_points |
| 10 | The game ends by a time limit (Kenko Mahjong, 60 minutes) | None | end.time_limit_sec |
| 11 | Tobi: exactly 0 points is not tobi (Wareme, Mahjong Soul) / tobi at exactly 0 (ZOO three-player) / a tobi penalty of 10,000 to a tenpai player (Wareme) / below zero the player borrows and goes on (JPML, Sports) | Only at and exact_zero | `penalty_points` and `penalty_to` in tobi; below zero `negative_points: continue` |
| 12 | Dead wall of 16, two dora indicators at all times (Wareme) | Possible | Kept |
| 13 | Each kind of abortive draw is used or not. On an abortive draw the dealer **continues** (Tenhou, Mahjong Soul) / three rons = a draw (JPML, ZOO) / only the nearest player wins (Saikouisen, NPM) | Four kinds in ryukyoku; continuing not stated | `three_ron` added; `renchan_on_abort` |
| 14 | Conditions for the dealer to continue: only by winning (Sakae, Marchao four-player) / when tenpai / the dealer continues when everyone is noten (Wareme) / in the south round the dealer continues even when noten (Kansai three-player) | One enumeration | renchan became a set of conditions + an override by round wind |
| 15 | Honba 300 / 1,000 (three-player) / 1,500 (Sakae, daisen) | Possible | Kept |
| 16 | A two-han minimum from the fifth honba, dora excluded (Wareme) | None | scoring.shibari |
| 17 | Noten penalty of 3,000 on the table / no penalty at nagashi mangan (Mahjong Soul) | None | scoring.noten_penalty, nagashi.noten_penalty |
| 18 | Nagashi mangan: none (all organisations) / used, in place of the tenpai settlement (Tenhou) / a mangan treated as a draw (Mahjong Soul) / treated as a winning yaku (Marchao) / a yakuman (Kansai three-player) | None | game_rules.nagashi_mangan |
| 19 | Pao: none (Saikouisen, NPM, RMU) / daisangen and daisuushii (Tenhou, Mahjong Soul, μ) / + suukantsu (JPML, M.League) / all on a tsumo and split on a ron / honba and riichi sticks from the player who dealt in (JPML) / pao for rinshan after an open kan (JPML official only) | None | game_rules.pao |
| 20 | Counted yakuman: none = 11 han or more is sanbaiman (organisations) / 13 han (Mahjong Soul, RMU) / 14 han (Kansai three-player, ZOO three-player, Marchao three-player) | bool | scoring.limits.kazoe_from |
| 21 | Multiples of yakuman: a yakuman is four mangan (Sports, Kenko, Sakae) / no double yakuman (JPML, Saikouisen) / with (NPM, M.League, Mahjong Soul) / up to six times (Mahjong Soul) / yakuman and ordinary yaku do not combine | Only multipliers | `yakuman_base` (as a multiple of mangan), `max_multiple`, `stack_with_normal: false` in limits |
| 22 | Rounding up to mangan: none (JPML official, μ, Mahjong Soul) / used (others) | Possible | Kept |
| 23 | Fu: a pair of the double wind 2 fu / 4 fu (JPML official); rinshan tsumo fu 2 / 0 (ZOO); 2 fu for a single wait on a yakuhai (ZOO); chiitoitsu 25 fu 2 han; an open pinfu shape fixed at 30 fu (Sports); pinfu with tsumo; no fu counting (ZOO three-player) | None | scoring.fu |
| 24 | Rounding up below 1,000 points (Marchao three-player, Kansai three-player) | None | scoring.round_to |
| 25 | Three-player tsumo loss: none, with, adding 1000, marudori (Wikipedia) | None | scoring.tsumo_loss |
| 26 | No chi in three-player mahjong (allowed in Yokosuka) | None | flow.chi |
| 27 | North: nuki dora / a common yakuhai / always dora / robbing a nuki of North / a North set aside can be won on (Tenhou) / pao | nuki had only enabled | nuki became `{tiles, value, as_yakuhai, chan_nuki, pao}` |
| 28 | Four flower tiles (Marchao three-player, ZOO three-player): set aside and replaced from the dead wall | The number is possible with ex of the tileset | `ex` can be given in nuki.tiles |
| 29 | Seven pairs with four of a kind (three-player) | None | yaku.chiitoi_four_of_kind |
| 30 | Local yaku: daisharin, suurenkou, sanrenkou, shousharin, sanpuu, renhou (mangan / baiman / yakuman), half flush of characters, tsuuiisou as seven pairs, nagashi yakuman | Not in vocab | Local yaku are included in vocab. The han is in overrides |
| 31 | Open riichi: 2 han. A deal-in pays a yakuman (most exempt a player already in riichi; a player who declares afterwards pays; depending on the parlour, everyone pays / everyone gets 2 han). Combined with double riichi, 3 han / 4 han (じゃんラボ) | None | flow.open_riichi |
| 32 | Conditions for riichi: 1,000 points or more and a draw left (Tenhou) / not below 1,000 points, exactly 1,000 allowed (Mahjong Soul, Sakae) / allowed with 1,000 points but tobi if nothing comes in (ZOO three-player, Marchao three-player) / allowed even with no draw left (organisations) / no riichi on the last discard (JPML official) | Only min_points | flow.riichi was structured |
| 33 | Riichi while furiten: allowed (most organisations, Sakae) / not allowed (Kansai three-player, ZOO three-player) | None | riichi.furiten_riichi |
| 34 | A concealed kan after riichi: allowed if the waits and composition do not change / not allowed (μ) | None | riichi.ankan_after |
| 35 | Kuikae: not allowed / only the same tile not allowed (JPML) / allowed (μ) | bool | kuikae has three values |
| 36 | Kan dora: turned at once for a concealed kan, after the discard for an open or added kan (Tenhou, Mahjong Soul) / at once for all (NPM, RMU, Kenko) | A single value | kan_timing by kind of kan |
| 37 | Kokushi robbing a concealed kan: allowed (JPML) / not allowed (others). Ryuuiisou requires the green dragon (JPML). Chuuren is allowed in any suit | None | Three items in flow |
| 38 | Double ron: riichi sticks and honba to the nearest winner / only the nearest player wins. Triple ron: only the nearest player / a draw | Possible | `kyotaku_to: kamicha` added |
| 39 | Agari-yame: none (organisations) / only the dealer of the last round (Sakae) / automatic (Tenhou) / a forced end if first, and second or third place may choose to go on (Marchao) | enabled + when | `forced` in agari_yame |
| 40 | Extension: none / into the south, west and north winds, ending when someone has 30,000 or more (Tenhou) / no second extension (Mahjong Soul) / a return east round (Wareme) | extension | Kept (expressed with max_rounds) |
| 41 | Chombo: a mangan payment / a baiman payment / 8,000 from everyone / −20P or −40P (from the results) / 12,000 placed on the table / the round is replayed and honba does not increase | None | penalties.chombo |
| 42 | An empty pon and the like: 1,000 points placed on the table / forfeiting the right to win / chombo | None | penalties.false_call |
| 43 | Chips for called hands (ZOO, daisen) | No call in on | `call` in chips.on |
| 44 | Yakitori: no parlour states it (Sakae and ZOO: "not stated") | Possible | Kept |
| 45 | Complete sakizuke, no win on one side only (Kansai three-player) | atozuke was a bool | atozuke has three values |
| 46 | "Two han added on the table" (Sports, Kenko) is a premise of the score table and needs no item | — | Included in scoring.table=standard |
| 47 | Several sets per organisation: JPML official / WRC / WRC-R; RMU A / B / M; Saikouisen ordinary / Classic ([Wikipedia](https://ja.wikipedia.org/wiki/%E6%9C%80%E9%AB%98%E4%BD%8D%E6%88%A6Classic)) | One example per organisation | All sets are bundled as separate files in the collection of default rulesets |
| 48 | Tables that deal automatically have no step of "taking four tiles at a time"; the walls rise with the hands already dealt (AMOS ULTIMA 2005, Shoryu 2003, AMOS REXX 3 2021, S-tellar 2022. [Wikipedia: automatic mahjong table](https://ja.wikipedia.org/wiki/%E5%85%A8%E8%87%AA%E5%8B%95%E9%BA%BB%E9%9B%80%E5%8D%93)) | The meaning of deal was undefined | deal was stated explicitly as "N tiles each in turn order from the dealer, and finally one to the dealer". The taking procedure is not reproduced |
| 49 | A ruleset id should be made from the settings (the same settings under different names get the same id) | name was included in the hash | The id is the hash of all items except id, name and meta |
| 50 | Conversion to a final reward: parlours state a rate per 1,000 points, a value per chip, a game fee and a prize for first place ([doramahjong](https://doramahjong.org/freejyannsou/01/0003.html)) | Only a coefficient; no value per chip, no entry fee | unit(code), per_pt, chip_value and fees in payout. The form is the same whether the unit is a currency or in-game points |
| 51 | Sakae Shibuya: uma "1-1.5-3" with A-top (second place pays 1 if below 25,000, and receives 1.5 if at or above), honba 1500, a chip for a red tile even in an open hand, a tobi penalty of one chip, chips for a yakuman unknown, four red tiles on holidays ([doramahjong さかえ](https://doramahjong.org/freejyannsou/08/0040.html), [旅打ち](https://jangoro46.hatenablog.com/entry/2020/01/13/230000)) | No form in which uma changes with second place's points | threshold (start / return / an integer) in uma.by_floating |
| 52 | Mahjong Soul rank points = place points + (final points − starting points)/1000. Place points are a table of room × rank; the deduction for fourth place changes with the player's own rank ([game8](https://game8.jp/jantama/631616)) | None | settlement.external_points[] kind=rank_plus_raw, by_player_rank |
| 53 | Tenhou rank points depend on place only (no raw points); first and second by table × east-only/east-south; the deduction for last place by rank. Rate is a formula ([Tenhou manual](https://tenhou.net/man/)) | None | external_points kind=rank_only / formula |
| 54 | M.League P = 1P per 1000 points, return 30000, uma + oka 50/10/−10/−30 | Already expressed with uma | Can also be written as external_points mleague-p |
| 55 | Rules that allow a kan changing the waits after riichi hardly exist today, but the setting is needed (it changes whether "kan" appears among the candidate actions) | Only if_shape_unchanged / none | `any` added to ankan_after |
| 56 | 1-tile mahjong (nm-2p-1-*): a tsumo is half of the non-dealers' total in four-player mahjong, a ron is the whole amount. The other version of 4-tile mahjong (nm-2p-4-room): the opponent pays the whole total of the four players | No way to decide payments | scoring.payment |
| 57 | The other version of 4-tile mahjong (nm-2p-4-room): dead wall of 2, replacement tiles from the live wall | rinshan only inside the dead wall | rinshan "live" |
| 58 | 1-tile mahjong (nm-2p-1-*): the game ends at 50 honba | None | end.max_honba |
| 59 | N-tile mahjong (nm-*): on a draw the dealer continues whether tenpai or not; the last round ends if the dealer is ahead whether tenpai or not. The other version (nm-2p-4-room) has ties | None | renchan.draw, tenpai_yame.require_tenpai, tie draw |

## 3 Conclusion
- With the number of items in the earlier draft, not even the rules of the organisations could all be written (uma by the number of players above, pao, the details of fu, the han for a counted yakuman).
- The items above were reflected in ruleset.md. Within what was confirmed for online mahjong, TV, parlours and three-player mahjong, **no item remains that cannot be written**.
- However, Mahjong Soul has no official rule text, and the chips and uma of parlours are mostly not public. In the bundled rulesets, items the source does not state are set to the most plausible value and listed in `unknown`; they are corrected when the organisation or parlour tells us the correct value (CONTRIBUTING.md).
