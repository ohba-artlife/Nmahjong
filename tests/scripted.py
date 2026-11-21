"""山を組んだ 1 局を、決めた手順どおりに進行役に進めさせる（試験用）。

実対局に出てこない場面（包、途中流局、延長の終わり方 など）を、公表されているルールの文と突き合わせるために使う。
牌は "123m 456p 789s E S W N P F C"（数牌は数字＋色、字牌は 1 文字。空白は読み飛ばす。赤は 0m 0p 0s）で書く。
"""
import re

from nmahjong import dealer as D, observe as O, ruleset as R, tileset as TS, wall as W

HONORS = "ESWNPFC"


def kinds(text):
    """"123m55p E" → ["1m","2m","3m","5p","5p","E"]。赤は "0m" → ("5m", red)。
    印つきの牌：金の 5 は "Gm"／"Gp"／"Gs"、白ポッチは "Q"、逆ポッチは "R"。"""
    out = []
    for part in re.findall(r"\d+[mps]|G[mps]|[ESWNPFCQR]", text.replace(" ", "")):
        if part in HONORS or part in ("Q", "R") or part[0] == "G":
            out.append(part)
        else:
            out.extend(d + part[-1] for d in part[:-1])
    return out


class Table:
    """1 つのルールで、山を組んだ局を進める卓。"""

    def __init__(self, ruleset, **change):
        rs = R.find(name=ruleset) if isinstance(ruleset, str) else ruleset
        self.rs, self.ts = rs, TS.find(id=rs["tileset"]["id"])
        self.norm = R.normalize(rs)
        self.M, self.N = self.norm["players"], self.norm["hand_size"]
        self.by = {}
        special = {"gold": lambda k: "G" + k[1], "pocchi": lambda k: "Q", "reverse_pocchi": lambda k: "R"}
        self.marked = {}                                   # 牌種 → 印つき（赤以外）の牌。印なしが無くなったときだけ使う
        for i, t in enumerate(self.ts["tiles"]):
            m = t.get("mark")
            if m in special:
                self.by.setdefault(special[m](t["kind"]), []).append(i)
                self.marked.setdefault(t["kind"], []).append(i)
            else:
                self.by.setdefault(("0" + t["kind"][1]) if m == "red" else t["kind"], []).append(i)

    # ---- 山 ----
    def _take(self, kind, used):
        """kind の牌を 1 枚取る（赤でないものを番号の大きい方から。無くなったら赤）。"""
        red = ("0" + kind[1]) if kind[0] == "5" and len(kind) == 2 else None
        for t in list(reversed(self.by.get(kind, []))) + list(self.by.get(red, [])) + list(self.marked.get(kind, [])):
            if t not in used:
                used.add(t)
                return t
        raise ValueError(f"{kind} がもう無い")

    def wall(self, oya, hands, draws="", dora=None, ura=None, rinshan="", kan_dora="", haitei=None):
        """hands：{席: 牌}（書かない席は余りから配る）。draws：ツモ順（親の第 1 ツモから）。dora・ura：表示牌。
        rinshan：嶺上牌を取る順。kan_dora：カンドラ表示牌をめくる順。書かなかった所は余りの牌で埋める。"""
        K, wr = len(self.ts["tiles"]), self.norm["wall_rules"]
        dead = wr["dead_wall"]
        order = [None] * K
        used = set()

        def put(pos, kind):
            order[pos] = self._take(kind, used)
        for p in range(self.M):
            seat = (oya + p) % self.M
            ks = kinds(hands.get(seat, ""))
            assert len(ks) in (0, self.N), (seat, len(ks))
            for i, k in enumerate(ks):
                put(p * self.N + i, k)
        base = self.M * self.N
        for i, k in enumerate(kinds(draws)):
            put(base + i, k)
        live_end = K - dead
        for name, val in (("dora_indicator", dora), ("ura_indicator", ura)):
            if val:
                put(live_end + wr[name][0], kinds(val)[0])
        for i, k in enumerate(kinds(rinshan)):
            put(live_end + wr["rinshan"][i], k)
        for i, k in enumerate(kinds(kan_dora)):
            put(live_end + wr["kan_dora"][i], k)
        if haitei:
            put(live_end - 1, kinds(haitei)[0])
        rest = [t for t in range(K) if t not in used]
        # 余り：字牌と端から先に手牌へ入らないよう、番号順のまま後ろから埋める（決まった並び）
        it = iter(rest)
        for i in range(K):
            if order[i] is None:
                order[i] = next(it)
        return W.build_observed(self.ts, order)

    # ---- 進行 ----
    def play(self, wall, script, state=None, **dealer_kw):
        """script：{席: [(種類, 牌 か None), …]}。その席に順に 1 つずつ「できるときにやる」。
        種類＝discard／riichi／open_riichi／tsumo／ron／pon／chi／kan／nuki／draw_declare／skip（和了れるときに 1 回見送る）。牌は kind（"5m" など。kan は種類を "ankan"／"kakan"／"minkan" と書ける）。
        書いていない判断は、自分の番はツモ切り（鳴いた直後は手牌の最後の牌）、他家の牌には見送り。
        戻り値は (result, info, 局, 進行役)。"""
        st = {"bakaze": "E", "kyoku": 1, "honba": 0, "kyotaku": 0, "oya": 0, "scores": [self.norm["settlement"]["start_points"]] * self.M}
        st.update(state or {})
        todo = {s: list(v) for s, v in script.items()}
        holder = {}

        def decide(seat, phase, at):
            return self._decide(holder["d"], todo, seat, phase, at)

        d = D.Dealer(self.rs, self.ts, decide=decide, **dealer_kw)
        holder["d"] = d
        result, info = d.play_round(st, wall)
        self.left = {s: v for s, v in todo.items() if v}
        return result, info, d.rc.rec["rounds"][-1], d

    def _decide(self, d, todo, seat, phase, at):
        ts = self.ts

        def kind_of(t):
            return O.kind_of(ts, t)

        def match(a, want):
            typ, k = want
            if typ in ("ankan", "kakan", "minkan"):
                return a["type"] == "kan" and a.get("kind") == typ and (k is None or kind_of(a["tiles"][0]) == k)
            if typ == "open_riichi":
                return a["type"] == "riichi" and bool(a.get("open")) and (k is None or kind_of(a["tile"]) == k)
            if a["type"] != typ or (typ == "riichi" and a.get("open")):
                return False
            if k is None:
                return True
            if typ in ("discard", "riichi", "nuki"):
                return kind_of(a["tile"]) == k
            if typ in ("pon", "kan"):
                return kind_of(a["tiles"][0]) == k
            if typ == "chi":
                return sorted(kind_of(x) for x in a["tiles"]) == sorted(kinds(k))
            return True

        legal = d._legal(seat, phase, at)
        ev = d._evs()[at] if at < len(d._evs()) else None
        if phase == "C" and ev is not None and ev["t"] in ("kan", "nuki") and ev["who"] != seat:
            # カン・抜きの牌へのロン（槍槓）を聞かれている
            kind = ev.get("kind") if ev["t"] == "kan" else "nuki"
            tile = ev["tile"] if ev["t"] == "nuki" else d._added_tile({"tiles": ev["tiles"]}, at) if kind == "kakan" else ev["tiles"][0]
            obs, _, _ = d.gw.legal(seat, "A", at)
            ok = O.can_rob(d.norm, ts, obs, kind, tile) and d._winnable(seat, ev["who"], tile)
            legal = ([{"type": "ron"}] if ok else []) + [{"type": "pass"}]
        q = todo.get(seat) or []
        if q and q[0][0] == "skip":                       # 和了れるのに見送る（1 回ぶん）
            if any(a["type"] in ("ron", "tsumo") for a in legal):
                q.pop(0)
                return {"type": "pass"}
        elif q:
            a = next((a for a in legal if match(a, q[0])), None)
            if a is not None:
                q.pop(0)
                return a
        if phase == "B":
            ds = [a for a in legal if a["type"] == "discard"]
            evs = d._evs()
            last = next((e for e in reversed(evs) if e["t"] == "draw" and e["who"] == seat), None)
            drawn = last["tile"] if last and evs.index(last) >= max((i for i, e in enumerate(evs) if e["t"] in ("pon", "chi") and e["who"] == seat), default=-1) else None
            return next((a for a in ds if a["tile"] == drawn), ds[-1] if ds else None)
        return {"type": "pass"}

    def game(self, wall, script, seed, state=None):
        """第 1 局だけ山と手順を決め、あとは全員ツモ切り・見送りで最後まで進めた対局 (record, walls)。
        JavaScript 版に同じ判断で進め直させて、同じ結果になるかを見るための材料（tools/gen_js_testdata.py）。"""
        todo = {s: list(v) for s, v in script.items()}
        holder = {}

        def decide(seat, phase, at):
            d = holder["d"]
            first = len(d.rc.rec["rounds"]) == 1
            return self._decide(d, todo if first else {}, seat, phase, at)

        d = D.Dealer(self.rs, self.ts, decide=decide)
        holder["d"] = d
        rec = d.play(lambda k, st: wall if k == 0 else W.build(self.ts, f"{seed}/{k}"))
        self.left = {s: v for s, v in todo.items() if v}
        return rec, list(d.walls.values())

    def next_state(self, d, state, result, info):
        st = {"bakaze": "E", "kyoku": 1, "honba": 0, "kyotaku": 0, "oya": 0}
        st.update(state)
        return d.next_state(st, result, info, 0)


