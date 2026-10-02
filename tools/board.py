# -*- coding: utf-8 -*-
r"""이름·키워드 입력판 한글화 (2026-10-02, 사용자: «일단 영문 없이» — 영문 26칸을 음절로, 숫자·기호는 그대로)
  입력판 = 두 쪽: 가나 56칸 + 영숫자 41칸. 칸 글자 = 실행 파일의 4 B 문자열 97개(목록 바탕 = WIZARDRY 0x060148F8 · WIZ6 0x0604A798 ·
      SL 0x0604B448, 셋 다 같은 배치: +0 «ー» … +0xDC «ア»(가나 56, 거꾸로) · +0xE0 «！» … +0x180 «Ａ»(영숫자 41)).
  ゛ 표: 바탕 21칸(カ‥ト·ハ‥ホ·ウ) → 탁음 문자열 +0x288(21) / ゜ 표: ハ‥ホ → +0x384(5).
  배정: 키워드(대사의 «#…@») 음절 + 이름에 흔한 음절(남는 칸만큼)을 가나다순 한 줄로 세워 판 순서(ア イ ウ … 다음 Ａ…Ｚ)대로
      채우되, ゛ 바탕 칸 바로 다음 음절은 그 칸의 ゛, ハ‥ホ 는 그다음 음절이 ゜ — 규칙 «゛ = 이 칸 다음 글자, ゜ = 그다음 글자».
  python tools/board.py      → 배정표 출력 + work/text/wiz_입력판.tsv(빌더가 읽음)
"""
import csv, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.stdout.reconfigure(encoding='utf-8')

BOARD = {'WIZARDRY.BIN': 0x060148F8, 'WIZ6.BIN': 0x0604A798, 'SL.BIN': 0x0604B448}
KANA_ORDER = 'アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲンァィゥェォャュョッー'
ALPHA = 'ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ'
LIST = 'ーッョュャォェゥィァンヲワロレルリラヨユヤモメムミマホヘフヒハノネヌニナトテツチタソセスシサコケクキカオエウイア' \
       '！？＿－．９８７６５４３２１０ＺＹＸＷＶＵＴＳＲＱＰＯＮＭＬＫＪＩＨＧＦＥＤＣＢＡ'
VOICED_BASE = 'カキクケコサシスセソタチツテトハヒフヘホウ'      # +0x288 순서
SEMI_BASE = 'ハヒフヘホ'                                        # +0x384 순서
SPARE = '민수영준현진희지호우연서윤은성혜경미정'                # 남는 ゛·゜ 칸에 넣을 이름 음절(앞에서부터, 이미 판에 있으면 건너뜀)
OUT = os.path.join(ROOT, 'work', 'text', 'wiz_입력판.tsv')


def cho(s):
    return (ord(s) - 0xAC00) // 588


def keyword_syllables():
    syl = {}
    for f in ('wiz6_대사', 'wiz7_대사'):
        for r in csv.reader(open(os.path.join(ROOT, 'work', 'text', f + '.tsv'), encoding='utf-8', newline=''),
                            delimiter='\t', quoting=csv.QUOTE_NONE):
            if len(r) == 6 and r[0] != 'ID' and r[4].startswith('#') and '@' in r[4]:
                for w in re.findall(r'#([^@#]+)@', r[5]):
                    for c in w:
                        if '가' <= c <= '힣':
                            syl[c] = syl.get(c, 0) + 1
    return syl


def plan():
    need = keyword_syllables()
    slots = list(KANA_ORDER) + list(ALPHA)                     # 직접 칸(판 순서) — ★영문 26칸은 비워 원래 글자(2026-10-03 사용자: 키워드 줄여 영문 되살림)
    fill = list(KANA_ORDER)
    nd = len(fill); bases = [(b, '゛', i) for i, b in enumerate(VOICED_BASE)] + [(b, '゜', i) for i, b in enumerate(SEMI_BASE)]
    allsyl = sorted(need)
    assert len(allsyl) <= nd + len(bases), ('음절이 칸보다 많음', len(allsyl))
    # ★가나다순 한 줄로: 판 순서대로 칸을 채우다가 바탕 칸을 지나면 바로 다음 음절 = ゛, 그다음 = ゜(ハ‥ホ)
    #   → 플레이어 규칙 «゛ = 이 칸 다음 글자 · ゜ = 그다음 글자»
    cap = nd + len(bases)
    spare = [c for c in SPARE if c not in need][:cap - len(allsyl)]
    seq = sorted(set(allsyl) | set(spare))
    vb = {b: i for i, b in enumerate(VOICED_BASE)}; sb = {b: i for i, b in enumerate(SEMI_BASE)}
    at = {}; pair = {}; it = iter(seq)
    order = fill
    for sl in order:
        c = next(it, None)
        if c is None:
            break
        at[sl] = c
        if sl in vb:
            d = next(it, None)
            if d: pair[('゛', sl)] = d
        if sl in sb:
            d = next(it, None)
            if d: pair[('゜', sl)] = d
    left = list(it)
    assert not left, ('칸 모자람', left)
    bases_k = {(m, b): k for k, (b, m, i) in enumerate(bases)}
    pair = {bases_k[k]: v for k, v in pair.items()}
    allv = list(at.values()) + list(pair.values())
    assert len(allv) <= cap
    assert len(allv) == len(set(allv)), '음절 중복'
    assert set(need) <= set(allv), '키워드 음절 빠짐'
    rows = [('직접', s, at[s]) for s in slots if s in at] + \
           [('직접', s, '') for s in slots if s not in at] + \
           [(mark, b, pair.get(k, '')) for k, (b, mark, i) in enumerate(bases)]
    return rows, need


