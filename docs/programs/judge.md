# Judgement of yaku and fu for a win (nmahjong/judge.py)

A part of layer 4 (record). For one win it gives the yaku, fu and han according to the settings of the ruleset. Dealing the wall, running the round and moving points are the work of the game runner (dealer.md) and are not here.

```
ctx = judge.win_context(record, round_index, event_index, ruleset, tileset, walls)   # take the situation of that win out of the events of the record
res = judge.judge(ruleset, tileset, ctx)                                             # yaku, fu, han
```

Command: `python3 -m nmahjong judge RECORD [--round R] [--merge-dora]` (judges the wins one by one and compares them with the record; exit code 1 if there is a difference)

## 1. Result

```json
{"ok": true, "yaku": [{"name": "riichi", "han": 1}, {"name": "pinfu", "han": 1}, {"name": "dora", "han": 2}],
 "fu": 30, "han": 4, "wait": "ryanmen", "form": "standard"}
```

- For a yakuman: `yaku` is `{"name", "yakuman": multiple}`, `yakuman` holds the sum of the multiples, and `han` is 0
- When the hand cannot win: `{"ok": false, "reason": …}`. The reason is a Japanese sentence: "役が無い" (no yaku) or "和了形ではない" (not a winning shape)
- Another reason is "抜く牌を手に残したままでは和了できない" (cannot win while a nuki tile remains in the hand; §6)
- `wait`: tanki / shanpon / ryanmen / kanchan / penchan / kokushi. `form`: standard / chiitoi / kokushi
- When there are several ways to divide the hand into sets or to take the wait, the highest is chosen in the order basic points → han → fu
- The names of yaku are those of vocab.json. They can be written as they are into `yaku`, `fu` and `han` of `result.wins[]` of a record

## 2. The number of tiles in a hand

A hand of N tiles is "(N−1)/3 sets + a pair". 1 tile = a pair only; 4 tiles = one set + a pair; 7 tiles = two sets; 10 tiles = three sets; 13 tiles = four sets.
Chiitoitsu and kokushi musou are looked at only with 13 tiles and no melds (if they are not used, they are not winning shapes).
A yaku for which there are not enough sets does not apply (sanankou needs three sets or more; suuankou and ryanpeikou need four). Toitoi is "all sets are triplets (one or more)".

## 3. Settings it follows (ruleset)

| Setting | Effect |
|---|---|
| yaku.base / yaku.overrides | The yaku used and their han. false = not used; an integer; `{"closed","open"}`; `"yakuman"` / `"yakuman:n"` |
| yaku.chiitoi_four_of_kind | Seven pairs using four of the same tile |
| flow.open_tanyao | Open tanyao |
| flow.ippatsu | Ippatsu |
| flow.ryuuiisou_requires_hatsu / chuuren_any_suit | The green dragon in ryuuiisou; the suit of chuuren poutou |
| flow.open_riichi | The han of open riichi (han_total, with_double_riichi_han); the yakuman payment for a deal-in (deal_in, exempt_prior_riichi, chaser_pays; open_riichi_deal_in in the situation) |
| scoring.fu.* | enabled, double_wind_pair, rinshan_tsumo_fu, chiitoi, open_pinfu_fu, menzen_tsumo_pinfu, yakuhai_tanki_fu |
| scoring.shibari | The minimum-han requirement (han han from from_honba on; dora are not counted) |
| scoring.limits.stack_with_normal | Combining yakuman with ordinary yaku |
| dora.* | Whether dora, ura dora, kan dora and kan ura are used, and the han per tile (values) |
| nuki | The han of nuki dora (value); as_yakuhai=common (the fu of the pair, and the judgement of pinfu); chan_nuki (whether a ron on a nuki gets chankan); win_with_nuki_in_hand (see §6) |
| marks / mark_overrides | The effects of marks on tiles: dora (`aka_dora`), yaku (`mark_yaku`; a yaku separate from dora), almighty (usable as any tile), reverse (`reverse: true` in the result). With the conditions of `when`. A mark whose condition has how (tsumo / ron) works on the winning tile only. The treatment when it appears as an ura dora indicator (`as_ura_indicator` = choose_any: the number of tiles of the kind most numerous in the hand is counted as ura dora) |
| winds | The seat wind (winds are assigned in the order seat − dealer. Two-player N-tile mahjong is East and West) |

