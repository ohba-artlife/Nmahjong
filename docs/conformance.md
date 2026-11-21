# Conformance — what was compared with what, and how far it was checked

This document brings together (1) the means by which someone implementing the formats in another language can confirm "I got the same result", (2) the evidence that this library itself is correct, and (3) what has not been checked.
Numbers carry the date on which they were checked. The tests in the repository check again on every run; the comparisons with large numbers of games were done locally during development.

## 1. What conformance means

| Level | Content | Means of checking |
|---|---|---|
| 1 Ids agree | Canonical JSON and ids; tileset ids; wall generation (`fy-sha256-v1`) and wall ids; the normal form and id of a ruleset | Test vectors (§2) |
| 2 The shape is right | Files of the five layers have the shape of the specification | JSON Schemas (§3) and the verification section of each specification |
| 3 The content is right | Verification of records (comparison with the wall, flow, scores, settlement), legal actions, yaku and fu, the game runner | Test games, and the results given by the reference implementation (§4) |

An id is the SHA-256 of the canonical JSON of the content, so if level 1 agrees, a file with the same content has the same name and the same id whoever makes it.

## 2. Test vectors (tests/vectors/conformance.json)

JSON that does not depend on a language. It is made from the reference implementation (Python) with `python3 tools/gen_vectors.py`. **Python (tests/test_vectors.py) and JavaScript (js/test.js) read the same file, each computes again, and agreement is confirmed.**

| Key | Input | Expected value | Count |
|---|---|---|---|
| `canonical_json` | JSON values (order of keys, nesting, Japanese text, decimals that are integers, escapes) | The canonical string and its id | 9 |
| `fy_sha256_v1` | The number of tiles n and a seed | The shuffled order (all of it, or the first 8), and the SHA-256 of the order as bytes | 6 (n = 1, 2, 10, 136, 256) |
| `tilesets` | The bundled tileset files | The number of tiles, the id | 10 |
| `walls` | A tileset id and a seed | The first 8 and last 4 of the order, the SHA-256 of the order, the wall id | 6 (136, 108, 36 and 144 tiles) |
| `rulesets` | The bundled ruleset files | The id computed from the normal form | 46 |

The value written in the specification (the wall id in spec/wall.md §3) is the same as the first entry of this file.
For the reproduction of Tenhou's walls (`tenhou-mt19937ar-sha512-n288-nm1`), the random number generator MT19937 was compared with the original author's sample output, and the values of walls made from an artificial seed are fixed (tests/test_wall.py). Agreement with real game logs is in §5.

## 3. JSON Schemas (nmahjong/data/schema/)

A JSON Schema (draft 2020-12) for each of the five layers, made with `python3 tools/gen_schema.py`. For checking the shape in editors and in other languages.
A schema looks only at the shape. For agreement of ids, cross-layer consistency (X1–X14 in overview.md §5) and consistency that depends on the ruleset, the verifier (`nmahjong validate`) is authoritative.

## 4. Agreement of Python and JavaScript

### 4.1 Tests in the repository (checked on every run)

| Test | What | Compared with |
|---|---|---|
| js/test.js (8 tests) | SHA-256, the wall test vector, the ids of bundled tilesets and rulesets, making a tileset, the normal form and difference of rulesets, canonical JSON, the test vectors of §2 | The bundled data and test vectors made by Python |
| js/test_game.js (12 tests) | Verification of records (the same down to the text of warnings), positions, legal actions and the action actually taken, the situation of a win and yaku and fu, the recorder, checking of chankan, the game runner (directly / while checking against the legal actions), games with the bundled players (the same id with the same seed), evaluation, the arena, and the ways of paying and ending that a ruleset can choose | The results written out by Python in js/testdata (35 games: 20 of N-tile mahjong, four-player and three-player games of 13-tile mahjong, 13 on constructed walls; 1,319 decision points, 73 wins, 8,353 evaluated points; 1,200 ways for a round to end; 27 games of the bundled players) |

The test data are made from the Python implementation by `python3 tools/gen_js_testdata.py`.

### 4.2 Comparisons with large numbers of games (run locally during development; 2026-11-18, with the program of that date)

The results of the Python implementation were written out and compared with those of the JavaScript implementation. Tenhou games cannot be bundled, so this comparison was done outside the repository.

