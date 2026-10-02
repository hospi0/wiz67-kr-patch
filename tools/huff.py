# -*- coding: utf-8 -*-
r"""Wizardry VI·VII (새턴) 대사 허프만 압축 — MSG?J.DBS(본문)·MSG?J.HDR(색인)·MISC?J.HDR(트리)
  출처: Remisse 영문 패치 도구(HuffmanCompressor.cpp, GPL-3) · Gertius 노트 — ★여기선 사실 확인 전까지 «후보»
  트리: 4 B 노드 [왼 int16 LE][오른 int16 LE] · 값 < 0 → 자식 노드(−값×4 바이트 위치) · 값 ≥ 0 → 글자 바이트(잎)
  HDR: u16 LE 개수 + 항목 6 B [u16 색인][u16 주소][u8 조각수−1][u8 블록] · 시작 = 블록×1024 + 주소
  조각: [u8 바이트수+1][u8 글자수] + 비트열(바이트 안 MSB 먼저)
  python tools/huff.py 6|7   → work/text/msg6.tsv|msg7.tsv (색인·조각·SJIS 문자열)
"""
import os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
DISC = os.path.join(ROOT, 'work', 'disc')
NAMES = {'6': ('MSG6J.DBS', 'MSG6J.HDR', 'MISC6J.HDR'), '7': ('MSGJ.DBS', 'MSGJ.HDR', 'MISCJ.HDR')}


def tree(t):
    return t


def decode_piece(tr, d, p):
    nbytes = d[p] - 1; nchars = d[p + 1]
    out = bytearray(); node = 0
    for i in range(nbytes):
        b = d[p + 2 + i]
        for j in range(8):
            bit = (b >> (7 - j)) & 1
            v = struct.unpack_from('<h', tr, node + 2 * bit)[0]
            if v < 0:
                node = -v * 4
            else:
                out.append(v); node = 0
                if len(out) == nchars:
                    return bytes(out), p + 2 + nbytes
    return bytes(out), p + 2 + nbytes


def entries(which):
    dbs, hdr, misc = (open(os.path.join(DISC, n), 'rb').read() for n in NAMES[which])
    n = struct.unpack_from('<H', hdr, 0)[0]
    res = []
    for k in range(n):
        idx, addr, sub, blk = struct.unpack_from('<HHBB', hdr, 2 + 6 * k)
        if idx == 0:
            continue
        p = blk * 1024 + addr; pieces = []
        for s in range(sub + 1):
            txt, p = decode_piece(misc, dbs, p)
            pieces.append(txt)
        res.append((idx, pieces))
    return n, res


if __name__ == '__main__':
    w = sys.argv[1]
    n, res = entries(w)
    os.makedirs(os.path.join(ROOT, 'work', 'text'), exist_ok=True)
    nch = 0
    with open(os.path.join(ROOT, 'work', 'text', 'msg%s.tsv' % w), 'w', encoding='utf-8') as f:
        f.write('색인\t조각\t원문\n')
        for idx, pieces in res:
            for s, t in enumerate(pieces):
                u = t.decode('cp932', 'backslashreplace')
                nch += len(u)
                esc = ''.join('\\x%02X' % ord(ch) if ord(ch) < 0x20 else ch for ch in u.replace('\n', '\x00N'))
                f.write('%d\t%d\t%s\n' % (idx, s, esc.replace('\\x00N', '\\n')))
    print('항목 %d(색인 표 %d) · 조각 %d · 글자 %d' % (len(res), n, sum(len(p) for _, p in res), nch))


# ── 다시 묶기 ──────────────────────────────────────────────
def codes_of(tr):
    """트리 → {바이트: 비트열 문자열}"""
    out = {}

    def walk(node, bits):
        for bit in (0, 1):
            v = struct.unpack_from('<h', tr, node + 2 * bit)[0]
            if v < 0:
                walk(-v * 4, bits + str(bit))
            else:
                out.setdefault(v, bits + str(bit))
    walk(0, '')
    return out


def build_tree(freq):
    """빈도 {바이트: 횟수} → 트리 바이트(뿌리 = 0번 노드, 노드 ≤ 255개 = 1020 B ≤ 1024)"""
    import heapq, itertools
    cnt = itertools.count()
    h = [(f, next(cnt), ('leaf', b)) for b, f in freq.items() if f > 0]
    if len(h) == 1:
        h.append((0, next(cnt), ('leaf', 0 if h[0][2][1] else 1)))
    heapq.heapify(h)
    while len(h) > 1:
        a = heapq.heappop(h); b = heapq.heappop(h)
        heapq.heappush(h, (a[0] + b[0], next(cnt), ('node', a[2], b[2])))
    root = h[0][2]
    nodes = []                                       # 너비 우선 번호 — 뿌리가 0

    order = [root]; idx = {id(root): 0}
    i = 0
    while i < len(order):
        n = order[i]; i += 1
        for c in n[1:]:
            if c[0] == 'node':
                idx[id(c)] = len(order); order.append(c)
    t = bytearray(1024)
    for k, n in enumerate(order):
        for side, c in enumerate(n[1:]):
            v = -idx[id(c)] if c[0] == 'node' else c[1]
            struct.pack_into('<h', t, k * 4 + side * 2, v)
    assert len(order) * 4 <= 1024
    return bytes(t)


def encode_piece(codes, s):
    bits = ''.join(codes[b] for b in s)
    bits += '0' * (-len(bits) % 8)
    body = bytes(int(bits[i:i + 8], 2) for i in range(0, len(bits), 8))
    assert len(body) + 1 < 256 and len(s) < 256, ('조각이 너무 김', len(body), len(s))
    return bytes([len(body) + 1, len(s)]) + body


def pack(items, tr, nslots=None):
    """items = [(색인, [조각 bytes…])] (원래 HDR 순서) → (dbs, hdr)"""
    codes = codes_of(tr)
    dbs = bytearray(); ents = []
    for idx, pieces in items:
        pos = len(dbs)
        ents.append(struct.pack('<HHBB', idx, pos % 1024, len(pieces) - 1, pos // 1024))
        for s in pieces:
            dbs += encode_piece(codes, s)
    hdr = struct.pack('<H', nslots or len(ents)) + b''.join(ents)
    return bytes(dbs), hdr
