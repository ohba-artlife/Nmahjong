"""対局 record（nmahjong-record 1.0）— 検証・id。仕様 record.md、層またぎ overview.md §5（X4〜X10）。"""
from typing import Dict, List, Optional, Tuple

from . import ruleset as R, scoring as S, tileset as TS, wall as W
from .canon import ValidationError, id_hex64, sha256_id

FORMAT = "nmahjong-record"
VERSION = "1.0"
EVENT_TYPES = {"deal", "dora", "draw", "discard", "chi", "pon", "kan", "riichi", "nuki", "win", "draw_end", "abort", "chombo"}
TOP_KEYS = {"format", "version", "id", "source", "ruleset", "venue", "device", "event", "players", "started_at", "ended_at",
            "end", "parent", "rounds", "final", "meta"}


def compute_id(rec: dict) -> str:
    return sha256_id({k: v for k, v in rec.items() if k != "id"})


def filename(rec: dict, rs: dict) -> str:
    return f"{rs['tileset']['name']}_{id_hex64(rec['id'])}.record.json"


class Ctx:
    def __init__(self):
        self.errs: List[str] = []
        self.warns: List[str] = []

    def err(self, m):
        self.errs.append(m)

    def warn(self, m):
        self.warns.append(m)


def validate(rec: dict, rs: Optional[dict] = None, ts: Optional[dict] = None, walls: Optional[Dict[str, dict]] = None,
             search_dirs=()) -> List[str]:
    """record.md §4 ＋ X4〜X8、X10。walls は {wall.id: wall}。戻り値は警告、エラーは ValidationError。"""
    c = Ctx()
    if rec.get("format") != FORMAT:
        c.err(f"format が {FORMAT} ではない")
    if rec.get("version") != VERSION:
        c.err(f"version が {VERSION} ではない")
    for k in rec:
        if k not in TOP_KEYS:
            c.err(f"{k}: 未知の項目")
    try:
        id_hex64(rec.get("id", ""))
        if rec["id"] != compute_id(rec):
            c.err("id が内容のハッシュと一致しない")
    except ValidationError as e:
        c.err(str(e))
    src = rec.get("source")
    if not isinstance(src, dict) or src.get("kind") not in R.VOCAB["source_kinds"] or not isinstance(src.get("from"), str):
        c.err("source は {kind, from, ref}")
    if rec.get("end") not in R.VOCAB["record_end"]:
        c.err(f"end が語彙外: {rec.get('end')!r}")
    # ruleset
    rref = rec.get("ruleset")
    norm = None
    if not isinstance(rref, dict) or "id" not in rref:
        c.err("ruleset が {name, id} ではない")
    else:
        if rs is None:
            try:
                rs = R.find(id=rref["id"], search_dirs=search_dirs)
            except ValidationError:
                c.warn("ルールが見つからないため層またぎ検証は未実施")
        if rs is not None:
            if rs["id"] != rref["id"]:
                c.err("ruleset.id が渡されたルールと一致しない")
            norm = R.normalize(rs)
            if ts is None:
                try:
                    ts = TS.find(id=norm["tileset"]["id"], search_dirs=search_dirs)
                except ValidationError:
                    c.warn("牌表が見つからないため牌番号の範囲は未照合")
    M = norm["players"] if norm else None
    N = norm["hand_size"] if norm else None
    K = TS.K(ts) if ts else None
    # players
    pl = rec.get("players")
    if not isinstance(pl, list) or not pl:
        c.err("players が無い")
    else:
        if M is not None and len(pl) != M:
            c.err(f"players の長さ {len(pl)} ≠ ruleset.players {M}")
        for i, p in enumerate(pl):
            if not isinstance(p, dict) or p.get("seat") != i:
                c.err(f"players[{i}].seat が連番ではない")
        M = M or len(pl)
    # rounds
    rounds = rec.get("rounds")
    if not isinstance(rounds, list) or not rounds:
        c.err("rounds が空")
        rounds = []
    # やり直し（parent あり）は元の局の持ち点から始まるので、開始点との照合はしない
    prev_scores = [norm["settlement"]["start_points"]] * M if norm and not rec.get("parent") else None
    for k, rd in enumerate(rounds):
        p = f"rounds[{k}]"
        if rd.get("index") != k:
            c.err(f"{p}.index が連番ではない")
        st = rd.get("state")
        if not isinstance(st, dict):
            c.err(f"{p}.state が無い"); continue
        if st.get("bakaze") not in ("E", "S", "W", "N"):
            c.err(f"{p}.state.bakaze が不正")
        for key in ("kyoku", "honba", "kyotaku", "oya"):
            if not isinstance(st.get(key), int):
                c.err(f"{p}.state.{key} が整数ではない")
        scores = st.get("scores")
        if not isinstance(scores, list) or len(scores) != M:
            c.err(f"{p}.state.scores の長さ ≠ {M}")
        elif prev_scores is not None and scores != prev_scores:
            c.err(f"{p}.state.scores {scores} ≠ 前局の結果 {prev_scores}")
        if norm:
            if norm["wall_rules"]["break"]["by"] == "dice" and "dice" not in st:
                if rd.get("wall"):
                    c.err(f"{p}.state.dice が無い（break.by=dice）")
                else:
                    c.warn(f"{p}.state.dice が無い（山なしの取り込みでは不明）")
            if norm["game_rules"]["flow"]["wareme"] and "wareme" not in st:
                c.err(f"{p}.state.wareme が無い（wareme）")
        oya = st.get("oya", 0)
        evs = rd.get("events")
        if not isinstance(evs, list) or not evs:
            c.err(f"{p}.events が空"); continue
        _check_events(c, p, evs, M, K, norm)
        res = rd.get("result")
        if not isinstance(res, dict):
            c.err(f"{p}.result が無い"); continue
        _check_result(c, p, res, st, evs, M, K, norm, oya, k == len(rounds) - 1, ts)
        prev_scores = res.get("scores")
        # X5：山との突合
        wid = (rd.get("wall") or {}).get("id") if rd.get("wall") else None
        if wid is None:
            if evs[0].get("t") == "deal" and "hands" not in evs[0]:
                c.err(f"{p}: wall が null なら deal.hands が必要")
            c.warn(f"{p}: 山なし（配牌・ツモ順は未照合）")
        elif walls and wid in walls and norm and ts:
            _check_against_wall(c, p, walls[wid], norm, ts, oya, evs, rd.get("result") or {})
        elif norm and ts:
            c.warn(f"{p}: wall {wid[:19]}… が渡されていないため未照合")
    # final
    fin = rec.get("final")
    if rec.get("end") != "in_progress":
        if not isinstance(fin, dict):
            c.err("final が無い")
        elif rounds and isinstance(rounds[-1].get("result"), dict):
            last = rounds[-1]["result"].get("scores")
            fs = fin.get("scores")
            if not isinstance(fs, list) or len(fs) != M:
                c.err("final.scores の長さが違う")
            elif norm:
                # 終局時の供託（立直棒）：stick_at_end=to_first ならトップへ
                leftover = norm["settlement"]["start_points"] * M - sum(last)
                exp = list(last)
                if leftover > 0 and norm["game_rules"]["flow"]["riichi"]["stick_at_end"] == "to_first":
                    rk = S.ranks(last, tie=norm["settlement"]["tie"])
                    tops = [i for i in range(M) if rk[i] == 1]
                    for i in tops:
                        exp[i] += leftover // len(tops)
                if fs != exp:
                    c.err(f"final.scores {fs} ≠ 最終局の結果（供託の扱い込み）{exp}")
                rk = S.ranks(fs, tie=norm["settlement"]["tie"])
                if fin.get("rank") != rk:
                    c.err(f"final.rank {fin.get('rank')} ≠ 再計算 {rk}")
                if "settled" in fin:
                    calc = S.settle(fs, norm["settlement"])
                    if any(abs(a - b) > 1e-6 for a, b in zip(fin["settled"], calc)):
                        c.err(f"final.settled {fin['settled']} ≠ 再計算 {calc}（X8）")
                else:
                    c.err("final.settled が無い")
                if "chips" in fin:
                    tot_c = [0] * M
                    for r_ in rounds:
                        for w_ in (r_.get("result") or {}).get("wins") or []:
                            if isinstance(w_.get("chips"), list) and len(w_["chips"]) == M:
                                tot_c = [a + b for a, b in zip(tot_c, w_["chips"])]
                    if fin["chips"] != tot_c:
                        c.err(f"final.chips {fin['chips']} ≠ 各和了の祝儀の合計 {tot_c}")
    if c.errs:
        raise ValidationError("; ".join(c.errs))
    return c.warns