| What | Compared with | Result |
|---|---|---|
| The situation of a win; yaku and fu | N-tile mahjong: 3,000 games of 4 tiles (9,866 wins), 254 of 4 tiles with kans (778), 3,000 of 1 tile (6,795), 20 games played by people (29); 1,005 Tenhou games (8,421 wins) | All the same |
| Verification of records (down to the text of warnings), recorder (the same ids), evaluation (all at once / step by step, the same ids) | Same (7,279 games in total) | All the same |
| Game runner: running again with the same walls and the same decisions, while checking against the legal actions | Same (without 2 games that continue an earlier game) | All the same as the original |
| Positions, legal actions, the action actually taken | N-tile mahjong: 200 games of 4 tiles (14,405 decision points), 254 of 4 tiles with kans (19,144), 200 of 1 tile (10,884), 20 played by people (396); 40 Tenhou games (18,771) | All the same |

### 4.3 Run again with the program of version 1.0.0 (2026-11-21)

After 4.2, the program was changed while the bundled rulesets were being re-read against their sources (judgement of a win, the end of the wall, verification of records). With the changed program (the same as 1.0.0), the following were run again.

| What | Compared with | Result |
|---|---|---|
| Python: verification of records, judging every win again, the recorder, the game runner (directly / through the gateway) | 1,005 Tenhou games (8,421 wins); N-tile mahjong: 8,000 games of 4 tiles (26,302 wins), 3,000 games of 1 tile (6,795 wins) | 0 differences |
| JavaScript: reading the same games and comparing verification, the situation of a win, judgement, recorder, game runner and evaluation with the Python results | 1,005 Tenhou games; N-tile mahjong: 3,000 of 4 tiles, 3,000 of 1 tile (7,005 games in total) | All the same |
| Three-player games made with a player that takes nuki dora and kans whenever it can (Toutenkou 40, Tenhou three-player 15, Kansai 10, ZOO 5, Marchao 5) | 75 games, 922 wins, 6,956 replacement draws | 0 differences in both Python and JavaScript |

Not run again: the "254 games of 4 tiles with kans" of 4.2 (the material could not be made again; checked up to the program of 2026-11-18). The 20 games played by people are checked on every run by the tests in the repository (tests/corpus.py).

What the JavaScript version does not have (conversion to mjai, connection to players that are other programs, import, the command) is in programs/js-game.md §4.

## 5. Comparison with games made by other implementations

Using games made outside the library as material, it was confirmed that the results of the library agree.

| Compared with | Count | What was confirmed | Date |
|---|---|---|---|
| Tenhou games (a collection of 1,002 public logs = 724 four-player and 278 three-player, and 3 others) | 1,005 games, 8,421 wins | The wall reproduced from the seed agrees with the deal, every draw, the replacement tiles and the dora. The records pass verification (flow, scores, settlement). Yaku, fu and han of every win agree. When the game runner runs with the same walls and the same decisions, the events, wins, draws, scores, next round, how the game ended and the final result are all the same | 2026-11-15 to 17. Run again in full on 2026-11-18 and on 2026-11-21 (§4.3), with the same result |
| Games played by the game engine of a separate implementation of N-tile mahjong (8,254 of 4 tiles, 3,000 of 1 tile) | 11,254 games, 33,875 wins | Yaku, fu, scores, flow and settlement agree | 2026-11-16 to 17. Run again in full on 2026-11-18, with the same result. On 2026-11-21, 8,000 of 4 tiles and 3,000 of 1 tile (§4.3) |
| N-tile mahjong played by people | 20 games, 29 wins | Same (for the game runner, 18 games, without 2 that continue an earlier game) | 2026-11-17. Run again on 2026-11-18, with the same result |

Situations that do not appear in real games were compared, item by item, with **the rule text published by Tenhou** (42 items for four-player ranked games, 12 items for three-player, and the notes of the list of yaku). The game runner runs rounds with a chosen wall and a chosen sequence of actions, and the outcome is compared with the result computed from the text (rules/tenhou-rules.md; tests/test_tenhou_rules.py, 30 tests; 2026-11-18). This comparison found 9 differences, which were fixed (§4 of that document).

