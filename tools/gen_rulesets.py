"""既定ルール集を nmahjong/data/rulesets/ に生成する（ruleset.md §7、ruleset-survey.md、nm-defaults.md）。

書き方の約束：
- 出典に書いてある項目だけを書く。出典に無い項目は書かず、`unknown` にパスを列挙する（既定値で補完され、検証で「欠落」として出る）
- meta.source に出典 URL、meta.note に要点
"""
import copy
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from nmahjong import nmrules as NR, ruleset as R, tileset as TS, files  # noqa: E402

DEFS = TS.bundled_definitions()
T = {k: TS.build(**v) for k, v in DEFS.items()}

WALL4 = {"deal": "N_each_then_1_to_dealer", "dead_wall": 14, "dora_indicator": [8], "ura_indicator": [9],
         "kan_dora": [6, 4, 2, 0], "kan_ura": [7, 5, 3, 1], "rinshan": [12, 13, 10, 11], "break": {"by": "dice"}}
WALL_WAREME = dict(WALL4, dead_wall=16, dora_indicator=[8, 10], ura_indicator=[9, 11], kan_dora=[6, 4, 2, 0], kan_ura=[7, 5, 3, 1], rinshan=[14, 15, 12, 13])


def base(name, tileset_key="mpsz", players=4, hand=13, length="east_south", wall=None, **sections):
    rs = {"format": R.FORMAT, "version": R.VERSION, "name": name, "tileset": TS.ref(T[tileset_key]),
          "players": players, "hand_size": hand, "length": length,
          "winds": (["E", "W"] if players == 2 else ["E", "S", "W", "N"][:players]), "wall_rules": wall or WALL4}
    rs.update(sections)
    return rs


NO_IPPATSU_URA_KAN = {"dora": {"ura": False, "kan": False, "kan_ura": False}, "flow": {"ippatsu": False}}
DOUBLE_YAKUMAN = {"suuankou_tanki": "yakuman:2", "kokushi13": "yakuman:2", "junsei_chuuren": "yakuman:2", "daisuushii": "yakuman:2"}
S_JPML = "https://www.ma-jan.or.jp/column_other/115081.html"
S_JPML_O = [S_JPML, "https://www.ma-jan.or.jp/guide/yaku.html"]
S_SAIKOU = "https://saikouisen.com/_rule.php"
S_NPM = "https://npm2001.com/about/rule/"
S_RMU = "https://rmu.jp/rule"
S_CMP = "https://mj.maku.blog/p/triuood/"
S_SPORTS = "https://sportsmahjong.com/page/rule01.html"
S_KENKO = "https://tojankyo.com/kenma-rule/"
S_MLEAGUE = ["https://m-league.jp/about/", "https://janten.net/guide/m-league-rules", "https://p.eagate.573.jp/game/mfc/mfc_sp/howto/mode/mleague/index.html"]
S_TENHOU = ["https://tenhou.net/man/", "https://wikiwiki.jp/tenhou-chat/%E5%A4%A9%E9%B3%B3%E9%BA%BB%E9%9B%80%E3%81%AE%E5%9F%BA%E6%9C%AC%E3%83%AB%E3%83%BC%E3%83%AB"]
S_JANTAMA = ["https://note.com/qar13ktk20/n/nf9c7cf0eb025", "https://ja.wikipedia.org/wiki/%E9%9B%80%E9%AD%82"]
S_WAREME = "https://ja.wikipedia.org/wiki/THE%E3%82%8F%E3%82%8C%E3%82%81DE%E3%83%9D%E3%83%B3"
S_SAKAE = ["https://jan39.com/shop/11686/rule/", "https://media.jannavi.net/sakae/", "https://doramahjong.org/freejyannsou/08/0040.html",
           "https://note.com/shirokichi1996/n/n444029cf98d6"]
S_ZOO = ["https://mj-zoo.jp/rule.html", "https://jan39.com/shop/12399/rule/"]
S_MARCHAO = ["https://mj-king.net/tempos/rule/8362", "https://jan39.com/shop/12243/rule/", "https://mj-king.net/tempos/rule/9295"]
S_KANSAI = ["https://ameblo.jp/kansai3mj/entry-12100946684.html", "https://ja.wikipedia.org/wiki/%E4%B8%89%E4%BA%BA%E9%BA%BB%E9%9B%80"]
S_OPEN = "https://media.jannavi.net/open-reach/"
S_POCCHI = ["https://www.mahjong-press.com/mahjong-strategy/white-tile-almighty/", "https://note.com/daisen/n/n66fdb6489afb"]
S_NM_ROOM = "nm-defaults.md §3（4 枚麻雀の別版）"

RULESETS = []


def add(rs, source, note, unknown=()):
    rs["meta"] = {"source": source, "note": note}
    if unknown:
        rs["unknown"] = list(unknown)
    RULESETS.append(rs)


# ---- 団体 ----------------------------------------------------------------------------
add(base("jpml-official", "mpsz-nored",
         game_rules={"dora": {"ura": False, "kan": False, "kan_ura": False},
                     "flow": {"ippatsu": False, "kuikae": "forbidden", "triple_ron": "head",
                              "riichi": {"on_houtei": False}},
                     "pao": {"yakuman": ["daisangen", "daisuushii", "suukantsu"], "daiminkan_rinshan": False},
                     "scoring": {"fu": {"double_wind_pair": 2}, "mangan_round_up": False, "limits": {"kazoe_from": None, "max_multiple": 6}},
                     "penalties": {"chombo": {"kind": "rank_points", "value": 20}}},
         end={"negative_points": "continue"},
         settlement={"start_points": 30000, "return_points": 30000, "oka": "none", "tie": "split",
                     "uma": {"by_floating": {"1": [12, -1, -3, -8], "2": [8, 4, -4, -8], "3": [8, 3, 1, -12]}, "threshold": "return"}}),
    S_JPML_O, "連盟公式：一発・裏・カンドラなし、浮き人数別順位点、連風牌の雀頭 2 符、喰い替えなし、途中流局なし、和了は上家優先、数え役満なし、役満の重複あり（四暗刻単騎・大四喜・国士十三面・九蓮九面は 1 つではダブル役満にならない）、"
            "包（大三元・大四喜・四槓子。ツモ全額、ロン折半）、国士の暗槓和了なし、大明槓の嶺上は責任払いなし、河底牌での立直不可、30 符 4 翻は切り上げない、−20P",
    unknown=["settlement.start_points", "end.tobi", "game_rules.flow.riichi.min_points"])

