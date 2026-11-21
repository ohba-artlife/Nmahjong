"""ルール ruleset（nmahjong-ruleset 1.0）— 既定値・正規形・id・検証・差分。仕様 ruleset.md。

方針（ruleset.md §2.0、§9）：
- game_rules／end／settlement の下は省略可。読み込み時に既定値を埋めた正規形を作り、id はそこから計算する
- 未知のキー・未知の語彙はエラー
- `unknown`（任意）：出典に無く値が分からない項目のパスの列。既定値で埋めるが、検証は「欠落」として列挙する。
  unknown は id に含める（「不明」と「既定値を主張」は別の設定）
"""
import copy
import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from . import tileset as TS
from .canon import ValidationError, sha256_id, id_hex64

FORMAT = "nmahjong-ruleset"
VERSION = "1.0"
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_DATA = os.path.join(os.path.dirname(__file__), "data")


def _load_json(name: str) -> dict:
    with open(os.path.join(_DATA, name), encoding="utf-8") as f:
        return json.load(f)


VOCAB = _load_json("vocab.json")
YAKU_TABLES = {"riichi-standard": _load_json("yaku-riichi-standard.json")}
YAKU_NAMES = set(VOCAB["yaku"]) | set(VOCAB["yakuman"])

# ---- 既定値（ruleset.md §2 の例。external_points は空が既定） ----------------------

DEFAULT_GAME_RULES: Dict[str, Any] = {
    "agari_form": "standard",
    "marks": {"red": {"effects": ["dora"]}},
    "mark_overrides": [],
    "dora": {"indicator": True, "ura": True, "kan": True, "kan_ura": True,
             "kan_timing": {"ankan": "immediate", "minkan": "after_discard", "kakan": "after_discard"},
             "values": {"indicator": 1, "ura": 1, "kan": 1, "kan_ura": 1}},
    "nuki": {"enabled": False},
    "yaku": {"base": "riichi-standard", "overrides": {}, "chiitoi_four_of_kind": False},
    "nagashi_mangan": {"enabled": False},
    "pao": {"yakuman": ["daisangen", "daisuushii", "suukantsu"], "tsumo": "full", "ron": "split",
            "honba_kyotaku": "discarder", "daiminkan_rinshan": False},
    "flow": {
        "open_tanyao": True, "atozuke": "allowed", "kuikae": "forbidden", "chi": True, "ippatsu": True,
        "riichi": {"min_points": 1000, "below_min": "forbidden", "without_draw": True, "on_houtei": True,
                   "furiten_riichi": True, "ankan_after": "if_shape_unchanged", "stick_at_end": "stays",
                   "stick_if_ronned": False},
        "open_riichi": {"enabled": False},
        "renchan": {"dealer_win": True, "dealer_tenpai": True, "all_noten": False, "draw": False, "by_bakaze": {}},
        "renchan_on_abort": True,
        "ryukyoku": {"nine_terminals": False, "four_winds": False, "four_kans": False, "four_riichi": False, "three_ron": False},
        "double_ron": False, "triple_ron": "head", "kyotaku_to": "kamicha", "wareme": False,
        "kokushi_ankan_chankan": False, "ryuuiisou_requires_hatsu": False, "chuuren_any_suit": True, "max_kans": 4,
        "pon": True, "kan_kinds": ["ankan", "minkan", "kakan"], "max_kans_per_player": None,
    },
    "scoring": {
        "table": "standard", "honba_points": 300, "kyotaku_points": 1000, "noten_penalty": 3000,
        "mangan_round_up": True, "round_to": 100,
        "fu": {"enabled": True, "double_wind_pair": 2, "rinshan_tsumo_fu": 2, "chiitoi": "25fu_2han",
               "open_pinfu_fu": 30, "menzen_tsumo_pinfu": True, "yakuhai_tanki_fu": 0},
        "limits": {"sanbaiman_from": 11, "kazoe_from": None, "yakuman_base": 4, "max_multiple": 1, "stack_with_normal": False},
        "shibari": {"from_honba": None, "han": 2, "exclude_dora": True},
        "tsumo_loss": "none", "payment": "standard",
    },
    "penalties": {
        "chombo": {"kind": "rank_points", "value": 20, "replay": True, "honba_increase": False},
        "false_call": {"kind": "agari_houki"},
        "noten_riichi": "chombo",
    },
}
DEFAULT_END: Dict[str, Any] = {
    "tobi": {"enabled": False}, "negative_points": "continue", "cold_points": None, "time_limit_sec": None,
    "extension": {"enabled": False}, "agari_yame": {"enabled": False}, "tenpai_yame": {"enabled": False}, "max_honba": None,
}
DEFAULT_SETTLEMENT: Dict[str, Any] = {
    "start_points": 25000, "return_points": 30000,
    "unit": {"name": "pt", "points_per_unit": 1000, "decimals": 1},
    "uma": [30, 10, -10, -30], "oka": "to_first", "tie": "split", "dealer_takes_all": False,
    "chips": [], "yakitori": {"enabled": False}, "external_points": [], "payout": None,
    "rounding": {"score_to_1000": "none", "remainder_to_top": False},
}
# 「enabled: true のときだけ使う」項目の既定（省略時に埋める）
ENABLED_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "game_rules.nuki": {"tiles": ["N"], "value": 1, "as_yakuhai": "none", "chan_nuki": False, "win_with_nuki_in_hand": True, "pao": False, "forbid_keep": False},
    "game_rules.nagashi_mangan": {"as": "tenpai_settlement", "noten_penalty": False, "renchan_if_dealer_tenpai": True},
    "game_rules.flow.open_riichi": {"han_total": 2, "deal_in": "yakuman", "exempt_prior_riichi": True, "chaser_pays": True, "with_double_riichi_han": 3},
    "end.tobi": {"at": 0, "exact_zero_is_tobi": False, "on_noten_penalty": True, "penalty_points": 0, "penalty_to": "none"},
    "end.extension": {"until_points": 30000, "max_rounds": 4, "once": True, "renchan_first": False},
    "end.agari_yame": {"when": "last_round", "forced": False, "others_may_continue": False},
    "end.tenpai_yame": {"forced": False, "require_tenpai": True},
    "settlement.yakitori": {"penalty": {"kind": "chips", "count": 1}, "revive": []},
}

# 「あるときだけ書く」項目（正規形に既定値を足さない＝これまでのルールの id を変えない）。
# 値が既定と同じなら正規形から落とす（省略したときと同じ id になる）
OPTIONAL_KEYS: Dict[str, Any] = {
    "game_rules.flow.next_dealer": "rotate",                 # rotate＝親は順に回る、winner＝和了した人が次の親
    "game_rules.scoring.tsumo_table": None,                   # 三人打ちの子のツモの払いの表 {"ロンの点": [親の払い, 子の払い]}
    "game_rules.yaku.wheel": "2to8",                          # 大車輪の形。2to8＝一色の 2〜8 の七対子、any_suit＝清一色の七対子ならどれでも
}
# scoring.table＝additive のときだけ持つ項目の既定
ADDITIVE_DEFAULTS: Dict[str, Any] = {"per_han": 1, "base": 2, "dealer": 1, "honba": 1, "honba_dealer_only": True, "multiplier": 1,
                                     "round_to": 1, "yakuman": 50, "karasu": {"menzen": 0, "open": 0}}

