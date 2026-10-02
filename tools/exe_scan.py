# -*- coding: utf-8 -*-
r"""실행 파일 SJIS 문자열 후보 — NUL 앞에서 끝나는 SJIS(전각만, 반각 영숫자 섞임 허용) 덩어리, 앞 바이트가 NUL·정렬 경계
  분류: menu = 가나·전각 영숫자·기호만(FONT_1 로 그릴 수 있음) / kanji = 한자 섞임(KANJI12 쪽 추정)
  python tools/exe_scan.py WIZ6.BIN …  → work/text/exe_<파일>.tsv
"""
import os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.stdout.reconfigure(encoding='utf-8')
LEAD = set(range(0x81, 0xA0)) | set(range(0xE0, 0xF0))


def scan(d):
    out = []; i = 0; n = len(d)
    while i < n:
        j = i; s = bytearray(); ok = True; jp = 0
        while j < n and d[j] != 0:
            b = d[j]
            if b in LEAD and j + 1 < n and (0x40 <= d[j + 1] <= 0xFC and d[j + 1] != 0x7F):
                s += d[j:j + 2]; j += 2; jp += 1
            elif 0x20 <= b < 0x7F or b in (0x0A,):
                s.append(b); j += 1
            else:
                ok = False; break
        if ok and j < n and d[j] == 0 and jp >= 1 and (i == 0 or d[i - 1] == 0):
            try:
                t = s.decode('cp932')
                if re.search('[぀-ヿ一-鿿]', t):
                    out.append((i, t))
            except UnicodeDecodeError:
                pass
            i = j + 1
        else:
            i = max(j, i) + 1 if not ok else j + 1
    return out


if __name__ == '__main__':
    os.makedirs(os.path.join(ROOT, 'work', 'text'), exist_ok=True)
    for f in sys.argv[1:]:
        d = open(os.path.join(ROOT, 'work', 'disc', f), 'rb').read()
        res = scan(d)
        menu = [(o, t) for o, t in res if not re.search('[一-鿿]', t)]
        kan = [(o, t) for o, t in res if re.search('[一-鿿]', t)]
        with open(os.path.join(ROOT, 'work', 'text', 'exe_%s.tsv' % f.split('.')[0]), 'w', encoding='utf-8') as w:
            w.write('오프셋\t분류\t원문\n')
            for o, t in res:
                w.write('%X\t%s\t%s\n' % (o, 'kanji' if re.search('[一-鿿]', t) else 'menu', t.replace('\n', '\n')))
        print('%s: 문자열 %d (메뉴꼴 %d·글자 %d / 한자 섞임 %d·글자 %d)' % (f, len(res), len(menu), sum(len(t) for _, t in menu), len(kan), sum(len(t) for _, t in kan)))
