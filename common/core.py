"""
Copyright 2021-2026 AstreaTSS.
This file is part of PYTHIA.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

import asyncio
import collections

import discord
import typing_extensions as typing
from discord.ext import bridge, commands

import common.models as models

__all__ = (
    "Cog",
    "THIABase",
    "THIABridgeApplicationContext",
    "THIABridgeContext",
    "THIABridgeExtContext",
    "THIAContextMixin",
    "THIASlashContext",
)


class THIAContextMixin:
    guild_config: models.GuildConfig | None
    guild_id: discord.Snowflake
    bot: "THIABase"

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        self.guild_config = None
        super().__init__(*args, **kwargs)

    async def fetch_config(
        self,
        include: models.GuildConfigInclude | None = None,
    ) -> models.GuildConfig:
        """
        Gets the configuration for the context's guild.

        Returns:
            The guild config.
        """
        if self.guild_config:
            return self.guild_config

        config = await models.GuildConfig.fetch_create(int(self.guild_id), include)
        self.guild_config = config
        return config


class THIABridgeApplicationContext(THIAContextMixin, bridge.BridgeApplicationContext):
    pass


THIASlashContext = THIABridgeApplicationContext


class THIABridgeExtContext(THIAContextMixin, bridge.BridgeExtContext):
    pass


THIABridgeContext = THIABridgeApplicationContext | THIABridgeExtContext


class THIABase(bridge.AutoShardedBot):
    owner: discord.User
    color: discord.Color
    background_tasks: set[asyncio.Task]
    msg_enabled_bullets_guilds: set[int]
    gacha_locks: collections.defaultdict[str, asyncio.Lock]

    async def get_application_context(
        self,
        interaction: discord.Interaction,
        _: type[discord.ApplicationContext] | None = None,
    ) -> THIABridgeApplicationContext:
        return await super().get_application_context(
            interaction, cls=THIABridgeApplicationContext
        )

    async def get_context(
        self, message: discord.Message, _: type[commands.Context] | None = None
    ) -> THIABridgeExtContext:
        return await super().get_context(message, cls=THIABridgeExtContext)

    def create_task(self, coro: typing.Coroutine) -> asyncio.Task:
        # see the "important" note below for why we do this (to prevent early gc)
        # https://docs.python.org/3/library/asyncio-task.html#asyncio.create_task
        task = asyncio.create_task(coro)
        self.background_tasks.add(task)
        task.add_done_callback(self.background_tasks.discard)
        return task


class Cog(commands.Cog):
    def __init__(self, bot: THIABase) -> None:
        self.bot = bot