# ---- 語彙 ------------------------------------------------------------------------
ENUM = {
    "length": ["one", "east", "east_south", "full", "custom", "endless"],
    "deal": ["N_each_then_1_to_dealer"],
    "break.by": ["dice", "fixed", "none"],
    "agari_form_fixed": ["standard"],
    "mark_effects": ["dora", "yaku", "almighty", "reverse", "none"],
    "when.state": ["any", "riichi"], "when.how": ["any", "tsumo", "ron"],
    "kan_timing": ["immediate", "after_discard", "after_rinshan"],
    "as_yakuhai": ["none", "common", "seat"],
    "yaku.base": ["riichi-standard", "none"],
    "nagashi.as": ["tenpai_settlement", "draw_mangan", "win", "yakuman"],
    "pao.tsumo": ["full"], "pao.ron": ["split", "split_all", "full"], "pao.honba_kyotaku": ["discarder", "liable"],
    "atozuke": ["allowed", "forbidden", "kanzen_sakizuke"], "kuikae": ["allowed", "no_same_tile", "forbidden"],
    "below_min": ["forbidden", "allowed"], "ankan_after": ["if_shape_unchanged", "none", "any"],
    "stick_at_end": ["stays", "to_first"], "deal_in": ["yakuman", "normal"],
    "triple_ron": ["allow", "draw", "head"], "kyotaku_to": ["kamicha", "split"],
    "table_fixed": ["standard"], "fu.chiitoi": ["25fu_2han", "50fu_1han"],
    "tsumo_loss": ["none", "loss", "add_1000", "marudori", "north_split"],
    "payment": ["standard", "4p_total_from_opponent", "4p_child_half_from_opponent", "4p_dealer_share_from_opponent"],
    "chombo.kind": ["points", "rank_points", "kyotaku"], "false_call.kind": ["agari_houki", "kyotaku", "chombo"],
    "noten_riichi": ["chombo", "agari_houki"],
    "negative_points": ["continue", "zero"], "penalty_to": ["none", "tenpai_players", "winner"],
    "agari_yame.when": ["last_round"],
    "oka": ["to_first", "none", "split"], "tie": ["split", "seat_order", "draw"],
    "uma.threshold": ["return", "start"],
    "chips.when": ["always", "menzen", "tsumo", "ron"], "chips.per": ["tile", "event"],
    "yakitori.penalty.kind": ["chips", "points"], "yakitori.revive": ["all_cleared", "feed_yakitori", "last_cleared_returns"],
    "ext.kind": ["rank_only", "rank_plus_raw", "formula"],
    "fees.collect": ["each", "top_pays_all"],
    "winds": ["E", "S", "W", "N"],
}

# ---- 正規形 ----------------------------------------------------------------------

def _merge(default: Any, given: Any, path: str, errors: List[str]) -> Any:
    """default の構造に given を重ねる。default に無いキーは未知キーとしてエラー。"""
    if isinstance(default, dict):
        if given is None:
            return copy.deepcopy(default)
        if not isinstance(given, dict):
            errors.append(f"{path}: オブジェクトであるべき")
            return copy.deepcopy(default)
        if path in _FREE_KEY_OBJECTS:
            return copy.deepcopy(given)          # 名前→値の自由なオブジェクトは丸ごと置き換え
        out = {}
        free = False
        for k, dv in default.items():
            out[k] = _merge(dv, given.get(k), f"{path}.{k}", errors) if k in given else copy.deepcopy(dv)
        for k in given:
            if k not in default:
                if f"{path}.{k}" in OPTIONAL_KEYS:
                    if given[k] != OPTIONAL_KEYS[f"{path}.{k}"]:
                        out[k] = copy.deepcopy(given[k])
                elif path == "game_rules.scoring" and k == "additive":
                    if not isinstance(given[k], dict):
                        errors.append(f"{path}.additive: オブジェクトであるべき")
                    else:
                        for kk in given[k]:
                            if kk not in ADDITIVE_DEFAULTS:
                                errors.append(f"{path}.additive.{kk}: 未知の項目")
                        if isinstance(given[k].get("karasu"), dict):
                            for kk in given[k]["karasu"]:
                                if kk not in ("menzen", "open"):
                                    errors.append(f"{path}.additive.karasu.{kk}: 未知の項目")
                        out[k] = copy.deepcopy(given[k])
                elif free or _enabled_extra(path, k, given):
                    out[k] = copy.deepcopy(given[k])
                else:
                    errors.append(f"{path}.{k}: 未知の項目")
        # enabled: true の既定を埋める
        if path in ENABLED_DEFAULTS and out.get("enabled") is True:
            for k, dv in ENABLED_DEFAULTS[path].items():
                out.setdefault(k, copy.deepcopy(dv))
        if path == "game_rules.scoring" and out.get("table") == "additive":
            ad = out.get("additive") if isinstance(out.get("additive"), dict) else {}
            full = copy.deepcopy(ADDITIVE_DEFAULTS)
            for k, v in ad.items():
                if k == "karasu" and isinstance(v, dict):
                    full["karasu"].update(v)
                else:
                    full[k] = v
            out["additive"] = full
        return out
    return copy.deepcopy(given) if given is not None or default is None else copy.deepcopy(default)


# 中身のキーが自由（名前→値）なオブジェクト
_FREE_KEY_OBJECTS = {"game_rules.marks", "game_rules.yaku.overrides", "game_rules.flow.renchan.by_bakaze"}
# uma は配列か by_floating オブジェクト、payout は null かオブジェクト：_merge では触らず後で検証
_PASSTHROUGH = {"settlement.uma", "settlement.payout", "settlement.chips", "settlement.external_points",
                "game_rules.mark_overrides", "game_rules.pao.yakuman"}


def _enabled_extra(path: str, key: str, given: dict) -> bool:
    if path in ENABLED_DEFAULTS and given.get("enabled") is True:
        return key in ENABLED_DEFAULTS[path]
    if path == "settlement.uma":
        return True
    return False


