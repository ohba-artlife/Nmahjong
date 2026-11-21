"""天鳳の SHUFFLE seed から 136 枚の山を再現する（mt19937ar-sha512-n288）。

実牌譜 2019051522gm-00a9-0000-8c64c236（10 局、カン 3 回）で配牌・全ツモ・嶺上・ドラ表示・
カンドラ・サイコロの一致を確認済み（2026-11-15。牌譜を置けば tests/test_tenhou_logs.py が確かめる）。

天鳳の向き：yama[135] から順にツモ、yama[0..13] が王牌。
  ドラ表示 yama[5]、裏 yama[4]、カンドラ yama[7,9,11,13]、カン裏 yama[6,8,10,12]、嶺上 yama[1,0,3,2]
  サイコロ (rnd[135] % 6, rnd[136] % 6)（INIT.seed の 4・5 番目、0 始まり）
"""
import base64
import hashlib
import struct
from typing import List, Tuple

METHOD = "tenhou-mt19937ar-sha512-n288-nm1"
PREFIX = "mt19937ar-sha512-n288-base64,"

# 天鳳配列での王牌内位置（上の docstring）
TENHOU_DORA = 5
TENHOU_URA = 4
TENHOU_KAN_DORA = [7, 9, 11, 13]
TENHOU_KAN_URA = [6, 8, 10, 12]
TENHOU_RINSHAN = [1, 0, 3, 2]


class MT19937:
    """mt19937ar（init_by_array 版）。Python の random と同じ系統だが、出力は genrand_int32。"""

    def __init__(self, init_key: List[int]):
        self.mt = [0] * 624
        self.idx = 624
        self.mt[0] = 19650218
        for i in range(1, 624):
            self.mt[i] = (1812433253 * (self.mt[i - 1] ^ (self.mt[i - 1] >> 30)) + i) & 0xFFFFFFFF
        i, j = 1, 0
        for _ in range(max(624, len(init_key))):
            self.mt[i] = ((self.mt[i] ^ ((self.mt[i - 1] ^ (self.mt[i - 1] >> 30)) * 1664525)) + init_key[j] + j) & 0xFFFFFFFF
            i += 1
            j += 1
            if i >= 624:
                self.mt[0] = self.mt[623]
                i = 1
            if j >= len(init_key):
                j = 0
        for _ in range(623):
            self.mt[i] = ((self.mt[i] ^ ((self.mt[i - 1] ^ (self.mt[i - 1] >> 30)) * 1566083941)) - i) & 0xFFFFFFFF
            i += 1
            if i >= 624:
                self.mt[0] = self.mt[623]
                i = 1
        self.mt[0] = 0x80000000

    def genrand_int32(self) -> int:
        if self.idx >= 624:
            mt = self.mt
            for i in range(624):
                y = (mt[i] & 0x80000000) | (mt[(i + 1) % 624] & 0x7FFFFFFF)
                mt[i] = mt[(i + 397) % 624] ^ (y >> 1) ^ (0x9908B0DF if y & 1 else 0)
            self.idx = 0
        y = self.mt[self.idx]
        self.idx += 1
        y ^= y >> 11
        y ^= (y << 7) & 0x9D2C5680
        y ^= (y << 15) & 0xEFC60000
        y ^= y >> 18
        return y & 0xFFFFFFFF


