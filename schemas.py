"""Схемы инструментов saitik-interface — то, что читает модель.

Инструменты отложенные (Tool Search): схема не висит в промпте, но платится шагом
`tool_describe`. Поэтому описания короткие, а подробности — на полках навыка hermes-interface.
"""

SCREEN = {
    "name": "screen",
    "description": (
        "Экран узла: сцена задачи, ответ, шаги, знаки-лента, витрина, уборка, арт, снимок. "
        "Заменяет вызовы g.py; ops — несколько действий одним вызовом. args — добить сырыми флагами."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "op": {
                "type": "string",
                "enum": [
                    "scene", "new", "say", "title", "report", "answer", "note", "log", "plan",
                    "steps", "step", "pieces", "tint", "art", "frame", "ask", "panel",
                    "strip", "verify", "show", "stat", "ch", "lib", "home", "word",
                    "hash", "check", "snap", "screens", "back", "clear", "del", "pin", "unpin", "prune",
                ],
                "description": "действие",
            },
            "task": {"type": "string"},
            "steps": {"type": "array", "items": {"type": "string"}},
            "text": {"type": "string", "description": "основной текст действия"},
            "note": {"type": "string", "description": "ход для журнала"},
            "num": {"type": "string", "description": "номер шага или all"},
            "mark": {"type": "string", "enum": ["ok", "work", "err", "wait"]},
            "ids": {"type": "array", "items": {"type": "string"}},
            "status": {"type": "string"},
            "role": {"type": "string", "description": "роль цвета: normal|muted|accent|success|warning|danger"},
            "tree": {"type": "boolean"},
            "args": {"type": "array", "items": {"type": "string"}, "description": "сырые доводы g.py (--width, --safe, …)"},
            "node": {"type": "string", "description": "чужой узел"},
            "ops": {
                "type": "array",
                "items": {"type": "object", "description": "то же: op + любые поля выше"},
                "description": "несколько действий одним вызовом",
            },
        },
        "required": [],
    },
}

NODE = {
    "name": "node",
    "description": (
        "Узел Ткани напрямую из шлюза (без процессов): чтение, запись скриптом SaitikLang, "
        "список узлов, создание, врезка-симбиоз, загрузка файла. op=call — любой инструмент Ткани по имени."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "op": {
                "type": "string",
                "enum": ["read", "write", "list", "create", "symbiosis", "upload", "call"],
                "description": "действие",
            },
            "id": {"type": "string", "description": "узел"},
            "script": {"type": "string", "description": "скрипт SaitikLang (op=write)"},
            "file": {"type": "string", "description": "файл со скриптом или для загрузки"},
            "name": {"type": "string", "description": "имя нового узла (op=create/rename)"},
            "host": {"type": "string", "description": "узел-хозяин (op=create, для симбиоза — хозяин врезки)"},
            "child": {"type": "string", "description": "врезка: узел, который встраиваем (op=symbiosis)"},
            "mode": {"type": "string", "enum": ["json", "plain", "text"], "description": "форма чтения"},
            "action": {"type": "string", "enum": ["list", "add", "switch", "remove"], "description": "для op=symbiosis"},
            "url": {"type": "string", "description": "op=upload: прямая ссылка на файл"},
            "tool": {"type": "string", "description": "op=call: имя инструмента Ткани"},
            "params": {"type": "object", "description": "op=call: доводы инструмента"},
        },
        "required": [],
    },
}
