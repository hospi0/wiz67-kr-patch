# -*- coding: utf-8 -*-
r"""번역 «쓰는 순간»에 거는 규칙 — 번역을 채우는 스크립트가 줄마다 validate() 를 통과시키고, 빌더도 같은 걸 다시 건다.

  막는 것(확실한 것만): 실개행 · 탭 · 제어 토큰 {XX} 개수/순서 · `@` 개수 · 인코딩 불가 글자 ·
      실행 파일 «원문 바이트» 초과 · 나레이션 화면의 FF/FD 토큰 · 메뉴(실행 파일) 반각 소문자 등 글꼴 밖 글자
  경고(휴리스틱): 대사 «공백 없는 덩어리» 52칸 초과(원문 벼랑 50‥52칸, 엔진은 공백에서 접는 것으로 보임) · `/` 개수
  공백: 문장부호 뒤 1칸은 빌더가 지운다(squeeze) — 칸·바이트 계산도 지운 뒤로.
"""
import re

N = chr(92) + 'n'
PUNCT = set(',.!?:;)]}\'"~、。，．！？：；）］｝」』】〉》”’…‥・·～〜♪♥')
TOKEN = re.compile(r'\{[0-9A-F]{2}\}')
NTOKEN = re.compile(r'\{(?:FF|FD)[0-9A-F]{2}\}')
CHUNK_WARN = 52

BANNER = """
── 위저드리 번역 규칙 (validate 가 강제한다) ───────────────────
 1 줄바꿈은 N = chr(92)+'n' 로만       ⛔실제 개행·탭 금지
 2 {01}·{1F} 같은 제어 토큰과 @ 는 원문 그대로 같은 순서·같은 개수
 3 대사는 낱말 사이 띄어쓰기를 자연스럽게 — 빌더가 13칸으로 접는다(엔진은 반각 공백 = 줄바꿈)
 4 실행 파일(X-)은 «실행N» 바이트 안 (한글 1자 = 2B, 반각 1B)
 5 실행 파일 반각은 원문에 쓰인 글자만(소문자 a‥z 금지 — 메뉴 글꼴에 없음)
 6 부호 뒤 공백은 자연스럽게 — 빌더가 뗀다
────────────────────────────────────────────────────────────"""


LINE = 13                                       # 대사 출력(VI 0x06016C08 · VII 0x060365C8) 한 줄 칸 수
FW = {',': '，', '.': '．', '(': '（', ')': '）', '-': '－', '?': '？', '!': '！', ':': '：',
      **{chr(48 + i): chr(0xFF10 + i) for i in range(10)}}
VARS = set('^$#%&]')                            # 실행 중 이름 등으로 바뀌는 자리 — 폭 모름, 4칸으로 어림
VAR_CELLS = 4
UI_TOK = re.compile(r'\{1[0-7]\}')              # 버튼·대기 토큰 = 대화창 밖 UI 문구


def is_dialog(src):
    """대화창(13칸, 0x20 = 줄바꿈)으로 찍히는 조각인가 — 키워드 목록(/ @)·칸 맞춤 UI(앞뒤·겹 공백, 버튼 토큰)·반각 가나는 아님"""
    if '/' in src or '@' in src or UI_TOK.search(src) or re.search('[｡-ﾟ]', src):
        return False
    return src == src.strip(' ') and '  ' not in src


def layout(src, k):
    r"""★대사 출력은 반각 공백 0x20 = «줄바꿈»(13칸 넘으면 자동 줄바꿈, 반각 0x01‥0x7E 는 건너뜀 — 그려지지 않음).
    → 번역을 13칸으로 직접 접는다: 줄 바꿀 자리 = ' ' · 같은 줄 띄어쓰기 = 전각 공백 '　' · 딱 13칸 줄 뒤엔 ' ' 안 넣음(빈 줄).
    원문에 없는 반각 부호·숫자는 전각으로(안 그러면 사라진다). 부호 뒤도 줄 바꿀 수 있는 자리(띄어쓰기 없이)."""
    if not is_dialog(src):
        return k
    k = ''.join(FW[c] if c in FW and c not in src else c for c in k)
    if src[:1] == '　' or src[-1:] == '　':
        # 표지판: 원문 = 전각 공백으로 13칸을 채운 가운데 맞춤 한 줄(2026-10-03 «근무 시간 / 중» — 채움 공백이 낱말에 붙어 넘침)
        t = k.strip('　 ').replace(' ', '　')
        n = sum(1 for c in t if is_kr(c) or ord(c) > 0x7F)
        if n <= LINE:
            a = (LINE - n) // 2
            return '　' * a + t + '　' * (LINE - n - a)
        k = t.replace('　', ' ')
    words = []; cur = ''; i = 0                     # (낱말, 앞 띄어쓰기 여부)
    gap = False
    while i < len(k):
        m = TOKEN.match(k, i)
        if m:
            cur += m.group(); i = m.end(); continue
        if k.startswith(N, i):
            cur += N; i += 2; continue
        c = k[i]; i += 1
        if c == ' ':
            if cur:
                words.append((cur, gap)); cur = ''
            gap = True; continue
        cur += c
        if c in PUNCT and i < len(k) and k[i] != ' ':
            words.append((cur, gap)); cur = ''; gap = False
    if cur:
        words.append((cur, gap))

    def w(s):
        t = TOKEN.sub('', s.replace(N, ''))
        return sum(VAR_CELLS if c in VARS else (1 if (is_kr(c) or ord(c) > 0x7F) else 0) for c in t)
    out = ''; col = 0
    for s, g in words:
        n = w(s)
        if col == 0:
            out += s
        elif col + (1 if g else 0) + n <= LINE:
            out += ('　' if g else '') + s; col += 1 if g else 0
        else:
            out += ' ' + s; col = 0
        col = (col + n) % LINE                      # 13칸 딱 = 엔진이 이미 줄을 바꿈 → 0
    return out


