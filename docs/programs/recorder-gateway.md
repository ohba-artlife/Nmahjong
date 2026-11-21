# The recorder and the gateway for players (nmahjong/recorder.py, nmahjong/gateway.py)

Parts that build a game while it is being played, checking as they go. Dealing the wall and running the round is the work of the game runner (dealer.md); the game runner uses these two.

```
    table ──(situation: the events visible from that seat + the list of actions that can be taken)──→ player
    table ←──(action: discard, riichi, kan, pon, chi, nuki, win, pass)── player
```

## 1. The recorder (Recorder)
It receives events one by one, checks each, and then adds it to the record.

```python
rec = Recorder(ruleset, tileset, players=[...], source={...})
rec.start_round(state, wall)      # state = {bakaze, kyoku, honba, kyotaku, oya, scores}. The deal and the first dora are added automatically
rec.push({"t": "draw", "who": 0, "tile": 52})
rec.push({"t": "discard", "who": 0, "tile": 52, "tsumogiri": True})
…
rec.end_round(result)             # result = {wins, draw, scores}
record = rec.finish()             # computes the settlement, attaches the id, verifies the whole record and returns it
```

What push checks:
- A draw: is it the next tile of the wall (when there is a wall)? Is a replacement tile at the position given by the ruleset?
- A discard, riichi, kan, pon, chi, nuki, win: is it among the legal actions of that seat at that moment (observe → legal_actions)?
- Chankan (a ron on the tile of an added kan or of a nuki): is the hand able to win and not furiten? A ron on the tile of a concealed kan only when the ruleset allows it (flow.kokushi_ankan_chankan) and the shape is kokushi musou
- Discarding or calling with a tile that is not in the hand; an event after the round has ended

What it does not check: a pass (it does not become an event), and the content of yaku and fu (judgement is judge.md). The movement of points and the settlement are checked by the verification of the whole record (finish).
A violation raises ValidationError. The offending event is not added (the state stays as before).

## 2. The gateway (Gateway)
It stands between the table (the recorder) and a player, a person or an AI. The form of the exchange is mjai (overview.md §6, design/observation.md).
The situation is a sequence of mjai events (other players' hands and draws are `"?"`) + `request_action`; the action is an mjai response (dahai / reach / chi / pon / daiminkan / ankan / kakan / nukidora / hora / none / ryukyoku).

```python
gw = Gateway(recorder, {0: player, 1: player, …})
action = gw.ask(seat, "A")        # sends the situation, checks the action that comes back and returns it (ValidationError or a default action if it is not a legal action)
gw.apply(seat, action)            # adds the action to the recorder (it becomes an event)
```

A player is anything that has `respond(msg)`. msg = `{"events": [events added since last time], "request": request_action}`; the return value is an mjai response. actor of the response and target of hora may be omitted (the gateway fills them in).

| Player | What it is |
|---|---|
| `FunctionPlayer(fn)` | A function inside the program |
| `ProcessPlayer(cmd)` | Another program. JSON is sent one line at a time to its standard input and a response is read as one line from its standard output (the same transport as mjai). An example is tests/data/gateway_bot.py |
| `ReplayPlayer(record)` | Answers as recorded (for checking) |

## 3. What was checked
- Test games (50 of N-tile mahjong; four-player and three-player games of 13-tile mahjong) give a record with the same id as the original, both when built again through the recorder and when played again through the gateway (tests/test_recorder.py, tests/test_gateway.py)
- An action that cannot be taken, a tile not in the hand, and an event after the round has ended are refused (same tests)
- When Tenhou game logs are placed, the same is checked on those games (tests/test_tenhou_logs.py)
