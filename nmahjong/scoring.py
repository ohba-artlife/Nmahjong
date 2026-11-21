"""点数と精算の計算（検証 X7・X8 用の最小実装）。和了判定・符計算は持たない（符・翻は record が持つ値を使う）。"""
import math
from typing import Dict, List, Optional, Tuple

from .canon import ValidationError


def _ceil100(x: int) -> int:
    return int(math.ceil(x / 100.0)) * 100


def base_points(fu: int, han: int, yakuman: int, sc: dict) -> int:
    """基本点。sc は ruleset.game_rules.scoring（正規形）。yakuman は役満の倍数（0 なら通常手）。"""
    lm = sc["limits"]
    if yakuman:
        return 2000 * lm["yakuman_base"] * min(yakuman, lm["max_multiple"])
    if sc["table"] == "custom:nm1-limits":
        # 1 枚麻雀（nm-2p-1-*）：最低が跳満（6〜7）、倍満 8、三倍満 11、数え役満 13
        if lm["kazoe_from"] and han >= lm["kazoe_from"]:
            return 2000 * lm["yakuman_base"]
        if han >= lm["sanbaiman_from"]:
            return 6000
        if han >= 8:
            return 4000
        return 3000
    if lm["kazoe_from"] and han >= lm["kazoe_from"]:
        return 2000 * lm["yakuman_base"]
    if han >= lm["sanbaiman_from"]:
        return 6000
    if han >= 8:
        return 4000
    if han >= 6:
        return 3000
    if han >= 5:
        return 2000
    if not sc["fu"]["enabled"]:
        fu = 20
    b = fu * (2 ** (han + 2))
    if b >= 2000 or (sc["mangan_round_up"] and b >= 1920):
        return 2000
    return b


