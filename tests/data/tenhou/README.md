# tests/data/tenhou — the place to put Tenhou game logs

Tenhou game logs (mjlog XML) are not bundled in this repository (they are not redistributed, under Tenhou's terms).
If you put logs here (with the extension `.xml` or `.mjlog`), `tests/test_tenhou_logs.py` runs. If you do not, that test is skipped and the other tests pass as they are.
To use another folder, point to it with the environment variable `NMAHJONG_TENHOU_LOGS`.

What that test confirms: the wall made from the seed agrees with the deal, the draws, the replacement tiles and the dora of the log; the imported record passes verification; yaku, fu and points of every win agree with Tenhou's results; and playing the game again through the game runner, the recorder and the gateway gives the same record.

## expected.json

Expected values per log name (the number of rounds, the numbers of wins and draws, the points of the wins, the final points and settlement, the id of the imported record). The content of the logs is not included. If you put a log of the same name, it is compared.

| Log name | Ruleset | Where to get it |
|---|---|---|
| `2019051522gm-00a9-0000-8c64c236` | tenhou-4p-hanchan-red | One of the logs contained in `paipuxmls.7z` of GitHub Releases v1.0.4 of Agony5757/mahjong |

The expected values of your own logs can be written out with `PYTHONPATH=. python3 tests/test_tenhou_logs.py --expected`.