add(base("jpml-wrc", "mpsz-nored",
         game_rules={"flow": {"kokushi_ankan_chankan": True}, "scoring": {"mangan_round_up": True}, "penalties": {"chombo": {"kind": "rank_points", "value": 30}}},
         settlement={"start_points": 30000, "return_points": 30000, "oka": "none", "uma": [15, 5, -5, -15]}),
    S_JPML, "連盟 WRC：一発・裏・カンドラあり、30000/30000、15-5、途中流局なし、国士は暗槓をロンできる、切り上げ満貫、−30P",
    unknown=["end.tobi"])

add(base("jpml-wrc-r",
         game_rules={"flow": {"kokushi_ankan_chankan": True}, "scoring": {"mangan_round_up": True}, "penalties": {"chombo": {"kind": "rank_points", "value": 30}}},
         settlement={"start_points": 30000, "return_points": 30000, "oka": "none", "uma": [30, 10, -10, -30]}),
    S_JPML, "連盟 WRC-R：WRC ＋ 赤 3、30-10", unknown=["end.tobi"])

add(base("saikouisen", "mpsz-nored",
         game_rules={"flow": {"ryukyoku": {"nine_terminals": False, "four_winds": False, "four_kans": False, "four_riichi": False, "three_ron": False}, "triple_ron": "head"},
                     "pao": {"yakuman": []}, "scoring": {"limits": {"max_multiple": 1}},
                     "penalties": {"chombo": {"kind": "rank_points", "value": 40}}},
         settlement={"start_points": 30000, "return_points": 30000, "oka": "none", "uma": [30, 10, -10, -30]}),
    S_SAIKOU, "最高位戦：30000 持ち・オカなし、順位点 10-30、途中流局なし、和了やめ・聴牌やめなし、包なし、数え役満なし、役満の複合なし、国士の暗槓和了なし、−40P",
    unknown=["end.tobi", "game_rules.flow.riichi.min_points"])

add(base("saikouisen-classic", "mpsz-nored",
         game_rules={"dora": {"ura": False, "kan": False, "kan_ura": False},
                     "flow": {"ippatsu": False, "kuikae": "allowed", "riichi": {"ankan_after": "none"},
                              "renchan": {"dealer_win": True, "dealer_tenpai": False},
                              "ryukyoku": {"nine_terminals": False, "four_winds": False, "four_kans": False, "four_riichi": False, "three_ron": False}, "triple_ron": "head"},
                     "pao": {"yakuman": []}, "scoring": {"noten_penalty": 0, "mangan_round_up": False, "limits": {"max_multiple": 1}},
                     "penalties": {"chombo": {"kind": "rank_points", "value": 16}}},
         settlement={"start_points": 30000, "return_points": 30000, "oka": "none", "uma": [12, 4, -4, -12]}),
    [S_SAIKOU, "https://ja.wikipedia.org/wiki/%E6%9C%80%E9%AB%98%E4%BD%8D%E6%88%A6Classic"],
    "最高位戦 Classic：順位点 12-4、一発・裏ドラ・槓ドラ・槓裏なし（ドラは最初の 1 種類）、連荘は親の和了だけ、ノーテン罰符なし、1 本場 300 点、"
    "切り上げ満貫なし（30 符 4 翻は 7700・11600）、喰い替え可、立直後の暗槓不可、−16P。出典に書かれていない所（途中流局なし、包なし、役満の複合なし）は最高位戦ルールと同じにしてある",
    unknown=["game_rules.flow.ryukyoku", "game_rules.pao", "end.tobi"])

add(base("npm", "mpsz-nored",
         game_rules={"pao": {"yakuman": []},
                     "scoring": {"limits": {"max_multiple": 6}}, "penalties": {"chombo": {"kind": "rank_points", "value": 40}}},
         end={"negative_points": "continue"},
         settlement={"start_points": 25000, "return_points": 30000, "oka": "to_first", "uma": [30, 10, -10, -30]}),
    S_NPM, "協会：25000/30000、順位点 50-10（オカ込み）、途中流局なし、二家和・三家和なし（上家）、人和・流し満貫なし、包なし、純粋な役の複合による役満の重複あり、"
           "持ち点が無くなっても続行、ツモ番が無くても立直可、−40P",
    unknown=["game_rules.scoring.limits.kazoe_from", "game_rules.flow.kokushi_ankan_chankan", "game_rules.flow.riichi.min_points"])

add(base("rmu-a", "mpsz-nored",
         game_rules={"pao": {"yakuman": []}, "scoring": {"limits": {"kazoe_from": 13, "max_multiple": 6}}},
         end={"negative_points": "continue"},
         settlement={"start_points": 30000, "return_points": 30000, "oka": "none", "uma": [15, 5, -5, -15]}),
    S_RMU, "RMU A：30000/30000、15-5、一発裏カンあり、途中流局なし、上家優先、箱下でも続行、数え 13、役満の重複あり、包なし", unknown=[])

add(base("rmu-b", "mpsz-nored",
         game_rules={"dora": {"ura": False, "kan": False, "kan_ura": False}, "flow": {"ippatsu": False},
                     "pao": {"yakuman": []}, "scoring": {"limits": {"kazoe_from": 13, "max_multiple": 6}}},
         end={"negative_points": "continue"},
         settlement={"start_points": 30000, "return_points": 30000, "oka": "none", "uma": [15, 5, -5, -15]}),
    S_RMU, "RMU B：A から一発・裏・カンドラを除く", unknown=[])

add(base("rmu-m",
         game_rules={"scoring": {"limits": {"kazoe_from": 13, "max_multiple": 6}}},
         end={"negative_points": "continue"},
         settlement={"start_points": 25000, "return_points": 30000, "oka": "to_first", "uma": [30, 10, -10, -30]}),
    S_RMU, "RMU M：A ＋ 赤 3、25000 持ち、順位点 50-10（オカ込み）、包あり", unknown=[])

