"""天鳳の牌譜を使う試験（試験 T16）。牌譜はこのリポジトリに同梱していないので、置いたときだけ動く（置き場所は tests/tenhou_logs.py）。

別の実装（天鳳）が作った対局と、このライブラリの山の再現・取り込み・検証・役と点の判定・進行が一致することを確かめる。
"""
import json
import re
import unittest
import xml.etree.ElementTree as ET

from nmahjong import (annotation as A, dealer as D, evaluate as E, gateway as GW, judge as J, record as REC, recorder as RC,
                      ruleset as R, tileset as TS, wall as W)
from nmahjong.tenhou import importer as I, json6 as J6, shuffle as TH

import tenhou_logs as TL

LOGS = TL.logs()
_cache = {}


def load(path):
    if path not in _cache:
        rec, walls = I.import_mjlog(path, source_ref=TL.ref_of(path))
        rs = R.find(id=rec["ruleset"]["id"])
        _cache[path] = (rec, walls, rs, TS.find(id=rs["tileset"]["id"]))
    return _cache[path]


def summary(rec, rs):
    """牌譜 1 件の期待値（expected.json の 1 項目）。牌譜の中身は含まない。"""
    wins = [w for rnd in rec["rounds"] for w in (rnd["result"].get("wins") or [])]
    return {"ruleset": rs["name"], "rounds": len(rec["rounds"]), "wins": len(wins),
            "draws": sum(1 for rnd in rec["rounds"] if rnd["result"].get("draw")),
            "win_points": [w["points"] for w in wins],
            "scores": rec["final"]["scores"], "settled": rec["final"]["settled"], "record_id": rec["id"]}


