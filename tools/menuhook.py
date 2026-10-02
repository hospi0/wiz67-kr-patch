# -*- coding: utf-8 -*-
r"""Wizardry VI·VII 메뉴 8×8 한글 — 동적 칸 캐시 훅 (2026-10-02, 사용자 A안: 8×8 · 간격 9 그대로)

  메뉴 글자 = FONT_1(VDP1, 16×10 4bpp 칸, VRAM 0x25C10000 + 80×프레임) · 프레임 = SJIS + 묶음별 K(히라가나 0x7D61).
  한글 부호(실행 파일·대사 공통): 음절 i → JIS 구점 n = 21×94 + i(22구 1점부터) → SJIS 리드 0x8B‥0x98.
      ★22구부터인 까닭: 그리기 R6 = 부호 + 0x7D61 ≥ 0x0900 → 스프라이트 정의 번호(≤ 0x898)와 안 겹침.
  ① 분류 0x0603392C 를 블롭의 CLS 로 옮김(원래 뜻 그대로 + 리드 0x8B‥0x9F = 종류 3 히라가나 묶음).
     옛 분류 자리(0x8C B)에 = 점프 + 트램펄린.
  ② 그리기 0x06033B1C 첫 두 명령 → «BRA 트램펄린 / MOV.L R8,@-R15». 트램펄린: R9 저장 → R9 = 돌아갈 곳, R8 = 기준 변수 주소,
     R1 = FONT_1 VRAM → 블롭 DRAW. DRAW: R6 이 한글이면 칸 캐시(음절→칸 u8, 칸→음절 u16, 칸 시각 u32, LRU) →
     8×8 글리프를 그 칸 VRAM 에 «매번» 다시 씀(FONT_1 재적재·표 초기화에도 글자가 틀리지 않게) → R6 = 프레임 − 기준.
  풀 = 가나 프레임 0‥170 중 83(ー) 뺀 170칸. 글리프 = 칸 안 x 0‥7 · 줄 2‥9(가나와 같은 자리), 색 15.
  블롭 = KANJI12.FON 안 70구(칸 6,486‥, 파일 +0x26010) — 파일 전체가 Low RAM 상주(VII 0x2D2430 · VI 0x280000),
      위치 독립 코드(MOVA), 쓰기 가능한 표도 같이.
"""
import os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, r'C:\claude\project\aww-kr-patch\tools')
import sh2asm

KR_N0 = 21 * 94                     # 음절 0 = 22구 1점
BLOB_OFF = 69 * 94 * 24             # KANJI12 안 블롭 자리(70구 1점) = 0x26010
NPOOL = 170
assert NPOOL < 256
POOL_SKIP = 83                      # ー
FONT8 = r'C:\claude\utils\font\Galmuri-v2.40.3\Galmuri7.bdf'

GAMES = {   # 실행 파일 → 주소
    'WIZARDRY.BIN': dict(load=0x06010000, kanji=0x2D2430, cls=0x0603392C, cls_end=0x060339B8,
                         draw=0x06033B1C, basev=0x06078B96, vram=0x25C10000,
                         conv=0x06020608, conv_end=0x06020694, conv_tab=0x06059EC0, conv_buf=0x06085F98,
                         jobs=(0x06010D90, 0x06010DF8)),
    'WIZ6.BIN':     dict(load=0x06010000, kanji=0x280000, cls=0x06015480, cls_end=0x06015510,
                         draw=0x06015678, basev=0x06078836, vram=0x25C10000,
                         conv=0x0603A9A4, conv_end=0x0603AA30, conv_tab=0x060861CC, conv_buf=0x060A1714,
                         jobs=(0x060182FC, 0x06018364)),
    'SL.BIN':       dict(load=0x06010000, kanji=0x280000, cls=0x06015548, cls_end=0x060155D8,
                         draw=0x06015740, basev=0x0607A456, vram=0x25C10000,
                         conv=0x0603B654, conv_end=0x0603B6E0, conv_tab=0x06087514, conv_buf=0x060A2BC4,
                         jobs=(0x060183C4, 0x0601842C)),
}   # conv = 이름 전각→반각(초상 라벨) 함수(코드는 셋이 같음 — 바이트 패턴), conv_tab = (전각 ptr, 반각 ptr)×124(마지막 = ﾌﾒｲ 기본값)
    # jobs = 반각 직업 이름 14개 구역(ﾆﾝｼﾞｬ‥ﾌｧｲﾀｰ, 끝 다음 = 남의 코드) — 빌더가 구역 안에서 다시 배치하고 포인터를 고침
    # VI: KANJI12 0x280000 = 오프닝 스테이트에서 확인(메뉴 중 상주는 ⏳실기), FONT_1 → 0x25C10000(0x06015384 적재, 리터럴 확인)