NARR_W, NARR_H = 23, 4                          # 나레이션 한 줄 23칸(원문 최장) · 한 화면 4줄(원문 최대)


def narr_layout(k):
    r"""★나레이션(오프닝·엔딩)은 2바이트 글자 + 반각 공백만 — 다른 반각(, . ! 등)은 2바이트로 읽혀 뒤의 줄바꿈 FF02 를 먹고
    줄이 겹쳐 찍히며 멈춘다(2026-10-03 VII 오프닝 실기 «글자 겹침»·«음악만 나옴»). 공백은 첫 줄에서 정상(1칸).
    → 부호 전각 · 줄 나눔(
)은 무시하고 23칸으로 다시 접기(공백 1칸).
    ★부호 뒤 공백은 지운다(
 이 공백이 되면 «왔다．  “나는»처럼 두 칸으로 벌어짐 — 전각 부호는 칸 왼쪽에 점만) — 부호 뒤도 줄 바꿀 자리.
    반환 = (글, 줄 수, 최장 칸)."""
    k = ''.join(FW.get(c, c) for c in k).replace(N, ' ')
    words = []; cur = ''; gap = False                # (낱말, 앞 공백 여부)
    for i, c in enumerate(k):
        if c == ' ':
            if cur:
                words.append((cur, gap)); cur = ''; gap = True
            continue
        cur += c
        if c in PUNCT and i + 1 < len(k) and k[i + 1] != ' ' and c not in '“「『（':
            words.append((cur, gap)); cur = ''; gap = False
        elif c in PUNCT and c not in '“「『（':
            pass
    if cur:
        words.append((cur, gap))
    # 부호로 끝난 낱말 뒤 공백은 없앤다
    words = [(w, g and not (j and words[j - 1][0][-1] in PUNCT and words[j - 1][0][-1] not in '“「『（')) for j, (w, g) in enumerate(words)]
    lines = ['']
    for wd, g in words:
        if not lines[-1]:
            lines[-1] = wd
        elif len(lines[-1]) + (1 if g else 0) + len(wd) <= NARR_W:
            lines[-1] += (' ' if g else '') + wd
        else:
            lines.append(wd)
    return N.join(lines), len(lines), max(len(l) for l in lines)


def squeeze(s):
    """문장부호 뒤 «한 칸» 공백 삭제(두 칸 이상은 칸 맞춤이라 둠)"""
    out = []; i = 0
    while i < len(s):
        out.append(s[i])
        if s[i] in PUNCT and i + 1 < len(s) and s[i + 1] == ' ' and (i + 2 >= len(s) or s[i + 2] != ' '):
            i += 2; continue
        i += 1
    return ''.join(out)


def is_kr(ch):
    return '가' <= ch <= '힣'


def cells(s):
    return sum(2 if is_kr(c) or len(c.encode('cp932', 'replace')) == 2 else 1 for c in s)


def encodable(s):
    """한글이 아닌 글자 중 cp932 로 못 바꾸는 것"""
    bad = []
    for c in TOKEN.sub('', NTOKEN.sub('', s.replace(N, ''))):
        if is_kr(c):
            continue
        try:
            c.encode('cp932')
        except UnicodeEncodeError:
            bad.append(c)
    return bad


def nbytes(s):
    t = NTOKEN.sub('xx', TOKEN.sub('x', s.replace(N, 'x')))
    return sum(2 if is_kr(c) else len(c.encode('cp932', 'replace')) for c in t)


def validate(kind, jp, kr, cap=None, allowed=None):
    """kind = '대사' | '실행' | '나레이션' → (막을 문제들, 경고들). kr 은 squeeze 전 그대로 넣어도 됨"""
    bad, warn = [], []
    if '\n' in kr or '\r' in kr or '\t' in kr:
        bad.append('REAL_NEWLINE/TAB')
    k = squeeze(kr)
    e = encodable(k)
    if e:
        bad.append('ENCODE %s' % ''.join(sorted(set(e))))
    tok = NTOKEN if kind == '나레이션' else TOKEN
    if tok.findall(jp) != tok.findall(k):
        bad.append('TOKENS %s → %s' % (tok.findall(jp), tok.findall(k)))
    if jp.count('@') != k.count('@'):
        bad.append('AT %d→%d' % (jp.count('@'), k.count('@')))
    if jp.count('/') != k.count('/'):
        warn.append('SLASH %d→%d' % (jp.count('/'), k.count('/')))
    if kind == '실행':
        n = nbytes(k)
        if cap is not None and n > cap:
            bad.append('BYTES %d>%d' % (n, cap))
        if allowed is not None:
            odd = sorted({c for c in k if not is_kr(c) and c not in allowed})
            if odd:
                bad.append('MENU_GLYPH %s' % ''.join(odd))
    if kind == '나레이션' and not NTOKEN.search(k):
        _, nl, w = narr_layout(k)
        if nl > NARR_H or w > NARR_W:
            bad.append('NARR %d줄·최장 %d칸 > %d줄·%d칸' % (nl, w, NARR_H, NARR_W))
    if kind == '대사':
        for line in k.split(N):
            for seg in TOKEN.sub('', line).split(' '):
                if cells(seg) > CHUNK_WARN:
                    warn.append('CHUNK %d칸 «%s…»' % (cells(seg), seg[:8])); break
    return bad, warn