def write(rows):
    with open(OUT, 'w', encoding='utf-8', newline='\n') as f:
        f.write('종류\t원래\t한글\n' + ''.join('%s\t%s\t%s\n' % r for r in rows))


def load():
    rows = [l.rstrip('\n').split('\t') for l in open(OUT, encoding='utf-8').read().split('\n')[1:] if l.strip()]
    return rows


def patch(g, name, enc):
    """실행 파일 바이트 → 입력판 칸 바꾼 바이트(enc = 한글 음절 → SJIS 2 B)"""
    g = bytearray(g); base = BOARD[name] - 0x06010000
    have = ''.join(g[base + 4 * k:base + 4 * k + 2].decode('cp932') for k in range(97))
    assert have == LIST, ('입력판 목록이 다름', name)
    for kind, src, ko in load():
        if not ko:
            continue
        if kind == '직접':
            o = base + 4 * LIST.index(src)
        elif kind == '゛':
            o = base + 0x288 + 4 * VOICED_BASE.index(src)
        else:
            o = base + 0x384 + 4 * SEMI_BASE.index(src)
        assert g[o + 2:o + 4] == b'\0\0' or kind != '직접' or True
        g[o:o + 4] = enc(ko) + b'\0\0'
    return bytes(g)


# ★화면의 판은 글자가 아니라 NOHA.SB 안 4bpp 그림(184 폭, 한 줄 92 B) — 2026-10-03 실기 «입력판이 가타카나 그대로».
#   가나 판 0xD7C0(87줄, 잉크 1) · 영문 판 0xF720(잉크 15). 칸 = 가로 11px 간격 · 글자 8×8(갈무리7, menuhook.glyph8 와 같음).
NOHA_W = 184
COLS = [0, 11, 22, 33, 44, 66, 77, 88, 99, 110, 132, 143, 154, 165, 176]
NOHA_KANA = (0xD7C0, 1, [(19, 'アイウエオカキクケコサシスセソ'), (34, 'タチツテトナニヌネノハヒフヘホ'),
                         (49, 'マミムメモヤ　ユ　ヨラリルレロ'), (64, 'ワヲン　　ァィゥェォャ　ュ　ョ'), (79, 'ッ　　　　ー')])   # 판은 87줄(0‥86) — 80 부터 8줄이면 다음 그림(영문 판 머리)을 찍는다
TABS = ['한글', '영문', '끝']           # 2026-10-03 영문 되살림 뒤(전: 한글1·한글2·끝)
TAB_SPANS = [(6, 46), (77, 107), (143, 171)]       # 원래 탭 글자 x 범위(두 판 같음)
NOHA_ALPHA = (0xF720, 15, [(19, 'ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯ'), (34, 'ＰＱＲＳＴＵＶＷＸＹＺ')])   # 원래 글자 20‥26줄 → 8줄 칸은 19‥26


def patch_noha(noha):
    """NOHA.SB 의 두 입력판 그림에 배정표 음절을 다시 그린다(칸을 지우고 8×8 글리프)"""
    import menuhook as M
    d = bytearray(noha)
    ko = {src: k for kind, src, k in load() if kind == '직접' and k}

    def put(base, x, y, v):
        o = base + y * (NOHA_W // 2) + x // 2
        d[o] = (d[o] & 0x0F) | (v << 4) if x % 2 == 0 else (d[o] & 0xF0) | v

    n = 0
    # 위 탭(0‥8줄) «カタカナ / えいご / おわり» → «한글1 / 한글2 / 끝»(사용자 2026-10-03) — 원래 글자 범위 가운데에
    for base, ink, _ in (NOHA_KANA, NOHA_ALPHA):
        for (a, b), label in zip(TAB_SPANS, TABS):
            cols = []
            for ch in label:
                g = M.glyph8(ch)
                w = max((x + 1 for x in range(8) for y in range(8) if g[y] & (0x80 >> x)), default=4)
                cols += [[(g[y] >> (7 - x)) & 1 for y in range(8)] for x in range(w)] + [[0] * 8] * 2   # 글자 사이 2px(원래 탭 간격)
            cols = cols[:-2]
            x0 = (a + b + 1 - len(cols)) // 2
            for y in range(9):
                for x in range(a - 2, b + 3):
                    put(base, x, y, 0)
            for i, col in enumerate(cols):
                for y in range(8):
                    if col[y]:
                        put(base, x0 + i, y, ink)
    for base, ink, rows in (NOHA_KANA, NOHA_ALPHA):
        for y0, line in rows:
            for x0, src in zip(COLS, line):
                if src not in ko:
                    continue
                g = M.glyph8(ko[src])
                for y in range(8):
                    for x in range(min(10, NOHA_W - x0)):      # 오른쪽 끝 칸은 184 를 넘으면 다음 줄 머리를 지운다
                        put(base, x0 + x, y0 + y, ink if x < 8 and g[y] & (0x80 >> x) else 0)
                n += 1
    return bytes(d), n


if __name__ == '__main__':
    rows, need = plan()
    write(rows)
    print('키워드 음절 %d · 직접 칸 %d · ゛゜ %d' % (len(need), sum(1 for r in rows if r[0] == '직접' and r[2]), sum(1 for r in rows if r[0] != '직접')))
    print('가나 쪽:', ' '.join('%s=%s' % (r[1], r[2]) for r in rows if r[0] == '직접' and r[1] in KANA_ORDER))
    print('영문 쪽:', ' '.join('%s=%s' % (r[1], r[2]) for r in rows if r[0] == '직접' and r[1] in ALPHA))
    print('゛゜  :', ' '.join('%s%s→%s' % (r[1], r[0], r[2]) for r in rows if r[0] != '직접'))
    print('→', OUT)
