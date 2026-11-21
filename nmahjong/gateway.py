"""打ち手の接続口（overview.md §0 のＡ「状況と行動」）。卓（記録係）と、人・AI の打ち手の間に立つ。

    卓 ──（状況：その席から見える出来事＋打てる手の一覧）──→ 打ち手
    卓 ←──（行動：打牌・立直・カン・ポン・チー・抜き・和了・見送り）── 打ち手

やり取りの形は mjai（observation.md）。状況は mjai の出来事の列（他家の手牌・ツモは "?"）＋ request_action、
行動は mjai の応答（dahai／reach／chi／pon／daiminkan／ankan／kakan／nukidora／hora／none／ryukyoku）。

    gw = Gateway(recorder, {0: 打ち手, 1: 打ち手, …})
    action = gw.ask(seat, "A")          # 状況を送り、返ってきた行動を確かめて返す（合法手に無ければ ValidationError か既定の行動）
    gw.apply(seat, action)              # 行動を記録係に積む（出来事になる）

打ち手は respond(msg) を持つもの。msg ＝ {"events": [前回から増えた出来事], "request": request_action（"actor"＝応答する席 を足してある）}、戻り値＝ mjai の応答。
応答の actor と、hora の target は省いてよい（接続口が補う）。
- FunctionPlayer(fn)：プログラムの中の関数
- ProcessPlayer(cmd)：別のプログラム。標準入力に JSON を 1 行ずつ送り、標準出力から応答を 1 行読む（mjai と同じ運び方）
- ReplayPlayer(record)：記録どおりに答える（確認用）

山を配る・局を進める・和了の役と符を出すのは、この接続口の役目ではない（4 層の進行役・判定）。
"""
import json
import subprocess
from typing import Callable, Dict, List, Optional

from . import mjai as MJ, observe as O
from .canon import ValidationError


class FunctionPlayer:
    """respond を関数で与える打ち手。wants_events=False なら出来事の列を作らずに request だけ渡す（速い）。"""

    def __init__(self, fn: Callable[[dict], dict], wants_events: bool = True):
        self.fn = fn
        self.wants_events = wants_events

    def respond(self, msg: dict) -> dict:
        return self.fn(msg)

    def notify(self, events: List[dict]) -> None:
        pass

    def close(self) -> None:
        pass


