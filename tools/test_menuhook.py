# -*- coding: utf-8 -*-
r"""menuhook 블롭 검산 — 블롭에 쓰인 명령만 아는 작은 SH-2 해석기로 CLS·DRAW 를 돌린다.
  python tools/test_menuhook.py
"""
import os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import menuhook as M

M32 = 0xFFFFFFFF


class CPU:
    def __init__(self, mem):
        self.m = mem; self.r = [0] * 16; self.t = 0; self.pr = 0; self.macl = 0

    def rb(self, a): return self.m.get(a, 0)
    def rw(self, a): return self.rb(a) << 8 | self.rb(a + 1)
    def rl(self, a): return self.rw(a) << 16 | self.rw(a + 2)
    def wb(self, a, v): self.m[a] = v & 0xFF
    def ww(self, a, v): self.wb(a, v >> 8); self.wb(a + 1, v)
    def wl(self, a, v): self.ww(a, v >> 16); self.ww(a + 2, v)

    def step(self, op, pc):
        self._cur = pc
        r = self.r; n = (op >> 8) & 15; m = (op >> 4) & 15
        s8 = lambda x: x - 256 if x & 0x80 else x
        hi = op >> 12; lo4 = op & 15
        if op == 0x0009: return None
        if op == 0x000B: return ('d', self.pr)
        if hi == 0x6:
            if lo4 == 3: r[n] = r[m]
            elif lo4 == 0xC: r[n] = r[m] & 0xFF
            elif lo4 == 0xD: r[n] = r[m] & 0xFFFF
            elif lo4 == 0: v = self.rb(r[m]); r[n] = (v - 256 if v & 0x80 else v) & M32
            elif lo4 == 1: v = self.rw(r[m]); r[n] = (v - 0x10000 if v & 0x8000 else v) & M32
            elif lo4 == 2: r[n] = self.rl(r[m])
            elif lo4 == 4: v = self.rb(r[m]); r[n] = (v - 256 if v & 0x80 else v) & M32; r[m] = (r[m] + 1) & M32 if m != n else r[n]
            elif lo4 == 6: v = self.rl(r[m]); r[m] = (r[m] + 4) & M32; r[n] = v
            else: raise ValueError(hex(op))
            return None
        if hi == 0xE: r[n] = s8(op & 0xFF) & M32; return None
        if hi == 0x7: r[n] = (r[n] + s8(op & 0xFF)) & M32; return None
        if hi == 0x3:
            if lo4 == 0xC: r[n] = (r[n] + r[m]) & M32
            elif lo4 == 8: r[n] = (r[n] - r[m]) & M32
            elif lo4 == 0: self.t = int(r[n] == r[m])
            elif lo4 == 2: self.t = int(r[n] >= r[m])
            elif lo4 == 6: self.t = int(r[n] > r[m])
            else: raise ValueError(hex(op))
            return None
        if hi == 0x4:
            k = op & 0xFF
            if k == 0x19: r[n] >>= 8
            elif k == 0x00: r[n] = (r[n] << 1) & M32
            elif k == 0x08: r[n] = (r[n] << 2) & M32
            elif k == 0x01: r[n] >>= 1
            elif k == 0x09: r[n] >>= 2
            elif k == 0x10: r[n] = (r[n] - 1) & M32; self.t = int(r[n] == 0)
            elif k == 0x2B: return ('d', r[n])
            else: raise ValueError(hex(op))
            return None
        if hi == 0x2:
            if lo4 == 0xE: self.macl = (r[n] & 0xFFFF) * (r[m] & 0xFFFF)
            elif lo4 == 2: self.wl(r[n], r[m])
            elif lo4 == 1: self.ww(r[n], r[m])
            elif lo4 == 0: self.wb(r[n], r[m])
            elif lo4 == 6: r[n] = (r[n] - 4) & M32; self.wl(r[n], r[m])
            else: raise ValueError(hex(op))
            return None
        if hi == 0x0:
            if lo4 == 0xA and m == 1: r[n] = self.macl; return None
            a = (r[0] + r[m]) & M32
            if lo4 == 0xC: v = self.rb(a); r[n] = (v - 256 if v & 0x80 else v) & M32
            elif lo4 == 0xD: v = self.rw(a); r[n] = (v - 0x10000 if v & 0x8000 else v) & M32
            elif lo4 == 0xE: r[n] = self.rl(a)
            elif lo4 == 4: self.wb((r[0] + r[n]) & M32, r[m])
            elif lo4 == 5: self.ww((r[0] + r[n]) & M32, r[m])
            elif lo4 == 6: self.wl((r[0] + r[n]) & M32, r[m])
            else: raise ValueError(hex(op))
            return None
        if hi == 0xD: r[n] = self.rl(((pc + 4) & ~3) + (op & 0xFF) * 4); return None
        if (op >> 8) == 0xC7: r[0] = ((pc + 4) & ~3) + (op & 0xFF) * 4; return None
        if (op >> 8) == 0xC9: r[0] &= op & 0xFF; return None
        if (op >> 8) == 0x8D: return ('d', pc + 4 + s8(op & 0xFF) * 2) if self.t else None
        if (op >> 8) == 0x8F: return ('d', pc + 4 + s8(op & 0xFF) * 2) if not self.t else None
        if hi == 0x9: v = self.rw(pc + 4 + (op & 0xFF) * 2); r[n] = (v - 0x10000 if v & 0x8000 else v) & M32; return None
        if (op >> 8) == 0x89: return ('b', pc + 4 + s8(op & 0xFF) * 2) if self.t else None
        if (op >> 8) == 0x8B: return ('b', pc + 4 + s8(op & 0xFF) * 2) if not self.t else None
        if hi == 0xA:
            d = op & 0xFFF; d = d - 0x1000 if d & 0x800 else d
            return ('d', pc + 4 + d * 2)
        raise ValueError(hex(op))