@unittest.skipUnless(LOGS, "天鳳の牌譜が無い（tests/tenhou_logs.py を参照）")
class TestTenhouLogs(unittest.TestCase):
    def each(self):
        for path in LOGS:
            with self.subTest(log=TL.ref_of(path)):
                yield (path,) + load(path)

    def test_TL1_import_and_validate(self):
        """T4-1：取り込んだ対局が検証を通る（警告なし）。"""
        for path, rec, walls, rs, ts in self.each():
            self.assertEqual(REC.validate(rec, rs, ts, {w["id"]: w for w in walls}), [])
            for w in walls:
                self.assertEqual(W.validate(w, ts), [])

    def test_TL2_expected_values(self):
        """牌譜の名前ごとの期待値（expected.json）と一致する。期待値の無い牌譜は飛ばす。"""
        exp = TL.expected()
        n = 0
        for path, rec, walls, rs, ts in self.each():
            e = exp.get(TL.ref_of(path))
            if e is None:
                continue
            self.assertEqual(json.loads(json.dumps(summary(rec, rs))), e)
            n += 1
        if exp and not n:
            self.skipTest("期待値のある牌譜が無い")

    def test_TL3_walls_match_the_log(self):
        """T6-1：種から作った山が、牌譜の配牌・全ツモ・嶺上・ドラ・カンドラ・サイコロと一致する（四麻）。"""
        for path in LOGS:
            with open(path, encoding="utf-8") as f:
                s = f.read()
            go = re.search(r'<GO type="(\d+)"', s)
            if go and int(go.group(1)) & 0x10:
                continue                                    # 三麻は取り込み（TL1）の中で突き合わせている
            ts = TS.find(name="mpsz")
            seed = re.search(r'SHUFFLE seed="([^"]+)"', s).group(1)
            rounds, cur = [], None
            for t in ET.fromstring(s):
                if t.tag == "INIT":
                    cur = {"init": t.attrib, "ev": []}
                    rounds.append(cur)
                elif cur is not None and (re.fullmatch(r"[TUVW]\d+", t.tag) or t.tag in ("N", "DORA")):
                    cur["ev"].append(t)
            with self.subTest(log=TL.ref_of(path)):
                self.assertTrue(rounds)
                for k, r in enumerate(rounds):
                    init = r["init"]
                    oya = int(init["oya"])
                    sv = list(map(int, init["seed"].split(",")))
                    w = W.build_tenhou(ts, seed, k, oya)
                    self.assertEqual(W.validate(w, ts), [])
                    order = w["order"]
                    for p in range(4):                       # 配牌：親から 13 枚ずつ
                        who = (oya + p) % 4
                        self.assertEqual(sorted(order[p * 13:(p + 1) * 13]), sorted(map(int, init[f"hai{who}"].split(","))), f"round {k} hands")
                    dead = order[136 - 14:]
                    self.assertEqual(dead[TH.NM1_DORA[0]], sv[5], f"round {k} dora")
                    _, dice = TH.tenhou_wall(seed, k)
                    self.assertEqual(list(dice), sv[3:5], f"round {k} dice")
                    pos = 52
                    nk = nd = 0
                    pending = False
                    for t in r["ev"]:
                        if t.tag == "N":
                            m = int(t.attrib["m"])
                            if (m & 0x4) == 0 and not (m & 0x8):
                                pending = True               # カン：次のツモは嶺上
                            continue
                        if t.tag == "DORA":
                            self.assertEqual(int(t.attrib["hai"]), dead[TH.NM1_KAN_DORA[nk]], f"round {k} kandora {nk}")
                            nk += 1
                            continue
                        v = int(t.tag[1:])
                        if pending:
                            exp = dead[TH.NM1_RINSHAN[nd]]
                            nd += 1
                            pending = False
                        else:
                            exp = order[pos]
                            pos += 1
                        self.assertEqual(v, exp, f"round {k} draw")
                    self.assertLessEqual(pos, 136 - 14)

    def test_TL4_judge_matches_every_win(self):
        """T11-1：全和了の役・符・翻・点が、天鳳の結果と一致する。"""
        n = 0
        for path, rec, walls, rs, ts in self.each():
            wm = {w["id"]: w for w in walls}
            for rnd in rec["rounds"]:
                for w in rnd["result"].get("wins") or []:
                    i = next(k for k, e in enumerate(rnd["events"]) if e["t"] == "win" and e["who"] == w["who"])
                    res = J.judge_win(rec, rnd["index"], i, rs, ts, wm)
                    self.assertIsNone(J.same_as_recorded(res, w, merge_dora=True), (rnd["index"], res, w["yaku"], w["fu"]))
                    n += 1
        self.assertGreater(n, 0)

    def test_TL5_dealer_gives_the_same_game(self):
        """T12-2・T12-3：同じ山・同じ判断で進行役に進めさせると、同じ進行・同じ結果になる（直接／接続口ごし）。"""
        for path, rec, walls, rs, ts in self.each():
            wm = {w["id"]: w for w in walls}
            d = D.replay_with_dealer(rec, rs, ts, wm)
            self.assertIsNone(D.differences(d.rc.rec, rec, merge_dora=True))
            d = D.replay_with_dealer(rec, rs, ts, wm, through_gateway=True)
            self.assertIsNone(D.differences(d.rc.rec, rec, merge_dora=True))

    def test_TL6_recorder_and_gateway_give_the_same_id(self):
        """T9-5・T9-7：出来事を 1 つずつ積み直しても、接続口ごしに打ち直しても、同じ id になる。"""
        for path, rec, walls, rs, ts in self.each():
            wm = {w["id"]: w for w in walls}
            self.assertEqual(RC.replay_record(rec, rs, ts, wm).rec["id"], rec["id"])
            r, gw = GW.replay_through_gateway(rec, rs, ts, wm)
            self.assertEqual(r.rec["id"], rec["id"])
            self.assertEqual(gw.faults, [])

    def test_TL7_every_action_is_legal_and_evaluation_validates(self):
        """T5：全判断点で実際の行動が合法手に含まれ（評価の検証が確かめる）、評価が検証を通る。"""
        for path, rec, walls, rs, ts in self.each():
            wm = {w["id"]: w for w in walls}
            ann = E.annotate(rec, rs, ts, wm)
            A.validate(ann, rec, rs, ts, wm)
            self.assertGreater(len(ann["points"]), 100)

    def test_TL8_tenhou_json_round_trip(self):
        """T6-8：天鳳 JSON に書き出して読み戻すと、同じ結果になる。"""
        for path, rec, walls, rs, ts in self.each():
            rec2 = J6.import_json(J6.export_json(rec, rs, ts, {w["id"]: w for w in walls}), source_ref="rt")
            self.assertEqual(len(rec2["rounds"]), len(rec["rounds"]))
            for a, b in zip(rec["rounds"], rec2["rounds"]):
                self.assertEqual(a["result"]["scores"], b["result"]["scores"], a["index"])
            self.assertEqual(rec2["final"]["scores"], rec["final"]["scores"])
            self.assertEqual(rec2["final"]["settled"], rec["final"]["settled"])


if __name__ == "__main__":
    import sys
    if sys.argv[1:2] == ["--expected"]:
        # 置いてある牌譜の期待値を書き出す（expected.json の元）
        print(json.dumps({TL.ref_of(p): summary(*[load(p)[i] for i in (0, 2)]) for p in LOGS}, ensure_ascii=False, indent=1))
    else:
        unittest.main()