class ProcessPlayer:
    """別プログラムの打ち手。出来事と request_action を 1 行 1 JSON で標準入力に送り、応答を 1 行読む。"""
    wants_events = True

    def __init__(self, cmd: List[str]):
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, encoding="utf-8", bufsize=1)

    def _send(self, obj: dict) -> None:
        try:
            self.proc.stdin.write(json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n")
            self.proc.stdin.flush()
        except OSError:
            raise ValidationError("打ち手のプログラムが終わっていて、送れない")

    def notify(self, events: List[dict]) -> None:
        for e in events:
            self._send(e)

    def respond(self, msg: dict) -> dict:
        self.notify(msg.get("events") or [])
        self._send(msg["request"])
        line = self.proc.stdout.readline()
        if not line:
            raise ValidationError("打ち手のプログラムが応答せずに終わった")
        try:
            return json.loads(line)
        except ValueError:
            raise ValidationError(f"打ち手の応答が JSON ではない: {line[:80]!r}")

    def close(self) -> None:
        try:
            self.proc.stdin.close()
            self.proc.wait(timeout=5)
        except Exception:
            self.proc.kill()
            self.proc.wait()
        self.proc.stdout.close()


class ReplayPlayer:
    """出来上がった対局の、その席の判断を記録どおりに答える打ち手（確認用）。出来事の列は見ない。"""
    wants_events = False

    def __init__(self, record: dict, ts: dict, seat: int):
        self.record, self.ts, self.seat = record, ts, seat

    def notify(self, events: List[dict]) -> None:
        pass

    def close(self) -> None:
        pass

    def respond(self, msg: dict) -> dict:
        ctx = msg["context"]                      # {"round", "at", "phase"}：卓が付ける。記録のどの時点の判断か
        act = O.actual_action(self.record, ctx["round"], ctx["at"], self.seat, ctx["phase"])
        if act is None:
            raise ValidationError(f"記録にこの判断点が無い（round {ctx['round']} at {ctx['at']} seat {self.seat} {ctx['phase']}）")
        return action_to_mjai(act, self.ts, self.seat, msg["obs"])


def action_to_mjai(a: dict, ts: dict, seat: int, obs: dict) -> dict:
    """行動（annotation 2.3.1 の形）→ mjai の応答。request_action の possible_actions と同じ形に actor を足したもの。"""
    one = MJ.request_action(obs, [a], ts, "x")["possible_actions"]
    if not one:
        raise ValidationError(f"mjai にできない行動: {a}")
    r = dict(one[0])
    r["actor"] = seat
    if r["type"] == "hora":
        ld = obs.get("last_discard")
        r["target"] = seat if a["type"] == "tsumo" else (ld["who"] if ld else None)
    return r


class Gateway:
    def __init__(self, recorder, players: Dict[int, object], strict: bool = True):
        """strict=True：合法手に無い応答・壊れた応答は ValidationError。False：既定の行動（ツモ切り／見送り）に置き換え、faults に残す。"""
        self.rc = recorder
        self.players = players
        self.strict = strict
        self.faults: List[str] = []
        self.requests = 0
        self._sent = {s: 0 for s in players}      # 席ごとに、送り終えた mjai の出来事の数
        self._req_n = 0

    # ---- 状況を作る ------------------------------------------------------------------------
    def _events_for(self, seat: int) -> List[dict]:
        """その席にまだ送っていない出来事（他家の手牌・ツモは伏せる）。局の途中では end_kyoku／end_game を付けない。"""
        rec = self.rc.rec
        if not rec["rounds"]:
            return []
        evs = MJ.to_mjai(rec, self.rc.rs, self.rc.ts, self.rc.walls, seat=seat)
        while evs and evs[-1]["type"] in ("end_game", "end_kyoku") and (evs[-1]["type"] == "end_game" or "result" not in rec["rounds"][-1]):
            evs.pop()
        new = evs[self._sent[seat]:]
        self._sent[seat] = len(evs)
        return new

    def flush(self) -> None:
        """判断を求めずに、たまっている出来事だけを全員に送る（局の終わりなど）。"""
        for seat, p in self.players.items():
            if getattr(p, "wants_events", True):
                try:
                    p.notify(self._events_for(seat))
                except ValidationError as e:
                    if self.strict:
                        raise
                    self.faults.append(f"seat {seat} へ送れない: {e}")

    def legal(self, seat: int, phase: str, at: Optional[int] = None):
        rnd = self.rc.rec["rounds"][-1]
        if at is None:
            at = len(rnd["events"]) - 1
        obs = O.observe(self.rc.rec, rnd["index"], at, seat, self.rc.rs, self.rc.ts, self.rc.walls)
        return obs, O.legal_actions(self.rc.rs, self.rc.ts, obs, phase=phase), at

    # ---- 判断を求める ----------------------------------------------------------------------
    def ask(self, seat: int, phase: str, at: Optional[int] = None, time: Optional[dict] = None, legal: Optional[List[dict]] = None) -> dict:
        """seat に状況を送り、行動を受け取って返す（annotation 2.3.1 の形）。phase：A＝ツモ後の宣言、B＝打牌、C＝他家の打牌への反応。
        legal：打てる手を呼ぶ側で決めて渡す（進行役が、役の無い和了を除く・槍槓のロンを足すとき）。省くと legal_actions の結果。"""
        obs, legal0, at = self.legal(seat, phase, at)
        legal = legal0 if legal is None else legal
        if not legal:
            raise ValidationError(f"seat {seat} に求める判断が無い（phase {phase}）")
        p = self.players[seat]
        self._req_n += 1
        rnd = self.rc.rec["rounds"][-1]
        req = MJ.request_action(obs, legal, self.rc.ts, f"{rnd['index']}-{at}-{seat}-{phase}-{self._req_n}", time)
        req["actor"] = seat                       # 応答する席。別プログラムの打ち手が自分の席を知る手がかり
        msg = {"request": req, "obs": obs, "context": {"round": rnd["index"], "at": at, "phase": phase},
               "events": self._events_for(seat) if getattr(p, "wants_events", True) else []}
        self.requests += 1
        try:
            resp = p.respond(msg)
            if not isinstance(resp, dict):
                raise ValidationError("応答が JSON のオブジェクトではない")
            resp = dict(resp)
            resp.setdefault("actor", seat)
            if resp.get("type") == "hora" and "target" not in resp:      # 省かれたら局面から補う（A＝ツモ和了、C＝ロン）
                ld = obs.get("last_discard")
                resp["target"] = seat if phase == "A" or not ld else ld["who"]
            action = MJ.from_mjai_action(resp, self.rc.ts, obs)
            if action.get("type") in ("tsumo", "ron"):                   # 和了の種類は、いま打てるほうに合わせる（槍槓・抜きへのロンは直前の打牌者が自分のことがある）
                can = {a["type"] for a in legal} & {"tsumo", "ron"}
                if len(can) == 1:
                    action["type"] = next(iter(can))
            if action.get("type") == "riichi" and "tile" not in action:
                raise ValidationError("立直の応答には切る牌（pai か tile）が要る")
            if self.rc._key(action) not in {self.rc._key(a) for a in legal}:
                raise ValidationError(f"seat {seat} の応答 {resp} は打てる手に無い")
            return action
        except ValidationError as e:
            if self.strict:
                raise
            self.faults.append(f"round {rnd['index']} at {at} seat {seat} {phase}: {e}")
            return default_action(obs, legal, phase)

    # ---- 行動を出来事にして記録係に積む ------------------------------------------------------
    def apply(self, seat: int, action: dict, at: Optional[int] = None) -> List[dict]:
        """行動 → 出来事（1 つか 2 つ）を記録係に積む。見送りは何も積まない。戻り値は積んだ出来事。at は ask に渡したのと同じ時点。"""
        rnd = self.rc.rec["rounds"][-1]
        obs = O.observe(self.rc.rec, rnd["index"], len(rnd["events"]) - 1 if at is None else at, seat, self.rc.rs, self.rc.ts, self.rc.walls)
        t = action["type"]
        ld = obs.get("last_discard")
        evs: List[dict] = []
        if t == "pass":
            return evs
        if t == "discard":
            evs.append({"t": "discard", "who": seat, "tile": action["tile"], "tsumogiri": action["tile"] == obs.get("drawn")})
        elif t == "riichi":
            r = {"t": "riichi", "who": seat}
            if action.get("open"):
                r["open"] = True
            evs.append(r)
            evs.append({"t": "discard", "who": seat, "tile": action["tile"], "tsumogiri": action["tile"] == obs.get("drawn"), "riichi": True})
        elif t in ("chi", "pon"):
            evs.append({"t": t, "who": seat, "tiles": sorted(action["tiles"]), "from": ld["who"]})
        elif t == "kan":
            e = {"t": "kan", "who": seat, "kind": action["kind"], "tiles": sorted(action["tiles"])}
            if action["kind"] == "minkan":
                e["from"] = ld["who"]
            evs.append(e)
        elif t == "nuki":
            evs.append({"t": "nuki", "who": seat, "tile": action["tile"]})
        elif t == "tsumo":
            evs.append({"t": "win", "who": seat, "from": seat, "tile": obs.get("drawn")})
        elif t == "ron":
            evs.append({"t": "win", "who": seat, "from": ld["who"], "tile": ld["tile"]})
        elif t == "draw_declare":
            evs.append({"t": "draw_end", "reason": action.get("reason")})
        else:
            raise ValidationError(f"積めない行動: {action}")
        done = 0
        try:
            for e in evs:
                self.rc.push(e)
                done += 1
        except ValidationError:
            del rnd["events"][len(rnd["events"]) - done:]        # 2 つ組（立直＋打牌）の途中で断られたら、積んだ分も戻す
            self.rc._riichi_at = None
            raise
        return evs

    def close(self) -> None:
        for p in self.players.values():
            p.close()


def default_action(obs: dict, legal: List[dict], phase: str) -> dict:
    """応答が無い・壊れている・打てない手だったときの既定の行動：打牌ならツモ切り（できなければ候補の先頭）、それ以外は見送り。"""
    if phase == "B":
        d = obs.get("drawn")
        return next((a for a in legal if a["type"] == "discard" and a["tile"] == d), legal[0])
    return next((a for a in legal if a["type"] == "pass"), legal[0])


def replay_through_gateway(rec: dict, rs: dict, ts: dict, walls: Optional[Dict[str, dict]] = None,
                           players: Optional[Dict[int, object]] = None, strict: bool = True):
    """出来上がった対局を、接続口ごしに打ち直す（確認用）。山から出る出来事（ツモ・カンドラ・流局・切断の印）は記録から、
    打ち手の判断は全部、接続口が状況を送って受け取った応答から積む。戻り値は (記録係, 接続口)。記録係の .rec が積み直した対局。"""
    import copy
    from . import recorder as RC, ruleset as R
    M = R.normalize(rs)["players"]
    r = RC.Recorder(rs, ts, players=copy.deepcopy(rec["players"]), source=copy.deepcopy(rec["source"]), parent=copy.deepcopy(rec.get("parent")))
    if players is None:
        players = {s: ReplayPlayer(rec, ts, s) for s in range(M)}
    gw = Gateway(r, players, strict=strict)
    INFO = ("abort", "dora")
    for rnd in rec["rounds"]:
        wall = (walls or {}).get(rnd["wall"]["id"]) if rnd.get("wall") else None
        evs = rnd["events"]
        dora = next((e["tile"] for e in evs[:3] if e["t"] == "dora"), None)
        cur = r.start_round(rnd["state"], wall, dora=dora)
        if [e["t"] for e in evs[:len(cur["events"])]] != [e["t"] for e in cur["events"]]:
            cur["events"] = [copy.deepcopy(evs[0])]
        i = len(cur["events"])
        ri = rnd["index"]

        def anchor():
            a = len(cur["events"]) - 1
            while a > 1 and cur["events"][a]["t"] in INFO:
                a -= 1
            return a

        def ask_reactions(dat, i):
            """打牌（時点 dat）への反応を、打牌者の次の席から順に聞く。記録の次の出来事と合う応答だけを積み、積んだ出来事の数を返す。"""
            frm = cur["events"][dat]["who"]
            n_total = 0
            for k in range(1, M):
                seat = (frm + k) % M
                if any(x["t"] == "win" and x["who"] == seat for x in cur["events"][dat + 1:]):
                    continue
                obs, legal, _ = gw.legal(seat, "C", dat)
                if all(x["type"] == "pass" for x in legal):
                    continue
                a = gw.ask(seat, "C", dat)
                nxt = evs[i + n_total] if i + n_total < len(evs) else None
                want = None
                if nxt is not None and nxt.get("who") == seat:
                    if nxt["t"] == "win" and nxt["from"] != seat:
                        want = "ron"
                    elif nxt["t"] in ("chi", "pon"):
                        want = nxt["t"]
                    elif nxt["t"] == "kan" and nxt.get("kind") == "minkan":
                        want = "kan"
                if a["type"] == "pass" or a["type"] != want:
                    continue                         # 見送り、または優先順位が上の席の行動に負けた応答
                n = len(gw.apply(seat, a, dat))
                _same(cur["events"][-n:], evs[i + n_total:i + n_total + n], ri, i + n_total)
                n_total += n
                if a["type"] != "ron":
                    break
            return n_total

        while i < len(evs):
            e = evs[i]
            t = e["t"]
            at = anchor()
            last = cur["events"][at]
            if t in ("dora", "abort"):
                r.push(e)
                i += 1
                continue
            if t == "win" and e["from"] != e["who"] and last["t"] in ("kan", "nuki"):
                r.push(e)                            # 槍槓・抜きへのロンは合法手の一覧に無い（記録係も警告で通す）
                i += 1
                continue
            if last["t"] in ("discard", "win") and t != "draw_end" or (t == "draw_end" and last["t"] == "discard"):
                # 直前が打牌：他家の反応（C）を先に聞く。誰も動かなければ、山からのツモ・流局を積む
                dat = at if last["t"] == "discard" else max(k for k in range(at) if cur["events"][k]["t"] == "discard")
                n = ask_reactions(dat, i)
                if n:
                    i += n
                    continue
                if t in ("draw", "draw_end"):
                    r.push(e)
                    i += 1
                    continue
                raise ValidationError(f"round {ri} events[{i}]: 記録の {t}（seat {e.get('who')}）を、どの席の応答からも作れなかった")
            if t == "draw" or (t == "draw_end" and e.get("reason") != "nine_terminals"):
                r.push(e)                            # 嶺上のツモ、途中流局など：卓の側の出来事
                i += 1
                continue
            if last["t"] == "draw" or last["t"] in ("chi", "pon"):
                seat = last["who"]
                if e.get("who", seat) != seat:
                    raise ValidationError(f"round {ri} events[{i}]: seat {seat} の番に seat {e.get('who')} の {t}")
                n = 0
                if last["t"] == "draw" and any(x["type"] != "pass" for x in gw.legal(seat, "A", at)[1]):
                    a = gw.ask(seat, "A", at)        # ツモった席に、できる宣言があれば聞く（A）。見送りなら打牌（B）を聞く
                    if a["type"] != "pass":
                        n = len(gw.apply(seat, a, at))
                if not n:
                    a = gw.ask(seat, "B", at)
                    n = len(gw.apply(seat, a, at))
                _same(cur["events"][-n:], evs[i:i + n], ri, i)
                i += n
                continue
            raise ValidationError(f"round {ri} events[{i}]: {last['t']} のあとの {t} を扱えない")
        r.end_round(rnd["result"])
        gw.flush()
    extra = {k: copy.deepcopy(v) for k, v in rec.items() if k not in ("format", "version", "id", "source", "ruleset", "players", "end", "parent", "rounds", "final")}
    r.finish(final=copy.deepcopy(rec["final"]), end=rec["end"], **extra)
    gw.flush()
    return r, gw


def _same(got: List[dict], want: List[dict], ri: int, i: int) -> None:
    if got != want:
        raise ValidationError(f"round {ri} events[{i}]: 接続口ごしに積んだ出来事 {got} が記録 {want} と違う")