When a higher yaku applies, the lower one is not given: double riichi > riichi, ryanpeikou > iipeikou, chinitsu > honitsu, junchan > chanta, the 13-sided kokushi > kokushi, junsei chuuren > chuuren, suuankou tanki > suuankou, daisuushii > shousuushii, tsuuiisou and chinroutou > honroutou. If the higher one is not used, the lower one is given.

## 4. Taking out the situation (win_context)

| Item | How it is decided |
|---|---|
| Riichi, double riichi | The riichi event. Double riichi = before it the player has no discard and nobody has called, made a kan or set a tile aside |
| Ippatsu | After the riichi discard and before the player's next discard, nobody has called, made a kan or set a tile aside (an added kan or a nuki that was ronned is not counted) |
| Rinshan kaihou | The last draw is a replacement tile (after a kan or a nuki) |
| Haitei, houtei | The remaining wall is 0. A replacement draw and a chankan are excluded |
| Chankan | A ron on the tile of a kan. A ron on the tile of a nuki only when nuki.chan_nuki is true |
| Tenhou, chiihou, renhou | No call, kan or nuki; tenhou = the dealer's first draw; chiihou = a non-dealer's first draw; renhou = a ron before the player's own first draw |
| Dora indicators | Those turned up to that moment (`dora` events). A kan dora not yet turned is not counted |
| Ura dora indicators | `ura_indicators` of the record; if absent, from the wall |

## 5. What was checked

| Compared with | Number of wins | Result |
|---|---|---|
| 1,005 real Tenhou games (four-player east-only and east-south, three-player; public data at hand) | 8,421 | Yaku, fu and han all agree |
| 4-tile N-tile mahjong (8,254 games played by the game engine of a separate implementation) | 27,080 | All agree |
| 1-tile N-tile mahjong (3,000 games, as above) | 6,795 | All agree |
| 20 games of N-tile mahjong played by people | 29 | All agree |

Yaku that appeared in the real games: riichi, double riichi, ippatsu, menzen tsumo, pinfu, tanyao, iipeikou, ryanpeikou, the five kinds of yakuhai, haitei, houtei, rinshan kaihou, chiitoitsu, sanshoku doujun, ittsu, chanta, junchan, honroutou, toitoi, sanankou, sanshoku doukou, shousangen, honitsu, chinitsu, dora, ura dora, red dora, nuki dora; and the yakuman tenhou, chiihou, renhou, kokushi musou, suuankou, daisangen, shousuushii, tsuuiisou, chinroutou, ryuuiisou.

**Things that did not appear in the real games and were checked only with hands made by hand** (tests/test_judge.py; the expected values follow the common way of counting): chankan, sankantsu, suukantsu, the 13-sided kokushi, suuankou tanki, daisuushii, chuuren poutou and junsei chuuren, switching the pair of the double wind between 2 fu and 4 fu, no tsumo fu for rinshan, an open pinfu shape at 20 fu, no pinfu with tsumo, chiitoitsu as 50 fu 1 han, the minimum-han requirement, changing the han of a yaku, the three ways of renhou, the effects of marks (yaku, almighty), and 7, 10 and 13 tiles.

**What this check fixed**
- Import from Tenhou: the round wind and the round number of three-player games were wrong ("wind × 4 + round" was divided by 3)
- The bundled tenhou-* rulesets (5): the pair of the double wind was 2 fu. The real games have 4 fu (8 cases) → changed to 4

## 6. What is not judged, and notes

- Sakizuke (flow.atozuke = forbidden): there is no source for how "a win on one side is allowed" is decided, so it is not part of the judgement (the result is the same as allowed). Complete sakizuke (kanzen_sakizuke) is judged
- A win while a nuki tile remains in the hand (nuki.win_with_nuki_in_hand = false): the hand cannot win if a nuki tile is in the hand or in a meld. Only the yakuman that cannot be made without those tiles (kokushi musou, chinroutou, tsuuiisou, shousuushii, daisuushii) can be won
- Nagashi mangan: it is treated as a draw, not a win, and is handled by the game runner (dealer.md)
- Pao, and the yakuman payment for dealing in to an open riichi: these concern payment and are handled by the game runner (dealer.md)
- Marks: three or more almighty tiles (how = any) held in the hand are not handled. The dora of an almighty tile is counted by its original kind
- Local yaku that are judged: renhou, daisharin, shousharin, sanrenkou, suurenkou, sanpuu, half flush of characters (manzu_honitsu), tsuuiisou as seven pairs, open riichi
