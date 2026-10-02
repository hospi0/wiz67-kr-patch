# -*- coding: utf-8 -*-
r"""Wizardry VI·VII 번역 TSV 추출 (2026-10-02) → my files/tsv/
  열 = ID(6-/7-/X-/N- = VI 대사·VII 대사·실행 파일·나레이션) · 위치 · 구분 · 공유 · 원문 · 번역 (사이버 돌·블루 시드와 같은 꼴), 파일 하나 29KB 이하.
  ① wiz6_대사_NNN / wiz7_대사_NNN  = MSG6J / MSGJ 허프만 아카이브 조각(일본어 든 것만)
       위치 = 색인.조각(같은 원문이 여럿이면 첫 자리, 공유 = 개수 — 빌더가 같은 원문 전부에 넣음)
       제어 바이트 0x01‥0x1F → {01}‥{1F}(0x0A 는 \n) · `@`·공백은 원문 그대로.
       ⛔영어만 된 조각(HUMAN·FIGHTER·아이템 영문명 등 일본판도 영어)은 뽑지 않음.
  ② wiz_나레이션  = 오프닝/엔딩 CDSOP0‥3·BCFOP·CPKPLAY·CDS_END0‥3 의 [SJIS·FFxx·FExx]…FC 블록
       한 줄 = 한 화면(FExx 앞까지) · FF02 → \n · 위치 = 파일@블록오프셋#화면번호(공유 = 같은 화면이 든 파일 수)
  ③ wiz_실행  = WIZ6.BIN(VI)·WIZARDRY.BIN(VII)·SL.BIN 의 NUL 끝 SJIS 문자열
       구분 = «실행N»(N = 원래 바이트 수 = 제자리 한도) · 위치 = 파일@오프셋(16진)
       시작 = 4 B 정렬(또는 앞이 NUL) · 첫 글자 전각(또는 ' *?' + 가나 2자 이상) · 한자는 대사 말뭉치에 나오는 것만(가나 2자 이상이면 허용) · 2글자 이상
       (1글자 문자열 = 이름 입력 글자판 등 데이터라 뺌)
  ★같은 내용을 work/text/<이름>.tsv 에 통짜로도 씀(GitHub 저장소용 — 쪼개지 않음).
  python tools/extract.py
"""
import os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import huff
from disc import Disc

sys.stdout.reconfigure(encoding='utf-8')
OUT = os.path.join(ROOT, 'my files', 'tsv')
DISC = os.path.join(ROOT, 'work', 'disc')
TEXT = os.path.join(ROOT, 'work', 'text')        # 저장소용 통짜 TSV
HEAD = 'ID\t위치\t구분\t공유\t원문\t번역\n'
LIMIT = 29 * 1024                   # ★파일 하나 29KB 이하(줄 수 아님)
JP = re.compile('[぀-ヿ一-鿿ｦ-ﾟ]')
LEAD = set(range(0x81, 0xA0)) | set(range(0xE0, 0xF0))


def chunk(lines):
    files = []; cur = []; size = len(HEAD.encode('utf-8'))
    for ln in lines:
        b = len(ln.encode('utf-8'))
        if cur and size + b > LIMIT:
            files.append(cur); cur = []; size = len(HEAD.encode('utf-8'))
        cur.append(ln); size += b
    if cur:
        files.append(cur)
    return files


def write(name, lines):
    with open(os.path.join(OUT, name), 'w', encoding='utf-8', newline='\n') as f:
        f.write(HEAD + ''.join(lines))


def esc(s):
    s = s.replace('\n', '\\n')
    return re.sub('[\x00-\x1f]', lambda m: '{%02X}' % ord(m.group()), s)


def row(i, pos, kind, n, src):
    return '%s\t%s\t%s\t%d\t%s\t\n' % (i, pos, kind, n, src)


# ── ① 대사 ────────────────────────────────────────────────
def dialogue(w):
    _, res = huff.entries(w)
    first = {}; count = {}
    for idx, pieces in res:
        for s, b in enumerate(pieces):
            t = esc(b.decode('cp932', 'backslashreplace'))
            if not JP.search(t):
                continue
            first.setdefault(t, '%d.%d' % (idx, s)); count[t] = count.get(t, 0) + 1
    return [row('%s-%05d' % (w, k + 1), first[t], '대사', count[t], t) for k, t in enumerate(first)]


# ── ② 나레이션 ────────────────────────────────────────────
NARR = ['CDSOP0.BIN', 'CDSOP1.BIN', 'CDSOP2.BIN', 'CDSOP3.BIN', 'BCFOP.BIN', 'CPKPLAY.BIN',
        'CDS_END0.BIN', 'CDS_END1.BIN', 'CDS_END2.BIN', 'CDS_END3.BIN']


def narr_block(d, i):
    """[SJIS·FF xx·FE xx …] FC → 화면 목록 [(글, FE토큰)] / None"""
    pages = []; cur = []; j = i; nj = 0
    while j < len(d) - 1:
        b = d[j]
        if b in LEAD and 0x40 <= d[j + 1] <= 0xFC:
            try:
                cur.append(d[j:j + 2].decode('cp932')); nj += 1
            except UnicodeDecodeError:
                return None
            j += 2
        elif b == 0xFF and d[j + 1] == 0x02:
            cur.append('\\n'); j += 2
        elif b in (0xFF, 0xFD):
            cur.append('{%02X%02X}' % (b, d[j + 1])); j += 2
        elif b == 0xFE:
            pages.append(''.join(cur)); cur = []; j += 2
        elif b == 0xFC:
            if cur:
                pages.append(''.join(cur))
            return (pages, j) if nj >= 8 else None
        else:
            return None
    return None


