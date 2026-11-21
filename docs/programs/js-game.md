# Layers 4 and 5 in the JavaScript version (js/nmahjong-game.js)

Layers 4 (record) and 5 (annotation) of the Python implementation, moved to JavaScript with the same procedures. In a browser or on a server (Node.js), games can be run, verified and evaluated **without putting Python on the server**. Layers 1 to 3 (tileset, ruleset, wall) are in `js/nmahjong.js`.

```
Order of loading: js/bundled.js (bundled data) → js/nmahjong.js (layers 1–3) → js/nmahjong-game.js (layers 4 and 5)
Browser: load them in order with <script>. The globals are NMAHJONG_BUNDLE / NMAHJONG / NMAHJONG_GAME
Node   : const NM = require("./nmahjong.js"), B = require("./bundled.js"), G = require("./nmahjong-game.js")
```

## 1. What is in it

| Part | Python | JavaScript (G.…) | Role |
|---|---|---|---|
| Scores and settlement | scoring.py | `scoring` | Basic points, payments, places, settlement |
| Positions and legal actions | observe.py | `observe` | Rebuild a position from events; the list of actions that can be taken; furiten; waits |
| Judgement of yaku and fu | judge.py | `judge` | Yaku, fu and han of a win (the same as judge.md) |
| Verification of records | record.py | `record` | record.md §4 + cross-layer checks (comparison with wall and ruleset, scores, settlement) |
| Recorder | recorder.py | `recorder` | Checks events one by one and adds them to the record |
| Game runner | dealer.py | `dealer` | Holds the walls and runs one game (the same as dealer.md). Bundled players `dealer.bots` |
| Evaluation | evaluate.py | `evaluate` | All at once / each time an action arrives (LiveAnnotator) |
| Arena | arena.py | `arena` | Runs many games between players and gives a table of results |

## 2. How to use it (the game runner and players)

```js
const rs = B.rulesets.find(x => x.name === "nm-2p-4-mps");
const ts = B.tilesets.find(x => x.id === rs.tileset.id);
const human = msg => waitForClick(msg.legal);          // a person: return, as a Promise, the action chosen on the screen
const d = new G.dealer.Dealer(rs, ts, { players: { 0: human, 1: G.dealer.bots.simple(ts) } });
const live = new G.evaluate.LiveAnnotator(rs, ts, { onPoint: p => show(p) }).attach(d.rc);   // evaluate each time a discard arrives
const rec = await d.play(k => NM.wall.build(ts, `seed-${k}`));     // the record. The walls used are in d.walls
const ann = live.finish(rec);                                       // the annotation
```

- A player is a function `({seat, phase, round, at, obs, legal}) => action`. It may return at once or later (with a Promise). A person's operation is awaited with a Promise
- `phase`: A = declarations after a draw, B = the discard, C = reactions to another player's discard. `legal` = the list of actions that can be taken now (return one of them). A seat that can only pass is not asked
- `obs` = the position visible from that seat (other players' hands are not in it)
- The form of an action: `{type: "discard", tile}` / `{type: "riichi", tile}` / `{type: "tsumo"}` / `{type: "ron"}` / `{type: "pon"|"chi", tiles}` / `{type: "kan", kind, tiles}` / `{type: "nuki", tile}` / `{type: "pass"}`
- `strict: false`: a broken response or an action that cannot be taken is replaced with the default action (discard the drawn tile / pass) and play goes on (kept in `d.faults`)
- To add events yourself without the game runner, use `new G.recorder.Recorder(rs, ts)` (startRound → push … → endRound → finish)

## 3. What was checked (the same results as Python)

The results of the Python implementation were written out and compared with the results of the JavaScript implementation. The counts of the latest run are in conformance.md §4.

| What | Compared with | Result |
|---|---|---|
| The situation of a win; yaku and fu | 1,005 real Tenhou games (8,421 wins; public data at hand); N-tile mahjong: 3,000 games of 4 tiles (9,866 wins), 254 of 4 tiles with kans (778), 3,000 of 1 tile (6,795), 20 real games (29) | All the same |
| Positions, legal actions, the action actually taken | 40 Tenhou games (18,771 decision points); N-tile mahjong: 200 games of 4 tiles (14,405), 254 of 4 tiles with kans (19,144), 200 of 1 tile (10,884), 20 real games (396) | All the same |
| Verification of records (down to the text of warnings); recorder (the same ids) | 1,005 Tenhou games; N-tile mahjong: 3,000 of 4 tiles, 254 of 4 tiles with kans, 3,000 of 1 tile, 20 played by people (7,279 games in total) | All the same |
| Game runner: running again with the same walls and the same decisions (directly) | 1,005 Tenhou games; N-tile mahjong: 3,000 of 4 tiles, 254 of 4 tiles with kans, 3,000 of 1 tile, 18 played by people (without 2 that continue an earlier game) | All the same as the original |
| Game runner: the same, while checking against the legal actions | Same | All the same as the original |
| Evaluation: all at once / step by step (the same ids) | The same 7,279 games as for verification | All the same |
| Game runner + bundled players: the same game as Python with the same seed (the same id) | 27 games (1, 4, 7, 10 and 13 tiles; four players; three players) | All the same |
| The same games in a browser (Chromium) | 10 games under 4 rulesets | All the same |

Tests in the repository: `cd js && node test_game.js` (12 tests; the test data in js/testdata are made from the Python implementation by `python3 tools/gen_js_testdata.py`).

## 4. What the JavaScript version does not have

- Conversion to the mjai form and connection to players that are other programs (gateway.py / mjai.py). A JavaScript player is passed as a function
- Import (logs of Tenhou and others → records), the command (cli), verification of annotation files (annotation.validate)
- For the complete verification of a ruleset (ruleset.md §5), Python is authoritative. JavaScript goes as far as the normal form, the id and the vocabulary
- `record.validate` takes the ruleset and the tileset as arguments (it does not look them up among the bundled data)

## 5. How it is built

`js/nmahjong-game.js` is a generated file made by joining `js/src/game_*.js` (`python3 tools/gen_js_game.py`). To change it, change src and join again.
After changing the Python side, put the same change into src and compare with `python3 tools/gen_js_testdata.py && (cd js && node test_game.js)`.