add(base("mu", "mpsz-nored",
         game_rules={"dora": {"ura": False, "kan": False, "kan_ura": False},
                     "flow": {"ippatsu": False, "kuikae": "allowed", "riichi": {"ankan_after": "none"}},
                     "pao": {"yakuman": ["daisangen", "daisuushii"]},
                     "scoring": {"fu": {"double_wind_pair": 2}, "mangan_round_up": False},
                     "penalties": {"chombo": {"kind": "rank_points", "value": 20}}},
         settlement={"start_points": 30000, "return_points": 30000, "oka": "none", "uma": [12, 4, -4, -12]}),
    S_CMP, "麻将連合 μ：30000/30000、順位点 12-4、一発・裏・カンドラ・赤なし、途中流局なし、頭ハネ（三家和も）、流し満貫・人和なし、数え役満なし、役満の複合なし、"
           "喰い替え可、連風牌の雀頭 2 符、包（大三元・大四喜。ツモ責任払い、ロン折半）、立直後の暗槓不可、30 符 4 翻は 7700、箱割れ終了なし、−20P",
    unknown=["game_rules.flow.atozuke", "game_rules.flow.riichi.without_draw"])

add(base("mleague",
         game_rules={"flow": {"riichi": {"min_points": 1000, "below_min": "allowed"}},
                     "scoring": {"limits": {"kazoe_from": None, "max_multiple": 6}, "mangan_round_up": True},
                     "penalties": {"chombo": {"kind": "rank_points", "value": 20}}},
         end={"negative_points": "continue"},
         settlement={"start_points": 25000, "return_points": 30000, "oka": "to_first", "uma": [30, 10, -10, -30],
                     "external_points": [{"system": "mleague-p", "kind": "rank_plus_raw", "raw_base": 30000, "raw_divisor": 1000, "rank_points": [50, 10, -10, -30]}]}),
    S_MLEAGUE, "Mリーグ：赤 3、一発裏カン、途中流局なし、頭ハネ、流し満貫なし、トビなし、和了止め・聴牌止めなし、数え役満なし（11 翻以上は三倍満）、役満の複合あり（役満 1 種での二倍役満はなし）、"
               "包（大三元・大四喜・四槓子）、0 点・マイナスでも立直可、切り上げ満貫、順位点 50/10/−10/−30（オカ込み）、チョンボ −20P",
    unknown=["end.extension"])

add(base("sports-mahjong", "mpsz-nored",
         game_rules={"dora": {"ura": False, "kan": False, "kan_ura": False}, "flow": {"ippatsu": False},
                     "yaku": {"overrides": {"renhou": 8}}, "scoring": {"fu": {"open_pinfu_fu": 30}, "limits": {"yakuman_base": 4}}},
         end={"negative_points": "continue"},
         settlement={"start_points": 30000, "return_points": 30000, "oka": "none",
                     "uma": {"by_floating": {"1": [8, -1, -2, -5], "2": [5, 3, -3, -5], "3": [5, 2, 1, -8]}, "threshold": "return", "includes_threshold": True}}),
    S_SPORTS, "日本スポーツ麻雀協会：表ドラのみ、浮き人数別の順位点（1 人浮き +8/▲1/▲2/▲5、2 人浮き +5/+3/▲3/▲5、3 人浮き +5/+2/+1/▲8。原点ちょうどは浮き）、"
              "途中流局なし、上家和了、役満の重複なし、食い平和 30 符、役満 4 倍満、人和倍満",
    unknown=["end.tobi"])

add(base("kenko", "mpsz-nored",
         game_rules={"pao": {"yakuman": ["daisangen", "daisuushii"]},
                     "scoring": {"limits": {"yakuman_base": 4, "kazoe_from": None}},
                     "penalties": {"chombo": {"kind": "points", "value": 3000, "replay": True}}},
         end={"time_limit_sec": 3600, "negative_points": "continue"},
         settlement={"start_points": 30000, "return_points": 30000, "oka": "none",
                     "uma": {"by_floating": {"1": [12, -2, -4, -6], "2": [8, 4, -4, -8], "3": [6, 4, 2, -12]}, "threshold": "return", "includes_threshold": True}}),
    S_KENKO, "健康マージャン公式競技規定：一発・裏ドラ・カンドラ・カン裏あり（赤はドラ扱いしない）、時間制限（団体戦 60 分・個人戦 50 分）、"
             "順位点（1 人勝ち 12/△2/△4/△6、2 人勝ち 8/4/△4/△8、3 人勝ち 6/4/2/△12。30000 点は勝ち）、途中流局なし、頭ハネ、点棒が無くなったら借りて続行、"
             "13 翻以上は三倍満、ダブル役満なし、包（大三元・大四喜）、チョンボは 3 人に 3000 点ずつ",
    unknown=["game_rules.scoring.fu.double_wind_pair"])

# ---- ネット ----------------------------------------------------------------------------
# 天鳳マニュアル（https://tenhou.net/man/）：「大三元/大四喜のパオあり。複合役満を含む得点を、ツモ＝全額・ロン＝折半で支払う。積み棒は包。」「四槓子のパオなし」
# 「※役満は複合あり、四暗刻単騎・国士無双十三面待ち等はすべてシングル役満」→ max_multiple は上限なしの意味で 6
# 「サドンデスルールは、30000点(供託未収)以上になった時点で終了、ただし親の連荘がある場合は連荘を優先する」「サドンデスの最大局は東風戦は南場まで、東南戦は西場まで」
TENHOU_PAO = {"yakuman": ["daisangen", "daisuushii"], "ron": "split_all", "honba_kyotaku": "liable"}
TENHOU4 = dict(
    game_rules={"flow": {"riichi": {"min_points": 1000, "below_min": "forbidden", "without_draw": False, "stick_at_end": "to_first"},
                         "ryukyoku": {"nine_terminals": True, "four_winds": True, "four_kans": True, "four_riichi": True, "three_ron": True},
                         "renchan_on_abort": True, "double_ron": True, "triple_ron": "draw"},
                "nagashi_mangan": {"enabled": True, "as": "tenpai_settlement"},
                "pao": TENHOU_PAO,
                "scoring": {"fu": {"double_wind_pair": 4}, "mangan_round_up": False, "limits": {"kazoe_from": 13, "max_multiple": 6}}},
    end={"tobi": {"enabled": True, "at": 0, "exact_zero_is_tobi": False},
         "extension": {"enabled": True, "until_points": 30000, "max_rounds": 4, "once": True, "renchan_first": True},
         "agari_yame": {"enabled": True, "when": "last_round", "forced": True},
         "tenpai_yame": {"enabled": True, "forced": True}},
    settlement={"start_points": 25000, "return_points": 30000, "oka": "to_first", "uma": [20, 10, -10, -20],
                "tie": "seat_order", "rounding": {"score_to_1000": "half_up_500", "remainder_to_top": True},
                "external_points": [{"system": "tenhou-rank", "kind": "rank_only", "rank_points": {"by_player_rank": {"新人": [30, 15, 0, 0]}}},
                                    {"system": "tenhou-rate", "kind": "formula"}]})
