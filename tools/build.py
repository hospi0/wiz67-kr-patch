# -*- coding: utf-8 -*-
r"""Wizardry VI·VII 한글 빌더 (2026-10-02)
  번역 TSV(열 ID·위치·구분·공유·원문·번역 — tools/extract.py 꼴, 통짜·29KB 분할 아무거나, ID 로 합침)
    → ① 대사 MSG6J/MSGJ 허프만(원문이 같은 조각 전부, 새 트리)
       ② 실행 파일 WIZ6·WIZARDRY·SL 문자열 제자리(원문 바이트 한도, 같은 원문 전부)
       ③ 나레이션 CDSOP0‥3·BCFOP·CPKPLAY·CDS_END0‥3 블록 제자리(원래 블록 길이 한도)
       ④ KANJI12.FON: 음절 i → 22구 1점부터(menuhook.kcode) 16×12 갈무리11 · 70구 = 메뉴 훅 블롭(8×8 갈무리7)
       ⑤ 메뉴 훅 실행 파일 패치(tools/menuhook.py)
  ⛔번역이 없는 줄은 원문 그대로(일본어 한자가 한글 칸에 덮여 깨져 보임 — 전량 번역 전 시험에서만).
  python tools/build.py [번역폴더…]          → 검사·요약만(디스크 안 씀). 기본 폴더 = work/text
  python tools/build.py … --write            → work/out/ 트랙 1
  python tools/build.py … --install          → + F: 설치
  python tools/build.py --fake [--write]     → 가짜 번역(일본어 글자마다 한글 한 자)으로 전 과정 시험
"""
import collections, csv, glob, hashlib, os, re, shutil, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.append(r'C:\claude\project\anearth-kr-patch\tools')      # 맨 뒤에 — 앞에 넣으면 그쪽 extract 등이 이 프로젝트 것을 가린다
import bdf, extract, huff, menuhook as M, rules

sys.stdout.reconfigure(encoding='utf-8')
DISC = os.path.join(ROOT, 'work', 'disc')
F_DIR = r'F:\hospi\roms\ss roms\Wizardry VI  VII Complete (Japan) (3M)'
FONT12 = r'C:\claude\utils\font\Galmuri-v2.40.3\Galmuri11.bdf'
SLOT_MAX = 69 * 94                   # 70구 = 블롭 → 한글 칸은 그 앞까지
HEXB = re.compile(r'\\x([0-9A-Fa-f]{2})')


# ── 번역 읽기 ─────────────────────────────────────────────
def load(dirs):
    rows = {}
    for d in dirs:
        for f in sorted(glob.glob(os.path.join(d, '*.tsv'))):
            with open(f, encoding='utf-8', newline='') as fh:
                for r in csv.reader(fh, delimiter='\t', quoting=csv.QUOTE_NONE):
                    if len(r) < 6 or r[0] == 'ID' or not re.match(r'^[67XNL]-\d+$', r[0]):
                        continue
                    if r[5].strip():
                        rows[r[0]] = dict(id=r[0], pos=r[1], kind=r[2], src=r[4], kr=r[5])
                    else:
                        rows.setdefault(r[0], dict(id=r[0], pos=r[1], kind=r[2], src=r[4], kr=''))
    return rows


FAKE = [c for c in map(chr, range(0xAC00, 0xD7A4)) if len(c.encode('euc_kr', 'ignore')) == 2]   # 완성형 2,350자(칸·LRU 최대 부하)
assert len(FAKE) == 2350


FAKE_L = {'ﾆﾝｼﾞｬ': '닌자', 'ﾓﾝｸ': '몽크', 'ｻﾑﾗｲ': '사무라이', 'ﾛｰﾄﾞ': '로드', 'ﾋﾞｼｮｯﾌﾟ': '비숍', 'ｳﾞｧﾙｷﾘｰ': '발키리',
          'ｻｲｵﾆｯｸ': '사이오닉', 'ﾊﾞｰﾄﾞ': '바드', 'ｱﾙｹﾐｽﾄ': '연금술사', 'ﾚﾝｼﾞｬｰ': '레인저', 'ｼｰﾌ': '시프',
          'ﾌﾟﾘｰｽﾄ': '프리스트', 'ﾒｲｼﾞ': '메이지', 'ﾌｧｲﾀｰ': '파이터', 'ﾎﾞﾀﾝ': '버튼', 'ｶｰｿﾙ': '커서', 'ｽﾀｰﾄ': '시작'}