- Tenhou game logs are not bundled. If you place them locally, `tests/test_tenhou_logs.py` does the same comparison (tests/data/tenhou/README.md; the name of one log with expected values, and where to get it, are there too)
- Of the games of N-tile mahjong, 50 games (154 rounds) are bundled in the Nmahjong format in `tests/data/corpus/nm-engine.jsonl`, and the tests in the repository compare them on every run
- The differences found by these comparisons, and what was decided, are written in programs/judge.md §5 and programs/dealer.md §2 (for example: in Tenhou a pair of the double wind is 4 fu; there is no rounding up to mangan; the three-player wall shuffles 108 tiles directly)

Yaku that appeared in the real games: riichi, double riichi, ippatsu, menzen tsumo, pinfu, tanyao, iipeikou, ryanpeikou, yakuhai, haitei, houtei, rinshan kaihou, chiitoitsu, sanshoku doujun, ittsu, chanta, junchan, honroutou, toitoi, sanankou, sanshoku doukou, shousangen, honitsu, chinitsu.

## 6. What was checked with games of our own

Situations that do not appear in the comparisons with other implementations are checked with games run by the library itself and with situations made by hand. **This confirms that "replaying from the record gives the same result" and that "it behaves as decided"; it is not independent evidence.**

| Material | Content | Tests |
|---|---|---|
| Two games of 13-tile mahjong (tests/data/corpus/selfplay-13.jsonl; `python3 tools/gen_test_games.py` makes the same ones) | Four-player: 11 rounds (16 chi, 25 pon, 7 kans, 6 riichi, 5 draws, 1 chankan); three-player: 9 rounds (24 nuki dora) | Verification, positions and legal actions, evaluation, judgement, recorder, gateway, game runner |
| A game on a constructed wall | Kokushi musou ronning the tile of a concealed kan (under a rule that allows it and one that does not) | tests/test_dealer.py D6, D7 |
| Rounds on constructed walls, and score tables | The ways of paying and ending that a ruleset can choose: the payments of a three-player tsumo (compared with a published score table), units of 1000 points, equal division of riichi sticks among several winners, the tobi penalty, the treatments of nagashi mangan, the choice of agari-yame, the time limit, wareme, the yakuman payment for dealing in to an open riichi, additive scoring, chips, the white and reverse pocchi, complete sakizuke, replacement tiles set aside in the dead wall, nuki tiles kept in the hand | tests/test_rule_options.py O1–O59, js/test_game.js T14-11 |
| Wins made by hand | Chankan, sankantsu, suukantsu, the 13-sided kokushi, suuankou tanki, daisuushii, chuuren poutou and other yaku that did not appear in real games (the expected values follow the common way of counting) | tests/test_judge.py |
| Two games each of the 46 bundled rulesets between the bundled simple players (tools/selfplay_all.py) | All 92 games of the 46 rulesets run to the end and pass verification | programs/dealer.md §2 |

## 7. What has not been checked, and what cannot be done

Listed without hiding anything. Details are in each document.

- **Settings the game runner cannot follow yet** (programs/dealer.md §4): none in the bundled rulesets. A ruleset that uses wareme with other than four players is not started unless told to
- **Settings that are not judged** (programs/judge.md §6): sakizuke (flow.atozuke = forbidden), and three or more almighty tiles held in the hand
- **A ron on the tile of an added kan (chankan)**: it does not occur once in the 1,002 Tenhou games at hand. It is checked only with our own games and with situations made by hand (a ron on the tile of a nuki occurs 6 times in Tenhou, and agrees)
- **N-tile mahjong with 7, 10 and 13 tiles (nm-2p-7 / 10 / 13)**: only games between the bundled players. There is no check with games played by people
- **Mahjong Soul**: there is no official rule text; the bundled jantama-* rulesets are based on published articles. No comparison with Mahjong Soul game logs has been made
- **Rules of parlours and organisations**: they were written down from the text of the sources; no comparison with game records of those parlours or organisations has been made. Items not in the source are set to the most plausible value and listed in `unknown` of each file
- **Python 3.10 and earlier, and Node.js versions other than 22**: not tested

## 8. Checking for yourself

```bash
python -m unittest discover -s tests          # Python tests (test vectors, test games, references between documents)
cd js && node test.js && node test_game.js    # JavaScript tests
python3 tools/gen_vectors.py                  # make the test vectors again (if no difference appears, they are the same)
```