def kcode(i):
    """음절 번호 → SJIS 2바이트"""
    n = KR_N0 + i
    p, tt = divmod(n, 188)
    lead = 0x81 + p if p < 31 else 0xE0 + p - 31
    t = 0x40 + tt
    if t >= 0x7F:
        t += 1
    return bytes([lead, t])


def bdf_glyph(ch):
    for b in open(FONT8, encoding='utf-8').read().split('STARTCHAR'):
        if '\nENCODING %d\n' % ord(ch) in b:
            ln = b.split('\n'); i = ln.index('BITMAP'); rows = ln[i + 1:ln.index('ENDCHAR')]
            w, h, x0, y0 = map(int, [l for l in ln if l.startswith('BBX')][0].split()[1:])
            return [[(int(r, 16) >> (len(r) * 4 - 1 - x)) & 1 for x in range(w)] for r in rows], x0, 7 - h - y0
    raise KeyError(ch)


def glyph8(ch):
    """갈무리7 → 8줄 1bpp(줄 0 = 프레임 줄 2), 바닥을 8줄째(프레임 줄 9 = 가나 바닥)에 맞춤"""
    rows, x0, top = bdf_glyph(ch)
    g = bytearray(8)
    for y, r in enumerate(rows):
        for x, v in enumerate(r):
            if v and 0 <= top + y < 8 and x0 + x < 8:
                g[top + y] |= 0x80 >> (x0 + x)
    while not g[7] and any(g):                  # ★실기 2026-10-02: 가나보다 1줄 위 → 바닥 맞춤
        g = bytearray(1) + g[:7]
    return bytes(g)


