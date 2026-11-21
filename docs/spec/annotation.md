# annotation — specification of the annotation (nmahjong-annotation 1.0)

Key: MUST = required, MAY = optional, SHOULD = recommended. The container is JSON (UTF-8). See record.md for records, ruleset.md for rulesets, and overview.md §6 for positions and legal actions.
The ideas are set out in evaluation.md (numbers are of four kinds: A actions / B positions / C games / D aggregates; storing A is required, B and C are optional, D is not stored).

## 1 Purpose
For each decision point of one game (record), to hold "the choice actually made", "the candidates and their values", "the best" and "the loss". There is a **separate file** for each evaluator (an AI, a person, your own logic). Nothing is written into the record.

**The evaluator declares the names of its values.** The library verifies only clashes of names and the types; the meaning is the evaluator's responsibility. Values needed under particular rules (the expected number of chips, the rate of dealing in to the wareme player, probabilities of places, the win rate when M=1, …) can be expressed just by the evaluator adding names. No revision of the specification is needed.

## 2 Form

```json
{
  "format": "nmahjong-annotation",
  "version": "1.0",
  "id": "sha256:…",
  "record": {"id": "sha256:…"},
  "evaluator": {
    "name": "nm-basic", "version": "0.1",
    "visibility": "full",
    "metrics": [
      {"name": "win",       "scope": "candidate", "kind": "prob",        "higher_is_better": true, "primary": true},
      {"name": "chips_ev",  "scope": "candidate", "kind": "count",       "higher_is_better": true},
      {"name": "rank_prob", "scope": "point",     "kind": "prob_vector"}
    ],
    "params": {"verdict": {"o": 0.0, "d": 0.02}},
    "run_at": "2026-11-14T10:00:00+09:00"
  },
  "points": [
    {
      "round": 0, "at": 3, "phase": "B", "actor": 0,
      "actual": {"type": "discard", "tile": 108},
      "candidates": [
        {"type": "discard", "tile": 108, "values": {"win": 0.41, "chips_ev": 0.3}},
        {"type": "discard", "tile": 4,   "values": {"win": 0.45, "chips_ev": 0.1}},
        {"type": "riichi",  "tile": 4,   "values": {"win": 0.47, "chips_ev": 0.4}}
      ],
      "estimates": {"rank_prob": [0.3, 0.3, 0.2, 0.2]},
      "best": 2,
      "loss": 0.06,
      "verdict": "x",
      "note": null
    }
  ]
}
```

### 2.1 The whole file

| Item | Required | Content |
|---|---|---|
| format | MUST | `"nmahjong-annotation"` |
| version | MUST | `"1.0"` |
| id | MUST | `"sha256:"` + SHA-256( the canonical JSON of all items except `id` ). Canonicalisation is the same as in ruleset.md |
| record | MUST | `{"id": "sha256:…"}`. The game that was evaluated. **The order of tiles and the hands are not written here** (they are replayed from the record and the walls) |
| evaluator | MUST | See 2.2 |
| points[] | MUST | See 2.3. Only the decision points that were evaluated. There is no duty to write every turn |

### 2.2 evaluator

