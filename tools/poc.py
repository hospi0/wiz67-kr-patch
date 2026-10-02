# -*- coding: utf-8 -*-
r"""PoC (2026-10-02) — 대사 아카이브(VI·VII)의 일본어 글자를 전부 «한글시험중입니다» 8자로 차례로 바꾸고
  KANJI12.FON 16구 1‥8점(亜唖娃阿哀愛挨姶) 칸에 그 8자를 그린다 · 새 허프만 트리로 다시 묶는다.
  증명하려는 것: ①KANJI12.FON 이 대사 글꼴이다 ②게임이 새 트리(MISC?J.HDR)·새 DBS/HDR 를 읽는다 ③16×12 칸 판독성.
  글자 수는 원문과 같으므로 줄 배치는 원본 그대로. 제어 바이트·ASCII·부호(、。！？…「」 등)는 그대로.
  python tools/poc.py [--install]
"""
import collections, os, re, shutil, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, r'C:\claude\project\anearth-kr-patch\tools')
import bdf, disc, huff, iso

TEST = '한글시험중입니다'
SLOTS = [((16 - 1) * 94 + k) for k in range(8)]          # 16구 1‥8점
F_DIR = r'F:\hospi\roms\ss roms\Wizardry VI  VII Complete (Japan) (3M)'
OUT = os.path.join(ROOT, 'work', 'out', os.path.basename(disc.ROM))


def sjis_of(slot):
    ku, ten = slot // 94 + 1, slot % 94 + 1
    return ('\x1b$B' + chr(ku + 0x20) + chr(ten + 0x20)).encode('latin1').decode('iso2022_jp').encode('cp932')


def is_jp(ch):
    return '\u3040' <= ch <= '\u30ff' or '\u4e00' <= ch <= '\u9fff' or ch == '々'


def transform(b, codes, k):
    s = b.decode('cp932', 'surrogateescape')
    out = []
    for ch in s:
        if is_jp(ch):
            out.append(codes[k[0] % 8]); k[0] += 1
        else:
            out.append(ch.encode('cp932', 'surrogateescape'))
    return b''.join(out)


def glyph(F, ch):
    pts, _ = F.draw(ch, 0, 0)
    xs = [x for x, _ in pts]; ys = [y for _, y in pts]
    ox = (12 - (max(xs) - min(xs) + 1)) // 2 - min(xs); oy = (12 - (max(ys) - min(ys) + 1)) // 2 - min(ys)
    rows = [0] * 12
    for x, y in pts:
        X, Y = x + ox, y + oy
        if 0 <= X < 16 and 0 <= Y < 12:
            rows[Y] |= 1 << (15 - X)
    return b''.join(r.to_bytes(2, 'big') for r in rows)


def build(install=False):
    codes = [sjis_of(s) for s in SLOTS]
    files = {}
    for w in ('6', '7'):
        dn, hn, mn = huff.NAMES[w]
        dbs0, hdr0, misc0 = (open(os.path.join(huff.DISC, n), 'rb').read() for n in (dn, hn, mn))
        n, res = huff.entries(w)
        k = [0]
        res2 = [(idx, [transform(s, codes, k) for s in pieces]) for idx, pieces in res]
        fq = collections.Counter(b for _, p in res2 for s in p for b in s)
        tr = huff.build_tree(fq)
        mx = max(len(c) for c in huff.codes_of(tr).values())
        dbs, hdr = huff.pack(res2, tr, n)
        assert len(dbs) <= len(dbs0) and len(hdr) <= len(hdr0), (w, len(dbs), len(dbs0))
        files[dn] = dbs + bytes(len(dbs0) - len(dbs))
        files[hn] = hdr + bytes(len(hdr0) - len(hdr))
        files[mn] = tr
        print('Wiz%s: 일본어 %d자 → 시험 글자 · DBS %d/%d B · 트리 최장 부호 %d비트' % (w, k[0], len(dbs), len(dbs0), mx))
    F = bdf.Font(r'C:\claude\utils\font\Galmuri-v2.40.3\Galmuri11.bdf')
    fon = bytearray(open(os.path.join(huff.DISC, 'KANJI12.FON'), 'rb').read())
    for s, ch in zip(SLOTS, TEST):
        fon[s * 24:(s + 1) * 24] = glyph(F, ch)
    files['KANJI12.FON'] = bytes(fon)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    iso.patch(disc.ROM, OUT, files)
    if install:
        shutil.copyfile(OUT, os.path.join(F_DIR, os.path.basename(OUT)))
        print('F: 설치', F_DIR)


if __name__ == '__main__':
    build('--install' in sys.argv)
