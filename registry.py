"""Регистр и контексты saitik-interface — механика интерфейса в переменных, а не в коде.

Зачем: свои инструменты и навыки внедряются в клиентские агенты (задача 19.10.2026).
Форма задаётся регистром (данные, а не лестница if/elif), состояние — по узлам, узел — параметр.
Долговечное живёт в самом узле Ткани (перезапуск шлюза ничего не ломает); здесь — быстрый слой.

Публичное: SCREEN_OPS (регистр действий экрана), CONTEXTS (состояние по узлам), ctx_for(node).

Профиль агента (личные id — НЕ в коде): читается один раз при первом обращении из
~/.hermes/config.yaml → плагин saitik-interface:

    plugins:
      saitik-interface:
        node: <узел-интерфейс агента>     # куда писать экран (обязателен для screen)
        home: <узел-дом>                  # память агента
        journal: <узел-журнал>            # ходы
    # или переменными окружения SAITIK_NODE / SAITIK_HOME / SAITIK_JOURNAL

Без профиля screen не угадывает узел: отвечает «укажи node» — защита от записи на чужую страницу.
"""

import json
import os

# ── Регистр действий экрана ──────────────────────────────────────────────────
# Каждое действие: как собрать argv g.py. Ключи данных инструмента:
#   task, steps, text, note, num, mark, ids, status, role, args (+ node берётся из контекста)

SCREEN_OPS = {
    'scene':  {'pos': ['task'], 'args_map': {'steps': '--steps', 'status': '--status'}},
    'new':    {'pos': ['task', 'text']},
    'say':    {'pos': ['text'], 'args_map': {'status': '--status', 'role': '--role'}},
    'title':  {'pos': ['text']},
    'report': {'pos': ['text'], 'args_map': {'status': '--status', 'note': '--note'}},
    'answer': {},
    'note':   {'pos': ['text']},
    'log':    {'pos': ['text'], 'opt': True},
    'plan':   {'pos': ['text'], 'opt': True},
    'steps':  {'spread': 'steps'},
    'step':   {'pos': ['num', 'mark', 'text']},
    'pieces': {'spread': 'steps', 'fallback': 'text'},
    'tint':   {'special': 'tint'},
    'art':    {'pos': ['text'], 'opt': True},
    'frame':  {'pos': ['text'], 'opt': True},
    'ask':    {'pos': ['text'], 'spread': 'steps'},
    'panel':  {'pos': ['text']},
    'strip':  {'flags': {'tree': '--tree'}},
    'verify': {}, 'show': {}, 'stat': {}, 'ch': {}, 'home': {}, 'word': {},
    'hash':   {'opt': True}, 'check': {'opt': True},
    'snap':   {'opt': True}, 'screens': {}, 'lib': {'opt': True},
    'back':   {'opt': True}, 'clear': {}, 'prune': {},
    'del':    {'spread': 'ids'},
    'pin':    {'spread': 'ids'},
    'unpin':  {'spread': 'ids'},
}

# Роли цвета (знак = цвет + смысл): валидация довода role
ROLES = ('normal', 'muted', 'accent', 'success', 'warning', 'danger')

OPS_HINT = 'действия: ' + ', '.join(SCREEN_OPS)

# ── Профиль агента (личные id — из конфига/окружения, не из кода) ────────────

_PROFILE = None


def profile():
    """Профиль агента: {node, home, journal} или {} — без угадывания."""
    global _PROFILE
    if _PROFILE is None:
        _PROFILE = {}
        try:
            import yaml  # Hermes-окружение всегда имеет pyyaml
            cfg = yaml.safe_load(open(os.path.expanduser('~/.hermes/config.yaml')) or {}) or {}
            pl = cfg.get('plugins') or {}
            _PROFILE = dict((pl.get('saitik-interface') or {}))
            if not _PROFILE:
                _PROFILE = dict(((pl.get('entries') or {}).get('saitik-interface') or {}))
        except Exception:
            pass
        for env_key, key in (('SAITIK_NODE', 'node'), ('SAITIK_HOME', 'home'), ('SAITIK_JOURNAL', 'journal')):
            if os.environ.get(env_key):
                _PROFILE[key] = os.environ[env_key]
    return _PROFILE


# ── Контексты: состояние экрана по узлам (в памяти, узел — параметр) ─────────

CONTEXTS = {}
STATE_DIR = os.path.expanduser('~/.hermes/state')


def ctx_for(node):
    """Контекст узла: {узел, дом, журнал}. Профиль даёт значения по умолчанию."""
    node = str(node or '').strip()
    p = profile()
    if not node:
        node = p.get('node') or ''
    if not node:
        return None  # нет профиля и нет явного узла — screen не угадывает
    if node not in CONTEXTS:
        prof = {}
        try:
            prof = json.load(open(os.path.join(STATE_DIR, 'node-%s.json' % node)))
        except Exception:
            pass
        CONTEXTS[node] = {
            'node': node,
            'home': prof.get('home') or p.get('home') or '',
            'journal': prof.get('journal') or p.get('journal') or '',
        }
    return CONTEXTS[node]


def ctx_set(node, **kv):
    c = ctx_for(node)
    if c:
        c.update({k: v for k, v in kv.items() if v is not None})
    return c


def ctx_drop(node=None):
    if node:
        CONTEXTS.pop(str(node).strip(), None)
    else:
        CONTEXTS.clear()