def normalize(rs: dict) -> dict:
    """省略項目に既定値を埋めた正規形を返す（id は再計算しない）。未知キーは ValidationError。"""
    if not isinstance(rs, dict):
        raise ValidationError("ruleset がオブジェクトではない")
    errors: List[str] = []
    out: Dict[str, Any] = {}
    top_allowed = ["format", "version", "name", "id", "tileset", "players", "hand_size", "length", "rounds_total",
                   "winds", "wall_rules", "game_rules", "end", "settlement", "unknown", "meta"]
    for k in rs:
        if k not in top_allowed:
            errors.append(f"{k}: 未知の項目")
    for k in ("format", "version", "name", "id", "tileset", "players", "hand_size", "length", "rounds_total", "winds", "unknown", "meta"):
        if k in rs:
            out[k] = copy.deepcopy(rs[k])
    wr = rs.get("wall_rules")
    if isinstance(wr, dict):
        out["wall_rules"] = copy.deepcopy(wr)
        for k in wr:
            if k not in ("deal", "dead_wall", "dora_indicator", "ura_indicator", "kan_dora", "kan_ura", "rinshan", "break", "rinshan_reserved"):
                errors.append(f"wall_rules.{k}: 未知の項目")
        if wr.get("rinshan_reserved") is False:          # 書かないのと同じ（これまでの id のまま）
            del out["wall_rules"]["rinshan_reserved"]
    else:
        out["wall_rules"] = wr
    # game_rules / end / settlement：既定値と重ねる。_PASSTHROUGH は与えられた値をそのまま
    for sect, dflt in (("game_rules", DEFAULT_GAME_RULES), ("end", DEFAULT_END), ("settlement", DEFAULT_SETTLEMENT)):
        given = rs.get(sect, {})
        if given is None:
            given = {}
        merged = _merge(dflt, given, sect, errors)
        for p in _PASSTHROUGH:
            if p.startswith(sect + "."):
                key = p[len(sect) + 1:]
                if "." in key:
                    a, b = key.split(".", 1)
                    if isinstance(given.get(a), dict) and b in given[a]:
                        merged[a][b] = copy.deepcopy(given[a][b])
                elif key in given:
                    merged[key] = copy.deepcopy(given[key])
        out[sect] = merged
    # uma の既定は人数に依る：4 人は 30-10、それ以外は 0（出典が無いので値を発明しない）
    sgiven = rs.get("settlement") or {}
    if "uma" not in sgiven and isinstance(rs.get("players"), int) and rs["players"] != 4:
        out["settlement"]["uma"] = [0] * rs["players"]
    if errors:
        raise ValidationError("; ".join(errors))
    return out


def compute_id(norm: dict) -> str:
    """id ＝ id・name・meta を除く正規形の正規化 JSON の SHA-256（unknown は含める）。"""
    return sha256_id({k: v for k, v in norm.items() if k not in ("id", "name", "meta")})


def finalize(rs: dict) -> dict:
    """正規形にして id を付ける（生成器用）。"""
    n = normalize(rs)
    n["id"] = compute_id(n)
    return n


# ---- 検証 ------------------------------------------------------------------------

def _enum(v, key, path, errs):
    if v not in ENUM[key]:
        errs.append(f"{path}: 語彙外 {v!r}（{ENUM[key]}）")


def _int(v, path, errs, lo=None, hi=None, allow_none=False):
    if v is None and allow_none:
        return True
    if not isinstance(v, int) or isinstance(v, bool):
        errs.append(f"{path}: 整数であるべき {v!r}")
        return False
    if lo is not None and v < lo or hi is not None and v > hi:
        errs.append(f"{path}: 範囲外 {v}")
        return False
    return True


def _bool(v, path, errs):
    if not isinstance(v, bool):
        errs.append(f"{path}: 真偽値であるべき {v!r}")


def _han_value(v, path, errs):
    """役の翻数指定：false / 正整数 / {closed, open} / 'yakuman' / 'yakuman:n'"""
    if v is False:
        return
    if isinstance(v, bool):
        errs.append(f"{path}: true は不可（翻数か false）")
    elif isinstance(v, int):
        if v < 1:
            errs.append(f"{path}: 翻数は 1 以上")
    elif isinstance(v, dict):
        for k in v:
            if k not in ("closed", "open"):
                errs.append(f"{path}.{k}: closed／open 以外")
            elif v[k] is not None and (not isinstance(v[k], int) or isinstance(v[k], bool) or v[k] < 1):
                errs.append(f"{path}.{k}: 1 以上の整数か null")
    elif isinstance(v, str):
        if not re.fullmatch(r"yakuman(:[1-9]\d*)?", v):
            errs.append(f"{path}: 文字列は 'yakuman' か 'yakuman:n'")
    else:
        errs.append(f"{path}: 不正な値 {v!r}")