def run(cpu, pc, ret=0xDEAD0000):
    """지연 분기를 제대로: 분기 명령 → 다음 명령(슬롯) 하나 실행 → 대상"""
    cpu.pr = ret
    for _ in range(300000):
        if pc == ret:
            return
        res = cpu.step(cpu.rw(pc), pc)
        if res is None:
            pc += 2
        elif res[0] == 'b':
            pc = res[1]
        else:
            tgt = res[1]
            r2 = cpu.step(cpu.rw(pc + 2), pc + 2)
            assert r2 is None, '지연 슬롯에 분기'
            pc = tgt
    raise RuntimeError('무한')


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    syl = list('캐릭터만들기힘지혜')
    b, o = M.blob(syl)
    base = 0x2D2430 + M.BLOB_OFF
    mem = {base + i: v for i, v in enumerate(b)}
    cpu = CPU(mem)
    ok = True
    # ── CLS: 원래 분류와 비교(가나·기호·영숫자·반각) + 한글
    import importlib.util
    for exe_name in M.GAMES:
      exe = open(os.path.join(os.path.dirname(HERE), 'work', 'disc', exe_name), 'rb').read()
      for k, v in enumerate(exe):
        mem[0x06010000 + k] = v
      cpu.r[15] = 0x06100000
      print('──', exe_name)
      for code in [0x829F, 0x82F1, 0x8340, 0x8396, 0x8397, 0x815B, 0x8140, 0x824F, 0x8279, 0x8260, 0x2100, 0x5D41, 0xA600, 0xDD00,
                 0x889F, 0x8B9F, 0x9800, 0x9FFC, 0xE040, 0x0000, 0x8400]:
        cpu.r[4] = code; run(cpu, M.GAMES[exe_name]['cls']); orig = cpu.r[0]
        cpu.r[4] = code; run(cpu, base + o['CLS']); new = cpu.r[0]
        want = 3 if 0x8B <= code >> 8 <= 0x9F else orig
        flag = 'OK' if new == want else '★틀림'
        if new != want: ok = False
        print('분류 %04X 원래 %d → 새 %d %s' % (code, orig, new, flag))
      # 패치한 실행 파일: 분류 입구 → 블롭 CLS 로 가는지, 그리기 입구 → 트램펄린 → DRAW → 원래 셋째 명령으로 돌아오는지
      G = M.GAMES[exe_name]
      gp = M.patch_exe(exe, exe_name, o)
      for k, v in enumerate(gp):
        mem[0x06010000 + k] = v
      G2 = dict(G); blob_ram = G['kanji'] + M.BLOB_OFF
      for k, v in enumerate(b):
        mem[blob_ram + k] = v
      cpu.r[4] = 0x8BA0; cpu.r[15] = 0x06100000; run(cpu, G['cls'])
      ok &= cpu.r[0] == 3; print('패치 분류 입구 8BA0 →', cpu.r[0])
      # 그리기 입구: 지연 슬롯·트램펄린을 거쳐 DRAW 시작에 닿는지(DRAW 첫 명령에서 멈춤)
      cpu.r[15] = 0x06100000; cpu.r[8] = 0x88; cpu.r[9] = 0x99
      run(cpu, G['draw'], ret=blob_ram + o['DRAW'])
      good = cpu.r[9] == G['draw'] + 4 and cpu.r[8] == G['basev'] and cpu.r[1] == G['vram'] and cpu.rl(0x06100000 - 4) == 0x88 and cpu.rl(0x06100000 - 8) == 0x99 and cpu.r[15] == 0x06100000 - 8
      ok &= good; print('패치 그리기 입구 → DRAW (R9 %X R8 %X R1 %X, 저장 R8·R9)' % (cpu.r[9], cpu.r[8], cpu.r[1]), 'OK' if good else '★')
    # ── DRAW
    VR = 0x25C10000; BASEV = 0x06078B96
    mem[BASEV] = 0; mem[BASEV + 1] = 0

    def draw(r6):
        cpu.r[6] = r6; cpu.r[8] = BASEV; cpu.r[9] = 0xDEAD0000; cpu.r[1] = VR
        for k in (4, 5, 7, 10, 11, 12, 13, 14):
            cpu.r[k] = 0x1000 + k
        cpu.r[15] = 0x06100000
        run(cpu, base + o['DRAW'])
        for k in (4, 5, 7, 10, 11, 12, 13, 14):
            assert cpu.r[k] == 0x1000 + k, ('레지스터 망가짐', k)
        assert cpu.r[15] == 0x06100000
        return cpu.r[6]

    def vglyph(frame):
        a = VR + 80 * frame
        rows = []
        for y in range(10):
            row = ''.join('#' if cpu.rb(a + y * 8 + x // 2) >> (4 * (1 - x % 2)) & 15 else '.' for x in range(16))
            rows.append(row)
        return rows

    # 가나·기호 값은 그대로
    for v in (0, 82, 96, 170, 0xFFA3, 0x01DC, 0x0898):
        r = draw(v)
        print('통과 %04X → %04X %s' % (v, r, 'OK' if r == v else '★틀림')); ok &= r == v
    frames = {}
    for i, ch in enumerate(syl):
        code = int.from_bytes(M.kcode(i), 'big')
        r = draw((code + 0x7D61) & 0xFFFF)
        frames[ch] = r
        g = M.glyph8(ch)
        want = ['.' * 16] * 2 + [''.join('#' if g[y] & (0x80 >> x) else '.' for x in range(8)) + '.' * 8 for y in range(8)]
        good = vglyph(r) == want
        ok &= good
        print('%s 부호 %04X → 프레임 %d %s' % (ch, code, r, 'OK' if good else '★글리프 틀림'))
    # 다시 그리면 같은 칸
    for ch in '캐힘':
        i = syl.index(ch); code = int.from_bytes(M.kcode(i), 'big')
        r = draw((code + 0x7D61) & 0xFFFF)
        print('재사용 %s → %d %s' % (ch, r, 'OK' if r == frames[ch] else '★다른 칸')); ok &= r == frames[ch]
    # 칸 83 은 안 씀 · LRU 순환: 음절 300개를 돌려 프레임 범위·83 회피 확인
    syl2 = [chr(0xAC00 + k) for k in range(300)]
    b2, o2 = M.blob(syl2)
    mem2 = {base + i: v for i, v in enumerate(b2)}; cpu.m = mem2; mem2[BASEV] = 0; mem2[BASEV + 1] = 0
    seen = []
    for i in range(300):
        code = int.from_bytes(M.kcode(i), 'big'); seen.append(draw((code + 0x7D61) & 0xFFFF))
    bad = [f for f in seen if f > 170 or f == 83]
    print('LRU 300음절: 프레임 %d‥%d · 고유 %d · 83/범위 밖 %d %s' % (min(seen), max(seen), len(set(seen)), len(bad), 'OK' if not bad and len(set(seen)) == 170 else '★'))
    ok &= not bad and len(set(seen)) == 170
    # 첫 170개는 서로 다른 칸, 171번째는 가장 오래된(첫) 칸
    print('171번째 = 첫 칸 재사용', 'OK' if seen[170] == seen[0] else '★')
    ok &= seen[170] == seen[0]
    print('\n전체', '통과' if ok else '★실패')
    return ok


if __name__ == '__main__':
    sys.exit(0 if main() else 1)
