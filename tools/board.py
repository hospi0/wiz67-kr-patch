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
    slots = list(KANA_ORDER) + list(ALPHA)                     # 직접 칸(판 순서)
    nd = len(slots); bases = [(b, '゛', i) for i, b in enumerate(VOICED_BASE)] + [(b, '゜', i) for i, b in enumerate(SEMI_BASE)]
    allsyl = sorted(need)
    assert len(allsyl) <= nd + len(bases), ('음절이 칸보다 많음', len(allsyl))
    # ★가나다순 한 줄로: 판 순서대로 칸을 채우다가 바탕 칸을 지나면 바로 다음 음절 = ゛, 그다음 = ゜(ハ‥ホ)
    #   → 플레이어 규칙 «゛ = 이 칸 다음 글자 · ゜ = 그다음 글자»
    cap = nd + len(bases)
    spare = [c for c in SPARE if c not in need][:cap - len(allsyl)]
    seq = sorted(set(allsyl) | set(spare))
    vb = {b: i for i, b in enumerate(VOICED_BASE)}; sb = {b: i for i, b in enumerate(SEMI_BASE)}
    at = {}; pair = {}; it = iter(seq)
    order = list(KANA_ORDER) + list(ALPHA)
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


if __name__ == '__main__':
    rows, need = plan()
    write(rows)
    print('키워드 음절 %d · 직접 칸 %d · ゛゜ %d' % (len(need), sum(1 for r in rows if r[0] == '직접' and r[2]), sum(1 for r in rows if r[0] != '직접')))
    print('가나 쪽:', ' '.join('%s=%s' % (r[1], r[2]) for r in rows if r[0] == '직접' and r[1] in KANA_ORDER))
    print('영문 쪽:', ' '.join('%s=%s' % (r[1], r[2]) for r in rows if r[0] == '직접' and r[1] in ALPHA))
    print('゛゜  :', ' '.join('%s%s→%s' % (r[1], r[0], r[2]) for r in rows if r[0] != '직접'))
    print('→', OUT)