def validate(rs: dict, ts: Optional[dict] = None, search_dirs=()) -> Tuple[dict, List[str]]:
    """ruleset.md §5。戻り値 (正規形, 警告の列)。エラーは ValidationError（複数を ; で連結）。"""
    norm = normalize(rs)
    errs: List[str] = []
    warns: List[str] = []
    # 1
    if norm.get("format") != FORMAT:
        errs.append(f"format が {FORMAT} ではない")
    if norm.get("version") != VERSION:
        errs.append(f"version が {VERSION} ではない")
    name = norm.get("name")
    if not isinstance(name, str) or not NAME_RE.match(name):
        errs.append(f"name が [a-z0-9-]+ ではない: {name!r}")
    # 2 id
    if "id" in norm:
        try:
            id_hex64(norm["id"])
            if norm["id"] != compute_id(norm):
                errs.append("id が正規形のハッシュと一致しない")
        except ValidationError as e:
            errs.append(str(e))
    else:
        errs.append("id が無い")
    # 3 tileset
    tref = norm.get("tileset")
    K = None
    if not isinstance(tref, dict) or not isinstance(tref.get("name"), str) or not isinstance(tref.get("id"), str):
        errs.append("tileset が {name, id} ではない")
    else:
        if ts is None:
            try:
                ts = TS.find(id=tref["id"], search_dirs=search_dirs)
            except ValidationError:
                warns.append("牌表が見つからないため K・mark・kind は未照合")
        if ts is not None:
            if ts["id"] != tref["id"]:
                errs.append("tileset.id が渡された牌表と一致しない")
            K = TS.K(ts)
    # 4 players / hand_size / winds
    M = norm.get("players")
    N = norm.get("hand_size")
    _int(M, "players", errs, lo=1)
    _int(N, "hand_size", errs, lo=1)
    winds = norm.get("winds")
    if not isinstance(winds, list) or (isinstance(M, int) and len(winds) != M) or any(w not in ENUM["winds"] for w in (winds or [])):
        errs.append("winds は長さ players の E/S/W/N の配列")
    _enum(norm.get("length"), "length", "length", errs)
    if norm.get("length") == "endless":
        e_ = norm.get("end") or {}
        if not ((e_.get("tobi") or {}).get("enabled") or e_.get("time_limit_sec") is not None or e_.get("cold_points") is not None):
            errs.append("length=endless（区切りなし）のときは、終わり方（end.tobi／end.time_limit_sec／end.cold_points）のどれかが要る")
    if norm.get("length") == "custom":
        _int(norm.get("rounds_total"), "rounds_total", errs, lo=1)   # 18
    elif "rounds_total" in norm:
        errs.append("rounds_total は length=custom のときだけ")
    # wall_rules 5,6,7
    wr = norm.get("wall_rules")
    dead = None
    if not isinstance(wr, dict):
        errs.append("wall_rules が無い")
    else:
        _enum(wr.get("deal"), "deal", "wall_rules.deal", errs)
        if _int(wr.get("dead_wall"), "wall_rules.dead_wall", errs, lo=0):
            dead = wr["dead_wall"]
        br = wr.get("break")
        if not isinstance(br, dict) or br.get("by") not in ENUM["break.by"]:
            errs.append("wall_rules.break は {by: dice|fixed|none}")
        used: Dict[int, str] = {}
        def offs(key, must_len=None):
            v = wr.get(key)
            if v is None:
                return None
            if key == "rinshan" and v == "live":
                return "live"
            if not isinstance(v, list) or not v:
                errs.append(f"wall_rules.{key}: 配列であるべき")
                return None
            for x in v:
                if not _int(x, f"wall_rules.{key}[]", errs, lo=(-(dead or 0) if key in ("kan_dora", "kan_ura", "rinshan") else 0)):
                    continue
                if x < 0 and key not in ("kan_dora", "kan_ura", "rinshan"):
                    errs.append(f"wall_rules.{key}: 負のオフセットは kan_dora／kan_ura／rinshan だけ")
                    continue
                if dead is not None and x >= dead:
                    errs.append(f"wall_rules.{key}: オフセット {x} が dead_wall={dead} 以上")
                if x in used and used[x] != key:
                    errs.append(f"wall_rules.{key}: 位置 {x} が {used[x]} と重複")
                used[x] = key
            return v
        d = offs("dora_indicator"); u = offs("ura_indicator"); kd = offs("kan_dora"); ku = offs("kan_ura"); rin = offs("rinshan")
        if dead == 0 and any(k in wr for k in ("dora_indicator", "ura_indicator", "kan_dora", "kan_ura", "rinshan")):
            errs.append("dead_wall=0 のとき王牌内の位置項目は書けない")
        if "rinshan_reserved" in wr and (wr["rinshan_reserved"] is not True or not isinstance(rin, list)):
            errs.append("wall_rules.rinshan_reserved: true だけ。rinshan が位置の配列のときに書ける")
        if d is not None and u is not None and len(d) != len(u):
            errs.append("dora_indicator と ura_indicator の長さが違う")
        if kd is not None and ku is not None and len(kd) != len(ku):
            errs.append("kan_dora と kan_ura の長さが違う")
        if K is not None and isinstance(M, int) and isinstance(N, int) and dead is not None and N * M + 1 + dead > K:
            errs.append(f"N×M+1+dead_wall = {N*M+1+dead} > K = {K}")
    g = norm["game_rules"]; e = norm["end"]; s = norm["settlement"]
    fl = g["flow"]; sc = g["scoring"]
    # 7 rinshan 長さ
    if isinstance(wr, dict) and isinstance(wr.get("rinshan"), list):
        need = fl["max_kans"] if isinstance(fl.get("max_kans"), int) else 0
        if len(wr["rinshan"]) < need:
            errs.append(f"rinshan の長さ {len(wr['rinshan'])} < max_kans {need}")
    # 8 agari_form
    af = g["agari_form"]
    if af == "standard":
        if isinstance(N, int) and N % 3 != 1:
            errs.append(f"agari_form=standard は hand_size mod 3 = 1 が必要（N={N}）")
    elif not (isinstance(af, str) and af.startswith("custom:") and len(af) > 7):
        errs.append("agari_form は standard か custom:<name>")
    # 9 marks
    kinds = {t["kind"] for t in ts["tiles"]} if ts else None
    marks_in_ts = {t.get("mark") for t in ts["tiles"] if "mark" in t} if ts else None
    def mark_rule(v, path):
        if not isinstance(v, dict):
            errs.append(f"{path}: オブジェクトであるべき"); return
        eff = v.get("effects")
        if not isinstance(eff, list) or not eff or any(x not in ENUM["mark_effects"] for x in eff):
            errs.append(f"{path}.effects: {ENUM['mark_effects']} の配列")
        else:
            if "none" in eff and len(eff) > 1:
                errs.append(f"{path}.effects: none は単独")
            if "reverse" in eff and "almighty" not in eff:
                errs.append(f"{path}.effects: reverse は almighty と共に")
        for k in v:
            if k not in ("effects", "when", "forced_high", "value", "as_ura_indicator", "tile_kind", "tile_id", "mark"):
                errs.append(f"{path}.{k}: 未知の項目")
        w = v.get("when")
        if w is not None:
            if not isinstance(w, dict):
                errs.append(f"{path}.when: オブジェクト")
            else:
                for k, val in w.items():
                    if k == "state": _enum(val, "when.state", f"{path}.when.state", errs)
                    elif k == "how": _enum(val, "when.how", f"{path}.when.how", errs)
                    elif k in ("ippatsu_only", "rinshan_ok", "haitei_ok", "menzen_only"): _bool(val, f"{path}.when.{k}", errs)
                    else: errs.append(f"{path}.when.{k}: 未知の項目")
        if "value" in v: _int(v["value"], f"{path}.value", errs, lo=1)
        if "forced_high" in v: _bool(v["forced_high"], f"{path}.forced_high", errs)
    for mk, v in g["marks"].items():
        if marks_in_ts is not None and mk not in marks_in_ts:
            warns.append(f"marks.{mk}: 牌表に無い印（効果なし。既定の red は赤なし牌表では無視される）")
        mark_rule(v, f"game_rules.marks.{mk}")
    if not isinstance(g["mark_overrides"], list):
        errs.append("mark_overrides は配列")
    else:
        for i, o in enumerate(g["mark_overrides"]):
            p = f"game_rules.mark_overrides[{i}]"
            mark_rule(o, p)
            if isinstance(o, dict):
                if "tile_kind" not in o and "tile_id" not in o:
                    errs.append(f"{p}: tile_kind か tile_id が必要")
                if kinds is not None and "tile_kind" in o and o["tile_kind"] not in kinds:
                    errs.append(f"{p}.tile_kind: 牌表に無い {o['tile_kind']!r}")
                if K is not None and "tile_id" in o and not (isinstance(o["tile_id"], int) and 0 <= o["tile_id"] < K):
                    errs.append(f"{p}.tile_id: 範囲外")
                if marks_in_ts is not None and "mark" in o and o["mark"] not in marks_in_ts:
                    errs.append(f"{p}.mark: 牌表に無い印")
    # dora
    dr = g["dora"]
    for k in ("indicator", "ura", "kan", "kan_ura"):
        _bool(dr[k], f"game_rules.dora.{k}", errs)
    for k, v in dr["kan_timing"].items():
        _enum(v, "kan_timing", f"game_rules.dora.kan_timing.{k}", errs)
    for k, v in dr["values"].items():
        _int(v, f"game_rules.dora.values.{k}", errs, lo=0)
    # 10 yaku
    y = g["yaku"]
    _enum(y["base"], "yaku.base", "game_rules.yaku.base", errs)
    _bool(y["chiitoi_four_of_kind"], "game_rules.yaku.chiitoi_four_of_kind", errs)
    for yn, v in y["overrides"].items():
        if yn not in YAKU_NAMES:
            errs.append(f"yaku.overrides.{yn}: 語彙に無い役")
        _han_value(v, f"game_rules.yaku.overrides.{yn}", errs)
    for yn in g["pao"]["yakuman"]:
        if yn not in VOCAB["yakuman"]:
            errs.append(f"pao.yakuman: 語彙に無い役満 {yn!r}")
    _enum(g["pao"]["tsumo"], "pao.tsumo", "game_rules.pao.tsumo", errs)
    _enum(g["pao"]["ron"], "pao.ron", "game_rules.pao.ron", errs)
    _enum(g["pao"]["honba_kyotaku"], "pao.honba_kyotaku", "game_rules.pao.honba_kyotaku", errs)
    _bool(g["pao"]["daiminkan_rinshan"], "game_rules.pao.daiminkan_rinshan", errs)
    nm = g["nagashi_mangan"]
    _bool(nm.get("enabled"), "game_rules.nagashi_mangan.enabled", errs)
    if nm.get("enabled"):
        _enum(nm.get("as"), "nagashi.as", "game_rules.nagashi_mangan.as", errs)
        _bool(nm.get("noten_penalty"), "game_rules.nagashi_mangan.noten_penalty", errs)
        _bool(nm.get("renchan_if_dealer_tenpai"), "game_rules.nagashi_mangan.renchan_if_dealer_tenpai", errs)
    # 11 nuki
    nk = g["nuki"]
    _bool(nk.get("enabled"), "game_rules.nuki.enabled", errs)
    if nk.get("enabled"):
        tiles = nk.get("tiles")
        if not isinstance(tiles, list) or not tiles:
            errs.append("nuki.tiles は空でない配列")
        else:
            for t in tiles:
                if kinds is not None and t not in kinds:
                    errs.append(f"nuki.tiles: 牌表に無い {t!r}")
                if nk.get("as_yakuhai") == "seat" and t not in ("E", "S", "W", "N"):
                    errs.append("nuki.as_yakuhai=seat のとき tiles は風牌")
        _int(nk.get("value"), "game_rules.nuki.value", errs, lo=0)
        _enum(nk.get("as_yakuhai"), "as_yakuhai", "game_rules.nuki.as_yakuhai", errs)
        for k in ("chan_nuki", "win_with_nuki_in_hand", "pao", "forbid_keep"):
            _bool(nk.get(k), f"game_rules.nuki.{k}", errs)
    # flow
    _bool(fl["open_tanyao"], "flow.open_tanyao", errs)
    _enum(fl["atozuke"], "atozuke", "flow.atozuke", errs)
    _enum(fl["kuikae"], "kuikae", "flow.kuikae", errs)
    _bool(fl["chi"], "flow.chi", errs)
    _bool(fl["ippatsu"], "flow.ippatsu", errs)
    r = fl["riichi"]
    _int(r["min_points"], "flow.riichi.min_points", errs, lo=0)
    _enum(r["below_min"], "below_min", "flow.riichi.below_min", errs)
    for k in ("without_draw", "on_houtei", "furiten_riichi", "stick_if_ronned"):
        _bool(r[k], f"flow.riichi.{k}", errs)
    _enum(r["ankan_after"], "ankan_after", "flow.riichi.ankan_after", errs)
    _enum(r["stick_at_end"], "stick_at_end", "flow.riichi.stick_at_end", errs)
    orr = fl["open_riichi"]
    _bool(orr.get("enabled"), "flow.open_riichi.enabled", errs)
    if orr.get("enabled"):
        _int(orr.get("han_total"), "flow.open_riichi.han_total", errs, lo=1)
        _enum(orr.get("deal_in"), "deal_in", "flow.open_riichi.deal_in", errs)
        for k in ("exempt_prior_riichi", "chaser_pays"):
            _bool(orr.get(k), f"flow.open_riichi.{k}", errs)
        _int(orr.get("with_double_riichi_han"), "flow.open_riichi.with_double_riichi_han", errs, lo=1)
        if y["overrides"].get("open_riichi") is False:
            warns.append("open_riichi.enabled だが yaku.overrides.open_riichi が false")   # 22
    rc = fl["renchan"]
    for k in ("dealer_win", "dealer_tenpai", "all_noten", "draw"):
        _bool(rc[k], f"flow.renchan.{k}", errs)
    for bk, bv in rc["by_bakaze"].items():
        if bk not in ENUM["winds"]:
            errs.append(f"flow.renchan.by_bakaze.{bk}: 風ではない")
        if not isinstance(bv, dict) or any(k not in ("dealer_win", "dealer_tenpai", "all_noten", "draw", "dealer_noten") for k in bv):
            errs.append(f"flow.renchan.by_bakaze.{bk}: 項目が不正")
    _bool(fl["renchan_on_abort"], "flow.renchan_on_abort", errs)
    for k, v in fl["ryukyoku"].items():
        _bool(v, f"flow.ryukyoku.{k}", errs)
    _bool(fl["double_ron"], "flow.double_ron", errs)
    _enum(fl["triple_ron"], "triple_ron", "flow.triple_ron", errs)
    _enum(fl["kyotaku_to"], "kyotaku_to", "flow.kyotaku_to", errs)
    _bool(fl["wareme"], "flow.wareme", errs)
    if fl["wareme"] and isinstance(wr, dict) and isinstance(wr.get("break"), dict) and wr["break"].get("by") == "none":
        errs.append("wareme=true のとき break.by は none 以外")   # 12
    for k in ("kokushi_ankan_chankan", "ryuuiisou_requires_hatsu", "chuuren_any_suit"):
        _bool(fl[k], f"flow.{k}", errs)
    _int(fl["max_kans"], "flow.max_kans", errs, lo=0)
    _bool(fl["pon"], "flow.pon", errs)
    kk = fl["kan_kinds"]
    if not isinstance(kk, list) or any(x not in ("ankan", "minkan", "kakan") for x in kk) or len(set(kk)) != len(kk):
        errs.append("flow.kan_kinds は ankan／minkan／kakan の配列（重複なし）")
    elif "kakan" in kk and not fl["pon"]:
        errs.append("flow.kan_kinds に kakan があるなら flow.pon=true（加槓はポンから）")
    if fl["max_kans_per_player"] is not None:
        _int(fl["max_kans_per_player"], "flow.max_kans_per_player", errs, lo=0)
    if M == 4 and fl["chi"] is False:
        warns.append("players=4 で chi=false")   # 13
    # scoring 20
    tb = sc["table"]
    if not (tb in ("standard", "additive") or (isinstance(tb, str) and tb.startswith("custom:") and len(tb) > 7)):
        errs.append("scoring.table は standard か additive か custom:<name>")
    if tb == "additive":
        ad = sc["additive"]
        for k in ("per_han", "base", "dealer", "honba", "yakuman"):
            _int(ad.get(k), f"scoring.additive.{k}", errs, lo=0)
        for k in ("multiplier", "round_to"):
            _int(ad.get(k), f"scoring.additive.{k}", errs, lo=1)
        _bool(ad.get("honba_dealer_only"), "scoring.additive.honba_dealer_only", errs)
        ka = ad.get("karasu")
        if not isinstance(ka, dict):
            errs.append("scoring.additive.karasu はオブジェクト")
        else:
            for k in ("menzen", "open"):
                _int(ka.get(k), f"scoring.additive.karasu.{k}", errs, lo=0)
        if sc["payment"] != "standard":
            errs.append("scoring.table＝additive のとき payment は standard")
    elif "additive" in sc:
        errs.append("scoring.additive は table＝additive のときだけ")
    if "next_dealer" in fl and fl["next_dealer"] not in ("rotate", "winner"):
        errs.append("flow.next_dealer は rotate か winner")
    if "tsumo_table" in sc:
        tt = sc["tsumo_table"]
        if M != 3:
            errs.append("scoring.tsumo_table は三人打ちのときだけ")
        if not isinstance(tt, dict) or not tt:
            errs.append("scoring.tsumo_table は {\"ロンの点\": [親の払い, 子の払い]} の表")
        else:
            for k, v in tt.items():
                if not (isinstance(k, str) and k.isdigit() and isinstance(v, list) and len(v) == 2 and all(isinstance(x, int) and not isinstance(x, bool) and x >= 0 for x in v)):
                    errs.append(f"scoring.tsumo_table[{k!r}]: [親の払い, 子の払い]（0 以上の整数 2 つ）")
    if "wheel" in g["yaku"] and g["yaku"]["wheel"] not in ("2to8", "any_suit"):
        errs.append("yaku.wheel は 2to8 か any_suit")
    for k in ("honba_points", "kyotaku_points", "noten_penalty"):
        _int(sc[k], f"scoring.{k}", errs, lo=0)
    _bool(sc["mangan_round_up"], "scoring.mangan_round_up", errs)
    if sc["round_to"] not in (100, 1000):
        errs.append("scoring.round_to は 100 か 1000")
    fu = sc["fu"]
    _bool(fu["enabled"], "scoring.fu.enabled", errs)
    if fu["double_wind_pair"] not in (2, 4): errs.append("fu.double_wind_pair は 2 か 4")
    if fu["rinshan_tsumo_fu"] not in (0, 2): errs.append("fu.rinshan_tsumo_fu は 0 か 2")
    _enum(fu["chiitoi"], "fu.chiitoi", "scoring.fu.chiitoi", errs)
    _int(fu["open_pinfu_fu"], "scoring.fu.open_pinfu_fu", errs, lo=20)
    _bool(fu["menzen_tsumo_pinfu"], "scoring.fu.menzen_tsumo_pinfu", errs)
    _int(fu["yakuhai_tanki_fu"], "scoring.fu.yakuhai_tanki_fu", errs, lo=0)
    lm = sc["limits"]
    _int(lm["sanbaiman_from"], "scoring.limits.sanbaiman_from", errs, lo=1)
    if lm["kazoe_from"] is not None:
        if _int(lm["kazoe_from"], "scoring.limits.kazoe_from", errs, lo=1) and isinstance(lm["sanbaiman_from"], int) and lm["kazoe_from"] <= lm["sanbaiman_from"]:
            errs.append("limits.kazoe_from は sanbaiman_from より大きい")
    _int(lm["yakuman_base"], "scoring.limits.yakuman_base", errs, lo=1)
    _int(lm["max_multiple"], "scoring.limits.max_multiple", errs, lo=1)
    _bool(lm["stack_with_normal"], "scoring.limits.stack_with_normal", errs)
    sh = sc["shibari"]
    _int(sh["from_honba"], "scoring.shibari.from_honba", errs, lo=1, allow_none=True)
    _int(sh["han"], "scoring.shibari.han", errs, lo=1)
    _bool(sh["exclude_dora"], "scoring.shibari.exclude_dora", errs)
    _enum(sc["tsumo_loss"], "tsumo_loss", "scoring.tsumo_loss", errs)
    _enum(sc["payment"], "payment", "scoring.payment", errs)
    if sc["payment"] != "standard" and M != 2:
        errs.append("scoring.payment が standard 以外なら players=2")
    # penalties 21
    ch = g["penalties"]["chombo"]
    _enum(ch.get("kind"), "chombo.kind", "penalties.chombo.kind", errs)
    _int(ch.get("value"), "penalties.chombo.value", errs, lo=0)
    for k in ("replay", "honba_increase"):
        _bool(ch.get(k), f"penalties.chombo.{k}", errs)
    fc = g["penalties"]["false_call"]
    _enum(fc.get("kind"), "false_call.kind", "penalties.false_call.kind", errs)
    if fc.get("kind") == "kyotaku":
        _int(fc.get("value"), "penalties.false_call.value", errs, lo=0)
    _enum(g["penalties"]["noten_riichi"], "noten_riichi", "penalties.noten_riichi", errs)
    # end 19
    tb_ = e["tobi"]
    _bool(tb_.get("enabled"), "end.tobi.enabled", errs)
    if tb_.get("enabled"):
        _int(tb_.get("at"), "end.tobi.at", errs)
        _bool(tb_.get("exact_zero_is_tobi"), "end.tobi.exact_zero_is_tobi", errs)
        _bool(tb_.get("on_noten_penalty"), "end.tobi.on_noten_penalty", errs)
        _int(tb_.get("penalty_points"), "end.tobi.penalty_points", errs, lo=0)
        _enum(tb_.get("penalty_to"), "penalty_to", "end.tobi.penalty_to", errs)
        if tb_.get("penalty_to") != "none" and not tb_.get("penalty_points"):
            errs.append("end.tobi.penalty_to ≠ none なら penalty_points > 0")
    _enum(e["negative_points"], "negative_points", "end.negative_points", errs)
    _int(e["cold_points"], "end.cold_points", errs, lo=1, allow_none=True)
    _int(e["time_limit_sec"], "end.time_limit_sec", errs, lo=1, allow_none=True)
    _int(e["max_honba"], "end.max_honba", errs, lo=1, allow_none=True)
    ex = e["extension"]
    _bool(ex.get("enabled"), "end.extension.enabled", errs)
    if ex.get("enabled"):
        _int(ex.get("until_points"), "end.extension.until_points", errs)
        _int(ex.get("max_rounds"), "end.extension.max_rounds", errs, lo=1)
        _bool(ex.get("once"), "end.extension.once", errs)
        _bool(ex.get("renchan_first"), "end.extension.renchan_first", errs)
    ay = e["agari_yame"]
    _bool(ay.get("enabled"), "end.agari_yame.enabled", errs)
    if ay.get("enabled"):
        _enum(ay.get("when"), "agari_yame.when", "end.agari_yame.when", errs)
        _bool(ay.get("forced"), "end.agari_yame.forced", errs)
        _bool(ay.get("others_may_continue"), "end.agari_yame.others_may_continue", errs)
    ty = e["tenpai_yame"]
    _bool(ty.get("enabled"), "end.tenpai_yame.enabled", errs)
    if ty.get("enabled"):
        _bool(ty.get("forced"), "end.tenpai_yame.forced", errs)
        _bool(ty.get("require_tenpai"), "end.tenpai_yame.require_tenpai", errs)
    # settlement 14, 14b, 14c, 15, 16, 17
    _int(s["start_points"], "settlement.start_points", errs)
    _int(s["return_points"], "settlement.return_points", errs)
    un = s["unit"]
    if not isinstance(un, dict) or not isinstance(un.get("name"), str):
        errs.append("settlement.unit は {name, points_per_unit, decimals}")
    else:
        _int(un.get("points_per_unit"), "settlement.unit.points_per_unit", errs, lo=1)   # 17
        _int(un.get("decimals"), "settlement.unit.decimals", errs, lo=0)
    uma = s["uma"]
    def _uma_arr(arr, path):
        if not isinstance(arr, list) or (isinstance(M, int) and len(arr) != M) or any(not isinstance(x, (int, float)) or isinstance(x, bool) for x in arr):
            errs.append(f"{path}: 長さ players の数値配列")
            return
        if abs(sum(arr)) > 1e-9:
            warns.append(f"{path} の合計が 0 ではない（{sum(arr)}）")
    if isinstance(uma, list):
        _uma_arr(uma, "settlement.uma")
    elif isinstance(uma, dict):
        bf = uma.get("by_floating")
        if not isinstance(bf, dict):
            errs.append("settlement.uma.by_floating が無い")
        else:
            if isinstance(M, int) and set(bf) != {str(i) for i in range(1, M)}:
                errs.append(f"settlement.uma.by_floating のキーは 1〜{M-1} 全部")
            for k, arr in bf.items():
                _uma_arr(arr, f"settlement.uma.by_floating.{k}")
        th = uma.get("threshold", "return")
        if not (th in ENUM["uma.threshold"] or (isinstance(th, int) and not isinstance(th, bool))):
            errs.append("settlement.uma.threshold は return／start／整数")
        if "includes_threshold" in uma: _bool(uma["includes_threshold"], "settlement.uma.includes_threshold", errs)
        for k in uma:
            if k not in ("by_floating", "threshold", "includes_threshold"):
                errs.append(f"settlement.uma.{k}: 未知の項目")
    else:
        errs.append("settlement.uma は配列か {by_floating,…}")
    rd = s["rounding"]
    if rd.get("score_to_1000") not in ("none", "half_up_600", "half_up_500"):
        errs.append("settlement.rounding.score_to_1000 は none／half_up_600／half_up_500")
    _bool(rd.get("remainder_to_top"), "settlement.rounding.remainder_to_top", errs)
    _enum(s["oka"], "oka", "settlement.oka", errs)
    _enum(s["tie"], "tie", "settlement.tie", errs)
    _bool(s["dealer_takes_all"], "settlement.dealer_takes_all", errs)
    # 15 chips
    chips = s["chips"]
    if not isinstance(chips, list):
        errs.append("settlement.chips は配列")
        chips = []
    for i, c in enumerate(chips):
        p = f"settlement.chips[{i}]"
        if not isinstance(c, dict):
            errs.append(f"{p}: オブジェクト"); continue
        if c.get("on") not in VOCAB["chips_on"]:
            errs.append(f"{p}.on: 語彙外 {c.get('on')!r}")
        if c.get("on") == "yakitori" and not s["yakitori"].get("enabled"):
            errs.append(f"{p}: on=yakitori は yakitori.enabled のときだけ")
        if c.get("on") == "win_kind" and c.get("kind") not in VOCAB["win_kinds"]:
            errs.append(f"{p}.kind: win_kinds の語彙 {VOCAB['win_kinds']}")
        _enum(c.get("per"), "chips.per", f"{p}.per", errs)
        _int(c.get("count"), f"{p}.count", errs, lo=1)
        if c.get("payer") not in VOCAB["chips_payer"]:
            errs.append(f"{p}.payer: 語彙外")
        if "when" in c: _enum(c["when"], "chips.when", f"{p}.when", errs)
        if "win_tile" in c:
            _bool(c["win_tile"], f"{p}.win_tile", errs)
            if c.get("on") != "win_with_mark":
                errs.append(f"{p}.win_tile は on=win_with_mark のときだけ")
        if "kan_kind" in c:
            if c.get("on") != "kan":
                errs.append(f"{p}.kan_kind は on=kan のときだけ")
            elif not isinstance(c["kan_kind"], list) or any(k not in VOCAB["kan_kinds"] for k in c["kan_kind"]):
                errs.append(f"{p}.kan_kind: 語彙外")
        if marks_in_ts is not None and "mark" in c and c["mark"] not in marks_in_ts:
            errs.append(f"{p}.mark: 牌表に無い印")
        if kinds is not None and "tile_kind" in c and c["tile_kind"] not in kinds:
            errs.append(f"{p}.tile_kind: 牌表に無い")
        if K is not None and "tile_id" in c and not (isinstance(c["tile_id"], int) and 0 <= c["tile_id"] < K):
            errs.append(f"{p}.tile_id: 範囲外")
        for k in c:
            if k not in ("on", "kind", "mark", "tile_kind", "tile_id", "when", "per", "count", "payer", "kan_kind", "win_tile"):
                errs.append(f"{p}.{k}: 未知の項目")
    # 16 yakitori
    yk = s["yakitori"]
    _bool(yk.get("enabled"), "settlement.yakitori.enabled", errs)
    if yk.get("enabled"):
        pen = yk.get("penalty")
        if not isinstance(pen, dict) or pen.get("kind") not in ENUM["yakitori.penalty.kind"]:
            errs.append("settlement.yakitori.penalty は {kind: chips|points, …}")
        elif pen["kind"] == "chips":
            _int(pen.get("count"), "settlement.yakitori.penalty.count", errs, lo=1)
        else:
            _int(pen.get("value"), "settlement.yakitori.penalty.value", errs, lo=1)
        for rv in yk.get("revive", []):
            if isinstance(rv, dict):
                if set(rv) != {"time_limit_sec"} or not _int(rv["time_limit_sec"], "yakitori.revive.time_limit_sec", errs, lo=1):
                    errs.append("settlement.yakitori.revive の時間指定は {time_limit_sec}")
            elif rv not in ENUM["yakitori.revive"]:
                errs.append(f"settlement.yakitori.revive: 語彙外 {rv!r}")
    # 14b external_points
    eps = s["external_points"]
    if not isinstance(eps, list):
        errs.append("settlement.external_points は配列"); eps = []
    for i, ep in enumerate(eps):
        p = f"settlement.external_points[{i}]"
        if not isinstance(ep, dict) or not isinstance(ep.get("system"), str):
            errs.append(f"{p}: system が必要"); continue
        _enum(ep.get("kind"), "ext.kind", f"{p}.kind", errs)
        if ep.get("kind") in ("rank_only", "rank_plus_raw"):
            rp = ep.get("rank_points")
            if isinstance(rp, list):
                if isinstance(M, int) and len(rp) != M: errs.append(f"{p}.rank_points の長さ ≠ players")
            elif isinstance(rp, dict) and isinstance(rp.get("by_player_rank"), dict):
                for k, arr in rp["by_player_rank"].items():
                    if not isinstance(arr, list) or (isinstance(M, int) and len(arr) != M):
                        errs.append(f"{p}.rank_points.by_player_rank.{k} の長さ ≠ players")
            else:
                errs.append(f"{p}.rank_points は配列か {{by_player_rank}}")
        if ep.get("kind") == "rank_plus_raw":
            _int(ep.get("raw_base"), f"{p}.raw_base", errs)
            _int(ep.get("raw_divisor"), f"{p}.raw_divisor", errs, lo=1)
        for k in ep:
            if k not in ("system", "kind", "raw_base", "raw_divisor", "rank_points", "rounding"):
                errs.append(f"{p}.{k}: 未知の項目")
    # 14c payout
    po = s["payout"]
    if po is not None:
        if not isinstance(po, dict):
            errs.append("settlement.payout は null かオブジェクト")
        else:
            un2 = po.get("unit")
            if not isinstance(un2, dict) or not isinstance(un2.get("code"), str) or not re.fullmatch(r"[A-Z]{2,8}", un2["code"]):
                errs.append("payout.unit.code は大文字英字 2〜8 文字（ISO 4217 含む）")
            if not isinstance(po.get("per_pt"), (int, float)) or isinstance(po.get("per_pt"), bool) or po["per_pt"] <= 0:
                errs.append("payout.per_pt > 0")
            if chips and "chip_value" not in po:
                errs.append("chips があるとき payout.chip_value が必要")
            if "chip_value" in po and (not isinstance(po["chip_value"], (int, float)) or po["chip_value"] < 0):
                errs.append("payout.chip_value は 0 以上")
            if "rounding" in po and po["rounding"] not in ("none", "round_100"):
                errs.append("payout.rounding は none か round_100")
            fees = po.get("fees")
            if fees is not None:
                if not isinstance(fees, dict):
                    errs.append("payout.fees はオブジェクト")
                else:
                    br_ = fees.get("by_rank")
                    if not isinstance(br_, list) or (isinstance(M, int) and len(br_) != M) or any(not isinstance(x, (int, float)) or x < 0 for x in br_):
                        errs.append("payout.fees.by_rank は長さ players の非負数値")
                    _enum(fees.get("collect", "each"), "fees.collect", "payout.fees.collect", errs)
                    if "unit" in fees and not (isinstance(fees["unit"], dict) and isinstance(fees["unit"].get("code"), str)):
                        errs.append("payout.fees.unit は {code}")
                    for k in fees:
                        if k not in ("by_rank", "collect", "unit"):
                            errs.append(f"payout.fees.{k}: 未知の項目")
            for k in po:
                if k not in ("unit", "per_pt", "chip_value", "rounding", "fees"):
                    errs.append(f"payout.{k}: 未知の項目")
    # unknown（欠落の申告）
    unk = norm.get("unknown")
    if unk is not None:
        if not isinstance(unk, list) or any(not isinstance(x, str) for x in unk):
            errs.append("unknown はパス文字列の配列")
        else:
            for pth in unk:
                if not _path_exists(norm, pth):
                    errs.append(f"unknown: 存在しないパス {pth!r}")
            if unk:
                warns.append("欠落（出典に無い項目、既定値で補完）: " + ", ".join(unk))
    if errs:
        raise ValidationError("; ".join(errs))
    return norm, warns


