#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""注入前的自检：只读 st/data/，一个字节都不写。

cardbuild.py 只拦「会把主文档写坏」的错。这里拦的是另一类 ——
装得进去、跑起来却是错的：开局与简介对不上、世界书缺字段、槽位没填完。

用法：python3 tools/cardcheck.py [源码树]      默认 st/data
退出码：0 全过；1 有错（ERR）；警告（WARN）不影响退出码。
"""
import io, os, re, sys, json, glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, sys.argv[1] if len(sys.argv) > 1 else 'st/data')

FORBID = re.compile('|'.join(['cla' 'ude', 'anthro' 'pic', 'yen' 'wa']), re.I)
XOVER = ['贝罗娜', '克娄巴特拉', '姬瑶', '持田', '萨日乐']
META_KEYS = ['panelSpec', 'name', 'description', 'personality', 'scenario',
             'system_prompt', 'post_history_instructions', 'mes_example', 'first_mes']

errs, warns = [], []
def err(m):  errs.append(m)
def warn(m): warns.append(m)


def load(path):
    try:
        return json.load(io.open(path, encoding='utf-8'))
    except Exception as e:
        err('%s 解析失败：%s' % (os.path.relpath(path, ROOT), e))
        return None


def check_meta():
    m = load(os.path.join(DATA, 'meta.json'))
    if m is None:
        return None
    for k in META_KEYS:
        if k not in m:
            err('meta.json 缺字段 %s' % k)
    extra = [k for k in m if k not in META_KEYS]
    if extra:
        warn('meta.json 多出字段 %s（会原样进卡）' % extra)
    if m.get('first_mes'):
        warn('meta.json 的 first_mes 非空 —— 开局零才是首条消息，这里通常留空')
    ps = m.get('panelSpec') or {}
    for k in ['textOrder', 'reserved', 'badge', 'widgets']:
        if k not in ps:
            err('panelSpec 缺 %s' % k)
    keys = [w['k'] for w in ps.get('widgets', []) if 'k' in w]
    if ps.get('badge') and ps['badge'] not in keys:
        err('panelSpec.badge %r 不在 widgets 里' % ps['badge'])
    for w in ps.get('widgets', []):
        if w.get('type') == 'bar':
            caps = w.get('caps') or []
            if [c[0] for c in caps] != sorted(c[0] for c in caps):
                err('widget %r 的 caps 阈值没有升序' % w.get('k'))
    return m


def check_openings():
    ids = []
    for p in sorted(glob.glob(os.path.join(DATA, 'openings', '*.md'))):
        base = os.path.basename(p)
        raw = io.open(p, encoding='utf-8').read()
        head, sep, body = raw.partition('\n\n')
        if not sep:
            err('%s 首行 JSON 头之后要有一个空行' % base)
            continue
        try:
            h = json.loads(head)
        except Exception as e:
            err('%s 的 JSON 头解析失败：%s' % (base, e))
            continue
        for k in ['era', 'scene', 'year']:
            if k not in h:
                err('%s 的头缺 %s' % (base, k))
        if not body.strip():
            err('%s 正文是空的' % base)
        try:
            ids.append(int(base.split('.')[0]))
        except ValueError:
            err('%s 文件名不是两位数字' % base)
    if ids and sorted(ids) != list(range(len(ids))):
        err('开局编号不连续：%s' % sorted(ids))
    if not ids:
        err('一个开局都没有')
    return sorted(ids)


def check_briefs(ids):
    b = load(os.path.join(DATA, 'briefs.json'))
    if b is None:
        return
    have = sorted(int(k) for k in b)
    miss = [i for i in ids if i not in have]
    extra = [i for i in have if i not in ids]
    if miss:
        err('briefs.json 缺开局 %s 的简介' % miss)
    if extra:
        warn('briefs.json 多出开局 %s（没有对应的 openings 档）' % extra)


def check_lore():
    files = sorted(glob.glob(os.path.join(DATA, 'lore', '*.json')),
                   key=lambda p: (0 if os.path.basename(p) == 'core.json' else 1,
                                  os.path.basename(p)))
    if not any(os.path.basename(p) == 'core.json' for p in files):
        warn('lore/ 下没有 core.json —— 常驻条目通常放在这里，它强制排最前')
    n, seen = 0, {}
    for p in files:
        base = os.path.basename(p)
        lb = load(p)
        if lb is None:
            continue
        if not isinstance(lb, list):
            err('%s 顶层不是数组' % base)
            continue
        for i, e in enumerate(lb):
            n += 1
            where = '%s[%d]' % (base, i)
            for k in ['cat', 'title', 'keys', 'content']:
                if k not in e:
                    err('%s 缺 %s' % (where, k))
            if not isinstance(e.get('keys', []), list):
                err('%s 的 keys 不是数组' % where)
            if e.get('constant') and e.get('pos') == 'depth' and 'depth' not in e:
                err('%s 是 depth 常驻条目却没有 depth' % where)
            if not e.get('constant') and not e.get('keys'):
                warn('%s「%s」既非常驻又没有 keys —— 永远不会被检索到'
                     % (where, e.get('title', '?')))
            t = e.get('title')
            if t in seen:
                warn('标题重复：%s 与 %s 都叫「%s」' % (seen[t], where, t))
            else:
                seen[t] = where
    return n


def check_text():
    """禁字、串戏词、没填完的槽位 —— 扫整棵源码树。"""
    slots = 0
    for r, _, fs in os.walk(DATA):
        for f in fs:
            p = os.path.join(r, f)
            s = io.open(p, encoding='utf-8', errors='replace').read()
            rel = os.path.relpath(p, ROOT)
            hits = FORBID.findall(s)
            if hits:
                err('%s 含禁字 %r' % (rel, sorted(set(h.lower() for h in hits))))
            for w in XOVER:
                if w in s:
                    err('%s 含串戏词 %r' % (rel, w))
            slots += s.count('«')
    if slots:
        err('还有 %d 处槽位 «…» 没填完（grep -rn "«" %s 看清单）'
            % (slots, os.path.relpath(DATA, ROOT)))


def main():
    if not os.path.isdir(DATA):
        raise SystemExit('找不到源码树 %s' % DATA)
    check_meta()
    ids = check_openings()
    check_briefs(ids)
    n = check_lore()
    check_text()

    for w in warns:
        print('WARN  %s' % w)
    for e in errs:
        print('ERR   %s' % e)
    print('—— %s：开局 %d 局，世界书 %d 条，%d 错 %d 警'
          % (os.path.relpath(DATA, ROOT), len(ids), n, len(errs), len(warns)))
    return 1 if errs else 0


if __name__ == '__main__':
    sys.exit(main())
