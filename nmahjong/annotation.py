"""評価（nmahjong-annotation 1.0）の id・ファイル名・検証（annotation.md §3：単独 1〜7、層またぎ 8〜10）。"""
import re
from typing import Dict, List, Optional, Tuple

from . import observe as O
from . import ruleset as R
from .canon import ValidationError, canonical_json, sha256_id, id_hex64

FORMAT = "nmahjong-annotation"
VERSION = "1.0"
VISIBILITY = ("full", "actor", "none")
SCOPES = ("candidate", "point")
KINDS = ("prob", "prob_vector", "value", "count", "rank")
PHASES = ("A", "B", "C")
VERDICTS = ("o", "d", "x")
ACTION_TYPES = tuple(R.VOCAB["action_types"])
_NAME = re.compile(r"^[a-z][a-z0-9_]*$")
_EVAL = re.compile(r"^[a-z0-9-]+$")


def compute_id(ann: dict) -> str:
    return sha256_id({k: v for k, v in ann.items() if k != "id"})


def filename(ann: dict) -> str:
    return f"{id_hex64(ann['record']['id'])}_{ann['evaluator']['name']}.annotation.json"


class _Ctx:
    def __init__(self):
        self.errs: List[str] = []
        self.warns: List[str] = []

    def err(self, m):
        self.errs.append(m)


