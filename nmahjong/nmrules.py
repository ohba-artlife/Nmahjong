"""N 枚麻雀の既定ルール（同梱の nm-*）。手牌 N 枚（1・4・7・10・13）、2 人。内容の説明は nm-defaults.md。

同梱の nm-*.ruleset.json は tools/gen_rulesets.py がここから作る。色・長さを変えた組み合わせは ruleset_for で作れる
（同じ内容なら同じ id）。王牌・カンの回数・役などは ruleset の項目なので、作ったあとで変えてよい。
"""
import copy

from . import ruleset as R, tileset as TS
from .canon import ValidationError

SOURCE = "nm-defaults.md §2（N 枚麻雀の既定ルール）"
SUIT_ORDER = "mpsz"
LENGTHS = {"one": "one", "east": "east", "eastsouth": "east_south", "east_south": "east_south"}
COPIES = 4
DEAD = 4

# ---- ルール（nm-defaults.md §2） --------------------------------------------------------

_NO_RYUKYOKU = {"nine_terminals": False, "four_winds": False, "four_kans": False, "four_riichi": False, "three_ron": False}
_END = {"tobi": {"enabled": True, "at": 0, "exact_zero_is_tobi": False},
        "agari_yame": {"enabled": True, "when": "last_round", "forced": True},
        "tenpai_yame": {"enabled": True, "forced": True, "require_tenpai": False}, "max_honba": 50}
_SETTLE = {"start_points": 25000, "return_points": 30000, "oka": "to_first", "tie": "seat_order", "uma": [0, 0]}

GAME_1 = {
    "agari_form": "standard", "marks": {},
    "dora": {"indicator": True, "ura": True, "kan": False, "kan_ura": False},
    "yaku": {"base": "none", "overrides": {
        "chinitsu": 6, "tanyao": 1, "riichi": 1, "ippatsu": 1, "menzen_tsumo": 1,
        "tenhou": "yakuman", "chiihou": "yakuman", "renhou": "yakuman", "tsuuiisou": "yakuman", "chinroutou": "yakuman"}},
    "pao": {"yakuman": []},
    "flow": {"chi": False, "pon": False, "kan_kinds": [], "max_kans": 0,
             "riichi": {"min_points": 1000, "below_min": "forbidden", "stick_at_end": "to_first"},
             "renchan": {"dealer_win": True, "dealer_tenpai": True, "draw": True}, "ryukyoku": _NO_RYUKYOKU},
    "scoring": {"table": "custom:nm1-limits", "fu": {"enabled": False}, "honba_points": 300, "kyotaku_points": 1000,
                "noten_penalty": 0, "payment": "4p_child_half_from_opponent", "limits": {"kazoe_from": 13, "max_multiple": 2}},
}
WALL_1 = {"deal": "N_each_then_1_to_dealer", "dead_wall": DEAD, "dora_indicator": [0], "ura_indicator": [1], "break": {"by": "none"}}

GAME_4 = {
    "agari_form": "standard", "marks": {},
    "dora": {"indicator": True, "ura": True, "kan": False, "kan_ura": False},
    "yaku": {"base": "none", "overrides": {
        "riichi": 1, "double_riichi": 2, "ippatsu": 1, "menzen_tsumo": 1, "rinshan": 1, "haitei": 1, "houtei": 1,
        "tanyao": 1, "pinfu": 1, "yakuhai_haku": 1, "yakuhai_hatsu": 1, "yakuhai_chun": 1, "yakuhai_round": 1, "yakuhai_seat": 1,
        "toitoi": 2, "chanta": 2, "honroutou": 2, "honitsu": 3, "junchan": 3, "chinitsu": 6,
        "tenhou": "yakuman", "chiihou": "yakuman", "renhou": "yakuman",
        "chinroutou": "yakuman", "tsuuiisou": "yakuman", "ryuuiisou": "yakuman"}},
    "pao": {"yakuman": []},
    "flow": {"chi": False, "pon": False, "kan_kinds": ["ankan"], "max_kans": 2, "max_kans_per_player": 1,
             "riichi": {"min_points": 1000, "below_min": "forbidden", "without_draw": True, "on_houtei": False,
                        "furiten_riichi": True, "ankan_after": "if_shape_unchanged", "stick_at_end": "to_first"},
             "renchan": {"dealer_win": True, "dealer_tenpai": True, "draw": True}, "ryukyoku": _NO_RYUKYOKU},
    "scoring": {"table": "standard", "honba_points": 300, "kyotaku_points": 1000, "noten_penalty": 0, "mangan_round_up": False,
                "fu": {"enabled": True, "double_wind_pair": 4, "rinshan_tsumo_fu": 2, "menzen_tsumo_pinfu": True, "open_pinfu_fu": 30},
                "limits": {"sanbaiman_from": 11, "kazoe_from": 13, "yakuman_base": 4, "max_multiple": 2, "stack_with_normal": False},
                "payment": "4p_dealer_share_from_opponent"},
}
# 王牌 4 枚＝山の底の 4 枚（ドラ表示・裏ドラ表示・嶺上 2）。最初の嶺上は 4 枚目、2 回目は 1 回目のカンで王牌に入った元の海底牌（−1）
WALL_4 = {"deal": "N_each_then_1_to_dealer", "dead_wall": DEAD, "dora_indicator": [0], "ura_indicator": [1], "rinshan": [3, -1],
          "break": {"by": "none"}}

