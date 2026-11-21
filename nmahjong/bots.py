"""同梱の簡単な打ち手（進行役・接続口の動作確認と、対戦相手の最低線）。どれも mjai の応答を返す関数で、
gateway.FunctionPlayer に渡して使う。別プログラムとして動かすときは `python3 -m nmahjong.bots simple`（標準入力に 1 行 1 JSON）。

    tsumogiri   何もしない：ツモ切り、見送り
    simple      和了れるなら和了、立直できるなら立直、打牌は孤立した牌から。鳴かない
"""
import json
import sys
from typing import Callable, Dict, List

_ORDER = [f"{n}{s}" for s in "mps" for n in range(1, 10)] + ["E", "S", "W", "N", "P", "F", "C"]


def tsumogiri(msg: dict) -> dict:
    acts = msg["request"]["possible_actions"]
    ds = [a for a in acts if a["type"] == "dahai"]
    if ds:
        drawn = (msg.get("obs") or {}).get("drawn", msg.get("drawn"))
        return next((a for a in ds if a.get("tile") == drawn), ds[-1])
    return {"type": "none"}


def _isolation(kind: str, kinds: List[str]) -> int:
    """小さいほど孤立している（同じ牌・隣の牌が手に少ない）。"""
    same = kinds.count(kind) - 1
    if len(kind) != 2:
        return same * 4 + 1
    n, s = int(kind[0]), kind[1]
    near = sum(kinds.count(f"{n + d}{s}") for d in (-1, 1) if 1 <= n + d <= 9)
    far = sum(kinds.count(f"{n + d}{s}") for d in (-2, 2) if 1 <= n + d <= 9)
    return same * 4 + near * 2 + far + (2 if 2 <= n <= 8 else 1)


def _plain(pai: str) -> str:
    """赤牌の印（5mr の r）を外した牌種。赤も同じ牌種として数える。"""
    return pai[:2] if len(pai) == 3 and pai.endswith("r") else pai


def simple(msg: dict) -> dict:
    acts = msg["request"]["possible_actions"]
    for t in ("hora", "reach"):
        a = next((a for a in acts if a["type"] == t), None)
        if a is not None:
            return a
    ds = [a for a in acts if a["type"] == "dahai"]
    if ds:
        kinds = [_plain(a["pai"]) for a in ds]
        return min(reversed(ds), key=lambda a: _isolation(_plain(a["pai"]), kinds))
    return {"type": "none"}


BOTS: Dict[str, Callable[[dict], dict]] = {"tsumogiri": tsumogiri, "simple": simple}


def main(argv=None) -> int:
    """別プログラムとして：出来事と request_action を標準入力から 1 行ずつ読み、request_action に応答を 1 行返す。"""
    argv = sys.argv[1:] if argv is None else argv
    bot = BOTS[argv[0] if argv else "simple"]
    drawn = None
    for line in sys.stdin:
        m = json.loads(line)
        if m.get("type") == "tsumo" and m.get("pai") != "?":
            drawn = m.get("tile")
        if m.get("type") != "request_action":
            continue
        sys.stdout.write(json.dumps(bot({"request": m, "drawn": drawn}), ensure_ascii=False) + "\n")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