TENHOU4_NOTE = ("1000 点以上かつツモ番あり立直、途中流局 5 種（連荘）、自動和了止め・聴牌止め、流し満貫（聴牌清算代替）、飛び、数え 13、"
                "包（大三元・大四喜）、連風牌の雀頭 4 符（実牌譜の和了で確認）、切り上げ満貫なし（30 符 4 翻＝7700：実牌譜 434 件で確認）、終局時の供託はトップへ（実牌譜 owari で確認）、"
                "精算は持ち点を 1000 点単位に四捨五入（28500→29、36500→37、−500→−1）し端数はトップ、同点は起家側が上位（公開牌譜 1002 件の owari で確認）")
TENHOU4_UNKNOWN = ["settlement.external_points.0.rank_points"]

add(base("tenhou-4p-hanchan-red", **copy.deepcopy(TENHOU4)),
    S_TENHOU, "天鳳 四麻東南赤あり：" + TENHOU4_NOTE + "、西入（誰かが 30000 以上で終了、親の連荘を優先、西場まで）", unknown=TENHOU4_UNKNOWN)

_t = copy.deepcopy(TENHOU4)
_t["end"]["extension"]["max_rounds"] = 4
add(base("tenhou-4p-tonpu-red", length="east", **_t),
    S_TENHOU, "天鳳 四麻東風赤あり：" + TENHOU4_NOTE + "、南入（誰かが 30000 以上で終了、親の連荘を優先、南場まで）", unknown=TENHOU4_UNKNOWN)

# 精算を丸めない版（-exact）。2026-11 の一般卓の実牌譜 2 件では owari が 0.1 単位（例 10.4／−37.0／44.0／−17.4）で、
# 素点を 1000 点単位に丸めていない。ウマ 20-10・オカ・同点の扱いは同じ。2020 年の鳳凰卓（公開牌譜 1002 件）は丸めあり。
# 違いの原因は時期（天鳳マニュアル：2022/01/21 に四捨五入を廃止）。取り込みは owari に小数があるかで選ぶ。
TENHOU_EXACT_NOTE = "。精算は丸めない（0.1pt 単位。天鳳マニュアル「2022/01/21 終了時の得点の1000点未満の四捨五入を廃止」。2026-11 の実牌譜でも確認。丸めありの版は、それより前の牌譜用）"
for _name, _len, _maxr, _label in (("tenhou-4p-hanchan-red-exact", "east_south", 4, "東南"), ("tenhou-4p-tonpu-red-exact", "east", 4, "東風")):
    _t = copy.deepcopy(TENHOU4)
    _t["end"]["extension"]["max_rounds"] = _maxr
    _t["settlement"]["rounding"] = {"score_to_1000": "none", "remainder_to_top": False}
    add(base(_name, length=_len, **_t),
        S_TENHOU, f"天鳳 四麻{_label}赤あり（精算丸めなし）：" + TENHOU4_NOTE.split("、精算は")[0] + TENHOU_EXACT_NOTE,
        unknown=TENHOU4_UNKNOWN)

# 天鳳三麻の王牌（公開牌譜 278 件 2534 局で読んだ位置。天鳳の向き y[0..13] が王牌、ドラ y[9]、裏 y[8]、カンドラ y[11,13,15,17]、カン裏 y[10,12,14,16]、
# 嶺上 y[1,0,3,2,5,4,7,6]。本仕様の向きに写すと以下。負のオフセットは海底側＝王牌が取り込んだ牌）
WALL_TENHOU3 = {"deal": "N_each_then_1_to_dealer", "dead_wall": 14, "dora_indicator": [4], "ura_indicator": [5],
                "kan_dora": [2, 0, -2, -4], "kan_ura": [3, 1, -1, -3], "rinshan": [12, 13, 10, 11, 8, 9, 6, 7], "break": {"by": "dice"}}

add(base("tenhou-3p", "mpsz-x28", players=3, wall=WALL_TENHOU3,
         game_rules={"flow": {"chi": False, "riichi": {"min_points": 1000, "without_draw": False},
                              "ryukyoku": {"nine_terminals": True, "four_winds": True, "four_kans": True, "four_riichi": True, "three_ron": False},
                              "double_ron": True},
                     "nuki": {"enabled": True, "tiles": ["N"], "value": 1, "win_with_nuki_in_hand": True},
                     "nagashi_mangan": {"enabled": True, "as": "tenpai_settlement"},
                     "pao": TENHOU_PAO,
                     "scoring": {"tsumo_loss": "loss", "fu": {"double_wind_pair": 4}, "mangan_round_up": False, "limits": {"kazoe_from": 13, "max_multiple": 6}}},
         end={"tobi": {"enabled": True, "at": 0, "exact_zero_is_tobi": False},
              "extension": {"enabled": True, "until_points": 40000, "max_rounds": 3, "once": True, "renchan_first": True},
              "agari_yame": {"enabled": True, "when": "last_round", "forced": True},
              "tenpai_yame": {"enabled": True, "forced": True}},
         settlement={"start_points": 35000, "return_points": 40000, "oka": "to_first", "uma": [20, 0, -20],
                     "tie": "seat_order", "rounding": {"score_to_1000": "half_up_500", "remainder_to_top": True}}),
    S_TENHOU, "天鳳 三麻：35000/40000、北抜き（抜き北で和了可）、チーなし、ツモ損あり、切り上げ満貫なし、連風牌の雀頭 4 符、"
              "南 3 局で 40000 に届かなければ西入（誰かが 40000 以上で終了、西 3 局まで）、親がトップなら和了止め・聴牌止め（実牌譜 278 対局の終わり方で確認）、"
              "順位ウマ +20・0・−20（天鳳マニュアル）、包は四人打ちと同じ（マニュアルの三人打ちの欄は四人打ちと違う所だけを書いている）")