def _path_exists(obj: Any, path: str) -> bool:
    cur = obj
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        elif isinstance(cur, list) and part.isdigit() and int(part) < len(cur):
            cur = cur[int(part)]
        else:
            return False
    return True


def filename(rs: dict) -> str:
    return f"{rs['name']}_{id_hex64(rs['id'])}.ruleset.json"


def ref(rs: dict) -> dict:
    return {"name": rs["name"], "id": rs["id"]}


# ---- 生成器（CLI new／diff） ----------------------------------------------------------

def set_path(obj: dict, path: str, value: Any) -> None:
    parts = path.split(".")
    cur = obj
    for p in parts[:-1]:
        if p not in cur or not isinstance(cur[p], dict):
            cur[p] = {}
        cur = cur[p]
    cur[parts[-1]] = value


def flatten(obj: Any, prefix: str = "") -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.update(flatten(v, f"{prefix}.{k}" if prefix else k))
    else:
        out[prefix] = obj
    return out


def diff(a: dict, b: dict) -> List[Tuple[str, Any, Any]]:
    """正規形同士の差分（id・name を除く）。"""
    fa = flatten({k: v for k, v in normalize(a).items() if k not in ("id", "name", "meta")})
    fb = flatten({k: v for k, v in normalize(b).items() if k not in ("id", "name", "meta")})
    out = []
    for k in sorted(set(fa) | set(fb)):
        if fa.get(k, "<なし>") != fb.get(k, "<なし>"):
            out.append((k, fa.get(k, "<なし>"), fb.get(k, "<なし>")))
    return out


