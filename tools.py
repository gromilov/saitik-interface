"""Обработчики saitik-interface: screen (экран по регистру) и node (Ткань напрямую).

Экран — тонкая обёртка над g.py: регистр действий в registry.py, g.py остаётся источником правды
(его же зовут cron-скрипты). Узел — параметр: контекст на каждый вызов, экран живёт на любом узле
и на нескольких сразу. Node — тот же путь к Ткани, что у mcp_call.py.
"""

import contextlib
import importlib.util
import io
import json
import os
import sys

from . import registry

SCRIPTS = os.path.expanduser('~/.hermes/scripts')
_G = None
_MCP = None


def _load(name, path):
    if SCRIPTS not in sys.path:
        sys.path.insert(0, SCRIPTS)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _g():
    """g.py держим в памяти плагина: импорт один раз на процесс."""
    global _G
    if _G is None:
        _G = _load('hermes_g', os.path.join(SCRIPTS, 'g.py'))
    return _G


def _mcp():
    global _MCP
    if _MCP is None:
        _MCP = _load('hermes_mcp_call', os.path.join(SCRIPTS, 'mcp_call.py'))
    return _MCP


def _mcp_run(tool, arguments):
    m = _mcp()
    out = m.call(m.token(), tool, arguments or {})
    return out.get('result', out)


# ─────────────────────────── screen ───────────────────────────

def _argv(op, a, node):
    """argv для g.py из регистра: данные → позиционные и флаги. Узел — из контекста."""
    spec = registry.SCREEN_OPS.get(op)
    if spec is None:
        return None
    argv = [op]
    if spec.get('special') == 'tint':  # tint <блок> <роль>
        argv.append(a.get('ids') and str(a['ids'][0]) or str(a.get('text') or ''))
        argv.append(str(a.get('role') or 'normal'))
        return argv
    for key in spec.get('pos', []):
        v = a.get(key)
        if v is not None and str(v) != '':
            argv.append(str(v))
        elif not spec.get('opt'):
            break
    if spec.get('spread'):
        for v in (a.get(spec['spread']) or []):
            argv.append(str(v))
    elif spec.get('fallback') and a.get(spec['fallback']):
        argv.append(str(a[spec['fallback']]))
    if spec.get('opt') and not (spec.get('pos') and a.get(spec['pos'][0]) is None):
        pass
    for key, flag in (spec.get('args_map') or {}).items():
        v = a.get(key)
        if v:
            argv += [flag, ';'.join(str(x) for x in v) if isinstance(v, list) else str(v)]
    for key, flag in (spec.get('flags') or {}).items():
        if a.get(key):
            argv.append(flag)
    argv += [str(x) for x in (a.get('args') or [])]
    return ['--node', node] + argv


def _run(argv):
    g = _g()
    buf = io.StringIO()
    code = 0
    with contextlib.redirect_stdout(buf):
        try:
            res = g.main(['g.py'] + argv)
            code = res if isinstance(res, int) else 0
        except SystemExit as e:
            code = e.code if isinstance(e.code, int) else 0
    out = buf.getvalue().strip()
    lines = [ln for ln in out.split('\n') if ln.strip()]
    strip = next((ln for ln in reversed(lines) if ln.startswith('лента')), '')
    rest = '\n'.join(ln for ln in lines if ln != strip)
    return code, rest[-600:], strip


def _screen_one(a, default_node):
    op = str(a.get('op') or '').strip()
    node = str(a.get('node') or default_node or '').strip()
    ctx = registry.ctx_for(node)
    if not ctx:
        return ({'op': op or '—', 'ok': False,
                 'error': 'узел не задан: укажи node или поставь профиль в ~/.hermes/config.yaml '
                          '(plugins.saitik-interface.node) / переменную SAITIK_NODE'}, '')
    node = ctx['node']
    if op not in registry.SCREEN_OPS:
        return ({'op': op or '—', 'ok': False, 'error': registry.OPS_HINT}, '')
    argv = _argv(op, a, node)
    if argv is None:
        return ({'op': op, 'ok': False, 'error': registry.OPS_HINT}, '')
    code, rest, strip = _run(argv)
    item = {'op': op, 'node': node, 'ok': code == 0}
    if rest:
        item['out'] = rest
    if code:
        item['code'] = code
    return item, strip