JANTAMA4 = dict(
         game_rules={"flow": {"riichi": {"min_points": 1000, "below_min": "forbidden", "stick_at_end": "to_first"},
                              "ryukyoku": {"nine_terminals": True, "four_winds": True, "four_kans": True, "four_riichi": True, "three_ron": False},
                              "double_ron": True, "triple_ron": "allow", "kokushi_ankan_chankan": True},
                     "nagashi_mangan": {"enabled": True, "as": "draw_mangan", "noten_penalty": False},
                     "pao": {"yakuman": ["daisangen", "daisuushii"]},
                     "yaku": {"overrides": DOUBLE_YAKUMAN},
                     "dora": {"kan_timing": {"ankan": "immediate", "minkan": "after_discard", "kakan": "after_discard"}},
                     "scoring": {"mangan_round_up": False, "limits": {"kazoe_from": 13, "max_multiple": 6}}},
         end={"tobi": {"enabled": True, "at": 0, "exact_zero_is_tobi": False},
              "extension": {"enabled": True, "until_points": 30000, "max_rounds": 4, "once": True},
              "agari_yame": {"enabled": True, "when": "last_round", "forced": False},
              "tenpai_yame": {"enabled": True, "forced": False}},
         settlement={"start_points": 25000, "return_points": 25000, "oka": "none", "uma": [15, 5, -5, -15], "tie": "seat_order",
                     "external_points": [{"system": "jantama-rank", "kind": "rank_plus_raw", "raw_base": 25000, "raw_divisor": 1000,
                                          "rank_points": {"by_player_rank": {"初心1": [10, 5, 0, 0]}}}]})
JANTAMA_NOTE = ("（公式規定文なし、note 記事と Wikipedia 準拠）：25000 返し（オカなし）、順位ウマ 5-15、同点は起家に近い方、1000 点未満は立直不可、0 点は続行、"
                "流し満貫＝流局の扱いで満貫・罰符なし、役満は複合し最高六倍（四暗刻単騎・国士十三面・純正九蓮・大四喜は二倍）、包（大三元・大四喜）、"
                "国士は暗槓をロンできる、切り上げ満貫なし、カンドラ槓種別、ダブロン・トリプルロンあり（三家和は流局にしない。積み棒・供託は上家取り）、"
                "途中流局は九種九牌・四風連打・四槓散了・四家立直の 4 種、流局で終わったときの供託はトップ取り。実牌譜での照合は未")
add(base("jantama-4p", **copy.deepcopy(JANTAMA4)),
    S_JANTAMA, "雀魂 四麻半荘" + JANTAMA_NOTE + "、西入 1 回",
    unknown=["settlement.external_points.0.rank_points"])
add(base("jantama-4p-tonpu", length="east", **copy.deepcopy(JANTAMA4)),
    S_JANTAMA, "雀魂 四麻東風" + JANTAMA_NOTE + "、南入 1 回",
    unknown=["settlement.external_points.0.rank_points"])

# ---- TV ----------------------------------------------------------------------------
add(base("wareme-de-pon", length="east", wall=WALL_WAREME,
         game_rules={"flow": {"wareme": True, "renchan": {"dealer_win": True, "dealer_tenpai": True, "all_noten": True},
                              "ryukyoku": {"nine_terminals": True, "four_winds": True, "four_kans": True, "four_riichi": True, "three_ron": True},
                              "open_riichi": {"enabled": True, "han_total": 2, "deal_in": "yakuman"}},
                     "nagashi_mangan": {"enabled": True},
                     "yaku": {"overrides": {"open_riichi": 1}},
                     "scoring": {"shibari": {"from_honba": 5, "han": 2, "exclude_dora": True}}},
         end={"tobi": {"enabled": True, "at": 0, "exact_zero_is_tobi": False, "penalty_points": 10000, "penalty_to": "tenpai_players"},
              "extension": {"enabled": True, "until_points": 30000, "max_rounds": 4, "once": True},
              "agari_yame": {"enabled": True, "when": "last_round", "forced": False}},
         settlement={"start_points": 25000, "return_points": 30000, "oka": "to_first", "uma": [0, 0, 0, 0]}),
    S_WAREME, "THEわれめDEポン：東風戦（確定トップがいなければ帰り東、30,000 点を超えた人が出たら終了）、25000 持ち 30000 返し、オカはトップ取り、順位ウマなし、"
              "王牌 16・ドラ常時 2 枚、割れ目（和了の点が倍。ノーテン罰符・積み棒は倍にならない）、ダブロンは頭ハネ、流し満貫あり、途中流局は全部あり、"
              "聴牌連荘（全員ノーテンは親連荘）、和了止めの権利あり、トビあり（0 点ちょうどはトビにならない。トビ罰符 10000）、五本場から二翻縛り、オープン立直あり",
    unknown=["settlement.chips", "game_rules.marks", "game_rules.flow.open_riichi", "game_rules.nagashi_mangan.as", "game_rules.flow.ippatsu", "game_rules.dora.ura"])

# ---- 雀荘 ----------------------------------------------------------------------------
add(base("sakae-shibuya",
         game_rules={"mark_overrides": [{"tile_kind": "5p", "mark": "red", "effects": ["yaku"]}],
                     "flow": {"renchan": {"dealer_win": True, "dealer_tenpai": False, "all_noten": False},
                              "double_ron": True, "triple_ron": "draw",
                              "ryukyoku": {"nine_terminals": False, "four_winds": False, "four_kans": False, "four_riichi": False, "three_ron": True},
                              "riichi": {"min_points": 1000, "below_min": "forbidden"}},
                     "nagashi_mangan": {"enabled": True},
                     "pao": {"tsumo": "full", "ron": "split"},
                     "scoring": {"honba_points": 1500, "limits": {"yakuman_base": 4, "kazoe_from": 13}}},
         end={"cold_points": 60000, "negative_points": "zero", "tobi": {"enabled": True, "at": 0, "exact_zero_is_tobi": False},
              "agari_yame": {"enabled": True, "when": "last_round", "forced": False}},
         settlement={"start_points": 25000, "return_points": 30000, "oka": "to_first", "tie": "seat_order",
                     "uma": {"by_floating": {"1": [45, -10, -10, -25], "2": [40, 15, -25, -30], "3": [40, 15, 10, -65]}, "threshold": "start"},
                     "chips": [{"on": "win_with_mark", "mark": "red", "when": "always", "per": "tile", "count": 1, "payer": "loser"},
                               {"on": "win_kind", "kind": "ippatsu", "per": "event", "count": 1, "payer": "loser"},
                               {"on": "win_kind", "kind": "uradora", "per": "tile", "count": 1, "payer": "loser"},
                               {"on": "tobi", "per": "event", "count": 1, "payer": "loser"}]}),
    S_SAKAE, "リーチ麻雀さかえ渋谷：A トップ（2 着が 25000 を切ると払う）、赤 5p は 1 翻役＋鳴いても祝儀、一発・裏 1 枚、トビペナ 1 枚、本場 1500、6 万点コールド、"
             "持ち点を割ったら終了（箱下なし）、親はアガリ連荘、九種九牌・四風連打・四カン流れなし、四人立直は続行、三家和（トリプルロン）だけ流局、流し満貫あり、W ロンあり、オーラスの親はアガリやめ可、"
             "包はツモ責任払い・ロン折半、起家順同点、役満 4 倍満（13 翻以上も）",
    unknown=["settlement.uma.by_floating", "game_rules.nagashi_mangan.as", "game_rules.pao.yakuman"])

