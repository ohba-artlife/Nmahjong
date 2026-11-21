"""天鳳 JSON 牌譜（tenhou.net/6 の log 形式。SHUFFLE 無し＝山なし）⇄ record。

形：{"title":[…], "name":[…], "rule":{"disp":"…","aka":1}, "log":[局…], "sc":[点,pt,…]}
局：[[局番号(東1=0), 本場, 供託], [持ち点×M], [ドラ表示…], [裏表示…], 配牌0, ツモ0, 打牌0, 配牌1, …, 結果]
牌：11〜19 萬、21〜29 筒、31〜39 索、41〜47 字（東南西北白發中）、51／52／53 赤五萬筒索。
ツモ列の文字列：鳴き（"c121314" チー：先頭が鳴いた牌、"p"／"m" の位置が誰から：先頭＝上家、中＝対面、末尾＝下家）。
打牌列：60＝ツモ切り、"r31"＝立直宣言打牌、"a"＝暗槓、"k"＝加槓、"f"＝抜き（三麻の北）。カンの後の嶺上はツモ列の次。
結果：["和了", [増減×M], [who, from, pao, "30符2翻2000点", "立直(1飜)", …]]（ダブロンは増減と情報の組が 2 つ）、["流局", [増減×M]]、["九種九牌"] など。

牌の個体番号が無いので、取り込みでは牌表の同種の番号を**出現順に**割り当てる（赤は赤の番号）。wall は null、deal.hands を書く。
X5（山との照合）は行えない。X4・X6・X7・X8 は通常どおり検証できる。
"""
import json
import re
from typing import Dict, List, Optional, Tuple

from .. import ruleset as R, tileset as TS
from ..canon import ValidationError, sha256_id
from . import importer as I

# 天鳳 JSON の役名（日本語）→ 役名（vocab）。番号は importer.TENHOU_YAKU と同じ並び
JP_YAKU = {
    "門前清自摸和": "menzen_tsumo", "立直": "riichi", "一発": "ippatsu", "槍槓": "chankan", "嶺上開花": "rinshan", "海底摸月": "haitei",
    "河底撈魚": "houtei", "平和": "pinfu", "断幺九": "tanyao", "一盃口": "iipeikou",
    "自風 東": "yakuhai_seat", "自風 南": "yakuhai_seat", "自風 西": "yakuhai_seat", "自風 北": "yakuhai_seat",
    "場風 東": "yakuhai_round", "場風 南": "yakuhai_round", "場風 西": "yakuhai_round", "場風 北": "yakuhai_round",
    "役牌 白": "yakuhai_haku", "役牌 發": "yakuhai_hatsu", "役牌 中": "yakuhai_chun", "両立直": "double_riichi", "七対子": "chiitoitsu",
    "混全帯幺九": "chanta", "一気通貫": "ittsu", "三色同順": "sanshoku", "三色同刻": "sanshoku_doukou", "三槓子": "sankantsu",
    "対々和": "toitoi", "三暗刻": "sanankou", "小三元": "shousangen", "混老頭": "honroutou", "二盃口": "ryanpeikou",
    "純全帯幺九": "junchan", "混一色": "honitsu", "清一色": "chinitsu", "人和": "renhou", "天和": "tenhou", "地和": "chiihou",
    "大三元": "daisangen", "四暗刻": "suuankou", "四暗刻単騎": "suuankou_tanki", "字一色": "tsuuiisou", "緑一色": "ryuuiisou",
    "清老頭": "chinroutou", "九蓮宝燈": "chuuren", "純正九蓮宝燈": "junsei_chuuren", "国士無双": "kokushi", "国士無双１３面": "kokushi13",
    "大四喜": "daisuushii", "小四喜": "shousuushii", "四槓子": "suukantsu", "ドラ": "dora", "裏ドラ": "ura_dora", "赤ドラ": "aka_dora",
    "抜きドラ": "nuki_dora", "北ドラ": "nuki_dora",
}
_YAKU_JP = {}
for _jp, _nm in JP_YAKU.items():
    _YAKU_JP.setdefault(_nm, _jp)
