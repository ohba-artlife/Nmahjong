# Evaluation (the numbers an AI gives to positions and actions) — why values are held this way

Policy: make it **a form to which values can be added according to the rule**. The kinds of numbers are not fixed.

## 1 Facts: the numbers existing services give

| Service | Per candidate | Position | Game | Aggregate | Source |
|---|---|---|---|---|---|
| Mortal (mjai-reviewer) | Q value; π (the softmax of Q; the probability that the AI chooses that action) | — | Φ (expected pt at the start of the round, weighted by Tenhou pt [90,45,0,−135] and the like); P (probabilities of final places 1 to 4) | Agreement rate, bad-move rate, Rating (the mean of normalised Q, squared, ×100; **the official FAQ says it "is not a reliable indicator"**) | [FAQ](https://github.com/Equim-chan/mjai-reviewer/blob/master/faq.md) |
| NAGA | A degree of recommendation 0–10000 per tile; decision lines for calls and riichi (30–70% is acceptable) | The tenpai rate of each player; probabilities of tsumo, deal-in, win, and the course of tenpai | Expected place (probabilities of places 1 to 4) | Agreement rate, similarity, bad-move rate (a recommendation below 5% is a bad move), NAGA score (discards only, out of 100) | [How to read the report (Japanese)](https://note.com/showtamu2001/n/n621ef5634771) |
| Mahjong AI Dojo | An evaluation value and a comparison of candidates (definition not public) | Shape, acceptance, value, safety, score situation (put into words) | — | — | [mjdojo.ai](https://mjdojo.ai/) |

## 2 Sorting out: numbers are of four kinds
| Kind | What it is a value of | Examples | Storage |
|---|---|---|---|
| A Value of an action | One per candidate | Q value, π, degree of recommendation, rank | **Required** (candidates[].values) |
| B Value of a position | An estimate that does not depend on the candidate | Win rate, deal-in rate, tenpai rate, each player's tenpai rate, number of accepted tiles | Optional (estimates) |
| C Value of a game | An estimate about the end of the game | Probabilities of places P₁..P_M, expected pt, expected external_points, the win rate when M=2 | Optional (estimates) |
| D Aggregate | Computed from A to C for people | Agreement rate, bad-move rate, NAGA score, Rating | **Not stored** (recomputed) |

## 3 What "can be added according to the rule" means
The content of an evaluation changes with the rule. Fixed item names are not enough.

| Rule / form | Values that become necessary |
|---|---|
| With chips | The **expected number of chips** per candidate (expectation of red tiles, ippatsu, ura dora). pt alone does not decide the line of play |
| With yakitori | The value of "winning once" → the weight of the win rate changes |
| Wareme | The rate of dealing in to the player whose payments are doubled |
| Place-based systems (M.League, Tenhou, Mahjong Soul) | Probabilities of places P, and expected external_points per system (the value of avoiding fourth place differs by rank) |
| A single round, M=1, M=2 | "Win rate" and "expected number of moves until a win" become the main indicators (probabilities of places mean little) |
| 1-tile and 4-tile mahjong | In practice where the wall is visible, the true value by exhaustive search (visibility full) can be given |
| Nuki dora, flowers | The value of the `nuki` candidate |
| A person's comment | Not numbers but text (note), and only the judgement o/d/x |

→ The evaluator **declares the names** of its values (`evaluator.metrics[]`), and numbers are placed **under the same names** in candidates, positions and games. The library verifies only clashes of names and the types; the evaluator is responsible for the meaning. Names in frequent use are listed in the vocabulary (vocab) as **recommended names** (`q`, `prob`, `preference`, `ev_pt`, `win`, `dealin`, `tenpai`, `rank_prob`, `chips_ev`, `moves_to_win`). If a new rule needs a new value, the evaluator only adds a name; no revision of the specification is needed.

## 4 The form of the container (as reflected in annotation.md)
```json
"evaluator": {
  "name": "nm-basic", "version": "0.1", "visibility": "full",
  "metrics": [
    {"name": "win",      "scope": "candidate", "kind": "prob",  "higher_is_better": true,  "primary": true},
    {"name": "chips_ev", "scope": "candidate", "kind": "count", "higher_is_better": true},
    {"name": "rank_prob","scope": "point",     "kind": "prob_vector"}
  ],
  "params": {"verdict": {"o": 0.0, "d": 0.02}}
},
"points": [{
  "round": 0, "at": 3, "phase": "B", "actor": 0,
  "actual": {"type": "discard", "tile": 108},
  "candidates": [
    {"type": "discard", "tile": 108, "values": {"win": 0.41, "chips_ev": 0.3}},
    {"type": "discard", "tile": 4,   "values": {"win": 0.45, "chips_ev": 0.1}}
  ],
  "estimates": {"rank_prob": [0.3, 0.3, 0.2, 0.2]},
  "best": 1, "loss": 0.04, "verdict": "x"
}]
```
- `metrics[]`: the declaration of the values the evaluator gives. `scope` ∈ candidate (A) / point (B and C); `kind` ∈ prob / prob_vector / value / count / rank; `primary` is the one that decides best and loss
- `candidates[].values`: declared names → numbers. Several named values instead of a single score
- `estimates`: declared values of point scope
- best / loss / verdict are defined on primary
- candidates is a subset of `legal_actions(ruleset, position)` (the function of observation.md). An illegal one is an error

## 5 What was decided
1. The evaluator declares the names of its values. The library looks only at types and clashes of names (it does not standardise meanings)
2. There is one primary (to make best and loss unique)

The definition of the form is in spec/annotation.md. The evaluator `nm-basic` in the example above (a win rate given that the wall is visible) is an example to explain the form; the bundled evaluator is `nm-waits` (programs/layer5.md). The survey is as of 2026-11-13.