add(base("zoo-4p",
         game_rules={"flow": {"double_ron": True,
                              "ryukyoku": {"nine_terminals": True, "four_winds": True, "four_kans": True, "four_riichi": False, "three_ron": True}},
                     "nagashi_mangan": {"enabled": True},
                     "scoring": {"fu": {"rinshan_tsumo_fu": 0, "yakuhai_tanki_fu": 2}}},
         end={"cold_points": 55000, "tobi": {"enabled": True, "at": 0, "exact_zero_is_tobi": False}}),
    S_ZOO, "麻雀 ZOO 四人：0 点未満または 55000 点以上で終了、嶺上 0 符、連風牌の雀頭 2 符、役牌単騎 2 符、途中流局あり（九種九牌・四風連打・トリプルロン・四開カン）、"
           "流し満貫あり、親は聴牌連荘、ダブロンあり（積み棒・親権は頭ハネ）。鳴き祝儀あり（鳴いていても祝儀が付く。何に何枚付くかは出典に無いので、祝儀の規則は書いていない）",
    unknown=["settlement.uma", "settlement.start_points", "settlement.return_points", "game_rules.marks", "settlement.chips", "settlement.payout", "game_rules.nagashi_mangan.as"])

add(base("zoo-3p", "mpsz-x28", players=3,
         game_rules={"flow": {"chi": False, "double_ron": True, "riichi": {"min_points": 1000, "below_min": "forbidden", "furiten_riichi": False}},
                     "yaku": {"chiitoi_four_of_kind": True, "wheel": "any_suit",
                              "overrides": {"manzu_honitsu": "yakuman", "daisharin": "yakuman", "renhou": "yakuman", "nagashi_mangan": "yakuman"}},
                     "nagashi_mangan": {"enabled": True, "as": "yakuman"},
                     "scoring": {"fu": {"enabled": False}, "honba_points": 1000, "limits": {"kazoe_from": 14}, "tsumo_loss": "marudori"}},
         end={"tobi": {"enabled": True, "at": 0, "exact_zero_is_tobi": True},
              "agari_yame": {"enabled": True, "when": "last_round", "forced": True},
              "tenpai_yame": {"enabled": True, "forced": True}},
         settlement={"start_points": 35000, "return_points": 40000}),
    S_ZOO, "麻雀 ZOO 三人：35000 持ち 40000 返し、ツモ損なし（払う額は出典に無い。同じ「ツモ損なし」の東京の店マーチャオの例に合わせて丸取りにしてある）、符計算なし、0 点ちょうどでトビ、オーラスの和了り止め・聴牌止めあり（トップなら終了）、途中流局なし、"
           "親は聴牌連荘、ダブロンあり、1 本場 1000 点、包（大三元・大四喜・四槓子）、4 枚使いの七対子、特殊役満（萬子混一色・大車輪・人和・流し）、数え 14、フリテン立直なし。"
           "赤 5p・赤 5s 各 4 枚は牌表が別になるので入れていない",
    unknown=["settlement.uma", "game_rules.marks", "game_rules.nuki", "tileset"])

add(base("marchao-4p",
         game_rules={"flow": {"kuikae": "forbidden", "double_ron": True, "triple_ron": "allow",
                              "renchan": {"dealer_win": True, "dealer_tenpai": False, "all_noten": False}},
                     "nagashi_mangan": {"enabled": True, "as": "win"}},
         end={"cold_points": 55000, "tobi": {"enabled": True, "at": 0, "exact_zero_is_tobi": False},
              "agari_yame": {"enabled": True, "when": "last_round", "forced": True, "others_may_continue": True}},
         settlement={"start_points": 25000, "return_points": 30000}),
    S_MARCHAO, "マーチャオα 京都四条烏丸 四人：25000 持ち 30000 返し、55000 点以上で終了、箱割れで終了（0 点は続行）、喰い替えなし、オーラスの親が和了してトップなら終了・"
               "2 着 3 着は続行を選べる、親はあがり連荘（本文と広島店の記載。採用ルール欄の「親テンパイ連チャン」は店紹介の共通の欄）、流し満貫は和了役、ダブロン・トリプルロンあり、途中流局なし、"
               "フリテン立直は可（ツモ和了のみ）",
    unknown=["settlement.uma", "game_rules.marks", "settlement.chips"])

