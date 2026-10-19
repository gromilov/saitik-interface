"""Автоматики saitik-interface — знак «*» в действиях: гейтвей исполняет рецепт
и ГЛУШИТ сообщение, модель не просыпается (замысел Максима, 19.10.2026).

Как это устроено
----------------
Кнопка узла или человек в полоске пишут действие со знаком автоматики:

    действие:*<имя>[_довод]

Сообщение доходит до шлюза как обычная реплика (с меткой узла, а иногда и с
предупреждением «не от владельца»). Хук `pre_gateway_dispatch` смотрит текст
ДО того, как шлюз разбудит агента: находит знак «*», берёт имя и довод, зовёт
рецепт из реестра и возвращает `{"action": "skip"}` — сообщение проглочено.

Реестр — папка с исполняемыми рецептами (по умолчанию `~/.hermes/scripts/automations`,
можно задать в config.yaml → `plugins.entries.saitik-interface.automations`).
Рецепт — любой исполняемый файл: `.py` зовётся питоном, `.sh` — bash, прочее
запускается как есть. Имя рецепта = имя файла без расширения, на русском:
`убрать_входящее.py` ← `действие:*убрать_входящее_63970764`.

Что рецепт получает
-------------------
На stdin — JSON с полным контекстом (текст, имя, довод, узел, кто, комната),
плюс переменные окружения `SAITIK_ACTION_NAME`, `SAITIK_ACTION_ARG`,
`SAITIK_ACTION_TEXT`. Права решает сам рецепт: он видит, кто нажал.

Почему так, а не «пусть агент решит»
------------------------------------
Автоматика — там, где решение известно заранее и повторяется: убрать входящее,
завести запись, снять флаг. Модель на такое не нужна: это токены и секунды.
Агент остаётся для того, где нужно думать.
"""

import json
import logging
import os
import re
import subprocess
import sys
import time

logger = logging.getLogger(__name__)

# Знак автоматики в языке действий («действие:*имя_довод»).
AUTOMATION_SIGN = '*'

# Метка узла, которой полоска помечает сообщение: «[узел <id> «<имя>»]».
NODE_MARK = re.compile(r'\[узел\s+([^\s\]«]+)(?:\s+«([^»]*)»)?\]')
# Само действие внутри текста: до конца строки.
ACTION_IN_TEXT = re.compile(r'действие:\s*' + re.escape(AUTOMATION_SIGN) + r'([^\s]+)')

LOG = os.path.expanduser('~/.hermes/logs/automations.log')


def automations_dir() -> str:
    """Папка рецептов: настройка плагина или привычное место."""
    try:
        import yaml
        cfg = yaml.safe_load(open(os.path.expanduser('~/.hermes/config.yaml'), encoding='utf-8')) or {}
        entry = ((cfg.get('plugins') or {}).get('entries') or {}).get('saitik-interface') or {}
        path = str(entry.get('automations') or '').strip()
        if path:
            return os.path.expanduser(path)
    except Exception:
        pass
    return os.path.expanduser('~/.hermes/scripts/automations')


def known_names():
    """Имена рецептов из реестра — по файлам. Нужны, чтобы разбирать довод
    правильно: в русских именах подчёркивание есть и ВНУТРИ («убрать_входящее»),
    поэтому имя ищем сверкой со списком, а не по первому «_»."""
    root = automations_dir()
    names = []
    try:
        for f in os.listdir(root):
            if f.startswith('.'):
                continue
            stem = f.rsplit('.', 1)[0] if '.' in f else f
            if stem and stem not in names:
                names.append(stem)
    except Exception:
        pass
    return sorted(names, key=len, reverse=True)