| Item | Required | Content |
|---|---|---|
| name | MUST | The name of the evaluator. `mortal`, `naga`, `human`, `nm-basic` and so on. `[a-z0-9-]+` |
| version | MUST | The version. For a person it may be an identifier of the person who evaluated |
| visibility | MUST | The information the evaluator saw. `full` (everyone's hands and the wall = an all-seeing view; it reads the record and the walls) / `actor` (only the position visible to the player whose turn it is; the position of overview.md §6) / `none` (discards and melds only) |
| metrics[] | MUST | The declaration of the values it gives. Length ≥ 1. Each element: 2.2.1 |
| params | MAY | The settings of the evaluator. Any JSON. **The thresholds of verdict are here**: `"verdict": {"o": 0.0, "d": 0.02}` = loss ≤ o → `o`, ≤ d → `d`, more → `x`. Without it, verdict is not written |
| run_at | MAY | ISO 8601 |

#### 2.2.1 metrics[] — declaration of values

| Item | Required | Content |
|---|---|---|
| name | MUST | The name of the value. `[a-z][a-z0-9_]*`. Unique within the file |
| scope | MUST | `candidate` (A: per candidate; appears in candidates[].values) / `point` (B and C: per decision point; appears in estimates) |
| kind | MUST | The type. `prob` (0 to 1) / `prob_vector` (length M, sum 1) / `value` (a real number) / `count` (a real number; an expected number of chips or points) / `rank` (an integer where 1 is best) |
| higher_is_better | MUST (scope=candidate) | Whether larger is better. false for rank |
| primary | MAY | true on **exactly one** candidate value. best, loss and verdict are decided by this value |
| unit | MAY | For display. `pt`, `枚`, `点` |

Recommended names (in the bundled vocab.json; use them when you want meanings to match; there is no duty to use them):
`q` (Q value), `prob` (probability of choosing, π), `preference` (a degree of recommendation, 0 to 10000 and the like), `ev_pt` (expected pt), `win` / `dealin` / `tenpai` (the probability of one's own win, deal-in, tenpai), `others_tenpai` (the tenpai rate of the other players, prob_vector), `rank_prob` (probabilities of the final place), `chips_ev` (expected number of chips), `moves_to_win` (expected number of moves until a win), `rank` (place).

### 2.3 points[] — decision points

| Item | Required | Content |
|---|---|---|
| round | MUST | record.rounds[].index |
| at | MUST | The position in events[] of that round: **the event right before the decision** (for phase A and B the actor's draw; for C another player's discard). Exactly the arguments of the position `observe(record, round, at, actor)` of overview.md §6 |
| phase | MUST | `A` (right after a draw: choosing a win, a kan, a nuki, riichi, or declaring an abortive draw) / `B` (choosing a discard) / `C` (reacting to another player's discard: ron, pon, chi, kan, pass) |
| actor | MUST | The seat of the player who decided |
| actual | MUST | The choice actually made. See 2.3.1 |
| candidates[] | MUST | The candidates. Each element = 2.3.1 + `values` (declared candidate values → numbers). It **must contain** the same candidate as actual. There is no duty to list all legal actions. **Every element must be contained in `legal_actions(ruleset, position)`** |
| estimates | MAY | Declared point values → numbers |
| best | MUST | An index into candidates. The best by primary (ties are allowed; write the smallest index) |
| loss | MUST | The difference in primary. best − actual if higher_is_better, otherwise actual − best. ≥ 0 |
| verdict | MAY | `o` / `d` / `x`. MUST when params.verdict exists; not written when it does not |
| note | MAY | A person's comment. null for a machine evaluation |

#### 2.3.1 The form of a choice (= the same as an action in overview.md §6)

| type | Items | Content |
|---|---|---|
| discard | tile | A discard |
| riichi | tile | The discard that declares riichi. `open: true` for an open riichi |
| tsumo | — | A win by tsumo |
| ron | — | A win by ron (phase C) |
| chi / pon | tiles | Three tiles (including the called tile) |
| kan | kind, tiles | ankan / minkan / kakan |
| nuki | tile | A nuki |
| pass | — | Passing (C), or doing nothing in A (going on to B) |
| draw_declare | reason | A declaration such as nine terminals and honours |

Tiles are always numbers. Tile names are not held.

## 3 Verification
### 3.1 Alone
1. format / version; id agrees with the hash
2. evaluator.visibility is in the vocabulary. The names in metrics are unique; scope and kind are in the vocabulary; candidate values have higher_is_better; and there is **exactly one primary**
3. round and at of points[] ≥ 0; phase is in the vocabulary; actor is an integer
4. The keys of candidates[].values and estimates are declared names only, the scope fits the place, and the type fits kind (prob is 0 to 1; prob_vector has length M and sums to 1±1e-6; rank is a positive integer)
5. candidates contains exactly one choice equal to actual (type and tiles agree). best is in range and is the best by primary
6. loss is as defined and ≥ 0. If params.verdict exists, verdict is consistent with the thresholds
7. There are no two points with the same (round, at, phase, actor)

### 3.2 Cross-layer (with record, wall and ruleset)
8. The file of record.id can be read. The round exists, at is in range, and **the event at `at` fits the phase** (A/B → the actor's draw; C → another player's discard)
9. actual agrees with the next event of the record (A: the next is one of win / kan / nuki / riichi / draw_end, or, if there is none, the game goes on to B. B: the next is the actor's discard, with that tile. C: the next is the actor's chi / pon / kan / win, or another player's turn = pass). If it does not agree, it is an error
10. Each choice in candidates is contained in `legal_actions(ruleset, observe(record, round, at, actor))`. If not, it is an error (a kan after riichi among the candidates under a rule that forbids a kan changing the waits, a chi where chi is forbidden, and so on)
11. Whether an evaluator with visibility=actor / none depends on information it could not see is not verified (visibility is a statement to the reader)

## 4 File name
`{record id, 64 digits}_{evaluator.name}.annotation.json` (overview.md §4). If a file of the same name exists and the id of its content differs, saving fails instead of overwriting. To keep several versions side by side, put the version in name (`mortal-4-1`).

## 5 Relation to replays (record.parent)
A replayed game is a separate record, and its evaluation is a separate file. Decision points before the branch point refer to the evaluation of the original (they are not copied).

## 6 Examples of evaluators
- The bundled evaluator is `nm-waits` (visibility `actor`; for each discard, the value of a candidate is "the number of kinds of waiting tiles after the discard"; nmahjong/evaluate.py, layer5.md)
- `nm-basic`, which appears in the example of this document (visibility `full`, primary `win` = the win rate given that the wall is known), is an example to explain the form; no implementation is bundled. For 1-tile and 4-tile mahjong the true value can be obtained by exhaustive search. For 13 tiles and 4 players exhaustive search is not possible, so an external evaluator such as Mortal is connected through the mjai conversion
- Under rules with chips, `chips_ev` is written alongside
