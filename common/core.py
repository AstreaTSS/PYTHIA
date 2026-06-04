"""
Copyright 2021-2026 AstreaTSS.
This file is part of PYTHIA.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

import asyncio
import collections
import datetime

import discord
import typing_extensions as typing
from discord.ext import bridge, commands

import common.models as models

__all__ = (
    "Cog",
    "Interaction",
    "THIABase",
    "THIABridgeApplicationContext",
    "THIABridgeContext",
    "THIABridgeExtContext",
    "THIAContextMixin",
    "THIASlashContext",
)

CoroutineT = typing.TypeVar("CoroutineT", bound=typing.Coroutine)


class THIAContextMixin:
    guild_config: models.GuildConfig | None
    ephemeral: bool
    guild_id: int
    guild: discord.Guild
    bot: "THIABase"

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        self.guild_config = None
        self.ephemeral = False
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
    channel_id: int

    async def defer(self, *, ephemeral: bool = False, invisible: bool = True) -> None:
        await super().defer(ephemeral=ephemeral, invisible=invisible)
        self.ephemeral = ephemeral

    if typing.TYPE_CHECKING:
        # very funny way to make sure not to use the send method
        async def send(self) -> None: ...


THIASlashContext = THIABridgeApplicationContext


class THIABridgeExtContext(THIAContextMixin, bridge.BridgeExtContext):
    @property
    def guild_id(self) -> int:
        return self.guild.id


THIABridgeContext = THIABridgeApplicationContext | THIABridgeExtContext


class THIABase(bridge.AutoShardedBot):
    owner: discord.User
    color: discord.Color
    start_time: datetime.datetime
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

    @property
    def guild_count(self) -> int:
        return len(self._connection._guilds)

    def get_shard_id(self, guild_id: "discord.Snowflake") -> int:
        return (int(guild_id) >> 22) % len(self.shards.keys())

    def create_task(self, coro: CoroutineT) -> asyncio.Task[CoroutineT]:
        # see the "important" note below for why we do this (to prevent early gc)
        # https://docs.python.org/3/library/asyncio-task.html#asyncio.create_task
        task = asyncio.create_task(coro)
        self.background_tasks.add(task)
        task.add_done_callback(self.background_tasks.discard)
        return task

    def mention_command(self, name: str) -> str:
        cmd: discord.SlashCommand | None = self.get_application_command(
            name, type=discord.SlashCommand
        )
        if cmd is None:
            raise ValueError(f"No command named {name} found.")
        return cmd.mention

    def sync_command_info_task(self) -> None:
        self.create_task(self._sync_command_info())

    async def getch_channel(
        self, channel_id: int
    ) -> discord.abc.GuildChannel | discord.abc.PrivateChannel | discord.Thread | None:
        if chan := self.get_channel(channel_id):
            return chan

        try:
            return await self.fetch_channel(channel_id)
        except discord.HTTPException:
            return None

    async def _sync_command_info(self) -> None:
        await self.wait_until_ready()

        commands = await self.http.get_global_commands(self.user.id)

        for command in commands:
            cmd = discord.utils.get(
                self.pending_application_commands,
                name=command["name"],
                guild_ids=None,
                type=command.get("type"),
            )
            if cmd:
                cmd.id = command["id"]
                self._application_commands[cmd.id] = cmd


class Cog(discord.Cog):
    def __init__(self, bot: THIABase) -> None:
        self.bot = bot


# more of a typehint thing than anything else
class Interaction(discord.Interaction):
    guild_id: int
    guild: discord.Guild

    @property
    def client(self) -> THIABase:
        return super().client  # type: ignore
