#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cardbuild.py 的逆向：主文档 → st/data/*。

主文档是产物，不是底稿。这条线的底稿一度只存在于打包好的那一行 JSON 里 ——
把它拆回可编辑的源码树，此后改卡改 st/data/，再用 cardbuild.py 注回去。

拆出来的东西保证能原样装回：cardbuild.py 跑完，主文档逐字节不变。

  meta.json          panelSpec 与卡元字段（去掉 openings / lorebook）
  openings/NN.md     首行 JSON 头 + 空行 + 正文
  briefs.json        选局环的一句话简介
  lore/core.json     常驻条目（constant），cardbuild 强制排最前
  lore/aNN-类.json   其余条目，按原序切成组，序号保证文件名序 == 原序

用法：python3 tools/carddump.py
"""
import io, os, re, json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOC  = os.path.join(ROOT, 'core/vendor/three/build/chunks/9d717bc0/156a50943028.html')
DATA = os.path.join(ROOT, 'st/data')

LINE      = os.environ.get('ROMA_LINE', 'luzhi')
SCRIPT_ID = 'card' + LINE[:1].upper() + LINE[1:]
GLOBAL_ID = '__GAME_' + LINE.upper() + '__'


def grab(html, script_id):
    """从 <script id=…> 里挖出 JSON 字面量：括号配平，别用正则硬啃。"""
    m = re.search(r'<script id="%s">([\s\S]*?)</script>' % re.escape(script_id), html)
    if not m:
        raise SystemExit('找不到 %s 块' % script_id)
    b = m.group(1)
    i = b.index('{', b.index('='))
    d = 0
    for k, ch in enumerate(b[i:], i):
        if ch == '{':
            d += 1
        elif ch == '}':
            d -= 1
            if d == 0:
                return json.loads(b[i:k + 1])
    raise SystemExit('%s 括号不配平' % script_id)


def grab_briefs(html):
    m = re.search(r'var BRIEFS=\{%s:(\{[\s\S]*?\})\};' % re.escape(LINE), html)
    if not m:
        raise SystemExit('找不到 BRIEFS')
    return json.loads(m.group(1))


def slug(s):
    """类名进文件名：只留中文与字母数字，别让空格和标点跑进路径。"""
    return re.sub(r'[^\w一-鿿]+', '', s)[:12] or 'misc'


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    io.open(path, 'w', encoding='utf-8').write(text)


def dump_openings(ops):
    for o in ops:
        head = json.dumps({'era': o['era'], 'scene': o['scene'], 'year': o['year']},
                          ensure_ascii=False)
        write(os.path.join(DATA, 'openings', '%02d.md' % o['id']),
              head + '\n\n' + o['text'] + '\n')
    return len(ops)


def dump_lore(lb):
    """常驻条目进 core.json；其余按 cat 的原始游程切组，序号即原序。

    cat 在原数据里并不连续（同一类隔着别的类又出现一次），所以不能按类归并 ——
    那样会重排世界书。这里只沿着原顺序切，文件名序因此等于原序。
    """
    const = [e for e in lb if e.get('constant')]
    rest  = lb[len(const):]
    assert lb[:len(const)] == const, '常驻条目不在最前，需人工确认顺序'

    runs, files = [], []
    for e in rest:
        if not runs or runs[-1][0] != e['cat']:
            runs.append((e['cat'], []))
        runs[-1][1].append(e)

    write(os.path.join(DATA, 'lore', 'core.json'),
          json.dumps(const, ensure_ascii=False, indent=1) + '\n')
    files.append(('core.json', len(const)))
    for n, (cat, group) in enumerate(runs, 1):
        fn = 'a%02d-%s.json' % (n, slug(cat))
        write(os.path.join(DATA, 'lore', fn),
              json.dumps(group, ensure_ascii=False, indent=1) + '\n')
        files.append((fn, len(group)))
    return files


def main():
    html = io.open(DOC, encoding='utf-8').read()
    card = grab(html, SCRIPT_ID)
    briefs = grab_briefs(html)

    ops = card.pop('openings')
    lb  = card.pop('lorebook')

    write(os.path.join(DATA, 'meta.json'),
          json.dumps(card, ensure_ascii=False, indent=1) + '\n')
    write(os.path.join(DATA, 'briefs.json'),
          json.dumps(briefs, ensure_ascii=False, indent=1) + '\n')
    n_ops = dump_openings(ops)
    files = dump_lore(lb)

    print('拆解完成：线号 %s，开局 %d 局，世界书 %d 条 / %d 档' % (
        LINE, n_ops, len(lb), len(files)))
    for fn, n in files[:4]:
        print('   %-22s %d' % (fn, n))
    print('   … 共 %d 档' % len(files))


if __name__ == '__main__':
    main()