def _check_events(c: Ctx, p: str, evs: List[dict], M: int, K: Optional[int], norm: Optional[dict]):
    if evs[0].get("t") != "deal":
        c.err(f"{p}.events[0] は deal")
    kans = 0
    kans_by = {}
    riichi_pending = None
    for i, e in enumerate(evs):
        t = e.get("t")
        q = f"{p}.events[{i}]"
        if t not in EVENT_TYPES:
            c.err(f"{q}.t が語彙外: {t!r}"); continue
        for key in ("who", "from"):
            if key in e and not (isinstance(e[key], int) and 0 <= e[key] < M):
                c.err(f"{q}.{key} が 0〜{M-1} の外")
        tiles = []
        if "tile" in e:
            tiles.append(e["tile"])
        if "tiles" in e:
            tiles += e["tiles"]
        if K is not None:
            for x in tiles:
                if not (isinstance(x, int) and 0 <= x < K):
                    c.err(f"{q}: 牌番号 {x!r} が 0〜{K-1} の外")
        if t == "riichi":
            riichi_pending = e.get("who")
        elif t == "discard":
            if riichi_pending is not None:
                if e.get("who") != riichi_pending or not e.get("riichi"):
                    c.err(f"{q}: riichi の直後は同じ who の discard（riichi:true）")
                riichi_pending = None
        elif t == "kan":
            kans += 1
            if e.get("kind") not in ("ankan", "minkan", "kakan"):
                c.err(f"{q}.kind が不正")
            if e.get("kind") == "minkan" and "from" not in e:
                c.err(f"{q}: minkan には from")
            if norm and kans > norm["game_rules"]["flow"]["max_kans"]:
                c.err(f"{q}: カン {kans} 回目 > max_kans {norm['game_rules']['flow']['max_kans']}（X6）")
            if norm:
                fl = norm["game_rules"]["flow"]
                if e.get("kind") in ("ankan", "minkan", "kakan") and e.get("kind") not in fl["kan_kinds"]:
                    c.err(f"{q}: {e.get('kind')} の無いルール（X6）")
                kans_by[e.get("who")] = kans_by.get(e.get("who"), 0) + 1
                if fl["max_kans_per_player"] is not None and kans_by[e.get("who")] > fl["max_kans_per_player"]:
                    c.err(f"{q}: seat {e.get('who')} のカン {kans_by[e.get('who')]} 回目 > max_kans_per_player {fl['max_kans_per_player']}（X6）")
        elif t == "pon" and norm and not norm["game_rules"]["flow"]["pon"]:
            c.err(f"{q}: pon 禁止のルール（X6）")
        elif t == "chi" and norm and not norm["game_rules"]["flow"]["chi"]:
            c.err(f"{q}: chi 禁止のルール（X6）")
        elif t == "nuki" and norm and not norm["game_rules"]["nuki"]["enabled"]:
            c.err(f"{q}: 抜きの無いルール（X6）")
        if t in ("win", "draw_end", "abort") and i != len(evs) - 1 and t != "abort":
            # ダブロンは win が連続する
            if not (t == "win" and all(x.get("t") == "win" for x in evs[i:])):
                c.err(f"{q}: {t} は最後")