def _three_player_tsumo(parts: List[int], b: int, is_dealer: bool, mode: str) -> List[int]:
    """三人打ちのツモの払い（scoring.tsumo_loss）。parts は 4 人打ちと同じ式の各自の負担（親のツモ＝[子, 子]、子のツモ＝[親, 子]）。
    loss：そのまま（北家の分は誰も払わない＝ツモ損）。add_1000：2 人の払いにそれぞれ 1000 点を足す（千点加符）。
    marudori（丸取り）：ロンの点を分ける。子のツモは子＝ロン÷3 を 100 点単位に切り捨て、親＝残り（ほぼ 1:2）。親のツモは 2 人がロン÷2（切り上げ）。
    north_split（北家の分の折半）：子のツモは、子＝子の払い×1.5 を切り捨て、親＝親の払い＋子の払い÷2 を切り上げ。親のツモは丸取りと同じ。
    none（ツモ損なし。方式の指定なし）：丸取りで払う。
    額は docs/spec/ruleset.md の scoring.tsumo_loss に挙げた点数表と突き合わせてある（tests/test_scoring3p.py）。"""
    if mode == "add_1000":
        return [p + 1000 for p in parts]
    if mode in ("marudori", "north_split", "none"):
        ron = _ceil100(b * (6 if is_dealer else 4))
        if is_dealer:
            each = _ceil100(ron / 2)
            return [each, each]
        if mode == "north_split":
            c = parts[1]
            return [_ceil100(parts[0] + c / 2), (c * 3 // 2) // 100 * 100]
        child = ron // 300 * 100
        return [ron - child, child]
    return parts


def total_points(fu: int, han: int, yakuman: int, is_dealer: bool, is_tsumo: bool, players: int, sc: dict) -> Tuple[int, List[int]]:
    """(合計点, 支払い内訳[相手ごと]) を返す。本場・供託は含まない。
    payment: standard＝人数分で割る通常の形（M=4 の式。M=3 は親 2 倍・子 1 倍×2、M=2 は 1 人）。
             4p_total_from_opponent＝4 人麻雀の合計を相手 1 人が払う。4p_child_half_from_opponent＝ロン全額・ツモは子合計の半分。
             4p_dealer_share_from_opponent＝ロン全額・ツモは 4 人麻雀の親の負担分（基本点×2 を 100 点単位に切り上げ）を相手 1 人が払う。"""
    if sc["table"] == "additive":
        raise ValidationError("scoring.table＝additive の点数は additive_points で出す（本場とカラスが要る）")
    b = base_points(fu, han, yakuman, sc)
    pay = sc["payment"]
    if pay == "standard" and sc.get("round_to", 100) != 100:
        u = sc["round_to"]                                   # 1000 点単位：各自の払い（ロンは合計）を切り上げる
        total, parts = total_points(fu, han, yakuman, is_dealer, is_tsumo, players, dict(sc, round_to=100, tsumo_table=None))
        parts = [-(-p // u) * u for p in parts]
        tt = sc.get("tsumo_table")
        if tt and is_tsumo and not is_dealer and players == 3:
            # 子のツモの払いを表で決める（店の点数表。キー＝同じ手のロンの点、値＝[親の払い, 子の払い]）。表に無い点は上の式
            ron, _ = total_points(fu, han, yakuman, False, False, players, sc)
            if str(ron) in tt:
                parts = list(tt[str(ron)])
        return sum(parts), parts
    tt = sc.get("tsumo_table")
    if tt and pay == "standard" and is_tsumo and not is_dealer and players == 3:
        ron, _ = total_points(fu, han, yakuman, False, False, players, sc)
        if str(ron) in tt:
            return sum(tt[str(ron)]), list(tt[str(ron)])
    if pay == "standard":
        if is_tsumo:
            if players == 1:
                return 0, []
            if is_dealer:
                each = _ceil100(b * 2)
                parts = [each] * (players - 1)
            else:
                parts = [_ceil100(b * 2)] + [_ceil100(b)] * (players - 2)
            if players == 3:
                parts = _three_player_tsumo(parts, b, is_dealer, sc.get("tsumo_loss", "none"))
            return sum(parts), parts
        total = _ceil100(b * (6 if is_dealer else 4))
        return total, [total]
    # 2 人打ちの特別払い：4 人麻雀の額を基準にする
    if is_tsumo and pay == "4p_dealer_share_from_opponent":
        share = _ceil100(b * 2)
        return share, [share]
    if is_tsumo:
        if is_dealer:
            four = _ceil100(b * 2) * 3
        else:
            four = _ceil100(b * 2) + 2 * _ceil100(b)
        if pay == "4p_total_from_opponent":
            return four, [four]
        if pay == "4p_child_half_from_opponent":
            child_total = _ceil100(b * 2) + 2 * _ceil100(b)
            half = child_total // 2
            return half, [half]
    total = _ceil100(b * (6 if is_dealer else 4))
    return total, [total]


# ---- 足し算の点数（scoring.table＝additive） ------------------------------------------------

def karasu_kind(kinds_in_hand: List[str], nuki_count: int, menzen: bool, nuki_rule: dict) -> Optional[str]:
    """カラス（抜く牌を 1 枚も持たない和了）か。menzen／open／None。
    kinds_in_hand は手牌と副露の牌の種類、nuki_count は抜いた枚数、nuki_rule は game_rules.nuki（正規形）。"""
    if not (nuki_rule or {}).get("enabled"):
        return None
    tiles = set(nuki_rule.get("tiles") or [])
    if nuki_count or any(k in tiles for k in kinds_in_hand):
        return None
    return "menzen" if menzen else "open"


def additive_points(han: int, yakuman: int, is_dealer: bool, honba: int, karasu: Optional[str], sc: dict) -> Tuple[int, dict]:
    """足し算の点数。1 人が払う点と、その内訳を返す（ロンは放銃者が、ツモは残りの全員がそれぞれこの点を払う）。
    点＝（翻×per_han ＋ 役満の点 ＋ base ＋ 親なら dealer ＋ 本場×honba）× multiplier を round_to の単位に切り上げ、カラスの点を足す。
    本場は honba_dealer_only＝true なら親の和了のときだけ数える。役満の点は yakuman × 役満の倍数（limits.max_multiple まで）。"""
    a = sc["additive"]
    ym = min(yakuman, sc["limits"]["max_multiple"]) if yakuman else 0
    hon = honba if (is_dealer or not a["honba_dealer_only"]) else 0
    parts = {"han": han * a["per_han"], "yakuman": ym * a["yakuman"], "base": a["base"],
             "dealer": a["dealer"] if is_dealer else 0, "honba": hon * a["honba"]}
    raw = sum(parts.values()) * a["multiplier"]
    u = a["round_to"]
    each = -(-raw // u) * u
    parts["karasu"] = a["karasu"][karasu] if karasu else 0
    each += parts["karasu"]
    parts["each"] = each
    return each, parts


# ---- 祝儀（settlement.chips） ---------------------------------------------------------------

_CHIP_YAKU = {"haitei": ("haitei",), "houtei": ("houtei",), "tsumo": ("menzen_tsumo",)}


def win_chips(rules: List[dict], ts: dict, tiles: List[int], yaku: List[dict], yakuman: int, tsumo: bool, menzen: bool, win_tile: Optional[int] = None) -> Dict[str, int]:
    """和了 1 つに付く祝儀の枚数を、払い手の決まりごとに返す：{"loser": 枚数, "all": 枚数}。
    loser＝ロンは放銃者が、ツモは残りの全員が、それぞれこの枚数を払う。all＝ロンでもツモでも、残りの全員がそれぞれ払う。
    tiles＝和了者の手牌と副露（抜いた牌を含む）の牌番号。yaku＝判定の役の並び。on が win_with_mark・win_kind の規則だけを数える。
    規則に win_tile＝true があれば、和了牌だけを数える（白ポッチで和了したときの祝儀）。"""
    out = {"loser": 0, "all": 0}
    han = {y["name"]: y.get("han", 0) for y in yaku}
    for c in rules or []:
        w = c.get("when", "always")
        if (w == "menzen" and not menzen) or (w == "tsumo" and not tsumo) or (w == "ron" and tsumo) or c.get("payer") not in out:
            continue
        if c.get("on") == "win_with_mark":
            n = sum(1 for t in ([win_tile] if c.get("win_tile") else tiles) if t is not None and ("mark" not in c or ts["tiles"][t].get("mark") == c["mark"])
                    and ("tile_kind" not in c or ts["tiles"][t]["kind"] == c["tile_kind"]) and ("tile_id" not in c or t == c["tile_id"])
                    and ("mark" in c or "tile_kind" in c or "tile_id" in c))
        elif c.get("on") == "win_kind":
            k = c.get("kind")
            if k == "uradora":
                n = han.get("ura_dora", 0)
            elif k == "yakuman":
                n = yakuman
            elif k == "ron":
                n = 0 if tsumo else 1
            else:
                n = 1 if any(name in han for name in _CHIP_YAKU.get(k, (k,))) else 0
        else:
            continue
        out[c["payer"]] += c["count"] * (n if c.get("per") == "tile" else (1 if n else 0))
    return out


def chip_deltas(wc: Dict[str, int], who: int, frm: int, players: int, reverse: bool = False) -> List[int]:
    """win_chips の結果を席ごとの増減にする。reverse＝true（逆ポッチ）なら和了者が払う側になる。"""
    d = [0] * players
    for s in range(players):
        if s == who:
            continue
        n = wc["all"] + (wc["loser"] if (who == frm or s == frm) else 0)
        d[s] -= n
        d[who] += n
    return [-x for x in d] if reverse else d


# ---- 精算（X8） -----------------------------------------------------------------------

def ranks(scores: List[int], seats_order: Optional[List[int]] = None, tie: str = "split") -> List[int]:
    """各 seat の順位（1 始まり）。同点は tie=seat_order なら起家に近い方が上、split／draw なら同順位。"""
    M = len(scores)
    order = sorted(range(M), key=lambda i: (-scores[i], i))
    out = [0] * M
    if tie == "seat_order":
        for r, i in enumerate(order):
            out[i] = r + 1
        return out
    r = 0
    for k, i in enumerate(order):
        if k == 0 or scores[i] != scores[order[k - 1]]:
            r = k + 1
        out[i] = r
    return out


def settle(scores: List[int], st: dict, rounding: Optional[dict] = None) -> List[float]:
    """点の精算（pt）。st は ruleset.settlement（正規形）。"""
    M = len(scores)
    unit = st["unit"]["points_per_unit"]
    rd = rounding or st.get("rounding") or {"score_to_1000": "none", "remainder_to_top": False}
    rk = ranks(scores, tie=st["tie"])
    # 素点
    raw = []
    for s in scores:
        if rd["score_to_1000"] == "none":
            raw.append((s - st["return_points"]) / unit)
        else:
            # 持ち点そのものを 1000 点単位に丸めてから返し点を引く。丸めは絶対値に対して行い符号を戻す
            # （差に対して丸めると 28500 → −1.5 → −2 となり実データと合わない）。
            # half_up_500＝四捨五入（.5 切り上げ）、half_up_600＝五捨六入（.6 切り上げ）。
            # 天鳳は half_up_500：28500→29、36500→37、−500→−1（公開牌譜 1002 件の owari で確認）
            thr = 600 if rd["score_to_1000"] == "half_up_600" else 500
            q, r = divmod(abs(s), 1000)
            k = q + (1 if r >= thr else 0)
            k = k if s >= 0 else -k
            raw.append(k - st["return_points"] // 1000)
    # ウマ
    uma = st["uma"]
    if isinstance(uma, dict):
        th = uma.get("threshold", "return")
        thv = st["return_points"] if th == "return" else st["start_points"] if th == "start" else th
        inc = uma.get("includes_threshold", True)
        nfloat = sum(1 for s in scores if (s >= thv if inc else s > thv))
        nfloat = min(max(nfloat, 1), M - 1)
        arr = uma["by_floating"][str(nfloat)]
    else:
        arr = uma
    out = [0.0] * M
    for i in range(M):
        out[i] = raw[i] + _rank_share(arr, rk, i, st["tie"])
    # オカ：トップへ。同点トップが複数なら等分
    oka_total = (st["return_points"] - st["start_points"]) * M / unit
    if oka_total and st["oka"] != "none":
        tops = [i for i in range(M) if rk[i] == 1]
        for i in tops:
            out[i] += oka_total / len(tops)
    if rd.get("remainder_to_top"):
        tops = [i for i in range(M) if rk[i] == 1]
        others = sum(out[i] for i in range(M) if i not in tops)
        for i in tops:
            out[i] = -others / len(tops)
    return [round(x, 4) for x in out]


def _rank_share(arr: List[float], rk: List[int], i: int, tie: str) -> float:
    """同順位が複数なら順位点を平均（split／draw）。seat_order なら順位どおり。"""
    r = rk[i]
    if tie == "seat_order":
        return arr[r - 1]
    same = [j for j in range(len(rk)) if rk[j] == r]
    if len(same) == 1:
        return arr[r - 1]
    idx = list(range(r - 1, r - 1 + len(same)))
    return sum(arr[k] for k in idx) / len(same)