add(base("marchao-3p", "mpsz-x28", players=3,
         game_rules={"flow": {"chi": False, "double_ron": True, "riichi": {"min_points": 1000, "below_min": "allowed", "furiten_riichi": False}},
                     "marks": {"red": {"effects": ["dora"]}},
                     "yaku": {"wheel": "any_suit", "overrides": {"manzu_honitsu": "yakuman", "daisharin": "yakuman", "renhou": "yakuman", "nagashi_mangan": "yakuman"}},
                     "nagashi_mangan": {"enabled": True, "as": "yakuman"},
                     "pao": {"tsumo": "full", "ron": "full"},
                     "scoring": {"round_to": 1000, "honba_points": 1000, "limits": {"kazoe_from": 14}, "tsumo_loss": "marudori"},
                     "penalties": {"chombo": {"kind": "points", "value": 8000, "replay": False}}},
         end={"tobi": {"enabled": True, "at": 0, "exact_zero_is_tobi": True},
              "agari_yame": {"enabled": True, "when": "last_round", "forced": True}},
         settlement={"start_points": 35000, "return_points": 40000}),
    S_MARCHAO, "マーチャオα 三人：35000 持ち 40000 返し、0 点ちょうどでトビ、オーラスでトップなら強制終了、親は聴牌連荘、ツモ損なし（丸取り。川崎店の例：子のハネ満ツモ 4000・8000）、1000 点未満切り上げ、1 本場 1000 点、"
               "ダブロンあり（供託・本場は上家取り）、役満（人和・萬子の混一色・流し役満・大車輪＝清一七対子）、数え 14、役満の包は全額責任払い、"
               "フリテン立直はチョンボ（8000 オール）、1000 点持ちで立直可、花牌 4 枚（別牌表で表す）",
    unknown=["settlement.uma", "game_rules.nuki"])

add(base("kansai-3p", "mpsz-x28-allred", players=3, wall=WALL_TENHOU3,   # 出典「抜きドラ用の四枚、四槓のための四枚、計八枚を嶺上牌とし、その隣をドラ表示牌として開ける」
         game_rules={"nuki": {"enabled": True, "tiles": ["N"], "value": 1, "win_with_nuki_in_hand": False},
                     "flow": {"chi": False, "atozuke": "kanzen_sakizuke", "open_tanyao": False, "riichi": {"furiten_riichi": False},
                              "renchan": {"dealer_win": True, "dealer_tenpai": True, "by_bakaze": {"S": {"dealer_tenpai": True, "dealer_noten": True, "all_noten": True}}}},
                     "yaku": {"overrides": {"daisharin": "yakuman", "shousharin": 6, "suurenkou": "yakuman", "sanrenkou": 2, "sanpuu": 2, "nagashi_mangan": "yakuman"},
                              "wheel": "any_suit", "chiitoi_four_of_kind": True},
                     "nagashi_mangan": {"enabled": True, "as": "yakuman"},
                     "scoring": {"round_to": 1000, "honba_points": 1000, "limits": {"kazoe_from": 14}, "tsumo_loss": "marudori",
                                 "tsumo_table": {"8000": [5000, 3000], "12000": [8000, 4000], "16000": [10000, 6000], "24000": [16000, 8000], "32000": [20000, 12000]}}}),
    S_KANSAI, "関西サンマ一般：五筒・五索は全部赤（ドラ）、嶺上牌は 8 枚でその隣がドラ表示牌、抜きドラ 4 枚（出典の多数派は店ごとの華牌を抜く形。華牌は店ごとに違うので、ここでは出典にある北抜きの形にしてある。"
              "北は、北や字牌が要る役満のほかは手の内に使えない）、完全先付け（喰いタン・後付け・片和了なし）、チーなし、フリテン立直不可、1000 点単位（100 点棒なし）、積み棒 1000 点、ツモ損なし（丸取り。"
              "子のツモは満貫 5000-3000、跳満 8000-4000、倍満 10000-6000、三倍満 16000-8000、役満 20000-12000、親のツモはロンの半分ずつ）、"
              "南場は親ノーテン連荘、大車輪（清一色七対子）は役満、小車輪（混一色七対子）6 翻、四連刻は役満、三連刻・三風 2 翻、七対子の 4 枚使いあり、流し役満、数え 14",
    unknown=["settlement.uma", "settlement.start_points", "settlement.return_points", "end.tobi",
             "game_rules.scoring.noten_penalty"])

# 東天紅の王牌（lag.jp「ドラは9枚目をめくる(抜きドラ12枚+槓用の4枚)」「ドラ表示牌の隣までツモる」）：末尾から 8 幢＝16 枚が抜き・槓の補充、9 幢目の上がドラ表示牌。
WALL_TOUTENKOU = {"deal": "N_each_then_1_to_dealer", "dead_wall": 18, "dora_indicator": [0], "ura_indicator": [1],
                  "rinshan": [16, 17, 14, 15, 12, 13, 10, 11, 8, 9, 6, 7, 4, 5, 2, 3], "rinshan_reserved": True, "break": {"by": "dice"}}

S_TOUTENKOU = ["https://lag.jp/toutenko-rule/", "https://mahjong-item.jp/toutenko/", "https://www.mahjong-press.com/mahjong-else/three-player-mahjong-toutenkou/"]
add(base("toutenkou-3p", "mpsz-x28", players=3, length="endless", wall=WALL_TOUTENKOU,
         game_rules={"flow": {"chi": False, "next_dealer": "winner", "riichi": {"min_points": 1}},
                     "dora": {"kan": False, "kan_ura": False},
                     "nuki": {"enabled": True, "tiles": ["1m", "9m", "N"], "value": 1, "win_with_nuki_in_hand": False},
                     "yaku": {"overrides": {"sanshoku": False, "sanshoku_doukou": False, "nagashi_mangan": "yakuman"}},
                     "nagashi_mangan": {"enabled": True, "as": "yakuman"},
                     "scoring": {"table": "additive", "fu": {"enabled": False},
                                 "additive": {"per_han": 1, "base": 2, "dealer": 1, "honba": 1, "honba_dealer_only": True, "multiplier": 1, "round_to": 1,
                                              "yakuman": 50, "karasu": {"menzen": 20, "open": 10}},
                                 "kyotaku_points": 1, "noten_penalty": 30}},
         end={"tobi": {"enabled": True, "at": 0}},
         settlement={"start_points": 50, "return_points": 60, "unit": {"name": "pt", "points_per_unit": 1, "decimals": 0}}),
    S_TOUTENKOU, "東天紅（関東の三人打ち）の一般形：足し算の点数（1 翻 1 点、バンバン 2 点、親 1 点、本場 1 点＝親だけ、役満 50 点、カラス 20 点・鳴きカラス 10 点）、"
                 "ロンは放銃者が、ツモは 2 人がそれぞれ同じ点を払う。一萬・九萬・北を抜く。チーなし、三色なし、流し満貫は役満。和了した人が次の親、場は東のまま、"
                 "ノーテン罰符は場に 20 点（ノーテンの人が合計 20 点を払い、聴牌の人が受け取る）。区切りなし（50 点持ち 60 点返し、飛んだら終了）。王牌は 18 枚（補充用 16 枚＋9 幢目がドラ表示牌）、ドラは表と裏だけ。"
                 "ドラ表示牌の隣までツモる（抜き・槓の補充は取ってある 16 枚から取り、局は短くならない）。"
                 "一萬・九萬・北を手に残したままでは和了できない（国士無双・清老頭・字一色・四喜和だけは可）。店や仲間内で違いが大きい",
    unknown=["settlement.uma", "game_rules.scoring.kyotaku_points", "game_rules.flow.riichi.min_points", "game_rules.dora.kan",
             "game_rules.flow.renchan", "game_rules.flow.atozuke", "game_rules.flow.double_ron",
             "game_rules.pao", "game_rules.marks"])