def screen(args: dict, **kwargs) -> str:
    try:
        args = args or {}
        default_node = str(args.get('node') or registry.profile().get('node') or '').strip()
        queue = args.get('ops') if isinstance(args.get('ops'), list) and args.get('ops') else None
        if queue:
            results, last_strip = [], ''
            for step in queue:
                if not isinstance(step, dict):
                    continue
                merged = {k: v for k, v in args.items() if k != 'ops'}
                merged.update(step)
                item, strip = _screen_one(merged, default_node)
                last_strip = strip or last_strip
                if strip:
                    item.pop('strip', None)
                results.append(item)
            return json.dumps({'ok': all(r['ok'] for r in results), 'ops': results, 'strip': last_strip},
                              ensure_ascii=False)
        item, strip = _screen_one(args, default_node)
        if isinstance(item, dict) and 'strip' in item:
            item.pop('strip', None)
        result = dict(item)
        result['strip'] = strip
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        return json.dumps({'ok': False, 'error': '%s: %s' % (type(e).__name__, e)}, ensure_ascii=False)


# ─────────────────────────── node ───────────────────────────

def _unwrap(res):
    if isinstance(res, dict) and isinstance(res.get('content'), list):
        for item in res['content']:
            if isinstance(item, dict) and item.get('type') == 'text':
                res = item.get('text') or ''
                break
    if isinstance(res, str):
        try:
            res = json.loads(res)
        except Exception:
            cut = res.find('{')
            res = json.loads(res[cut:]) if cut >= 0 else {}
    if isinstance(res, dict) and isinstance(res.get('data'), dict):
        res = res['data']
    return res


def _flat(res, limit):
    obj = _unwrap(res)
    text = obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False)
    return text[:limit]


def _symbiosis_blocks(host):
    node = _unwrap(_mcp_run('reflexia', {'id': host, 'mode': 'json'}))
    if not isinstance(node, dict):
        return []
    blocks = node.get('blocks') or {}
    pairs = blocks.items() if isinstance(blocks, dict) else [
        ((b or {}).get('_id') or (b or {}).get('id'), b) for b in blocks]
    return [{'block': bid, 'child': ((blk or {}).get('options', {}).get('element', {}) or {}).get('app_id')}
            for bid, blk in pairs
            if (blk or {}).get('options', {}).get('component') == 'Saitik'
            and ((blk or {}).get('options', {}).get('element', {}) or {}).get('app_id')]


def _script(kind, body, action=None, obj=None, position=None):
    head = ['---']
    if action:
        head.append('Действие: %s' % action)
    if obj:
        head.append('Объект: %s' % obj)
    if kind:
        head.append('Тип: %s' % kind)
    if position:
        head.append('Позиция: %s' % position)
    head += ['---', '']
    return '\n'.join(head) + (json.dumps(body, ensure_ascii=False) if body is not None else '')


