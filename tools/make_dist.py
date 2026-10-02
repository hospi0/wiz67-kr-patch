# -*- coding: utf-8 -*-
r"""위저드리 VI & VII 컴플리트 배포 묶음 — dist/Wizardry67_KR_<VER>/ : 트랙 01 xdelta + xdelta.exe + readme.txt(CP949) + 한글패치_적용.bat
  (카오스 시드 tools/make_dist.py 를 옮김) 검증: 원본 트랙 01 → xdelta 적용 → md5 = 빌드 결과(work/out) md5.
  python tools/make_dist.py   (먼저 python tools/build.py --write)
"""
import hashlib, os, shutil, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import disc

VER = 'prealpha'                    # 사용자 2026-10-03 «pre alpha»
XDELTA = r'C:\claude\utils\xdelta.exe'
NAME = 'Wizardry67_KR_' + VER
TITLE = '위저드리 VI & VII 컴플리트 (세가 새턴 일본판) 한글 패치 pre-alpha'
ROMNAME = 'Wizardry VI & VII Complete (Japan) (3M)'
TRACKS = 12
OUT = os.path.join(ROOT, 'work', 'out', os.path.basename(disc.ROM))


def md5(p):
    h = hashlib.md5()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 22), b''):
            h.update(b)
    return h.hexdigest().upper()


HEAD = """{tracks}개의 트랙으로 이루어진 {rom} 의
트랙 01번에 패치하시면 됩니다.

원본md5 : {o}
패치md5 : {d}

입니다.
"""

BODY = """

[ 적용 방법 ]

  1) 원본 트랙 01 파일을 이 폴더에 복사
       "{bin}"
  2) 한글패치_적용.bat 실행 → 이름 끝에 [KR] 이 붙은 파일이 만들어집니다
  3) 만든 파일 이름을 원본 트랙 01 이름으로 바꿔 넣고, 나머지 트랙과 cue 는 그대로 쓰세요
     (트랙 01 크기는 바뀌지 않습니다)

  직접 적용:
    xdelta.exe -d -s "원본 트랙 01" "{patch}" "결과 파일"
  (Delta Patcher 같은 xdelta3 GUI 도구로 적용해도 됩니다. 원본이 다르면 xdelta 가 적용을 거부합니다.)


[ 바뀌는 것 ]

  - VI·VII 대사 전부, 전투·상태 메시지, 아이템·몬스터·주문 이름
  - 메뉴(8x8 한글), 초상 라벨(직업·이름)
  - 오프닝·엔딩 나레이션, VI 오프닝 동영상 자막
  - 이름·키워드 입력판(한글 / 영문 / 끝, 한글 쪽 82음절)


[ 알려진 점 ]

  - pre-alpha 입니다. 끝까지 실기로 통독하지 못했습니다. 이상한 곳이 있으면 알려 주세요.
  - 이름 입력판의 한글은 키워드에 쓰는 82음절뿐입니다(탁점 칸 = 이 칸 다음 글자, 반탁점 칸 = 그다음 글자). 나머지는 영문으로 지어 주세요.
  - 이름 뒤 조사(은/는·을/를 등)는 아직 받침에 맞춰 바뀌지 않습니다.
"""

BAT = r"""@echo off
chcp 949 >nul
set "XD=%~dp0xdelta.exe"
if not exist "%~dp0{bin}" (
  echo   [오류] 원본 트랙 01 파일을 이 폴더에 넣어 주세요(readme 참고).
  pause & exit /b 1
)
"%XD%" -d -f -s "%~dp0{bin}" "%~dp0{patch}" "%~dp0{kbin}"
if errorlevel 1 (
  echo   [오류] 패치 실패 - 원본이 다를 수 있습니다(readme 의 원본md5 확인).
  pause & exit /b 1
)
echo   완료: "{kbin}"
pause
"""


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    d = os.path.join(ROOT, 'dist', NAME)
    os.makedirs(d, exist_ok=True)
    b = ROMNAME + ' (Track 01).bin'
    src = disc.ROM
    assert os.path.basename(src) == b and os.path.basename(OUT) == b, (src, OUT)
    patch = NAME + '.xdelta'; pp = os.path.join(d, patch)
    subprocess.run([XDELTA, '-e', '-9', '-f', '-B', str(1 << 29), '-s', src, OUT, pp], check=True)
    chk = os.path.join(d, '_check.bin')
    subprocess.run([XDELTA, '-d', '-f', '-B', str(1 << 29), '-s', src, pp, chk], check=True)
    o, want, got = md5(src), md5(OUT), md5(chk)
    os.remove(chk)
    assert got == want, ('패치 적용 결과가 빌드와 다름', got, want)
    kbin = ROMNAME + ' (Track 01) [KR].bin'
    shutil.copy2(XDELTA, os.path.join(d, 'xdelta.exe'))
    readme = (TITLE + '\n' + '=' * 60 + '\n\n' + HEAD.format(tracks=TRACKS, rom=ROMNAME, o=o, d=want)
              + BODY.format(bin=b, patch=patch))
    open(os.path.join(d, 'readme.txt'), 'wb').write(readme.replace('\n', '\r\n').encode('cp949'))
    open(os.path.join(d, '한글패치_적용.bat'), 'wb').write(
        BAT.format(bin=b, patch=patch, kbin=kbin).replace('\n', '\r\n').encode('cp949'))
    print('원본md5 %s → 패치md5 %s · %s %d B' % (o, want, patch, os.path.getsize(pp)))
    print('✅', d)
    for f in sorted(os.listdir(d)):
        print('  %-50s %12d' % (f, os.path.getsize(os.path.join(d, f))))


if __name__ == '__main__':
    main()