# ---- 局所ルールの一般形 ----------------------------------------------------------------
add(base("open-riichi-house",
         game_rules={"flow": {"open_riichi": {"enabled": True, "han_total": 2, "deal_in": "yakuman", "exempt_prior_riichi": True, "chaser_pays": True, "with_double_riichi_han": 3}},
                     "yaku": {"overrides": {"open_riichi": 1}}}),
    S_OPEN, "オープンリーチ採用店の一般形：2 翻、放銃は役満払い（先リーチ者除外、追っかけは払う）、ダブリー複合 3 翻",
    unknown=["settlement.uma"])

add(base("pocchi-house", "mpsz-pocchi",
         game_rules={"marks": {"red": {"effects": ["dora"]},
                               "gold": {"effects": ["dora"]},
                               "pocchi": {"effects": ["almighty"], "when": {"state": "riichi", "how": "tsumo"}, "forced_high": True},
                               "reverse_pocchi": {"effects": ["almighty", "reverse"], "when": {"state": "riichi", "how": "tsumo"}}},
                     "scoring": {"honba_points": 1500}},
         settlement={"uma": [50, 20, -20, -50],
                     "chips": [{"on": "win_with_mark", "mark": "red", "per": "tile", "count": 1, "payer": "loser"},
                               {"on": "win_with_mark", "mark": "gold", "per": "tile", "count": 2, "payer": "loser"},
                               {"on": "win_with_mark", "mark": "pocchi", "win_tile": True, "per": "tile", "count": 1, "payer": "loser"}]}),
    S_POCCHI, "赤 3 金 3 白ポッチ逆ポッチ：金牌はドラ＋祝儀 2 倍、白ポッチはリーチ後ツモでオールマイティ（強制高目、祝儀 1 枚）、逆ポッチは支払い、1 本場 1500 点、ウマ 20-50（出典は「ウマはお好みで」）。牌表は同梱 mpsz-pocchi（赤 3・金 3・白ポッチ・逆ポッチ）",
    unknown=["settlement.start_points", "settlement.return_points"])

# ---- N 枚麻雀の既定（nm-defaults.md）。定義は nmahjong/nmrules.py ------------------------------
for n in NR.HAND_SIZES:
    for suits in ("m", "mps", "mpsz"):
        rs = NR.ruleset_for(n, suits, "east_south")
        RULESETS.append(rs)

# 4 枚麻雀の別版（2 人で部屋を作って打つ形。nm-defaults.md §3）
add(base("nm-2p-4-room", "m", players=2, hand=4, length="east_south",
         wall={"deal": "N_each_then_1_to_dealer", "dead_wall": 2, "dora_indicator": [0], "ura_indicator": [1], "rinshan": "live", "break": {"by": "none"}},
         game_rules={"agari_form": "standard", "marks": {"red": {"effects": ["dora"]}},
                     "dora": {"indicator": True, "ura": True, "kan": False, "kan_ura": False},
                     "yaku": {"base": "none", "overrides": {"renhou": 5, "rinshan": 1, "haitei": 1, "houtei": 1, "menzen_tsumo": 1, "chinitsu": 2, "pinfu": 1,
                                                            "toitoi": 2, "tanyao": 1, "junchan": 3, "riichi": 1, "double_riichi": 2, "ippatsu": 1,
                                                            "chinroutou": "yakuman", "tenhou": "yakuman", "chiihou": "yakuman"}},
                     "pao": {"yakuman": []},
                     "flow": {"chi": False, "pon": False, "kan_kinds": ["ankan"], "max_kans": 1, "riichi": {"min_points": 0, "below_min": "allowed", "ankan_after": "none"},
                              "renchan": {"dealer_win": True, "dealer_tenpai": True, "draw": True},
                              "ryukyoku": {"nine_terminals": False, "four_winds": False, "four_kans": False, "four_riichi": False, "three_ron": False}},
                     "scoring": {"honba_points": 1000, "kyotaku_points": 0, "noten_penalty": 0, "mangan_round_up": False,
                                 "fu": {"enabled": True, "menzen_tsumo_pinfu": True, "open_pinfu_fu": 30},
                                 "limits": {"sanbaiman_from": 11, "kazoe_from": 13, "yakuman_base": 4, "max_multiple": 1, "stack_with_normal": False},
                                 "payment": "4p_total_from_opponent"}},
         end={"tobi": {"enabled": True, "at": 0, "exact_zero_is_tobi": True},
              "tenpai_yame": {"enabled": True, "forced": True, "require_tenpai": False}},
         settlement={"start_points": 100000, "return_points": 100000, "oka": "none", "tie": "draw", "uma": [0, 0]}),
    S_NM_ROOM, "4 枚麻雀の別版（2 人で部屋を作って打つ形）：2 人、萬子 36 枚・赤 3/5/7、王牌 2・嶺上は生牌山、暗槓 1 回のみ（立直前）、立直棒なし、役 13 種＋役満 3 種、4 人分の合計を相手が全額、本場 1000、0 点以下トビ、同点引き分け")


def main():
    out = os.path.join(os.path.dirname(__file__), "..", "nmahjong", "data", "rulesets")
    ok = 0
    for rs in RULESETS:
        fin = R.finalize(rs)
        tkey = next(k for k, v in T.items() if v["id"] == fin["tileset"]["id"])
        norm, warns = R.validate(fin, T[tkey])
        print(f"{fin['name']:24s} {fin['id'][:23]}… " + ("; ".join(warns) if warns else "欠落なし"))
        files.save(fin, out, R.filename(fin))
        ok += 1
    print(f"{ok} rulesets")


if __name__ == "__main__":
    main()