def parse_seed(seed_attr: str) -> List[int]:
    """SHUFFLE の seed 属性（接頭辞付き可）→ 624 個の u32（little-endian）。"""
    s = seed_attr[len(PREFIX):] if seed_attr.startswith(PREFIX) else seed_attr
    raw = base64.b64decode(s)
    if len(raw) % 4:
        raise ValueError("seed の長さが 4 の倍数ではない")
    return list(struct.unpack("<%dI" % (len(raw) // 4), raw))


EXCL_3P = frozenset(range(4, 32))   # 三麻で除く 2m〜8m（天鳳番号）


def tenhou_to_x28(t: int) -> int:
    """天鳳番号（136 系）→ 牌表 mpsz-x28 の番号（108 系）。2m〜8m は無い。"""
    if t < 4:
        return t
    if t >= 32:
        return t - 28
    raise ValueError(f"三麻に無い牌 {t}")


def tenhou_walls(seed_attr: str, nrounds: int, players: int = 4) -> List[Tuple[List[int], Tuple[int, int]]]:
    """局ごとの (yama 天鳳の向き, (dice0, dice1) 0 始まり) を nrounds 局分返す。
    四麻は 136 枚。三麻は 2m〜8m を除いた 108 枚の並び（天鳳番号の昇順）を rnd[i] % (108−i) で混ぜる
    （公開牌譜 278 件 2534 局で配牌・ツモ順が全局一致。136 枚を混ぜてから除く案は 0 局一致）。"""
    mt = MT19937(parse_seed(seed_attr))
    out = []
    for _ in range(nrounds):
        src = [mt.genrand_int32() for _ in range(288)]
        rnd: List[int] = []
        for c in range(9):
            h = hashlib.sha512(struct.pack("<32I", *src[c * 32:(c + 1) * 32])).digest()
            rnd += list(struct.unpack("<16I", h))
        yama = [t for t in range(136) if t not in EXCL_3P] if players == 3 else list(range(136))
        n = len(yama)
        for i in range(n):
            j = i + rnd[i] % (n - i)
            yama[i], yama[j] = yama[j], yama[i]
        out.append((yama, (rnd[135] % 6, rnd[136] % 6)))
    return out


def tenhou_wall(seed_attr: str, round_index: int, players: int = 4) -> Tuple[List[int], Tuple[int, int]]:
    return tenhou_walls(seed_attr, round_index + 1, players)[round_index]


def tenhou_deal(yama: List[int], oya: int, players: int = 4, hand: int = 13):
    """天鳳の取り順で配牌を作る。戻り値 (hands[seat] 取った順, 次に引く位置 pos)。
    4 枚×3 回を親から順に、次に 1 枚ずつ。三麻は players=3。"""
    pos = len(yama) - 1
    hands = [[] for _ in range(players)]
    blocks, rest = divmod(hand, 4)
    for _ in range(blocks):
        for p in range(players):
            who = (oya + p) % players
            hands[who] += [yama[pos - i] for i in range(4)]
            pos -= 4
    for _ in range(rest):
        for p in range(players):
            hands[(oya + p) % players].append(yama[pos])
            pos -= 1
    return hands, pos


def to_nm1(yama: List[int], oya: int, players: int = 4, hand: int = 13) -> List[int]:
    """nm1 変換：本仕様の並び（先頭から消費、末尾 14 枚が王牌）にする。
    先頭 N×M+1 枚は「親から N 枚ずつ → 親に 1 枚」の順。各家の配牌の集合と以後のツモ順は天鳳と同じ。
    王牌オフセット（末尾 14 枚の先頭を 0）：ドラ 8・裏 9・カンドラ [6,4,2,0]・カン裏 [7,5,3,1]・嶺上 [12,13,10,11]。"""
    hands, pos = tenhou_deal(yama, oya, players, hand)
    order: List[int] = []
    for p in range(players):
        order += hands[(oya + p) % players]
    order.append(yama[pos])          # 親の第 1 ツモ
    pos -= 1
    order += [yama[i] for i in range(pos, 13, -1)]   # 以後のツモ（yama[14] まで）
    order += [yama[i] for i in range(13, -1, -1)]    # 王牌（反転）
    assert len(order) == len(yama) and sorted(order) == sorted(yama)
    return order


# 本仕様の並びでの王牌オフセット（nm1 後）。ruleset の既定値と一致させる
NM1_DEAD_WALL = 14
NM1_DORA = [8]
NM1_URA = [9]
NM1_KAN_DORA = [6, 4, 2, 0]
NM1_KAN_URA = [7, 5, 3, 1]
NM1_RINSHAN = [12, 13, 10, 11]