class A(sh2asm.Asm):
    """sh2asm + MOVA(라벨 또는 조립 뒤 정하는 주소) · mov.l @(d,Rm) · mov.w @Rm · @(R0,Rn) 저장 · align4"""
    def mova(self, lab):            self.items.append(('mova', lab))
    def movl_disp(self, d, m, n):   self.w(0x5000 | sh2asm.R[n] << 8 | sh2asm.R[m] << 4 | d // 4)
    def movw_load(self, m, n):      self.w(0x6001 | sh2asm.R[n] << 8 | sh2asm.R[m] << 4)
    def movw_r0store(self, m, n):   self.w(0x0005 | sh2asm.R[n] << 8 | sh2asm.R[m] << 4)   # mov.w Rm,@(R0,Rn)
    def movb_r0store(self, m, n):   self.w(0x0004 | sh2asm.R[n] << 8 | sh2asm.R[m] << 4)   # mov.b Rm,@(R0,Rn)
    def movl_r0store(self, m, n):   self.w(0x0006 | sh2asm.R[n] << 8 | sh2asm.R[m] << 4)   # mov.l Rm,@(R0,Rn)
    def movl_store(self, m, n):     self.w(0x2002 | sh2asm.R[n] << 8 | sh2asm.R[m] << 4)
    def align4(self):               self.items.append(('align4',))


def assemble_pic(a, late=None):
    """mova·align4 처리 조립. late = {라벨: 조립 뒤 주소를 정하는 함수(코드+풀 길이 → 주소)}"""
    src = a.items
    movas = []; items = []; addr = a.base
    for it in src:
        if it[0] == 'mova':
            movas.append((len(items), it[1])); items.append(('w', 0)); addr += 2
        elif it[0] == 'align4':
            if addr % 4:
                items.append(('w', 0x0009)); addr += 2
        else:
            items.append(it)
            if it[0] != 'label':
                addr += 2
    a.items = items
    out, code_len = sh2asm.Asm.assemble(a)
    a.items = src
    out = bytearray(out)
    for lab, f in (late or {}).items():
        a.labels[lab] = f(len(out))
    pos = a.base; addr_of = {}
    for k, it in enumerate(items):
        if it[0] == 'label':
            continue
        addr_of[k] = pos; pos += 2
    for k, lab in movas:
        p = addr_of[k]; tgt = a.labels[lab]
        d = (tgt - ((p + 4) & ~3)) // 4
        assert tgt % 4 == 0 and 0 <= d < 256, ('mova', lab, hex(tgt), d)
        struct.pack_into('>H', out, p - a.base, 0xC700 | d)
    return bytes(out), code_len


def blob(syllables):
    """syllables = 음절 문자열 목록(번호 순) → 블롭 바이트(위치 독립), 오프셋 사전"""
    ns = len(syllables)
    a = A(0)
    # ── CLS: 분류(R4 = 부호 → R0 종류). 원래처럼 R3 = 리드, R4 = R7 = 뒤 바이트
    a.label('CLS')
    a.mov('r4', 'r3'); a.shlr8('r3'); a.extub('r3', 'r3')
    a.extub('r4', 'r4'); a.mov('r4', 'r7')
    a.mov('r3', 'r1'); a.addi(-0x21, 'r1'); a.extuw('r1', 'r1'); a.movi(0x3C, 'r2'); a.cmphi('r2', 'r1')
    a.bf('t1')
    a.mov('r3', 'r1'); a.addi(-0x80, 'r1'); a.addi(-0x26, 'r1'); a.extuw('r1', 'r1'); a.movi(0x37, 'r2'); a.cmphi('r2', 'r1')
    a.bf('t0')
    a.movi(0x81, 'r2'); a.extub('r2', 'r2'); a.cmpeq('r2', 'r3')
    a.bt('t2')
    a.addi(1, 'r2'); a.cmpeq('r2', 'r3')                                  # 0x82
    a.bf('c83')
    a.mov('r4', 'r1'); a.addi(-0x4F, 'r1'); a.extuw('r1', 'r1'); a.movi(0x2A, 'r2'); a.cmphi('r2', 'r1')
    a.bf('t5')
    a.mov('r4', 'r1'); a.addi(-0x80, 'r1'); a.addi(-0x1F, 'r1'); a.extuw('r1', 'r1'); a.movi(0x52, 'r2'); a.cmphi('r2', 'r1')
    a.bf('t3')
    a.bra('t6'); a.nop()
    a.label('c83')
    a.addi(1, 'r2'); a.cmpeq('r2', 'r3')                                  # 0x83
    a.bf('ckr')
    a.mov('r4', 'r1'); a.addi(-0x40, 'r1'); a.extuw('r1', 'r1'); a.movi(0x56, 'r2'); a.cmphi('r2', 'r1')
    a.bf('t4')
    a.bra('t6'); a.nop()
    a.label('ckr')                                                         # 리드 0x8B‥0x9F = 한글
    a.mov('r3', 'r1'); a.addi(-0x80, 'r1'); a.addi(-0x0B, 'r1'); a.extuw('r1', 'r1'); a.movi(0x14, 'r2'); a.cmphi('r2', 'r1')
    a.bf('t3')
    a.label('t6'); a.rts(); a.movi(6, 'r0')
    a.label('t0'); a.rts(); a.movi(0, 'r0')
    a.label('t1'); a.rts(); a.movi(1, 'r0')
    a.label('t2'); a.rts(); a.movi(2, 'r0')
    a.label('t3'); a.rts(); a.movi(3, 'r0')
    a.label('t4'); a.rts(); a.movi(4, 'r0')
    a.label('t5'); a.rts(); a.movi(5, 'r0')

    # ── HCONV: 이름 전각 → 반각(초상 라벨). R4 = 원문, R5 = 버퍼, R6 = 표 → R0 = 버퍼 시작(원래처럼). R8 은 저장·복원
    #   한글(리드 0x8B‥0x9F) = 2바이트 그대로 복사(메뉴 훅이 그림) / 그 밖 = 원래처럼 표 123쌍에서 앞 2바이트가 같은 것, 없으면 124번째(ﾌﾒｲ)
    a.align4()
    a.label('HCONV')
    a.movl_predec('r5', 'r15'); a.movl_predec('r8', 'r15')
    a.label('hc_loop')
    a.movb_load('r4', 'r0'); a.extub('r0', 'r0'); a.tst('r0', 'r0')
    a.bt('hc_end')
    a.movb_postinc('r4', 'r0'); a.extub('r0', 'r0'); a.movb_postinc('r4', 'r1'); a.extub('r1', 'r1')
    a.mov('r0', 'r2'); a.addi(-0x80, 'r2'); a.addi(-0x0B, 'r2'); a.extub('r2', 'r2')
    a.movi(0x15, 'r3'); a.cmphs('r3', 'r2')
    a.bt('hc_find')
    a.movb_store('r0', 'r5'); a.addi(1, 'r5'); a.movb_store('r1', 'r5'); a.addi(1, 'r5')
    a.bra('hc_loop'); a.nop()
    a.label('hc_find')
    a.mov('r6', 'r2'); a.movi(123, 'r3')
    a.label('hc_k')
    a.movl_load('r2', 'r7')
    a.movb_postinc('r7', 'r8'); a.extub('r8', 'r8'); a.cmpeq('r0', 'r8')
    a.bf('hc_next')
    a.movb_load('r7', 'r8'); a.extub('r8', 'r8'); a.cmpeq('r1', 'r8')
    a.bt('hc_hit')
    a.label('hc_next')
    a.addi(8, 'r2'); a.dt('r3')
    a.bf('hc_k')
    a.label('hc_hit')                                                      # r2 = 찾은 쌍(못 찾으면 124번째)
    a.movl_disp(4, 'r2', 'r7')
    a.label('hc_cp')
    a.movb_postinc('r7', 'r8'); a.tst('r8', 'r8')
    a.bt('hc_loop')
    a.movb_store('r8', 'r5'); a.addi(1, 'r5')
    a.bra('hc_cp'); a.nop()
    a.label('hc_end')
    a.movi(0, 'r0'); a.movb_store('r0', 'r5')
    a.movl_postinc('r15', 'r8'); a.movl_postinc('r15', 'r0')
    a.rts(); a.nop()

    # ── DRAW: R6 = 부호+0x7D61, R8 = 기준 변수 주소, R9 = 돌아갈 곳, R1 = FONT_1 VRAM. R4·R5·R7·R10‥R14 보존
    a.align4()
    a.label('pass0')                                                       # 한글 아님 → 그대로 돌아감(bt 가 닿는 곳)
    a.jmp('r9'); a.nop()
    a.label('DRAW')
    a.mov('r6', 'r0'); a.movl_pc('K829F', 'r2'); a.add('r2', 'r0'); a.extuw('r0', 'r0')   # r0 = 부호
    a.mov('r0', 'r2'); a.shlr8('r2')                                       # r2 = 리드
    a.addi(-0x80, 'r2'); a.addi(-0x0B, 'r2')                               # 리드 − 0x8B
    a.movi(0x15, 'r3'); a.cmphs('r3', 'r2')
    a.bt('pass0')                                                           # 0x8B‥0x9F 밖
    a.extub('r0', 'r0'); a.addi(-0x40, 'r0')                               # tt
    a.movi(0x40, 'r3'); a.cmphs('r3', 'r0')
    a.bf('nohole')
    a.addi(-1, 'r0')
    a.label('nohole')
    a.movl_pc('K188', 'r3'); a.muluw('r3', 'r2'); a.sts_macl('r2'); a.add('r0', 'r2')
    a.addi(-94, 'r2')                                                      # r2 = 음절 번호
    a.movl_pc('NSYL', 'r3'); a.cmphs('r3', 'r2')
    a.bt('pass0')
    a.movl_predec('r10', 'r15'); a.movl_predec('r11', 'r15'); a.movl_predec('r12', 'r15')
    a.mov('r1', 'r12')                                                     # r12 = VRAM 바탕
    a.mov('r2', 'r10')                                                     # r10 = 음절
    a.mova('DATA'); a.mov('r0', 'r11')                                     # r11 = 자료 바탕
    # 칸 찾기: map[i]
    a.movl_pc('O_MAP', 'r0'); a.add('r10', 'r0'); a.movb_r0m('r11', 'r1'); a.extub('r1', 'r1')
    a.movi(NPOOL, 'r3'); a.extub('r3', 'r3'); a.cmphs('r3', 'r1')                  # ★170 은 부호 확장되므로 extu.b
    a.bt('miss')
    a.mov('r1', 'r0'); a.shll('r0'); a.movl_pc('O_OWN', 'r3'); a.add('r3', 'r0'); a.movw_r0m('r11', 'r2'); a.extuw('r2', 'r2')
    a.cmpeq('r10', 'r2')
    a.bt('stamp')
    a.label('miss')                                                        # LRU: 시각 최소 칸
    a.movl_pc('O_STM', 'r0'); a.movl_r0m('r11', 'r2'); a.movi(0, 'r1'); a.movi(1, 'r3')
    a.label('lru')
    a.mov('r3', 'r0'); a.shll2('r0'); a.movl_pc('O_STM', 'r6'); a.add('r6', 'r0'); a.movl_r0m('r11', 'r6')
    a.cmphs('r2', 'r6')                                                    # 시각 ≥ 최소면 넘김
    a.bt('lnext')
    a.mov('r6', 'r2'); a.mov('r3', 'r1')
    a.label('lnext')
    a.addi(1, 'r3'); a.movi(NPOOL, 'r6'); a.extub('r6', 'r6'); a.cmphs('r6', 'r3')
    a.bf('lru')
    a.mov('r1', 'r0'); a.shll('r0'); a.movl_pc('O_OWN', 'r3'); a.add('r3', 'r0'); a.movw_r0store('r10', 'r11')   # own[s] = i
    a.movl_pc('O_MAP', 'r0'); a.add('r10', 'r0'); a.movb_r0store('r1', 'r11')                                   # map[i] = s
    a.label('stamp')                                                       # r1 = 칸
    a.movl_pc('O_CLK', 'r0'); a.movl_r0m('r11', 'r2'); a.addi(1, 'r2'); a.movl_r0store('r2', 'r11')
    a.mov('r1', 'r0'); a.shll2('r0'); a.movl_pc('O_STM', 'r3'); a.add('r3', 'r0'); a.movl_r0store('r2', 'r11')
    # 프레임 = 칸 (+1, 83 이상)
    a.movi(POOL_SKIP, 'r3'); a.cmphs('r3', 'r1')
    a.bf('fr')
    a.addi(1, 'r1')
    a.label('fr')                                                          # r1 = 프레임
    a.mov('r1', 'r2'); a.shll2('r2'); a.shll2('r2'); a.mov('r2', 'r3'); a.shll2('r3'); a.add('r3', 'r2')   # ×16 + ×64 = ×80
    a.add('r12', 'r2')                                                     # r2 = VRAM 칸
    a.mov('r10', 'r0'); a.shll2('r0'); a.shll('r0'); a.movl_pc('O_FONT', 'r3'); a.add('r3', 'r0'); a.add('r11', 'r0')
    a.mov('r0', 'r6')                                                      # r6 = 글리프 8 B
    a.movl_pc('O_LUT', 'r12'); a.add('r11', 'r12')                         # r12 = LUT
    a.movi(0, 'r3')
    for _ in range(4):                                                     # 줄 0‥1 비움
        a.movl_store('r3', 'r2'); a.addi(4, 'r2')
    a.movi(8, 'r10')
    a.label('row')
    a.movb_postinc('r6', 'r0'); a.extub('r0', 'r0'); a.mov('r0', 'r11')
    a.shlr2('r0'); a.shlr2('r0'); a.shll('r0'); a.movw_r0m('r12', 'r3'); a.movw_store('r3', 'r2'); a.addi(2, 'r2')
    a.mov('r11', 'r0'); a.andi(15); a.shll('r0'); a.movw_r0m('r12', 'r3'); a.movw_store('r3', 'r2'); a.addi(2, 'r2')
    a.movi(0, 'r3'); a.movl_store('r3', 'r2'); a.addi(4, 'r2')
    a.dt('r10')
    a.bf('row')
    a.movw_load('r8', 'r6'); a.extuw('r6', 'r6'); a.sub('r6', 'r1'); a.extuw('r1', 'r6')   # R6 = 프레임 − 기준
    a.movl_postinc('r15', 'r12'); a.movl_postinc('r15', 'r11'); a.movl_postinc('r15', 'r10')
    a.jmp('r9'); a.nop()
    # 자료 배치(DATA = 코드·리터럴 풀 뒤 4 B 정렬)
    o_lut = 0; o_clk = 32; o_stm = 36; o_own = o_stm + 4 * NPOOL; o_map = o_own + 2 * NPOOL
    o_font = o_map + ns; o_font += -o_font % 4
    for k, v in (('K829F', 0x829F), ('K188', 188), ('NSYL', ns), ('O_MAP', o_map), ('O_OWN', o_own),
                 ('O_STM', o_stm), ('O_CLK', o_clk), ('O_FONT', o_font), ('O_LUT', o_lut)):
        a.defl(k, v)
    code, _ = assemble_pic(a, {'DATA': lambda n: n + (-n % 4)})
    data_at = a.labels['DATA']
    out = bytearray(code) + bytes(data_at - len(code))
    lut = b''.join(struct.pack('>H', sum(0xF << (12 - 4 * k) for k in range(4) if n & (8 >> k))) for n in range(16))
    data = bytearray(o_font + 8 * ns)
    data[0:32] = lut
    data[o_own:o_own + 2 * NPOOL] = b'\xff' * (2 * NPOOL)
    data[o_map:o_map + ns] = b'\xff' * ns
    for i, ch in enumerate(syllables):
        data[o_font + 8 * i:o_font + 8 * i + 8] = glyph8(ch)
    return bytes(out) + bytes(data), {'CLS': a.labels['CLS'], 'DRAW': a.labels['DRAW'], 'HCONV': a.labels['HCONV'], 'DATA': data_at}


def patch_exe(exe, name, offs):
    """실행 파일 → 분류 점프 + 트램펄린 + 그리기 입구"""
    G = GAMES[name]; g = bytearray(exe); L = G['load']
    blob_ram = G['kanji'] + BLOB_OFF
    get = lambda a: struct.unpack_from('>H', g, a - L)[0]
    assert get(G['draw']) == 0x2F86 and get(G['draw'] + 2) == 0x2F96 and get(G['draw'] + 4) == 0x2FA6
    assert get(G['cls']) == 0x2FE6
    a = A(G['cls'])
    a.movl_pc('CLS', 'r0'); a.jmp('r0'); a.nop()
    a.label('TRAMP')                                  # BRA 로 옴(지연 슬롯에서 R8 저장됨)
    a.movl_predec('r9', 'r15')
    a.movl_pc('DRAW', 'r0'); a.movl_pc('RET', 'r9'); a.movl_pc('BASEV', 'r8'); a.movl_pc('VRAM', 'r1')
    a.jmp('r0'); a.nop()
    a.defl('CLS', blob_ram + offs['CLS']); a.defl('DRAW', blob_ram + offs['DRAW'])
    a.defl('RET', G['draw'] + 4); a.defl('BASEV', G['basev']); a.defl('VRAM', G['vram'])
    code, _ = a.assemble()
    assert G['cls'] + len(code) <= G['cls_end'], len(code)
    g[G['cls'] - L:G['cls'] - L + len(code)] = code
    tramp = a.labels['TRAMP']
    d = (tramp - (G['draw'] + 4)) // 2
    assert -2048 <= d < 0
    struct.pack_into('>HH', g, G['draw'] - L, 0xA000 | (d & 0xFFF), 0x2F86)
    # 이름 변환 입구 → 블롭 HCONV(R5 = 버퍼, R6 = 표)
    assert get(G['conv']) == 0x2F86 and get(G['conv'] + 0x12) == 0x6C43
    c = A(G['conv'])
    c.movl_pc('BUF', 'r5'); c.movl_pc('TAB', 'r6'); c.movl_pc('HC', 'r0'); c.jmp('r0'); c.nop()
    c.defl('BUF', G['conv_buf']); c.defl('TAB', G['conv_tab']); c.defl('HC', blob_ram + offs['HCONV'])
    code, _ = c.assemble()
    assert G['conv'] + len(code) <= G['conv_end'], len(code)
    g[G['conv'] - L:G['conv'] - L + len(code)] = code
    return bytes(g)


def patch_kanji(fon, blob_bytes):
    f = bytearray(fon)
    assert BLOB_OFF + len(blob_bytes) <= len(f), len(blob_bytes)
    f[BLOB_OFF:BLOB_OFF + len(blob_bytes)] = blob_bytes
    return bytes(f)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    b, o = blob(list('한글시험'))
    print('블롭 %d B · 코드 %d B' % (len(b), o['DATA']), {k: hex(v) for k, v in o.items()})