# ---- 山を組んだ対局の一覧（Python の試験と、JavaScript 版との突き合わせの両方に使う）----
_PAO = {0: "123m 456m 678m 1p 1p 2s 3s", 1: "PP FF CC 22m 345p 6s 9s", 2: "P F 579m 57p 579s 1s 1s 1p", 3: "C 468m 468p 468s 9p 9p 9p"}
_PAO2 = {**_PAO, 1: "PP FF CC EEE W 2m 2m 6s"}
_PONS = [("pon", "P"), ("discard", "2m"), ("pon", "F"), ("discard", "2m"), ("pon", "C"), ("discard", "6s")]
_FEED = {2: [("discard", "P"), ("discard", "F")], 3: [("discard", "C")]}
_T4 = "tenhou-4p-hanchan-red"

SCENARIOS = [
    # (名前, ルール, 山の指定, 手順)
    ("pao-tsumo", _T4, dict(oya=0, hands=_PAO, draws="8s 8s 8s 7p 8p 8p 7m 7m 6p 9s"), {**_FEED, 1: _PONS + [("tsumo", None)]}),
    ("pao-ron", _T4, dict(oya=0, hands=_PAO, draws="8s 8s 8s 7p 8p 8p 7m 7m 9s"), {**_FEED, 1: _PONS + [("ron", None)]}),
    ("pao-compound-ron", _T4, dict(oya=0, hands=_PAO2, draws="8s 8s 8s 7p 8p 8p 7m 7m W"), {**_FEED, 1: _PONS + [("ron", None)]}),
    ("pao-ron-mleague", "mleague", dict(oya=0, hands=_PAO, draws="8s 8s 8s 7p 8p 8p 7m 7m 9s"), {**_FEED, 1: _PONS + [("ron", None)]}),
    ("four-riichi", _T4,
     dict(oya=0, hands={0: "123m 456m 789m 11p 23p", 1: "123p 456p 789p 11s 23s", 2: "123s 456s 789s EE 45m", 3: "SSS WWW NNN PP 56p"}, draws="F F C C"),
     {0: [("riichi", "F")], 1: [("riichi", "F")], 2: [("riichi", "C")], 3: [("riichi", "C")]}),
    ("three-ron", _T4,
     dict(oya=0, hands={0: "123m 456m 678m 11s 5p 9s", 1: "46p 123p 789p 22s 999m", 2: "46p 123s 456s 77s PPP", 3: "46p 789s 234m 88m FFF"}, draws="C"),
     {0: [("discard", "5p")], 1: [("ron", None)], 2: [("ron", None)], 3: [("ron", None)]}),
    ("double-ron", _T4,
     dict(oya=0, hands={0: "123m 456m 678m 11s 5p 9s", 1: "147m 258p 369s ESW P", 2: "46p 123s 456s 77s PPP", 3: "46p 789s 234m 88m FFF"}, draws="C"),
     {0: [("discard", "5p")], 2: [("ron", None)], 3: [("ron", None)]}),
    ("four-kans", _T4,
     dict(oya=0, hands={0: "1111m 2222m 3333m 5p", 1: "9999s 47m 258p 36s ES", 2: "47m 258p 36s ESW PFC", 3: "58m 369p 147s NN PP F"},
          draws="6p 7p", rinshan="7s 7s 8s 8s"),
     {0: [("ankan", "1m"), ("ankan", "2m"), ("ankan", "3m")], 1: [("ankan", "9s")]}),
    ("chankan-ippatsu", _T4,
     dict(oya=0, hands={0: "5p 147m 28p 369s EWS N", 2: "46p 123s 456s 77s 789m", 3: "55p 147m 28p 369s ES C"}, draws="9m 9p 9p F 0p"),
     {0: [("discard", "5p")], 3: [("pon", "5p"), ("discard", "C"), ("kakan", "5p")], 2: [("riichi", "F"), ("ron", None)]}),
    ("riichi-discard-ronned", _T4,
     dict(oya=0, hands={0: "123m 456m 789m 11p 23p", 1: "46p 123s 456s 77s PPP"}, draws="5p"), {0: [("riichi", "5p")], 1: [("ron", None)]}),
    ("3p-nuki-then-nine-terminals", "tenhou-3p",
     dict(oya=0, hands={0: "N 19m 258p 369s ESW 1p", 1: "19m 19p 19s ESW 2p 3p 4p 5s"}, draws="2s 4s P", rinshan="6s"),
     {0: [("nuki", "N")], 1: [("draw_declare", None)]}),
    ("3p-nuki-ron-on-north", "tenhou-3p",
     dict(oya=0, hands={0: "N N 123p 456p 789p PP", 2: "N 19m 258p 369s ESW 1p"}, draws="P 3s 4s", rinshan="6s"),
     {0: [("nuki", "N"), ("ron", None)], 2: [("discard", "N")]}),
]


def scenario_game(name):
    """SCENARIOS の 1 つを最後まで進めた対局 (record, walls, ruleset, tileset, やり残した手順)。"""
    _, ruleset, wall_kw, script = next(x for x in SCENARIOS if x[0] == name)
    t = Table(ruleset)
    rec, walls = t.game(t.wall(**wall_kw), script, seed="scenario/" + name)
    return rec, walls, t.rs, t.ts, t.left