def _check_result(c: Ctx, p: str, res: dict, st: dict, evs: List[dict], M: int, K: Optional[int], norm: Optional[dict], oya: int, is_last: bool, ts: Optional[dict] = None):
    wins = res.get("wins")
    draw = res.get("draw")
    if not isinstance(wins, list):
        c.err(f"{p}.result.wins が配列ではない"); return
    if not wins and not isinstance(draw, dict):
        c.err(f"{p}.result: wins が空なら draw が必要")
    if wins and draw:
        c.err(f"{p}.result: wins と draw の両方がある")
    total = [0] * M
    for j, w in enumerate(wins):
        q = f"{p}.result.wins[{j}]"
        for key in ("who", "from", "tile", "hand", "yaku", "fu", "han", "points", "deltas"):
            if key not in w:
                c.err(f"{q}.{key} が無い")
        d = w.get("deltas")
        if not isinstance(d, list) or len(d) != M:
            c.err(f"{q}.deltas の長さ ≠ {M}"); continue
        total = [a + b for a, b in zip(total, d)]
        if norm:
            # X7：役名が採用役、翻の合計、点数表
            ov = norm["game_rules"]["yaku"]["overrides"]
            base_tbl = R.YAKU_TABLES.get(norm["game_rules"]["yaku"]["base"], {"yaku": {}, "yakuman": {}})
            han_sum = 0
            for y in w.get("yaku", []):
                nm = y.get("name")
                if nm not in R.YAKU_NAMES:
                    c.err(f"{q}: 語彙に無い役 {nm!r}"); continue
                if nm in ("dora", "ura_dora", "aka_dora", "kan_dora", "nuki_dora", "mark_yaku"):
                    han_sum += y.get("han", 0); continue
                adopted = ov.get(nm, base_tbl["yaku"].get(nm, base_tbl["yakuman"].get(nm, False)))
                if adopted is False:
                    c.err(f"{q}: 不採用の役 {nm}（X7）")
                if "yakuman" not in y:
                    han_sum += y.get("han", 0)
            if "yakuman" not in w and han_sum != w.get("han"):
                c.err(f"{q}: 翻の合計 {han_sum} ≠ han {w.get('han')}（X7）")
            is_tsumo = w.get("who") == w.get("from")
            sc_ = norm["game_rules"]["scoring"]
            if sc_["table"] == "additive":
                # 足し算の点数：内訳（additive）から 1 人の払いを出し直す。カラスは内訳の値が設定のどれかであること
                bd = w.get("additive") if isinstance(w.get("additive"), dict) else {}
                ka = sc_["additive"]["karasu"]
                kk = next((n for n in ("menzen", "open") if ka[n] and bd.get("karasu") == ka[n]), None)
                if bd.get("karasu") not in (0, ka["menzen"], ka["open"]):
                    c.err(f"{q}: additive.karasu {bd.get('karasu')} が設定に無い（X7）")
                each, parts_ = S.additive_points(w.get("han", 0), w.get("yakuman", 0), w.get("who") == oya, st.get("honba", 0), kk, sc_)
                if bd != parts_:
                    c.err(f"{q}: additive {bd} ≠ 式 {parts_}（X7）")
                tot = each * (M - 1) if is_tsumo else each
            else:
                tot, _ = S.total_points(w.get("fu", 0), w.get("han", 0), w.get("yakuman", 0), w.get("who") == oya, is_tsumo, M, sc_)
            if tot != w.get("points"):
                c.err(f"{q}: points {w.get('points')} ≠ 点数表 {tot}（X7：fu={w.get('fu')} han={w.get('han')}）")
            # 祝儀：ルールの規則から数え直す（飛びの祝儀は最初の和了に入る）
            rules_ = norm["settlement"]["chips"]
            if rules_ and ts is not None and "chips" in w and isinstance(w.get("hand"), list):
                ms_ = w.get("melds") or []
                wc = S.win_chips(rules_, ts, list(w["hand"]) + [t for m in ms_ for t in m.get("tiles", [])], w.get("yaku", []), w.get("yakuman", 0), is_tsumo,
                                 not any(m.get("kind") in ("chi", "pon", "minkan", "kakan") for m in ms_), w.get("tile"))
                exp = S.chip_deltas(wc, w.get("who"), w.get("from"), M, bool(w.get("reverse")))
                if j == 0:
                    for x in res.get("tobi_chips") or []:
                        exp[x["from"]] -= x["chips"]
                        exp[x["to"]] += x["chips"]
                if w["chips"] != exp:
                    c.err(f"{q}: chips {w['chips']} ≠ 規則から数えた枚数 {exp}")
            elif "chips" in w and not rules_:
                c.err(f"{q}: ルールに祝儀の規則が無いのに chips がある")
    if draw:
        if draw.get("reason") not in R.VOCAB["draw_reasons"]:
            c.err(f"{p}.result.draw.reason が語彙外")
        d = draw.get("deltas")
        if isinstance(d, list) and len(d) == M:
            total = [a + b for a, b in zip(total, d)]
        else:
            c.err(f"{p}.result.draw.deltas の長さ ≠ {M}")
    # 増減の合計：供託の出入りを含むので 0 とは限らない。供託の本数×点 の範囲で説明できることを確認
    if norm:
        kp = norm["game_rules"]["scoring"]["kyotaku_points"]
        s = sum(total)
        riichis = sum(1 for e in evs if e.get("t") == "riichi")
        # 場に出た供託（前局までの kyotaku ＋ この局の立直）が和了者に入るぶんはプラス、流局で残るぶんは出ていくだけ
        allowed = {0}
        if kp:
            allowed |= {kp * n for n in range(-(riichis), st.get("kyotaku", 0) + riichis + 1)}
        if s not in allowed:
            c.err(f"{p}.result: 増減の合計 {s} が供託で説明できない")
    scores = res.get("scores")
    if not isinstance(scores, list) or len(scores) != M:
        c.err(f"{p}.result.scores の長さ ≠ {M}")
    elif isinstance(st.get("scores"), list) and len(st["scores"]) == M:
        exp = [a + b for a, b in zip(st["scores"], total)]
        if scores != exp:
            c.err(f"{p}.result.scores {scores} ≠ state.scores＋増減 {exp}")


