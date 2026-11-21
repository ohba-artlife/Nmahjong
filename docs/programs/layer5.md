# Parts of layer 5: step-by-step evaluation and the arena

The format of layer 5 (evaluation) is the annotation. Here are two programs on the side that makes it.

```
 4 record (in progress)                        5 annotation
 recorder ──each time one event is added──→ step-by-step evaluation LiveAnnotator ──→ one point at a time, on the spot (on_point)
     │                                              │
     ▼ the game closes                              ▼ finish
 record ─────────────────────────────────→ annotation (the same as one made all at once)

 players A, B, C … ──→ arena (runs many games with the game runner) ──→ table of results (average place, settlement, win rate, deal-in rate, a rough rating)
```

## 1. Step-by-step evaluation (LiveAnnotator in nmahjong/evaluate.py)

Each time an action arrives, that decision is evaluated. It does not wait for the game to end.

```python
from nmahjong import evaluate
live = evaluate.LiveAnnotator(rs, ts, on_point=lambda p: print(p["verdict"], p["loss"]))   # called each time one evaluation is made
live.attach(recorder)            # connect to the recorder (dealer.rc for the game runner)
… run the game (recorder.push / dealer.play) …
ann = live.finish(recorder.rec)  # after the game has closed, make the annotation file
```

- Without the recorder: call `live.update(rec, walls)` each time an event is added. The list of newly made evaluations is returned
- When an evaluation is made: when the action of that decision arrives (for a discard, when the discard event is added). For riichi it waits for the discard of the declaration tile
- The evaluator is the bundled `nm-waits` (for each discard it gives, per candidate, "the number of kinds of waiting tiles after the discard"; it does not look at whether there is a yaku). To add an evaluator, add a function of the same form as `evaluate.point_at`
- Command: `python3 -m nmahjong play RULESET --annotate [--verbose] [--out DIR]`

**What was checked**: the annotation made while feeding an existing game in one event at a time has the same id as the annotation made all at once after the game exists (`evaluate.annotate`) (the table below). Each evaluation arrives before the round closes.

## 2. The arena (nmahjong/arena.py)

It lets players play many games against each other and turns their strength into numbers.

```python
from nmahjong import arena, gateway, bots
res = arena.run(rs, ts, {"A": lambda: gateway.FunctionPlayer(bots.simple),
                         "B": lambda: gateway.ProcessPlayer(["python3", "my_ai.py"])}, games=20, seed="s1")
print(arena.format_table(res))
```

Command: `python3 -m nmahjong arena RULESET --entrant NAME=simple --entrant NAME='COMMAND' [--games N] [--seed S] [--no-mirror] [--out DIR]`

| What | How it is decided |
|---|---|
| One set | The same walls are played once per player, shifting the seats by one each time (to even out the luck of the deal among the players). `games` is the number of sets. `mirror=False` makes one set one game |
| More entrants than seats | Combinations of as many entrants as there are seats are run in turn |
| The same player in several seats | List it under different names (for example one of your own + three simple) |
| Table of results | Number of games, average place, breakdown of places, average final points, average settlement, win rate, deal-in rate and riichi rate (per round), a rough rating, the number of responses that were replaced |
| Rough rating | Starts at 1500; the places are split into wins and losses between pairs of players and moved by Elo (K=16). It changes with the order of the games, so it is only rough |
| Broken responses | Replaced with the default action (discard the drawn tile / pass) and play goes on; the number is counted (`strict=True` stops instead) |
| Reproduction | Walls are made from a seed. The same seed and the same players give the same table |

**What is not here**: staying connected and finding opponents (matching), storing users and their results, managing the time of games. These are the work of a server and are outside the library. The arena goes as far as "running the decided number of games and aggregating".

**About evaluators that measure strength**: an evaluator that turns the quality of each single decision into a number (one that gives a win rate or an expected place) needs a strong reference (exhaustive search, or a trained AI). Only `nm-waits` is bundled. Strength itself is measured by the results of the arena (average place, settlement).

## 3. What was checked

| What | Compared with | Result |
|---|---|---|
| Step-by-step evaluation = evaluation made all at once | 1,005 real Tenhou games; N-tile mahjong: 1,500 games of 4 tiles, 1,500 of 1 tile, 20 played by people | All the same ids (516,328 evaluated points) |
| Arena: the same seed gives the same table; the sum of the settlement is 0; the records made pass verification | The bundled players | tests/test_layer5.py |
| Arena: a player that aims to win is above a player that does nothing | simple against tsumogiri | Same test |
| A player that is another program; a broken player | Same | Same test |