def fake(rows):
    """가짜 번역: 일본어 글자(가나·한자·전각 영숫자) 하나 → 한글 하나(바이트 같음) — 전 과정·글꼴·길이 시험용"""
    k = 0
    for r in rows.values():
        out = []
        for ch in r['src']:
            if re.match('[\u3040-\u30ff\u4e00-\u9fff々]', ch):
                out.append(FAKE[k % len(FAKE)]); k += 1
            else:
                out.append(ch)
        r['kr'] = ''.join(out)
        if r['id'][0] == 'L':                       # 반각 라벨은 가짜 대신 실제 이름(바이트 예산 안)
            t = r['src']
            for jp, ko in sorted(FAKE_L.items(), key=lambda x: -len(x[0])):
                t = t.replace(jp, ko)
            r['kr'] = t


# ── 부호 ──────────────────────────────────────────────────
class Enc:
    def __init__(self, syl):
        self.idx = {s: i for i, s in enumerate(syl)}

    def text(self, s, narr=False):
        r"""TSV 꼴 → 바이트. \n·{XX}(대사·실행) / \n = FF02 · {FFxx}{FDxx}(나레이션) · \xNN(원래 못 읽은 바이트)"""
        out = bytearray(); i = 0
        while i < len(s):
            if s.startswith(rules.N, i):
                out += b'\xff\x02' if narr else b'\x0a'; i += 2; continue
            m = (rules.NTOKEN if narr else rules.TOKEN).match(s, i)
            if m:
                out += bytes.fromhex(m.group()[1:-1]); i = m.end(); continue
            m = HEXB.match(s, i)
            if m:
                out.append(int(m.group(1), 16)); i = m.end(); continue
            ch = s[i]
            out += M.kcode(self.idx[ch]) if rules.is_kr(ch) else ch.encode('cp932')
            i += 1
        return bytes(out)


# ── 나레이션 블록 ──────────────────────────────────────────
def narr_pages(d, i):
    """블록 시작 i → ([화면 글(TSV 꼴)], [구분 바이트(FExx/FC)], 끝 위치(FC 다음))"""
    pages, seps, cur = [], [], []; j = i
    while True:
        b = d[j]
        if b in extract.LEAD and 0x40 <= d[j + 1] <= 0xFC:
            cur.append(d[j:j + 2].decode('cp932')); j += 2
        elif b == 0xFF and d[j + 1] == 0x02:
            cur.append(rules.N); j += 2
        elif b in (0xFF, 0xFD):
            cur.append('{%02X%02X}' % (b, d[j + 1])); j += 2
        elif b == 0xFE:
            pages.append(''.join(cur)); seps.append(d[j:j + 2]); cur = []; j += 2
        elif b == 0xFC:
            if cur:
                pages.append(''.join(cur)); seps.append(b'')
            seps[-1] += b'\xfc'
            return pages, seps, j + 1
        else:
            raise ValueError('나레이션 블록 해석 실패 %X' % j)


def narr_blocks(d):
    """파일 바이트 → [(시작, 끝)] (extract.narration 과 같은 판정)"""
    out = []; i = 0
    while i < len(d) - 1:
        if d[i] in extract.LEAD and (i == 0 or d[i - 1] in (0, 0xFC)):
            r = extract.narr_block(d, i)
            if r:
                out.append((i, r[1] + 1)); i = r[1]; continue
        i += 1
    return out


# ── 16×12 글꼴 ─────────────────────────────────────────────
def glyph12(F, ch):
    pts, _ = F.draw(ch, 0, 0)
    xs = [x for x, _ in pts]; ys = [y for _, y in pts]
    ox = (12 - (max(xs) - min(xs) + 1)) // 2 - min(xs); oy = (12 - (max(ys) - min(ys) + 1)) // 2 - min(ys)
    rows = [0] * 12
    for x, y in pts:
        X, Y = x + ox, y + oy
        if 0 <= X < 16 and 0 <= Y < 12:
            rows[Y] |= 1 << (15 - X)
    return b''.join(r.to_bytes(2, 'big') for r in rows)


