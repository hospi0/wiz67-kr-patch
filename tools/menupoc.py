# -*- coding: utf-8 -*-
r"""메뉴 8×8 한글 PoC (2026-10-02) — VII·VI(WIZ6·SL) 캐릭터 화면·만들기 메뉴 문자열 몇 개를 한글로, 동적 칸 훅(tools/menuhook.py)으로 그린다.
  원본 디스크 기준(대사는 일본어 그대로) · 바꾸는 파일 = WIZARDRY.BIN·WIZ6.BIN·SL.BIN(문자열 제자리 + 분류 점프·트램펄린·그리기 입구) · KANJI12.FON(70구~ 블롭)
  ⚠KANJI12 70구 이후 한자(2수준 일부)는 블롭으로 덮여 대사에서 깨져 보일 수 있음(시험 한정).
  python tools/menupoc.py            → 바꿀 내용만 출력(디스크 안 씀)
  python tools/menupoc.py --write    → work/out/ 에 트랙 1
  python tools/menupoc.py --install  → + F: 설치
"""
import os, shutil, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import extract, menuhook as M

sys.stdout.reconfigure(encoding='utf-8')
TR = {'ちから': '힘', 'ちえ': '지혜', 'しんこう': '신앙', 'たいりょく': '체력', 'きようさ': '손재주', 'はやさ': '속도',
      'みりょく': '매력', 'カルマ': '카르마', 'アイテム': '아이템', 'じゅもん': '주문', 'スキル': '스킬', 'おとこ': '남자',
      'おんな': '여자', 'ファイター': '파이터', 'リザードマン': '리저드맨', 'キャラクターをつくる': '캐릭터　만들기',
      'パーティーをつくる': '파티　만들기', 'スレイウッド': '슬레이우드'}
F_DIR = r'F:\hospi\roms\ss roms\Wizardry VI  VII Complete (Japan) (3M)'


def find_strings(d):
    kan = extract.corpus_kanji(); i = 0; out = []
    while i < len(d) - 1:
        if i % 4 == 0 or d[i - 1] == 0:
            r = extract.exe_str(d, i, kan)
            if r:
                out.append((i, r[0], r[1] - i)); i = r[1] + 1; continue
        i += 1
    return out


def encode(s, syl):
    out = bytearray()
    for ch in s:
        if '가' <= ch <= '힣':
            if ch not in syl:
                syl.append(ch)
            out += M.kcode(syl.index(ch))
        else:
            out += ch.encode('cp932')
    return bytes(out)


def build(write=False, install=False):
    syl = []; files = {}
    for name in M.GAMES:                                   # VII WIZARDRY · VI WIZ6 · SL
        exe = bytearray(open(os.path.join(ROOT, 'work', 'disc', name), 'rb').read()); n = 0
        for off, src, size in find_strings(exe):
            if src in TR:
                b = encode(TR[src], syl)
                assert len(b) <= size, (src, TR[src], len(b), size)      # 제자리 예산 = 원문 바이트
                exe[off:off + size] = b + bytes(size - len(b))
                n += 1
        files[name] = exe
        print('%-12s 문자열 %d곳' % (name, n))
    blob, offs = M.blob(syl)
    for name in M.GAMES:
        files[name] = M.patch_exe(bytes(files[name]), name, offs)
    files['KANJI12.FON'] = M.patch_kanji(open(os.path.join(ROOT, 'work', 'disc', 'KANJI12.FON'), 'rb').read(), blob)
    print('음절 %d · 블롭 %d B(KANJI12 +0x%X)' % (len(syl), len(blob), M.BLOB_OFF))
    if not write:
        print('(시험 실행 — --write 로 디스크 만들기)'); return
    import disc, iso
    out = os.path.join(ROOT, 'work', 'out', os.path.basename(disc.ROM))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    iso.patch(disc.ROM, out, files)
    import hashlib
    print('트랙 1', out, hashlib.md5(open(out, 'rb').read()).hexdigest())
    if install:
        shutil.copyfile(out, os.path.join(F_DIR, os.path.basename(out)))
        print('F: 설치', F_DIR)


if __name__ == '__main__':
    build('--write' in sys.argv or '--install' in sys.argv, '--install' in sys.argv)