def new_from(base: Optional[dict], name: str, sets: Dict[str, Any]) -> dict:
    """雛形 base（None なら既定値だけ）に差分 sets（ドット区切りパス→値）を当てて正規形＋id を返す。"""
    rs = copy.deepcopy(base) if base else {"format": FORMAT, "version": VERSION}
    rs["name"] = name
    rs.pop("id", None)
    rs["meta"] = {"source": f"nmahjong ruleset new --from {base.get('name')}" if base else "nmahjong ruleset new", "note": ""}
    for pth, v in sets.items():
        set_path(rs, pth, v)
    return finalize(rs)


# ---- 同梱ルール集 ----------------------------------------------------------------------
_RS_DIR = os.path.join(_DATA, "rulesets")


def bundled() -> List[dict]:
    out = []
    if os.path.isdir(_RS_DIR):
        for fn in sorted(os.listdir(_RS_DIR)):
            if fn.endswith(".ruleset.json"):
                with open(os.path.join(_RS_DIR, fn), encoding="utf-8") as f:
                    out.append(json.load(f))
    return out


def find(name: Optional[str] = None, id: Optional[str] = None, search_dirs=()) -> dict:
    cands = list(bundled())
    for d in search_dirs:
        if d and os.path.isdir(d):
            for fn in os.listdir(d):
                if fn.endswith(".ruleset.json"):
                    with open(os.path.join(d, fn), encoding="utf-8") as f:
                        cands.append(json.load(f))
    if id:
        for rs in cands:
            if rs.get("id") == id:
                return rs
        raise ValidationError(f"ルール id {id} が見つからない")
    hits = [rs for rs in cands if rs.get("name") == name]
    if not hits:
        raise ValidationError(f"ルール name {name!r} が見つからない")
    if len({rs["id"] for rs in hits}) > 1:
        raise ValidationError(f"ルール name {name!r} は複数ある（id で指定）")
    return hits[0]
