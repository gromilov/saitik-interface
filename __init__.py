"""saitik-interface — регистрация инструментов экрана и Ткани.

Два инструмента:
  screen — экран узла (сцена, ответ, шаги, знаки, арт, витрина, уборка); `ops` — сборка одним вызовом.
  node   — Ткань напрямую (чтение, запись скриптом, список, создание, симбиоз, загрузка, op=call).

Подробности — навык hermes-interface (ядро + полки) и узел «Лоза · Интерфейс — система навыков».
"""

import logging

from . import schemas, tools

logger = logging.getLogger(__name__)


def register(ctx):
    ctx.register_tool(
        name="screen",
        toolset="saitik_interface",
        schema=schemas.SCREEN,
        handler=tools.screen,
    )
    ctx.register_tool(
        name="node",
        toolset="saitik_interface",
        schema=schemas.NODE,
        handler=tools.node,
    )
    logger.debug("saitik-interface: инструменты screen и node зарегистрированы")
