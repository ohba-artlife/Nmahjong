"""接続口の確認用の打ち手（別プログラム）。標準入力から 1 行 1 JSON を読み、request_action が来たら応答を 1 行返す。
打ち方：和了できるなら和了、打牌はツモ切り（できなければ候補の先頭）、それ以外は見送り。"""
import json
import sys

seen = []
drawn = None
for line in sys.stdin:
    m = json.loads(line)
    if m["type"] != "request_action":
        seen.append(m["type"])
        if m["type"] == "tsumo" and m.get("pai") != "?":
            drawn = m.get("tile")
        continue
    acts = m["possible_actions"]
    pick = next((a for a in acts if a["type"] == "hora"), None)
    if pick is None:
        ds = [a for a in acts if a["type"] == "dahai"]
        pick = next((a for a in ds if a.get("tile") == drawn), ds[0] if ds else {"type": "none"})
    pick = dict(pick)
    pick["seen"] = len(seen)
    sys.stdout.write(json.dumps(pick) + "\n")
    sys.stdout.flush()