_JP_YAKU_NORM = {re.sub(r"[\s　:：]", "", k): v for k, v in JP_YAKU.items()}
_JP_YAKU_NORM.update({
    # 雀魂（cfg.fan の name_jp）の表記
    "ダブル立直": "double_riichi", "役牌白": "yakuhai_haku", "役牌發": "yakuhai_hatsu", "役牌中": "yakuhai_chun", "白": "yakuhai_haku", "發": "yakuhai_hatsu", "中": "yakuhai_chun",
    "役牌自風牌": "yakuhai_seat", "自風牌": "yakuhai_seat", "自風": "yakuhai_seat", "役牌場風牌": "yakuhai_round", "場風牌": "yakuhai_round", "場風": "yakuhai_round",
    "自風東": "yakuhai_seat", "自風南": "yakuhai_seat", "自風西": "yakuhai_seat", "自風北": "yakuhai_seat",
    "場風東": "yakuhai_round", "場風南": "yakuhai_round", "場風西": "yakuhai_round", "場風北": "yakuhai_round",
    "国士無双十三面待ち": "kokushi13", "国士無双十三面": "kokushi13", "国士無双13面": "kokushi13", "純正九蓮宝燈": "junsei_chuuren",
    "一発": "ippatsu", "対々和": "toitoi", "断么九": "tanyao", "混全帯么九": "chanta", "純全帯么九": "junchan",
})
RESULT_DRAW = {"四開槓": "four_kans", "三家和": "three_ron", "流局": "exhaustive", "全員聴牌": "exhaustive", "全員不聴": "exhaustive", "流し満貫": "nagashi_mangan",
               "九種九牌": "nine_terminals", "四風連打": "four_winds", "四家立直": "four_riichi", "三家和了": "three_ron", "四槓散了": "four_kans"}
_DRAW_JP = {"exhaustive": "流局", "nagashi_mangan": "流し満貫", "nine_terminals": "九種九牌", "four_winds": "四風連打",
            "four_riichi": "四家立直", "three_ron": "三家和了", "four_kans": "四槓散了"}
SUIT = {1: "m", 2: "p", 3: "s"}
HONOR = "ESWNPFC"


# ---- 牌の記法 -----------------------------------------------------------------------

def code_to_kind(c: int) -> Tuple[str, bool]:
    """天鳳 JSON の牌番号 → (種類, 赤か)。"""
    if c in (51, 52, 53):
        return "5" + SUIT[c - 50], True
    a, b = divmod(c, 10)
    if a in (1, 2, 3) and 1 <= b <= 9:
        return f"{b}{SUIT[a]}", False
    if a == 4 and 1 <= b <= 7:
        return HONOR[b - 1], False
    raise ValidationError(f"天鳳 JSON の牌番号が不正: {c}")


def kind_to_code(kind: str, red: bool) -> int:
    if kind in HONOR:
        return 41 + HONOR.index(kind)
    n, s = int(kind[0]), kind[1]
    if red and n == 5:
        return 50 + "mps".index(s) + 1
    return ("mps".index(s) + 1) * 10 + n


class _Pool:
    """牌表の番号を種類ごとに出現順で払い出す。"""

    def __init__(self, ts: dict):
        self.by_kind: Dict[Tuple[str, bool], List[int]] = {}
        for t in ts["tiles"]:
            self.by_kind.setdefault((t["kind"], t.get("mark") == "red"), []).append(t["id"])
        self.used: set = set()

    def take(self, c: int) -> int:
        kind, red = code_to_kind(c)
        for tid in self.by_kind.get((kind, red), []):
            if tid not in self.used:
                self.used.add(tid)
                return tid
        if not red:     # 赤無し牌表に 5 を 5 枚…は無いはずだが、赤個体へ逃がす
            for tid in self.by_kind.get((kind, True), []):
                if tid not in self.used:
                    self.used.add(tid)
                    return tid
        raise ValidationError(f"牌 {c} の個体が牌表に足りない")


def _pick(hand: List[int], ts: dict, c: int, prefer: Optional[int] = None) -> int:
    """手牌から天鳳番号 c に当たる個体を 1 枚選ぶ。"""
    kind, red = code_to_kind(c)
    if prefer is not None and prefer in hand and ts["tiles"][prefer]["kind"] == kind:
        return prefer
    for tid in hand:
        t = ts["tiles"][tid]
        if t["kind"] == kind and (t.get("mark") == "red") == red:
            return tid
    for tid in hand:        # 赤の区別が付かない場合の逃げ
        if ts["tiles"][tid]["kind"] == kind:
            return tid
    raise ValidationError(f"手牌に牌 {c} が無い")