def narration():
    D = Disc(); fs = {e[0]: e for e in D.walk()}
    first = {}; files = {}
    for f in NARR:
        e = fs[f]; d = D.read(e[1], e[2]); i = 0
        while i < len(d) - 1:
            if d[i] in LEAD and (i == 0 or d[i - 1] in (0, 0xFC)):
                r = narr_block(d, i)
                if r:
                    for k, t in enumerate(r[0]):
                        first.setdefault(t, '%s@%X#%d' % (f.split('.')[0], i, k))
                        files.setdefault(t, set()).add(f)
                    i = r[1]; continue
            i += 1
    return [row('N-%04d' % (k + 1), first[t], '나레이션', len(files[t]), t) for k, t in enumerate(first)]


# ── ③ 실행 파일 ───────────────────────────────────────────
EXE = [('WIZ6.BIN', 'VI'), ('WIZARDRY.BIN', 'VII'), ('SL.BIN', 'SL')]


def corpus_kanji():
    s = set()
    for w in '67':
        for _, ps in huff.entries(w)[1]:
            for p in ps:
                s |= set(re.findall('[一-鿿]', p.decode('cp932', 'ignore')))
    return s


def exe_str(d, i, kan):
    """i 에서 NUL 까지 SJIS 문자열(조건 통과 시 (글, 끝))"""
    if not (d[i] in LEAD and 0x40 <= d[i + 1] <= 0xFC or d[i] in b' *?'):
        return None
    j = i; out = []
    while j < len(d) and d[j] != 0:
        b = d[j]
        if b in LEAD and j + 1 < len(d) and 0x40 <= d[j + 1] <= 0xFC and d[j + 1] != 0x7F:
            try:
                out.append(d[j:j + 2].decode('cp932'))
            except UnicodeDecodeError:
                return None
            j += 2
        elif 0x20 <= b < 0x7F or b == 0x0A:
            out.append(chr(b)); j += 1
        else:
            return None                                  # 반각 가나·제어 바이트 = 잡음
    if j >= len(d):
        return None
    t = ''.join(out)
    if len(t) < 2 or not JP.search(t):
        return None
    nkana = len(re.findall('[぀-ヿ]', t))
    if any('一' <= c <= '鿿' and c not in kan for c in t) and (nkana < 2 or re.search('[A-Za-z]', t)):
        return None
    if t[0] in ' *?' and nkana < 2:
        return None
    if re.search('[!-~ヽヾ]', t) and (nkana < 2 or re.search('[ヽヾ`\'"]', t)):
        return None
    return t, j


def exe_strings():
    kan = corpus_kanji()
    first = {}; count = {}; size = {}
    for f, tag in EXE:
        d = open(os.path.join(DISC, f), 'rb').read(); i = 0
        while i < len(d) - 1:
            if i % 4 == 0 or d[i - 1] == 0:
                r = exe_str(d, i, kan)
                if r:
                    t = esc(r[0])
                    first.setdefault(t, '%s@%X' % (f.split('.')[0], i)); count[t] = count.get(t, 0) + 1
                    size[t] = min(size.get(t, 999), r[1] - i)
                    i = r[1] + 1; continue
            i += 1
    return [row('X-%05d' % (k + 1), first[t], '실행%d' % size[t], count[t], t) for k, t in enumerate(first)]


if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    for f in os.listdir(OUT):
        if re.match(r'wiz(6|7)?_.*\.tsv$', f):
            os.remove(os.path.join(OUT, f))
    sets = [('wiz6_대사', dialogue('6')), ('wiz7_대사', dialogue('7')),
            ('wiz_실행', exe_strings()), ('wiz_나레이션', narration())]
    tail = []; nfile = 0
    for stem, lines in sets:
        nch = sum(len(JP.findall(l.split('\t')[4])) for l in lines)
        print('%s: %d줄 · 일본어 %d자' % (stem, len(lines), nch))
        with open(os.path.join(TEXT, stem + '.tsv'), 'w', encoding='utf-8', newline='\n') as f:
            f.write(HEAD + ''.join(lines))          # ★저장소용 통짜(쪼개지 않음)
        parts = chunk(lines)
        if len(parts) > 1 or stem == 'wiz6_대사':
            for k, p in enumerate(parts[:-1]):
                write('%s_%03d.tsv' % (stem, k + 1), p); nfile += 1
            last = ('%s_%03d.tsv' % (stem, len(parts)), parts[-1])
        else:
            last = None
        # 자투리(각 종류의 마지막 조각)는 29KB 안이면 합친다
        for nm, p in ([last] if last else [(stem + '.tsv', parts[0])]):
            tail.append((nm, p))
    # 자투리 합치기: 앞에서부터 채워 넣음
    merged = []; cur = []; names = []
    for nm, p in tail:
        if cur and len((HEAD + ''.join(cur + p)).encode('utf-8')) > LIMIT:
            merged.append((names, cur)); cur = []; names = []
        cur += p; names.append(nm)
    if cur:
        merged.append((names, cur))
    for names, p in merged:
        nm = names[0] if len(names) == 1 else 'wiz_자투리.tsv'
        write(nm, p); nfile += 1
    print('→ %s  파일 %d개' % (OUT, nfile))