NOTE_1 = ("1 枚麻雀：2 人、手牌 1 枚、王牌 4（ドラ表示・裏ドラ表示・非公開 2）、立直 1000、"
          "清一色 6・断么九 1・立直 1・一発 1・門前清自摸和 1、役満 5 種（重なれば倍数）、符なし、最低が跳満、"
          "ロンは全額・ツモは子の合計の半分、本場 300、流局は罰符なしで親連荘、0 点未満で終了、50 本場で終了、最終局は親が上なら終了。"
          "終局時に残った供託はトップへ。立直の宣言牌でロンされたら立直は成立せず、立直棒は出さない")
NOTE_4 = ("4 枚麻雀：2 人、手牌 4 枚（1 面子＋雀頭）、王牌 4（ドラ表示・裏ドラ表示・嶺上 2）、"
          "暗槓のみ・各自 1 回（1 局 2 回まで）・カンドラなし、立直 1000（聴牌・1000 点以上・山 1 枚以上）、"
          "役 20 種＋役満 6 種（重なれば倍数）、符あり（連風雀頭 4 符）、切り上げ満貫なし、数え役満 13 翻、"
          "ロンは全額・ツモは基本点×2（4 人麻雀の親の負担分）を相手 1 人が払う、本場 300、流局は罰符なしで親連荘、"
          "0 点未満で終了、50 本場で終了、最終局は親が上なら終了。"
          "終局時に残った供託はトップへ。立直の宣言牌でロンされたら立直は成立せず、立直棒は出さない")


# 7・10・13 枚：4 枚麻雀の延長（既定）。王牌・暗槓・点数・支払い・終了・精算は 4 枚と同じ。
# 役は「面子＋雀頭で作れる標準の役」。4 枚の 20 種はこの表のうち 1 面子で作れるもの。面子が増えると一盃口・三色・一気通貫・三暗刻なども付く。
# 七対子・国士無双（面子＋雀頭でない形）は 4 枚に無いので既定では入れない。どれも ruleset の項目で変えられる
HAND_SIZES = (1, 4, 7, 10, 13)
YAKU_EXT = {"base": "riichi-standard", "overrides": {"renhou": "yakuman", "chiitoitsu": False, "kokushi": False}}
NOTE_EXT = ("{n} 枚麻雀（4 枚麻雀の延長の既定）：2 人、手牌 {n} 枚（{m} 面子＋雀頭）、王牌 4（ドラ表示・裏ドラ表示・嶺上 2）、"
            "暗槓のみ・各自 1 回（1 局 2 回まで）・ポンなし・カンドラなし、役は面子＋雀頭で作れる標準の役（七対子・国士無双なし、人和は役満）、"
            "符・点数・支払い・本場・供託・終了・精算は 4 枚麻雀と同じ。王牌の枚数・カンの回数・役は ruleset の項目で変えられる")


def tileset_for(suits) -> dict:
    """選んだ色（"m","p","s","z" の列）の牌表。各 4 枚、赤なし。牌種の番号 k（1 始まり）の牌は 4(k−1)〜4(k−1)+3。"""
    name = "".join(c for c in SUIT_ORDER if c in suits)
    if not name or set(suits) - set(SUIT_ORDER):
        raise ValidationError(f"色の指定が不正: {suits!r}")
    return TS.build(name)


def ruleset_name(n: int, tileset_name: str, length: str = "east_south") -> str:
    return f"nm-2p-{n}-{tileset_name}" + {"east_south": "", "east": "-east", "one": "-one"}[length]


def ruleset_for(n: int, suits, length: str = "east_south") -> dict:
    """N 枚麻雀の既定ルール（id 付き）。n＝手牌の枚数（1・4・7・10・13）、suits＝使う色（"m","p","s","z" の列）、
    length＝対局の長さ（east_south／east／one）。東南戦で m／mps／mpsz のものは同梱の nm-* と同じ id。"""
    if n not in HAND_SIZES:
        raise ValidationError(f"枚数 n={n} は未対応（{HAND_SIZES}）")
    if length not in LENGTHS:
        raise ValidationError(f"対局の長さが不正: {length!r}")
    ln = LENGTHS[length]
    ts = tileset_for(suits)
    rs = {"format": R.FORMAT, "version": R.VERSION, "name": ruleset_name(n, ts["name"], ln), "tileset": TS.ref(ts),
          "players": 2, "hand_size": n, "length": ln, "winds": ["E", "W"],
          "wall_rules": copy.deepcopy(WALL_1 if n == 1 else WALL_4),
          "game_rules": copy.deepcopy(GAME_1 if n == 1 else GAME_4),
          "end": copy.deepcopy(_END), "settlement": copy.deepcopy(_SETTLE),
          "meta": {"source": SOURCE, "note": NOTE_1 if n == 1 else NOTE_4 if n == 4 else NOTE_EXT.format(n=n, m=(n - 1) // 3)}}
    if n > 4:
        rs["game_rules"]["yaku"] = copy.deepcopy(YAKU_EXT)
        rs["meta"]["source"] = "nm-defaults.md §2.2（4 枚麻雀の延長）"
    return R.finalize(rs)