def _parse_call(s: str, who: int, M: int) -> Tuple[str, int, List[int], int]:
    """ツモ列・打牌列の鳴き文字列 → (kind, from_rel, 牌番号列, 鳴いた牌)。from は seat。"""
    letter = next(ch for ch in s if ch.isalpha())
    pos = s.index(letter)
    digits = s.replace(letter, "")
    codes = [int(digits[i:i + 2]) for i in range(0, len(digits), 2)]
    # 文字の位置：先頭＝上家、中＝対面、末尾＝下家（四麻）。三麻は上家・下家のみ
    n = len(codes)
    if pos == 0:
        rel = M - 1              # 上家
    elif pos >= 2 * (n - 1):
        rel = 1                  # 下家
    else:
        rel = 2 if M == 4 else 1
    called = codes[pos // 2] if pos // 2 < n else codes[0]
    kind = {"c": "chi", "p": "pon", "m": "minkan", "k": "kakan", "a": "ankan", "f": "nuki"}[letter]
    frm = (who + rel) % M
    return kind, frm, codes, called


# ---- 取り込み --------------------------------------------------------------------------

def is_jantama(obj: dict) -> bool:
    """雀魂の牌譜を downloadlogs.js で天鳳 JSON にしたものか。ref が天鳳の牌譜 ID の形でなく、部屋名・段位が雀魂のもの。"""
    ref = str(obj.get("ref", ""))
    if re.match(r"^\d{10}gm-", ref):
        return False
    disp = (obj.get("rule") or {}).get("disp", "") if isinstance(obj.get("rule"), dict) else ""
    dans = " ".join(str(d) for d in (obj.get("dan") or []))
    return any(k in disp for k in ("の間", "友人戦", "大会戦")) or any(k in dans for k in ("雀士", "雀傑", "雀豪", "雀聖", "魂天", "初心"))


def _rule_from_disp(rule: dict, jantama: bool = False) -> Tuple[str, int]:
    disp = rule.get("disp", "") if isinstance(rule, dict) else ""
    players = 3 if "三" in disp else 4
    if jantama:
        if players == 3:
            raise ValidationError("雀魂 三麻の同梱ルールは未作成")
        return ("jantama-4p" if "南" in disp else "jantama-4p-tonpu"), 4
    aka = bool(rule.get("aka") or rule.get("aka51") or rule.get("aka52") or rule.get("aka53") or "赤" in disp) if isinstance(rule, dict) else True
    if players == 3:
        return "tenhou-3p", 3
    if not aka or "喰" not in disp:
        raise ValidationError(f"rule.disp={disp!r}（赤なし／喰断なし）の同梱ルールは未作成")
    return ("tenhou-4p-hanchan-red" if "南" in disp else "tenhou-4p-tonpu-red"), 4


def load_any(text: str) -> dict:
    """天鳳 JSON の入口 3 種を 1 つの dict に：
    (1) JSON そのもの、(2) 牌譜エディタの URL `https://tenhou.net/6/#json={…}`（URL エンコード可）、
    (3) (2) が複数行（雀魂の牌譜を downloadlogs.js で落とすと 1 行 1 局になる）→ 同じ対局として log を連結。"""
    from urllib.parse import unquote
    t = text.strip()
    if t.startswith("{"):
        return json.loads(t)
    merged = None
    for line in t.splitlines():
        line = line.strip()
        if not line:
            continue
        i = line.find("json=")
        if i < 0:
            continue
        obj = json.loads(unquote(line[i + 5:]))
        if merged is None:
            merged = obj
        else:
            if obj.get("name") != merged.get("name"):
                raise ValidationError("複数行の牌譜で name（対局者）が違う。別の対局が混ざっている")
            merged["log"] += obj.get("log", [])
            if "sc" in obj:
                merged["sc"] = obj["sc"]
    if merged is None:
        raise ValidationError("天鳳 JSON でも牌譜エディタの URL でもない")
    return merged


def import_json(obj, rs: Optional[dict] = None, ts: Optional[dict] = None, source_ref: Optional[str] = None) -> dict:
    """天鳳 JSON（読み込み済み dict か JSON 文字列／牌譜エディタ URL の行）→ record（wall なし）。"""
    if isinstance(obj, str):
        obj = load_any(obj)
    if not isinstance(obj, dict) or "log" not in obj:
        raise ValidationError("天鳳 JSON ではない（log が無い）")
    jantama = is_jantama(obj)
    if rs is None:
        name, m = _rule_from_disp(obj.get("rule", {}), jantama)
        sc0 = obj.get("sc")
        if not jantama and m == 4 and isinstance(sc0, list) and I.owari_has_fraction([float(x) for x in sc0]):
            name += "-exact"        # 精算を丸めていない牌譜
        rs = R.find(name=name)
    ts = ts or TS.find(id=rs["tileset"]["id"])
    norm = R.normalize(rs)
    M, N = norm["players"], norm["hand_size"]
    names = list(obj.get("name", []))[:M] + [""] * max(0, M - len(obj.get("name", [])))
    jantama_src = is_jantama(obj)
    players = [{"seat": i, "name": names[i], "external": [{"system": "jantama" if jantama_src else "tenhou", "id": names[i]}]} for i in range(M)]
    dans = obj.get("dan") or []
    rates = obj.get("rate") or []
    for i in range(M):
        if i < len(dans) and dans[i] not in (None, ""):
            players[i]["ranks"] = [{"system": "jantama-rank" if jantama_src else "tenhou-rank", "value": dans[i]}]
        if i < len(rates) and rates[i] not in (None, ""):
            players[i]["rating"] = {"system": "jantama-level-score" if jantama_src else "tenhou-rate", "value": float(rates[i])}
    rounds = []
    for k, L in enumerate(obj["log"]):
        rounds.append(_import_round(k, L, M, N, ts, norm))
    if not rounds:
        raise ValidationError("局が無い")
    final_scores = list(rounds[-1]["result"]["scores"])
    from .. import scoring as S
    leftover = norm["settlement"]["start_points"] * M - sum(final_scores)
    if leftover > 0 and norm["game_rules"]["flow"]["riichi"]["stick_at_end"] == "to_first":
        rk = S.ranks(final_scores, tie=norm["settlement"]["tie"])
        tops = [i for i in range(M) if rk[i] == 1]
        for i in tops:
            final_scores[i] += leftover // len(tops)
    rec = {"format": "nmahjong-record", "version": "1.0",
           "source": {"kind": "imported", "from": "jantama" if jantama else "tenhou", "ref": (obj.get("ref") if jantama else None) or source_ref or (obj.get("ref") or "tenhou-json")},
           "ruleset": R.ref(rs), "players": players, "end": "finished", "parent": None, "rounds": rounds,
           "final": {"scores": final_scores}}
    rec["final"]["rank"] = S.ranks(final_scores, tie=norm["settlement"]["tie"])
    sc = obj.get("sc")
    if isinstance(sc, list) and len(sc) >= 2 * M:
        rec["final"]["settled"] = [float(sc[2 * i + 1]) for i in range(M)]
    else:
        rec["final"]["settled"] = S.settle(final_scores, norm["settlement"])
    rec["id"] = sha256_id({k: v for k, v in rec.items() if k != "id"})
    return rec


def _import_round(k: int, L: list, M: int, N: int, ts: dict, norm: dict) -> dict:
    head, scores, doras, uras = L[0], L[1], L[2], L[3]
    kyoku_i, honba, kyotaku = head
    scores = list(scores)[:M]              # 三麻でも 4 人分入っている
    oya = kyoku_i % 4                      # 局番号は三麻でも「場×4＋局」（天鳳・downloadlogs.js とも）
    pool = _Pool(ts)
    hands = []
    draws = []
    discs = []
    for i in range(M):
        hands.append([pool.take(c) for c in L[4 + 3 * i]])
        draws.append(list(L[5 + 3 * i]))
        discs.append(list(L[6 + 3 * i]))
    result = L[4 + 3 * M] if len(L) > 4 + 3 * M else ["流局", [0] * M]
    evs: List[dict] = [{"t": "deal", "hands": [list(h) for h in hands]}, {"t": "dora", "tile": pool.take(doras[0])}]
    dora_i = 1
    cur = [list(h) for h in hands]
    di = [0] * M
    pi = [0] * M
    last_draw: Dict[int, Optional[int]] = {i: None for i in range(M)}
    last_discard: Optional[Tuple[int, int]] = None     # (who, tile id)
    last_kakan: List[Optional[Tuple[int, int]]] = [None]   # 直前の加槓 (who, 加えた牌)。槍槓の和了牌に使う
    pending_dora = 0
    kans = 0
    turn = oya
    riichi_decl = set()
    reason = None

    def reveal_dora():
        nonlocal dora_i
        if dora_i < len(doras):
            evs.append({"t": "dora", "tile": pool.take(doras[dora_i])})
            dora_i += 1

    def do_discard(who: int, entry) -> bool:
        """打牌列の 1 項目を処理。True なら局が続く（打牌した）、False なら打牌せず（カン・抜きで手番継続）。"""
        nonlocal last_discard, pending_dora, kans
        if isinstance(entry, str):
            if entry.startswith("r"):
                evs.append({"t": "riichi", "who": who})
                riichi_decl.add(who)
                c = int(entry[1:])
                tid = last_draw[who] if c == 60 else _pick(cur[who], ts, c)
                cur[who].remove(tid)
                evs.append({"t": "discard", "who": who, "tile": tid, "tsumogiri": tid == last_draw[who], "riichi": True})
                last_draw[who] = None            # 切ったあとは「直前に引いた牌」を持たない（鳴き後の打牌をツモ切りにしない）
                last_discard = (who, tid)
                return True
            kind, frm, codes, called = _parse_call(entry, who, M)
            if kind == "ankan":
                tiles = [_pick(cur[who], ts, c) for c in codes[:1]]
                for c in codes[1:]:
                    rest = [t for t in cur[who] if t not in tiles]
                    tiles.append(_pick(rest, ts, c))
                for t in tiles:
                    cur[who].remove(t)
                evs.append({"t": "kan", "who": who, "kind": "ankan", "tiles": sorted(tiles)})
                kans += 1
                reveal_dora()           # 暗槓は即めくり
            elif kind == "kakan":
                # ポンの 3 枚は手牌に無い。手牌から 1 枚だけ取り、ポンの牌は既存の meld から
                added = _pick(cur[who], ts, called)
                cur[who].remove(added)
                pon = next((m for m in melds[who] if m["kind"] == "pon" and ts["tiles"][m["tiles"][0]]["kind"] == ts["tiles"][added]["kind"]), None)
                if pon is None:
                    raise ValidationError(f"局 {k}: 加槓に対応するポンが無い")
                tiles = sorted(pon["tiles"] + [added])
                evs.append({"t": "kan", "who": who, "kind": "kakan", "tiles": tiles})
                last_kakan[0] = (who, added)
                pon["kind"] = "kakan"
                pon["tiles"] = tiles
                kans += 1
                pending_dora += 1       # 加槓・大明槓は嶺上ツモの後にめくる（実牌譜の順）
            elif kind == "nuki":
                tid = _pick(cur[who], ts, called)
                cur[who].remove(tid)
                evs.append({"t": "nuki", "who": who, "tile": tid})
            else:
                raise ValidationError(f"局 {k}: 打牌列に想定外の文字列 {entry!r}")
            return False
        c = int(entry)
        if c == 0:
            return False            # 大明槓のとき打牌列に置かれる 0（穴埋め）。打牌ではない
        if c == 60:
            tid = last_draw[who]
            if tid is None or tid not in cur[who]:
                raise ValidationError(f"局 {k}: ツモ切り（60）だがツモ牌が無い")
        else:
            tid = _pick(cur[who], ts, c)
        cur[who].remove(tid)
        evs.append({"t": "discard", "who": who, "tile": tid, "tsumogiri": tid == last_draw[who]})
        last_draw[who] = None            # 切ったあとは「直前に引いた牌」を持たない（鳴き後の打牌をツモ切りにしない）
        last_discard = (who, tid)
        return True

    melds: List[List[dict]] = [[] for _ in range(M)]
    # 和了・流局の判定は結果で分かるので、ツモ列・打牌列が尽きるまで回す
    guard = 0
    while True:
        guard += 1
        if guard > 2000:
            raise ValidationError(f"局 {k}: 進行が終わらない")
        who = turn
        # 他家の鳴き（直前の打牌に対する）を先に見る
        acted = False
        if last_discard is not None:
            for s in range(1, M):
                p = (last_discard[0] + s) % M
                if pi[p] < len(draws[p]) and isinstance(draws[p][pi[p]], str):
                    kind, frm, codes, called = _parse_call(draws[p][pi[p]], p, M)
                    if frm != last_discard[0] or code_to_kind(called)[0] != ts["tiles"][last_discard[1]]["kind"]:
                        continue
                    pi[p] += 1
                    ctile = last_discard[1]
                    # 呼んだ牌を除いた残りを手牌から取る
                    rest_codes = list(codes)
                    rest_codes.remove(called)
                    taken = []
                    for c in rest_codes:
                        avail = [t for t in cur[p] if t not in taken]
                        taken.append(_pick(avail, ts, c))
                    for t in taken:
                        cur[p].remove(t)
                    tiles = sorted(taken + [ctile])
                    if kind == "minkan":
                        evs.append({"t": "kan", "who": p, "kind": "minkan", "from": frm, "tiles": tiles})
                        melds[p].append({"kind": "minkan", "tiles": tiles})
                        kans += 1
                        pending_dora += 1
                        # 大明槓の嶺上ツモはツモ列の次の項目
                        if pi[p] < len(draws[p]) and not isinstance(draws[p][pi[p]], str):
                            rt = pool.take(int(draws[p][pi[p]]))
                            pi[p] += 1
                            cur[p].append(rt)
                            last_draw[p] = rt
                            evs.append({"t": "draw", "who": p, "tile": rt, "rinshan": True})
                            while pending_dora:
                                reveal_dora(); pending_dora -= 1
                    else:
                        evs.append({"t": kind, "who": p, "from": frm, "tiles": tiles})
                        melds[p].append({"kind": kind, "tiles": tiles})
                    last_discard = None
                    turn = p
                    who = p
                    acted = True
                    break
        if not acted:
            # 自分のツモ
            if pi[who] >= len(draws[who]):
                break
            entry = draws[who][pi[who]]
            if isinstance(entry, str):
                # 鳴きの文字列がここに来るのは、直前の打牌者が合わない場合
                raise ValidationError(f"局 {k}: seat {who} のツモ列の鳴き {entry!r} の相手が不明")
            pi[who] += 1
            tid = pool.take(int(entry))
            cur[who].append(tid)
            last_draw[who] = tid
            evs.append({"t": "draw", "who": who, "tile": tid})
        # 打牌（カン・抜きなら続けて次の打牌列へ。その前に嶺上ツモ）
        while True:
            if di[who] >= len(discs[who]):
                break
            entry = discs[who][di[who]]
            di[who] += 1
            if do_discard(who, entry):
                break
            # カン・抜きの後：嶺上ツモ
            if evs[-1]["t"] in ("kan", "nuki") or (evs[-1]["t"] == "dora" and len(evs) > 1 and evs[-2]["t"] == "kan"):
                if pi[who] < len(draws[who]) and not isinstance(draws[who][pi[who]], str):
                    tid = pool.take(int(draws[who][pi[who]]))
                    pi[who] += 1
                    cur[who].append(tid)
                    last_draw[who] = tid
                    evs.append({"t": "draw", "who": who, "tile": tid, "rinshan": True})
                    while pending_dora:
                        reveal_dora(); pending_dora -= 1
                else:
                    break
        else:
            pass
        if di[who] >= len(discs[who]) and pi[who] >= len(draws[who]):
            # この人の列が尽きた。他家の列も尽きていれば終わり
            if all(pi[p] >= len(draws[p]) for p in range(M)):
                break
        turn = (who + 1) % M

    # 結果
    res: dict
    tag = result[0]
    if tag == "和了":
        wins = []
        base = list(scores)
        after = list(scores)
        j = 1
        while j + 1 < len(result):
            deltas = list(result[j])[:M]
            info = result[j + 1]
            who, frm = int(info[0]), int(info[1])
            yaku, fu, han, yakuman = _parse_win_info(info[3:])
            after = [after[i] + deltas[i] for i in range(M)]
            if who == frm:
                win_tile = last_draw[who]
            elif evs and evs[-1]["t"] == "kan" and evs[-1]["kind"] == "kakan" and last_kakan[0] and last_kakan[0][0] == frm:
                win_tile = last_kakan[0][1]             # 槍槓：和了牌は加槓で加えた牌
            else:
                win_tile = last_discard[1] if last_discard else None
            hand = sorted(cur[who])
            if win_tile is not None and win_tile not in hand:
                hand = sorted(hand + [win_tile])        # 和了牌を含めた形（天鳳 AGARI.hai と同じ）
            w = {"who": who, "from": frm, "tile": win_tile, "hand": hand,
                 "melds": [{"kind": m["kind"], "tiles": m["tiles"], "from": frm} for m in melds[who]],
                 "yaku": yaku, "fu": fu, "han": han, "points": _points_from_info(info[3], M), "deltas": deltas}
            if yakuman:
                w["yakuman"] = yakuman
            if len(info) > 2 and info[2] != who:
                w["pao"] = int(info[2])
            wins.append(w)
            evs.append({"t": "win", "who": who, "from": frm, "tile": win_tile})
            j += 2
        res = {"wins": wins, "draw": None, "scores": after}
    else:
        reason = RESULT_DRAW.get(tag, "exhaustive")
        deltas = list(result[1])[:M] if len(result) > 1 and isinstance(result[1], list) else [0] * M
        after = [scores[i] + deltas[i] for i in range(M)]
        evs.append({"t": "draw_end", "reason": reason})
        res = {"wins": [], "draw": {"reason": reason, "tenpai": [None] * M, "hands": [None] * M, "deltas": deltas}, "scores": after}
        res["draw"]["tenpai"] = [d > 0 for d in deltas] if any(deltas) else [False] * M
    return {"index": k, "wall": None,
            "state": {"bakaze": "ESWN"[kyoku_i // 4], "kyoku": kyoku_i % 4 + 1, "honba": honba, "kyotaku": kyotaku,
                      "oya": oya, "scores": list(scores)},
            "events": evs, "result": res}


def _parse_win_info(items: List[str]) -> Tuple[List[dict], int, int, int]:
    """["30符2翻2000点", "立直(1飜)", "ドラ(2飜)"…] → (yaku[], fu, han, yakuman)。"""
    yaku = []
    han = 0
    yakuman = 0
    fu = 0
    head = items[0] if items else ""
    m = re.match(r"(\d+)符(\d+)[飜翻]", head)
    if m:
        fu, han_total = int(m.group(1)), int(m.group(2))
    else:
        han_total = None
    for s in items[1:]:
        m = re.match(r"(.+?)\((\d+)[飜翻]\)", s)
        if m:
            name = _yaku_name(m.group(1))
            if name is None:
                raise ValidationError(f"知らない役名 {m.group(1)!r}")
            yaku.append({"name": name, "han": int(m.group(2))})
            han += int(m.group(2))
            continue
        m = re.match(r"(.+?)\(役満\)", s)
        if m:
            name = _yaku_name(m.group(1))
            if name is None:
                raise ValidationError(f"知らない役名 {m.group(1)!r}")
            yaku.append({"name": name, "yakuman": 1})
            yakuman += 1
            continue
        m = re.match(r"(.+?)\(ダブル役満\)", s)
        if m:
            name = JP_YAKU.get(m.group(1))
            yaku.append({"name": name, "yakuman": 2})
            yakuman += 2
    if han_total is not None and han_total != han:
        han = han_total
    if not fu and not yakuman:
        # 満貫以上は符が書かれない。点数表の判定に必要な最小の符を置く
        fu = 70 if han == 3 else 40 if han == 4 else 30
    return yaku, fu, han, yakuman


def _yaku_name(jp: str) -> Optional[str]:
    """役名（日本語）→ 語彙。空白・コロンの有無の揺れ（天鳳「役牌 白」／雀魂「役牌:白」等）を吸収する。"""
    if jp in JP_YAKU:
        return JP_YAKU[jp]
    key = re.sub(r"[\s　:：]", "", jp)
    return _JP_YAKU_NORM.get(key)


def _points_from_info(head: str, M: int = 4) -> int:
    """点の文字列 → 合計点（本場・供託を含まない）。
    ロン "…2000点"、子のツモ "…500-1000点"（子の払い-親の払い）、親のツモ "…2000点∀"（1 人あたり）。"""
    m = re.search(r"(\d+)-(\d+)点", head)
    if m:
        return int(m.group(1)) * (M - 2) + int(m.group(2))
    m = re.search(r"(\d+)点∀", head)
    if m:
        return int(m.group(1)) * (M - 1)
    m = re.search(r"(\d+)点", head)
    if not m:
        raise ValidationError(f"点が読めない: {head!r}")
    return int(m.group(1))


# ---- 書き出し（record → 天鳳 JSON）。検証用：XML から作った record を JSON にして読み戻し、同じ進行になるか -----------

def export_json(rec: dict, rs: dict, ts: dict, walls: Optional[Dict[str, dict]] = None) -> dict:
    from .. import observe as O
    norm = R.normalize(rs)
    M = norm["players"]

    def code(tid: int) -> int:
        t = ts["tiles"][tid]
        return kind_to_code(t["kind"], t.get("mark") == "red")

    out = {"title": ["", ""], "name": [p.get("name", "") for p in sorted(rec["players"], key=lambda p: p["seat"])],
           "rule": {"disp": ("三" if M == 3 else "") + ("般南喰赤" if norm.get("length") == "east_south" else "般東喰赤"), "aka": 1}, "log": []}
    for rnd in rec["rounds"]:
        st = rnd["state"]
        wall = (walls or {}).get(rnd["wall"]["id"]) if rnd.get("wall") else None
        hands = O._initial_hands(rnd, norm, wall)
        evs = rnd["events"]
        res = rnd["result"] or {}
        doras = [e["tile"] for e in evs if e["t"] == "dora"]
        uras = []
        for w in res.get("wins", []):
            if w.get("ura_indicators"):
                uras = w["ura_indicators"]
        draws = [[] for _ in range(M)]
        discs = [[] for _ in range(M)]
        last_draw = {}
        last_discard = None
        pending_riichi = None
        for e in evs:
            t = e["t"]
            if t == "draw":
                draws[e["who"]].append(code(e["tile"]))
                last_draw[e["who"]] = e["tile"]
            elif t == "discard":
                c = 60 if e.get("tsumogiri") and last_draw.get(e["who"]) == e["tile"] else code(e["tile"])
                if pending_riichi == e["who"] or e.get("riichi"):
                    c = "r" + str(code(e["tile"]))
                    pending_riichi = None
                discs[e["who"]].append(c)
                last_discard = (e["who"], e["tile"])
            elif t == "riichi":
                pending_riichi = e["who"]
            elif t in ("chi", "pon"):
                called = last_discard[1]
                rest = [x for x in e["tiles"] if x != called]
                rel = (e["from"] - e["who"]) % M
                letter = "c" if t == "chi" else "p"
                s = _call_string(letter, code(called), [code(x) for x in rest], rel, M)
                draws[e["who"]].append(s)
            elif t == "kan":
                if e["kind"] == "minkan":
                    called = last_discard[1]
                    rest = [x for x in e["tiles"] if x != called]
                    rel = (e["from"] - e["who"]) % M
                    draws[e["who"]].append(_call_string("m", code(called), [code(x) for x in rest], rel, M))
                    discs[e["who"]].append(0)      # 天鳳は大明槓のとき打牌列に 0 を置く
                elif e["kind"] == "ankan":
                    cs = [code(x) for x in e["tiles"]]
                    discs[e["who"]].append("".join(str(c) for c in cs[:3]) + "a" + str(cs[3]))
                else:
                    cs = [code(x) for x in e["tiles"]]
                    discs[e["who"]].append("".join(str(c) for c in cs[:3]) + "k" + str(cs[3]))
            elif t == "nuki":
                discs[e["who"]].append("f" + str(code(e["tile"])))
        row = [[("ESWN".index(st["bakaze"])) * 4 + st["kyoku"] - 1, st["honba"], st["kyotaku"]], list(st["scores"]),
               [code(x) for x in doras], [code(x) for x in uras]]
        for i in range(M):
            row += [[code(x) for x in hands[i]], draws[i], discs[i]]
        if res.get("wins"):
            r = ["和了"]
            for w in res["wins"]:
                items = []
                # 点の書き方は天鳳どおり：ロン「2000点」、子のツモ「子-親点」、親のツモ「1 人あたり点∀」
                from .. import scoring as S
                is_tsumo = w["who"] == w["from"]
                is_dealer = w["who"] == st["oya"]
                _tot, parts = S.total_points(w["fu"], w["han"], w.get("yakuman", 0), is_dealer, is_tsumo, M, norm["game_rules"]["scoring"])
                if is_tsumo and is_dealer:
                    pts = f"{parts[0]}点∀"
                elif is_tsumo:
                    pts = f"{parts[-1]}-{parts[0]}点"
                else:
                    pts = f"{w['points']}点"
                if w.get("yakuman"):
                    items.append("役満" + pts)
                else:
                    b = S.base_points(w["fu"], w["han"], 0, norm["game_rules"]["scoring"])
                    limit = "満貫" if b == 2000 else "跳満" if b == 3000 else "倍満" if b == 4000 else "三倍満" if b == 6000 else "数え役満" if b >= 8000 else ""
                    items.append((limit if limit else f"{w['fu']}符{w['han']}飜") + pts)
                for y in w["yaku"]:
                    jp = _YAKU_JP.get(y["name"], y["name"])
                    items.append(f"{jp}(役満)" if "yakuman" in y else f"{jp}({y['han']}飜)")
                r += [list(w["deltas"]), [w["who"], w["from"], w.get("pao", w["who"])] + items]
            row.append(r)
        else:
            d = res.get("draw") or {}
            row.append([_DRAW_JP.get(d.get("reason"), "流局"), list(d.get("deltas", [0] * M))])
        out["log"].append(row)
    fin = rec.get("final", {})
    if fin.get("scores") and fin.get("settled"):
        sc = []
        for i in range(M):
            sc += [fin["scores"][i] // 100, fin["settled"][i]]
        out["sc"] = sc
    return out


def _call_string(letter: str, called: int, rest: List[int], rel: int, M: int) -> str:
    """rel＝from−who（mod M）。上家＝M−1 → 先頭、対面 → 中、下家 → 末尾。"""
    rest = sorted(rest)
    if rel == M - 1:
        return letter + str(called) + "".join(str(c) for c in rest)
    if rel == 1:
        return "".join(str(c) for c in rest) + letter + str(called)
    return str(rest[0]) + letter + str(called) + "".join(str(c) for c in rest[1:])