def parse_automation(text: str):
    """Достать (имя, довод, узел_id, узел_имя) из текста сообщения. Нет знака → None."""
    raw = str(text or '')
    m = ACTION_IN_TEXT.search(raw)
    if not m:
        return None
    body = m.group(1).strip().rstrip('.,;')
    if not body:
        return None
    name, arg = body, ''
    # Сперва — сверка с реестром (длинные имена первыми): «убрать_входящее_63970764».
    for known in known_names():
        if body == known:
            name, arg = known, ''
            break
        if body.startswith(known):
            name = known
            arg = body[len(known):]
            arg = arg.lstrip('_').strip()
            break
    else:
        # Реестра нет или имя чужое: режем по первому «_» — как последняя надежда.
        cut = body.find('_')
        name = (body if cut == -1 else body[:cut]).strip()
        arg = '' if cut == -1 else body[cut + 1:].strip()
    if not name:
        return None
    nm = NODE_MARK.search(raw)
    node_id = nm.group(1) if nm else ''
    node_name = (nm.group(2) or '') if nm else ''
    return name, arg, node_id, node_name


def log(line: str) -> None:
    """Тихая строка в свой журнал: автоматику не видно ни в чате, ни у агента."""
    try:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, 'a', encoding='utf-8') as f:
            f.write('%s %s\n' % (time.strftime('%Y-%m-%d %H:%M:%S'), line))
    except Exception:
        pass


def run(name: str, arg: str, text: str, node_id: str = '', node_name: str = '',
        who: str = '', room: str = '') -> bool:
    """Позвать рецепт. True — рецепт найден и запущен (сообщение глушим всегда)."""
    root = automations_dir()
    script = ''
    for ext in ('.py', '.sh', ''):
        cand = os.path.join(root, name + ext)
        if os.path.exists(cand):
            script = cand
            break
    if not script:
        log('нет рецепта «%s» (искал в %s) — сообщение проглочено' % (name, root))
        return False
    if script.endswith('.py'):
        cmd = [sys.executable, script]
    elif script.endswith('.sh'):
        cmd = ['/bin/bash', script]
    else:
        cmd = [script]
    payload = json.dumps({
        'name': name, 'arg': arg, 'text': text,
        'node': node_id, 'node_name': node_name, 'who': who, 'room': room,
    }, ensure_ascii=False)
    env = dict(os.environ)
    env.update({
        'SAITIK_ACTION_NAME': name,
        'SAITIK_ACTION_ARG': arg,
        'SAITIK_ACTION_TEXT': text,
        'SAITIK_NODE': node_id,
    })
    try:
        p = subprocess.run(cmd, input=payload, capture_output=True, text=True,
                           timeout=120, env=env)
        tail = (p.stdout or '').strip().replace('\n', ' | ')[:400]
        err = (p.stderr or '').strip().replace('\n', ' | ')[:400]
        log('рецепт «%s» довод «%s» → код %s%s%s'
            % (name, arg, p.returncode, ' · ' + tail if tail else '',
               ' · ОШИБКА: ' + err if err else ''))
        return True
    except Exception as e:
        log('рецепт «%s» не пошёл: %s' % (name, str(e)[:200]))
        return False


def gateway_hook(event=None, gateway=None, session_store=None, **kwargs):
    """Хук шлюза: знак автоматики → исполнить и проглотить. Агента не будим."""
    try:
        text = getattr(event, 'text', None)
        if text is None and isinstance(event, dict):
            text = event.get('text')
        parsed = parse_automation(text)
        if not parsed:
            return None
        name, arg, node_id, node_name = parsed
        who = ''
        room = ''
        for attr in ('sender', 'user_id', 'sender_id'):
            val = getattr(event, attr, None)
            if val:
                who = str(val)
                break
        for attr in ('chat_id', 'room_id', 'chat'):
            val = getattr(event, attr, None)
            if val:
                room = str(val)
                break
        found = run(name, arg, str(text or ''), node_id, node_name, who, room)
        # Глушим ВСЕГДА: знак «*» значит «агенту не идти». Не нашли рецепт — это
        # моя оплошность, её видно в журнале автоматик, но человек не должен
        # получить ответ модели на служебное действие.
        return {'action': 'skip', 'reason': 'автоматика %s%s' % (name, ' (рецепт не найден)' if not found else '')}
    except Exception as e:
        log('хук споткнулся: %s' % str(e)[:200])
        try:
            if parse_automation(getattr(event, 'text', '')):
                return {'action': 'skip', 'reason': 'автоматика (хук споткнулся)'}
        except Exception:
            pass
        return None