def _check_against_wall(c: Ctx, p: str, wall: dict, norm: dict, ts: dict, oya: int, evs: List[dict], res: Optional[dict] = None):
    """X5：wall.order と wall_rules から配牌・ツモ順・嶺上・ドラ表示を導き、events と順に一致するか。"""
    if wall["tileset"]["id"] != ts["id"]:
        c.err(f"{p}: wall.tileset.id ≠ ruleset.tileset.id"); return
    order = wall["order"]
    K = len(order)
    wr = norm["wall_rules"]
    M, N = norm["players"], norm["hand_size"]
    dead = wr["dead_wall"]
    live_end = K - dead
    live_end0 = live_end
    deadw = order[live_end:]
    pos = N * M + 1
    # 配牌の集合（deal.hands があれば照合）
    if "hands" in evs[0]:
        for s in range(M):
            who = (oya + s) % M
            exp = sorted(order[s * N:(s + 1) * N])
            if sorted(evs[0]["hands"][who]) != exp:
                c.err(f"{p}: 配牌 seat {who} が山と一致しない（X5）")
    first_draw_done = False
    kan_i = 0
    rin_i = 0
    dora_i = 0
    rin = wr.get("rinshan")
    for i, e in enumerate(evs):
        t = e.get("t")
        q = f"{p}.events[{i}]"
        if t == "dora":
            if dora_i < len(wr.get("dora_indicator", [])):
                exp = deadw[wr["dora_indicator"][dora_i]]
            else:
                kd = wr.get("kan_dora", [])
                if kan_i >= len(kd):
                    c.err(f"{q}: カンドラの位置が足りない"); continue
                o = kd[kan_i]
                # 負のオフセットは海底側（王牌が嶺上のぶん海底を取り込んだ牌）。−1 が元の海底
                exp = deadw[o] if o >= 0 else order[live_end0 + o]
                kan_i += 1
            dora_i += 1
            if e.get("tile") != exp:
                c.err(f"{q}: ドラ表示 {e.get('tile')} ≠ 山 {exp}（X5）")
        elif t == "draw":
            if not first_draw_done:
                exp = order[N * M]          # 親の第 1 ツモは配牌の最後の 1 枚
                first_draw_done = True
                if e.get("who") != oya:
                    c.err(f"{q}: 最初のツモは親（seat {oya}）のはず")
            elif e.get("rinshan"):
                if rin == "live":
                    exp = order[pos]; pos += 1
                elif isinstance(rin, list):
                    if rin_i < len(rin):
                        o = rin[rin_i]; rin_i += 1
                        # 負のオフセットは海底側（先の嶺上のぶん王牌に取り込まれた牌）。−1 が元の海底
                        exp = deadw[o] if o >= 0 else order[live_end0 + o]
                        shrink = not wr.get("rinshan_reserved")
                    else:
                        # 嶺上を使い切ったら海底側の牌（王牌が海底を取り込んだぶん）
                        exp = order[live_end - 1]
                        shrink = True
                        c.warn(f"{q}: 嶺上 {len(rin)} 枚を超えたので海底側から")
                    if shrink:
                        live_end -= 1   # 嶺上を 1 枚使うごとに海底が 1 枚王牌に入り、ツモれる牌が 1 枚減る（rinshan_reserved＝補充用に取ってある牌を使う間は減らない）
                else:
                    c.err(f"{q}: 嶺上の位置が足りない"); continue
            else:
                if pos >= live_end:
                    c.err(f"{q}: 山を引き切っている（X5）"); continue
                exp = order[pos]; pos += 1
            if e.get("tile") != exp:
                c.err(f"{q}: ツモ {e.get('tile')} ≠ 山 {exp}（X5）")
    if pos > live_end:
        c.err(f"{p}: 消費枚数 {pos} > K−dead_wall {live_end}")
    # 裏ドラ表示（和了に ura_indicators があるとき）：表の枚数ぶんの ura_indicator ＋ めくったカンの数ぶんの kan_ura
    if res:
        ura = wr.get("ura_indicator", [])
        ku = wr.get("kan_ura", [])
        n0 = min(dora_i, len(wr.get("dora_indicator", [])))
        exp_ura = [deadw[o] for o in ura[:n0]]
        for o in ku[:kan_i]:
            exp_ura.append(deadw[o] if o >= 0 else order[live_end0 + o])
        for j, w in enumerate(res.get("wins", [])):
            if "ura_indicators" in w and w["ura_indicators"] != exp_ura:
                c.err(f"{p}.result.wins[{j}].ura_indicators {w['ura_indicators']} ≠ 山 {exp_ura}（X5）")