def node(args: dict, **kwargs) -> str:
    try:
        a = args or {}
        op = str(a.get('op') or '').strip()
        nid = str(a.get('id') or '').strip()
        params = a.get('params') if isinstance(a.get('params'), dict) else {}

        if op == 'read':
            if not nid:
                return json.dumps({'ok': False, 'error': 'нужен id'}, ensure_ascii=False)
            res = _mcp_run('reflexia', {'id': nid, 'mode': a.get('mode') or 'json'})
            obj = _unwrap(res)
            text = obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False)
            return json.dumps({'ok': True, 'op': op, 'id': nid, 'len': len(text), 'node': text[:4000]},
                              ensure_ascii=False)

        if op == 'list':
            res = _mcp_run('list_saitiks', {})
            return json.dumps({'ok': True, 'op': op, 'nodes': _flat(res, 3000)}, ensure_ascii=False)

        if op == 'write':
            script = a.get('script') or ''
            if not script and a.get('file'):
                with open(str(a['file']), encoding='utf-8') as f:
                    script = f.read()
            if not (nid and script):
                return json.dumps({'ok': False, 'error': 'нужны id и script (или file)'}, ensure_ascii=False)
            res = _mcp_run('execute_saitik_script', {'id': nid, 'script': script})
            return json.dumps({'ok': True, 'op': op, 'id': nid, 'result': _flat(res, 1200)}, ensure_ascii=False)

        if op == 'create':
            if not (a.get('name') and a.get('host')):
                return json.dumps({'ok': False, 'error': 'нужны name и host'}, ensure_ascii=False)
            res = _mcp_run('create_saitik', {'name': a['name'], 'hostId': a['host']})
            return json.dumps({'ok': True, 'op': op, 'result': _flat(res, 800)}, ensure_ascii=False)

        if op == 'symbiosis':
            action = str(a.get('action') or 'list')
            host = a.get('host') or nid
            if not host:
                return json.dumps({'ok': False, 'error': 'нужен host'}, ensure_ascii=False)
            if action == 'list':
                return json.dumps({'ok': True, 'op': op, 'host': host, 'symbioses': _symbiosis_blocks(host)},
                                  ensure_ascii=False)
            child = str(a.get('child') or '').strip()
            block = str(params.get('block') or '').strip()
            if action in ('remove', 'switch') and not block:
                same = [x for x in _symbiosis_blocks(host) if child and x.get('child') == child]
                block = (same[0]['block'] if same else '')
            if action == 'remove':
                if not block:
                    return json.dumps({'ok': False, 'error': 'не нашёл блок врезки (дай params.block)'},
                                      ensure_ascii=False)
                res = _mcp_run('execute_saitik_script',
                               {'id': host, 'script': _script(None, None, action='Разрушение', obj=block)})
            elif action == 'switch':
                if not (block and child):
                    return json.dumps({'ok': False, 'error': 'нужны block и child'}, ensure_ascii=False)
                res = _mcp_run('execute_saitik_script', {'id': host, 'script': _script(
                    'Симбиоз', {'app_id': child}, action='Трансмутация', obj=block)})
            elif action == 'add':
                if not child:
                    return json.dumps({'ok': False, 'error': 'нужен child'}, ensure_ascii=False)
                pos = params.get('after') and ('После %s' % params['after']) or 'Конец'
                res = _mcp_run('execute_saitik_script', {'id': host, 'script': _script(
                    'Симбиоз', {'app_id': child}, position=pos)})
            else:
                return json.dumps({'ok': False, 'error': 'action: list|add|switch|remove'}, ensure_ascii=False)
            return json.dumps({'ok': True, 'op': op, 'action': action, 'host': host,
                               'result': _flat(res, 800)}, ensure_ascii=False)

        if op == 'upload':
            if not (nid and a.get('url')):
                return json.dumps({'ok': False, 'error': 'нужны id и url'}, ensure_ascii=False)
            res = _mcp_run('upload_file', dict(params, id=nid, url=a['url']))
            return json.dumps({'ok': True, 'op': op, 'result': _flat(res, 800)}, ensure_ascii=False)

        if op == 'call':
            tool = str(a.get('tool') or '').strip()
            if not tool:
                return json.dumps({'ok': False, 'error': 'нужен tool'}, ensure_ascii=False)
            res = _mcp_run(tool, params)
            return json.dumps({'ok': True, 'op': op, 'tool': tool, 'result': _flat(res, 3000)}, ensure_ascii=False)

        return json.dumps({'ok': False, 'error': 'op: read|write|list|create|symbiosis|upload|call'},
                          ensure_ascii=False)
    except Exception as e:
        return json.dumps({'ok': False, 'error': '%s: %s' % (type(e).__name__, e)}, ensure_ascii=False)
