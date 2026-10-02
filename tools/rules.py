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
 3 대사는 엔진이 공백에서 접는다 — 낱말 사이 띄어쓰기를 꼭 넣을 것
 4 실행 파일(X-)은 «실행N» 바이트 안 (한글 1자 = 2B, 반각 1B)
 5 실행 파일 반각은 원문에 쓰인 글자만(소문자 a‥z 금지 — 메뉴 글꼴에 없음)
 6 부호 뒤 공백은 자연스럽게 — 빌더가 뗀다
────────────────────────────────────────────────────────────"""


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
    if kind == '대사':
        for line in k.split(N):
            for seg in TOKEN.sub('', line).split(' '):
                if cells(seg) > CHUNK_WARN:
                    warn.append('CHUNK %d칸 «%s…»' % (cells(seg), seg[:8])); break
    return bad, warn
