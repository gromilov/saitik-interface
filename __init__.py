"""saitik-interface — регистрация инструментов экрана и Ткани.

Два инструмента:
  screen — экран узла (сцена, ответ, шаги, знаки, арт, витрина, уборка); `ops` — сборка одним вызовом.
  node   — Ткань напрямую (чтение, запись скриптом, список, создание, симбиоз, загрузка, op=call).

Плюс хук автоматик: действие со знаком «*» шлюз исполняет рецептом и глушит —
модель не просыпается (замысел Максима, 19.10.2026). Реестр — `automations.py`.

Подробности — навык hermes-interface (ядро + полки) и узел «Лоза · Интерфейс — система навыков».
"""

import logging

from . import automations, schemas, tools

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
    # Автоматики: «действие:*имя_довод» — гейтвей зовёт рецепт и глушит сообщение.
    try:
        ctx.register_hook("pre_gateway_dispatch", automations.gateway_hook)
        logger.debug("saitik-interface: хук автоматик зарегистрирован")
    except Exception as e:            # хук не критичен для инструментов — не падаем
        logger.warning("saitik-interface: хук автоматик не зарегистрировался: %s", e)
    logger.debug("saitik-interface: инструменты screen и node зарегистрированы")