# ── 빌드 ──────────────────────────────────────────────────
def build(dirs, use_fake=False, write=False, install=False):
    rows = load(dirs)
    if use_fake:
        fake(rows)
    tr = {k: v for k, v in rows.items() if v['kr']}
    print('번역 줄 %d / 전체 %d' % (len(tr), len(rows)))
    # 실행 파일 메뉴 글꼴에 있는 반각 = 원문 실행 파일 문자열에 쓰인 글자
    allowed = set()
    for r in rows.values():
        if r['id'][0] in 'XL':
            allowed |= {c for c in r['src'] if not rules.is_kr(c)}
    allowed |= {'　', ' '}
    # ① 규칙 검사
    bad = []; warn = collections.Counter(); wex = {}
    for r in tr.values():
        kind = {'6': '대사', '7': '대사', 'X': '실행', 'N': '나레이션', 'L': '실행'}[r['id'][0]]
        cap = int(r['kind'][2:]) if r['kind'][:2] in ('실행', '라벨') else None
        b, w = rules.validate(kind, r['src'], r['kr'], cap, allowed if kind == '실행' else None)
        r['k'] = rules.squeeze(r['kr'])
        if b:
            bad.append((r['id'], b))
        for x in w:
            warn[x.split()[0]] += 1; wex.setdefault(x.split()[0], (r['id'], x))
    if warn:
        print('경고', dict(warn), wex)
    if bad:
        print('★막힘 %d줄' % len(bad))
        for i, b in bad[:30]:
            print('  ', i, b)
        sys.exit(1)
    # ② 음절(많이 쓰는 순)
    cnt = collections.Counter(c for r in tr.values() for c in r['k'] if rules.is_kr(c))
    import board                                     # 이름·키워드 입력판(work/text/wiz_입력판.tsv)
    brows = board.load() if os.path.exists(board.OUT) else []
    for _, _, ko in brows:
        if ko:
            cnt[ko] += 0                              # 판 음절도 글꼴에(이름 음절은 번역에 없을 수 있음)
    syl = [c for c, _ in cnt.most_common()]
    assert M.KR_N0 + len(syl) <= SLOT_MAX, ('음절이 너무 많음', len(syl))
    E = Enc(syl)
    print('음절 %d (한자 칸 %d‥%d)' % (len(syl), M.KR_N0, M.KR_N0 + len(syl) - 1))
    files = {}
    # ③ 대사
    for w in '67':
        dn, hn, mn = huff.NAMES[w]
        dbs0, hdr0 = (open(os.path.join(DISC, n), 'rb').read() for n in (dn, hn))
        n, res = huff.entries(w)
        m = {r['src']: r['k'] for r in tr.values() if r['id'][0] == w}
        done = 0; res2 = []
        for idx, pieces in res:
            new = []
            for p in pieces:
                t = extract.esc(p.decode('cp932', 'backslashreplace'))
                if t in m:
                    new.append(E.text(m[t])); done += 1
                else:
                    new.append(p)
            res2.append((idx, new))
        fq = collections.Counter(b for _, p in res2 for s in p for b in s)
        tree = huff.build_tree(fq)
        dbs, hdr = huff.pack(res2, tree, n)
        assert len(hdr) <= len(hdr0)
        assert len(dbs) <= 256 * 1024, ('DBS 가 블록 번호(u8×1024) 한도 넘음', dn, len(dbs))   # HDR 블록 = u8
        if len(dbs) > len(dbs0):
            print('  ⚠%s 커짐 %d > %d B (파일 옮김 — 실기 확인)' % (dn, len(dbs), len(dbs0)))
        files[dn] = dbs + bytes(max(0, len(dbs0) - len(dbs)))
        files[hn] = hdr + bytes(len(hdr0) - len(hdr))
        files[mn] = tree
        # 되읽기
        for (i0, a), (i1, b) in zip(res2, _decode(dbs, hdr, tree)):
            assert i0 == i1 and a == b, ('대사 되읽기 불일치', w, i0)
        print('대사 Wiz%s: 조각 %d 교체 · DBS %d/%d B' % (w, done, len(dbs), len(dbs0)))
    # ④ 실행 파일
    xm = {r['src']: r['k'] for r in tr.values() if r['id'][0] == 'X'}
    for name in M.GAMES:
        g = bytearray(open(os.path.join(DISC, name), 'rb').read()); k = 0
        for off, src, size in _exe_strings(bytes(g)):
            t = extract.esc(src)
            if t in xm:
                b = E.text(xm[t])
                assert len(b) <= size, (name, hex(off), t, len(b), size)
                g[off:off + size] = b + bytes(size - len(b)); k += 1
        # 반각 라벨(제자리) · 직업 이름(구역 안 다시 배치 + 포인터)
        lm = {r['src']: r['k'] for r in tr.values() if r['id'][0] == 'L' and r['kind'].startswith('라벨')}
        jm = {r['src']: r['k'] for r in tr.values() if r['id'][0] == 'L' and r['kind'] == '직업'}
        G = M.GAMES[name]; LD = G['load']; kan = extract.corpus_kanji(); i = 0; kl = 0
        a0, a1 = G['jobs'][0] - LD, G['jobs'][1] - LD
        while lm and i < len(g) - 1:
            if (i % 4 == 0 or g[i - 1] == 0) and not a0 <= i < a1 and g[i]:
                r = extract.half_str(bytes(g), i, kan)
                if r:
                    if r[0] in lm:
                        b = E.text(lm[r[0]]); size = r[1] - i
                        assert len(b) <= size, (name, hex(i), r[0], len(b), size)
                        g[i:i + size] = b + bytes(size - len(b)); kl += 1
                    i = r[1] + 1; continue
            i += 1
        if jm:
            olds = []; p = a0
            while p < a1:
                if g[p] == 0:
                    p += 1; continue
                e = g.index(0, p); olds.append((p, g[p:e].decode('cp932'))); p = e
            blob_j = bytearray(); new_at = {}
            for p, t in olds:
                new_at[p] = len(blob_j); blob_j += (E.text(jm[t]) if t in jm else t.encode('cp932')) + bytes(1)
            assert len(blob_j) <= a1 - a0, ('직업 이름 구역 넘침', name, len(blob_j), a1 - a0)
            refs = {}
            for q in range(0, len(g) - 3, 4):
                v = struct.unpack_from('>I', g, q)[0] - LD
                if v in new_at:
                    refs.setdefault(v, []).append(q)
            assert all(p in refs for p, _ in olds), ('직업 포인터 못 찾음', name, [hex(p + LD) for p, _ in olds if p not in refs])
            g[a0:a1] = blob_j + bytes(a1 - a0 - len(blob_j))
            for p, qs in refs.items():
                for q in qs:
                    struct.pack_into('>I', g, q, LD + a0 + new_at[p])
            for p, t in olds:                       # 되읽기: 옛 포인터 자리 → 새 문자열
                want = E.text(jm[t]) if t in jm else t.encode('cp932')
                for q in refs[p]:
                    v = struct.unpack_from('>I', g, q)[0] - LD
                    assert bytes(g[v:g.index(0, v)]) == want, ('직업 되읽기', name, t)
        if brows:
            g = bytearray(board.patch(bytes(g), name, lambda ch: M.kcode(E.idx[ch])))
        files[name] = g
        print('실행 %-12s 문자열 %d곳 · 라벨 %d · 직업 %d · 입력판 %d칸' % (name, k, kl, len(jm), sum(1 for b in brows if b[2])))
    # ⑤ 나레이션
    nm = {r['src']: r['k'] for r in tr.values() if r['id'][0] == 'N'}
    D = __import__('disc').Disc(); fs = {e[0]: e for e in D.walk()}
    for f in extract.NARR:
        d = bytearray(D.read(fs[f][1], fs[f][2])); k = 0
        for s, e in narr_blocks(bytes(d)):
            pages, seps, end = narr_pages(bytes(d), s)
            assert end == e
            body = b''.join((E.text(nm[p], narr=True) if p in nm else E.text(p, narr=True)) + sp for p, sp in zip(pages, seps))
            k += sum(p in nm for p in pages)
            assert len(body) <= e - s, ('나레이션 블록 넘침', f, hex(s), len(body), e - s)
            d[s:e] = body + bytes(e - s - len(body))
        files[f] = bytes(d)
        print('나레이션 %-12s 화면 %d' % (f, k))
    # ⑥ 글꼴·메뉴 훅
    F = bdf.Font(FONT12)
    fon = bytearray(open(os.path.join(DISC, 'KANJI12.FON'), 'rb').read())
    for i, ch in enumerate(syl):
        s = M.KR_N0 + i
        fon[s * 24:(s + 1) * 24] = glyph12(F, ch)
    blob, offs = M.blob(syl)
    files['KANJI12.FON'] = M.patch_kanji(bytes(fon), blob)
    for name in M.GAMES:
        files[name] = M.patch_exe(bytes(files[name]), name, offs)
    print('KANJI12: 한글 %d칸 + 블롭 %d B' % (len(syl), len(blob)))
    if not write:
        print('(검사만 — --write 로 디스크 만들기)'); return
    import disc, iso
    out = os.path.join(ROOT, 'work', 'out', os.path.basename(disc.ROM))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    iso.patch(disc.ROM, out, files)
    print('트랙 1', out, hashlib.md5(open(out, 'rb').read()).hexdigest())
    if install:
        shutil.copyfile(out, os.path.join(F_DIR, os.path.basename(out)))
        print('F: 설치', F_DIR)


def _decode(dbs, hdr, tree):
    n = struct.unpack_from('<H', hdr, 0)[0]; out = []
    for k in range(n):
        idx, addr, sub, blk = struct.unpack_from('<HHBB', hdr, 2 + 6 * k)
        if idx == 0:
            continue
        p = blk * 1024 + addr; ps = []
        for s in range(sub + 1):
            t, p = huff.decode_piece(tree, dbs, p); ps.append(t)
        out.append((idx, ps))
    return out


def _exe_strings(d):
    kan = extract.corpus_kanji(); i = 0; out = []
    while i < len(d) - 1:
        if i % 4 == 0 or d[i - 1] == 0:
            r = extract.exe_str(d, i, kan)
            if r:
                out.append((i, r[0], r[1] - i)); i = r[1] + 1; continue
        i += 1
    return out


if __name__ == '__main__':
    a = [x for x in sys.argv[1:] if not x.startswith('--')]
    build(a or [os.path.join(ROOT, 'work', 'text')], '--fake' in sys.argv,
          '--write' in sys.argv or '--install' in sys.argv, '--install' in sys.argv)
