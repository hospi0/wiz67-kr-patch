# -*- coding: utf-8 -*-
r"""BCF_OP.CPK(VI 오프닝, Sega FILM + 세가식 Cinepak) 구운 자막 한글화 (2026-10-03)
  FILM: 'FILM' 머리길이 '1.08' · FDSC · STAB(기준 30, 항목 16 B = 위치·길이·info1·info2, info1=0xFFFFFFFF 는 소리)
  영상 356프레임 15fps, 전부 키 프레임, 띠 2개(112줄). ★세가식 Cinepak: 10 B 머리 뒤 2 B(0000) 더, 머리 길이 = 실제 − 8.
  자막 구간은 프레임이 통째로 같다(61‥120 / 121‥180 / 268‥327) → 새 그림 3장을 한 번씩 부호화해 그 구간 전부에 넣는다.
  그림: 자막 없는 프레임(60·267)의 위쪽으로 원래 글자를 덮고 갈무리11(대사창 글꼴) 흰색 12px, 줄마다 가운데.
  python tools/cpk.py          → work/movie/bcf/kr_*.png 미리보기 + work/kr/BCF_OP.CPK
"""
import os, struct, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.append(r'C:\claude\project\anearth-kr-patch\tools')
import bdf
from PIL import Image

FF = r'C:\claude\utils\ffmpeg-9.0.1-essentials_build\bin\ffmpeg.exe'
SRC = os.path.join(ROOT, 'work', 'movie', 'cpk', 'BCF_OP.CPK')
DST = os.path.join(ROOT, 'work', 'kr', 'BCF_OP.CPK')
WORK = os.path.join(ROOT, 'work', 'movie', 'bcf')
FONT = r'C:\claude\utils\font\Galmuri-v2.40.3\Galmuri11.bdf'
LINE_H = 12.5                      # 원래 줄 간격(4줄 9‥59)
TOP = 9
# (첫 프레임, 끝 프레임, 바탕 프레임, 줄들) — 프레임 번호 1부터(ffmpeg 출력 f%04d)
SUBS = [(61, 120, 60, ['만약 사태가 감당할 수 없을 만큼', '비참해질 것 같으면,', '언제든 되돌아와서', '여기서 밖으로 도망칠 수 있다.']),
        (121, 180, 60, ['성문 앞에 선 그대들은', '그렇게 확신하고 있었다.']),
        (268, 327, 267, ['하지만 아무래도', '그렇게는 되지 않을', '모양이다…'])]
COVER = (0, 0, 320, 66)            # 원래 글자 구역(가장 큰 4줄 자막 y 9‥59 + 여유)


def parse(d):
    hl = struct.unpack_from('>I', d, 4)[0]
    i = 16; stab = None
    while i < hl:
        tag = d[i:i + 4]; ln = struct.unpack_from('>I', d, i + 4)[0]
        if tag == b'STAB':
            stab = i
        i += ln
    base, n = struct.unpack_from('>II', d, stab + 8)
    ents = [list(struct.unpack_from('>IIII', d, stab + 16 + 16 * k)) for k in range(n)]
    return hl, stab, ents


def render(sub):
    a, b, bgf, lines = sub
    im = Image.open(os.path.join(WORK, 'f%04d.png' % a)).convert('RGB')
    bg = Image.open(os.path.join(WORK, 'f%04d.png' % bgf)).convert('RGB')
    im.paste(bg.crop(COVER), COVER[:2])
    F = bdf.Font(FONT)
    for k, t in enumerate(lines):
        pts, w = F.draw(t)
        x0 = (320 - w) // 2; y0 = int(TOP + k * LINE_H)
        for x, y in pts:
            if 0 <= x0 + x < 320:
                im.putpixel((x0 + x, y0 + y), (255, 255, 255))
    out = os.path.join(WORK, 'kr_%04d.png' % a)
    im.save(out)
    return out


def encode(png, q=2):
    """ffmpeg Cinepak(키 프레임·띠 2개, 화질 q — 클수록 작고 거침) → 세가식 바이트"""
    tmp = png[:-4] + '.avi'
    subprocess.run([FF, '-hide_banner', '-loglevel', 'error', '-y', '-i', png, '-c:v', 'cinepak', '-max_strips', '2',
                    '-min_strips', '2', '-g', '1', '-q:v', str(q), tmp], check=True)
    d = open(tmp, 'rb').read()
    i = d.find(b'00dc', d.find(b'movi'))
    n = struct.unpack_from('<I', d, i + 4)[0]
    f = d[i + 8:i + 8 + n]
    assert struct.unpack('>H', f[8:10])[0] == 2 and f[4:8] == bytes.fromhex('014000e0'), f[:12].hex()
    s = bytearray(f[:10] + b'\0\0' + f[10:])
    s += bytes(-len(s) % 4)          # ★샘플 크기·위치는 4의 배수(원본 전부) — 홀수면 뒤 샘플이 어긋나 SH-2 주소 오류(2026-10-03 실기 크래시)
    struct.pack_into('>I', s, 0, (len(s) - 8) | (f[0] << 24))      # 머리 길이 = 실제 − 8(세가식)
    return bytes(s)


def build():
    d = open(SRC, 'rb').read()
    hl, stab, ents = parse(d)
    vid = [k for k, e in enumerate(ents) if e[2] != 0xFFFFFFFF]
    maxv = max(ents[k][1] for k in vid)
    new = {}
    for sub in SUBS:
        png = render(sub); target = ents[vid[sub[0] - 1]][1]       # ★원래 그 구간 프레임 크기 이하(CD 읽기·버퍼)
        for q in range(2, 80):
            fr = encode(png, q)
            if len(fr) <= target:
                break
        assert len(fr) <= min(target, maxv) and len(fr) % 4 == 0, (len(fr), target)
        for f in range(sub[0], sub[1] + 1):
            new[vid[f - 1]] = fr
        print('자막 %d‥%d: %d B (원래 %d B, q=%d)' % (sub[0], sub[1], len(fr), target, q))
    body = bytearray(); out_e = []
    for k, e in enumerate(ents):
        data = new.get(k, d[hl + e[0]:hl + e[0] + e[1]])
        out_e.append([len(body), len(data), e[2], e[3]]); body += data
    head = bytearray(d[:hl])
    for k, e in enumerate(out_e):
        struct.pack_into('>IIII', head, stab + 16 + 16 * k, *e)
    os.makedirs(os.path.dirname(DST), exist_ok=True)
    open(DST, 'wb').write(bytes(head) + bytes(body))
    print(DST, len(d), '→', len(head) + len(body))


if __name__ == '__main__':
    build()
