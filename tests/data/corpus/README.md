# tests/data/corpus — a collection of games for tests

In the Nmahjong formats (ruleset, walls, record), one game per line. They are read by `tests/corpus.py`.

| File | Content |
|---|---|
| `nm-engine.jsonl` | 50 games (154 rounds) of N-tile mahjong (1 tile and 4 tiles, two players). They were played between CPU players by a game engine made separately from this library (an application for N-tile mahjong) and converted to the Nmahjong formats |
| `selfplay-13.jsonl` | Two games of 13-tile mahjong (four players and three players) played between the bundled players (`python3 tools/gen_test_games.py` makes the same ones) |

The form of one line: `{"ruleset": …, "walls": […], "record": …}`. The tileset can be made from `tileset.name` of the ruleset (four of each tile, no red tiles).

- Situations contained in `nm-engine.jsonl`: tenhou, chiihou, renhou, a double yakuman, draws, rinshan kaihou, haitei, two concealed kans in one round, games replayed from the middle (with parent)
- Rulesets: variations in suits and length of the same definition as the bundled nm-* (`nmahjong/nmrules.py`), and their variants. A variant can be told from its name
  - `-stays`: riichi sticks left at the end of the game stay on the table
  - `-ronstick`: the riichi stick is put out even when the declaration tile is ronned (the winner takes it)
- Use: to confirm that the results made by another implementation (yaku, fu, scores, flow, settlement) agree with the judgement, game runner, recorder, gateway and evaluation of this library