def _num(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _check_value(c: _Ctx, q: str, kind: str, v, M: Optional[int]):
    if kind == "prob":
        if not (_num(v) and 0 <= v <= 1):
            c.err(f"{q}: prob は 0〜1")
    elif kind == "prob_vector":
        if not (isinstance(v, list) and all(_num(x) and 0 <= x <= 1 for x in v)):
            c.err(f"{q}: prob_vector は 0〜1 の配列"); return
        if M is not None and len(v) != M:
            c.err(f"{q}: prob_vector の長さ {len(v)} ≠ M {M}")
        if abs(sum(v) - 1) > 1e-6:
            c.err(f"{q}: prob_vector の合計 {sum(v)} ≠ 1")
    elif kind in ("value", "count"):
        if not _num(v):
            c.err(f"{q}: {kind} は数値")
    elif kind == "rank":
        if not (isinstance(v, int) and not isinstance(v, bool) and v >= 1):
            c.err(f"{q}: rank は 1 以上の整数")


def _check_action_shape(c: _Ctx, q: str, a, K: Optional[int]):
    if not isinstance(a, dict) or a.get("type") not in ACTION_TYPES:
        c.err(f"{q}.type が語彙外: {a.get('type') if isinstance(a, dict) else a!r}"); return
    t = a["type"]
    tiles = []
    if t in ("discard", "riichi", "nuki"):
        if not isinstance(a.get("tile"), int):
            c.err(f"{q}: {t} には tile")
        else:
            tiles.append(a["tile"])
    if t in ("chi", "pon"):
        if not (isinstance(a.get("tiles"), list) and len(a["tiles"]) == 3):
            c.err(f"{q}: {t} の tiles は 3 枚")
        else:
            tiles += a["tiles"]
    if t == "kan":
        if a.get("kind") not in R.VOCAB["kan_kinds"]:
            c.err(f"{q}: kan.kind が語彙外")
        if not (isinstance(a.get("tiles"), list) and len(a["tiles"]) == 4):
            c.err(f"{q}: kan の tiles は 4 枚")
        else:
            tiles += a["tiles"]
    if t == "draw_declare" and a.get("reason") not in R.VOCAB["draw_reasons"]:
        c.err(f"{q}: draw_declare.reason が語彙外")
    if K is not None:
        for x in tiles:
            if not (isinstance(x, int) and 0 <= x < K):
                c.err(f"{q}: 牌番号 {x!r} が 0〜{K-1} の外")


def validate(ann: dict, rec: Optional[dict] = None, rs: Optional[dict] = None, ts: Optional[dict] = None,
             walls: Optional[Dict[str, dict]] = None) -> List[str]:
    """単独検証は常に行う。rec（と rs・ts・walls）があれば層またぎ（8〜10）も行う。戻り値は警告。"""
    c = _Ctx()
    if not isinstance(ann, dict):
        raise ValidationError("annotation はオブジェクト")
    allowed = {"format", "version", "id", "record", "evaluator", "points"}
    for k in ann:
        if k not in allowed:
            c.err(f"未知の項目: {k}")
    if ann.get("format") != FORMAT:
        c.err("format が nmahjong-annotation ではない")
    if ann.get("version") != VERSION:
        c.err("version が 1.0 ではない")
    if ann.get("id") != compute_id(ann):
        c.err("id がハッシュと一致しない")
    if not (isinstance(ann.get("record"), dict) and isinstance(ann["record"].get("id"), str)):
        c.err("record.id が無い")
    M = R.normalize(rs)["players"] if rs else None
    K = len(ts["tiles"]) if ts else None

    # 2 evaluator
    ev = ann.get("evaluator")
    metrics: Dict[str, dict] = {}
    primary = None
    params = {}
    if not isinstance(ev, dict):
        c.err("evaluator が無い")
    else:
        for k in ev:
            if k not in ("name", "version", "visibility", "metrics", "params", "run_at"):
                c.err(f"evaluator に未知の項目: {k}")
        if not (isinstance(ev.get("name"), str) and _EVAL.match(ev["name"])):
            c.err("evaluator.name は [a-z0-9-]+")
        if not isinstance(ev.get("version"), str):
            c.err("evaluator.version は文字列")
        if ev.get("visibility") not in VISIBILITY:
            c.err("evaluator.visibility が語彙外")
        ms = ev.get("metrics")
        if not (isinstance(ms, list) and ms):
            c.err("evaluator.metrics は長さ 1 以上の配列")
        else:
            for i, m in enumerate(ms):
                q = f"evaluator.metrics[{i}]"
                if not isinstance(m, dict):
                    c.err(f"{q} はオブジェクト"); continue
                for k in m:
                    if k not in ("name", "scope", "kind", "higher_is_better", "primary", "unit"):
                        c.err(f"{q} に未知の項目: {k}")
                nm = m.get("name")
                if not (isinstance(nm, str) and _NAME.match(nm)):
                    c.err(f"{q}.name が不正"); continue
                if nm in metrics:
                    c.err(f"{q}.name {nm} が重複")
                if m.get("scope") not in SCOPES:
                    c.err(f"{q}.scope が語彙外")
                if m.get("kind") not in KINDS:
                    c.err(f"{q}.kind が語彙外")
                if m.get("scope") == "candidate":
                    if not isinstance(m.get("higher_is_better"), bool):
                        c.err(f"{q}: candidate 値には higher_is_better")
                    if m.get("kind") == "rank" and m.get("higher_is_better") is True:
                        c.err(f"{q}: rank は higher_is_better=false")
                    if m.get("primary"):
                        if primary is not None:
                            c.err("primary が 2 つ以上")
                        primary = nm
                elif m.get("primary"):
                    c.err(f"{q}: primary は candidate 値だけ")
                metrics[nm] = m
            if primary is None:
                c.err("primary の candidate 値がちょうど 1 つ必要")
        params = ev.get("params") if isinstance(ev.get("params"), dict) else {}
    verdict_cfg = params.get("verdict") if isinstance(params, dict) else None
    if verdict_cfg is not None and not (isinstance(verdict_cfg, dict) and _num(verdict_cfg.get("o")) and _num(verdict_cfg.get("d"))):
        c.err("evaluator.params.verdict は {o, d} の数値")
        verdict_cfg = None

    # 3〜7 points
    pts = ann.get("points")
    if not isinstance(pts, list):
        c.err("points は配列"); pts = []
    seen = set()
    for i, p in enumerate(pts):
        q = f"points[{i}]"
        if not isinstance(p, dict):
            c.err(f"{q} はオブジェクト"); continue
        for k in p:
            if k not in ("round", "at", "phase", "actor", "actual", "candidates", "estimates", "best", "loss", "verdict", "note"):
                c.err(f"{q} に未知の項目: {k}")
        for k in ("round", "at", "actor"):
            if not (isinstance(p.get(k), int) and p[k] >= 0):
                c.err(f"{q}.{k} は 0 以上の整数")
        if p.get("phase") not in PHASES:
            c.err(f"{q}.phase が語彙外")
        key = (p.get("round"), p.get("at"), p.get("phase"), p.get("actor"))
        if key in seen:
            c.err(f"{q}: 同じ (round, at, phase, actor) の点が 2 つ")
        seen.add(key)
        if "actual" not in p:
            c.err(f"{q}.actual が無い")
        else:
            _check_action_shape(c, f"{q}.actual", p["actual"], K)
        cands = p.get("candidates")
        if not (isinstance(cands, list) and cands):
            c.err(f"{q}.candidates は長さ 1 以上の配列"); continue
        pvals: List[Optional[float]] = []
        for j, cd in enumerate(cands):
            qq = f"{q}.candidates[{j}]"
            if not isinstance(cd, dict):
                c.err(f"{qq} はオブジェクト"); pvals.append(None); continue
            _check_action_shape(c, qq, cd, K)
            vals = cd.get("values")
            if not isinstance(vals, dict):
                c.err(f"{qq}.values が無い"); pvals.append(None); continue
            for nm, v in vals.items():
                m = metrics.get(nm)
                if m is None:
                    c.err(f"{qq}.values.{nm} は宣言されていない"); continue
                if m.get("scope") != "candidate":
                    c.err(f"{qq}.values.{nm} は point 値（estimates に置く）"); continue
                _check_value(c, f"{qq}.values.{nm}", m.get("kind"), v, M)
            pv = vals.get(primary) if primary else None
            pvals.append(pv if _num(pv) else None)
            if primary and not _num(pv):
                c.err(f"{qq}.values に primary {primary} が無い")
        est = p.get("estimates")
        if est is not None:
            if not isinstance(est, dict):
                c.err(f"{q}.estimates はオブジェクト")
            else:
                for nm, v in est.items():
                    m = metrics.get(nm)
                    if m is None:
                        c.err(f"{q}.estimates.{nm} は宣言されていない"); continue
                    if m.get("scope") != "point":
                        c.err(f"{q}.estimates.{nm} は candidate 値（values に置く）"); continue
                    _check_value(c, f"{q}.estimates.{nm}", m.get("kind"), v, M)
        # 5 actual が candidates に 1 つ
        if isinstance(p.get("actual"), dict):
            ak = O.action_key(p["actual"])
            hits = [j for j, cd in enumerate(cands) if isinstance(cd, dict) and O.action_key(cd) == ak]
            if len(hits) != 1:
                c.err(f"{q}: actual と同じ候補が {len(hits)} 個（1 個であること）")
            actual_idx = hits[0] if len(hits) == 1 else None
        else:
            actual_idx = None
        best = p.get("best")
        if not (isinstance(best, int) and 0 <= best < len(cands)):
            c.err(f"{q}.best が範囲外"); continue
        if primary and all(v is not None for v in pvals):
            hib = metrics[primary].get("higher_is_better", True)
            bestv = max(pvals) if hib else min(pvals)
            if pvals[best] != bestv:
                c.err(f"{q}.best={best} は primary {primary} で最良ではない")
            elif best != pvals.index(bestv):
                c.err(f"{q}.best は同点のうち最小の添字 {pvals.index(bestv)}")
            # 6 loss
            if actual_idx is not None:
                exp_loss = (pvals[best] - pvals[actual_idx]) if hib else (pvals[actual_idx] - pvals[best])
                loss = p.get("loss")
                if not _num(loss) or abs(loss - exp_loss) > 1e-9:
                    c.err(f"{q}.loss {loss} ≠ 定義 {exp_loss}")
                if verdict_cfg:
                    exp_v = "o" if exp_loss <= verdict_cfg["o"] else "d" if exp_loss <= verdict_cfg["d"] else "x"
                    if p.get("verdict") != exp_v:
                        c.err(f"{q}.verdict {p.get('verdict')!r} ≠ 閾値から {exp_v}")
        if verdict_cfg is None and "verdict" in p:
            c.err(f"{q}: params.verdict が無いのに verdict がある")
        if "verdict" in p and p["verdict"] not in VERDICTS:
            c.err(f"{q}.verdict が語彙外")
        if "note" in p and p["note"] is not None and not isinstance(p["note"], str):
            c.err(f"{q}.note は文字列か null")

    # 8〜10 層またぎ
    if rec is not None and not c.errs:
        if rec.get("id") != ann["record"]["id"]:
            c.err("record.id が渡された対局と違う")
        elif rs is None or ts is None:
            c.warns.append("ruleset／tileset が無いので合法手の照合（10）は省略")
        else:
            for i, p in enumerate(pts):
                q = f"points[{i}]"
                rnd = next((r for r in rec["rounds"] if r["index"] == p["round"]), None)
                if rnd is None:
                    c.err(f"{q}.round {p['round']} が対局に無い"); continue
                evs = rnd["events"]
                if not (0 <= p["at"] < len(evs)):
                    c.err(f"{q}.at が範囲外"); continue
                ph = O.phase_of(evs, p["at"], p["actor"])
                want = "A" if p["phase"] in ("A", "B") else "C"
                if ph is None or (want == "A" and ph not in ("A", "B")) or (want == "C" and ph != "C"):
                    c.err(f"{q}: at の event が phase {p['phase']} に合わない（{evs[p['at']]}）"); continue
                try:
                    obs = O.observe(rec, p["round"], p["at"], p["actor"], rs, ts, walls)
                    legal = O.legal_actions(rs, ts, obs, p["phase"])
                except ValidationError as e:
                    c.err(f"{q}: 局面を再生できない: {e}"); continue
                act = O.actual_action(rec, p["round"], p["at"], p["actor"], p["phase"])
                if act is None or O.action_key(act) != O.action_key(p["actual"]):
                    c.err(f"{q}.actual {p['actual']} が対局の次の event と一致しない（対局では {act}）")
                keys = {O.action_key(a) for a in legal}
                for j, cd in enumerate(p["candidates"]):
                    if O.action_key(cd) not in keys:
                        c.err(f"{q}.candidates[{j}] {cd.get('type')} は合法手に無い（X12）")
    if c.errs:
        raise ValidationError("; ".join(c.errs))
    return c.warns


def finalize(ann: dict) -> dict:
    ann["id"] = compute_id(ann)
    return ann
