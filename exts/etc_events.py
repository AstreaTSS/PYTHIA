"""
Copyright 2021-2026 AstreaTSS.
This file is part of PYTHIA.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

import functools
import importlib
import logging
import typing

import discord

import common.models as models
import common.utils as utils

logger = logging.getLogger("discord")


async def fake_callback(
    command: discord.SlashCommand,
    _: typing.Any,
    __: typing.Any,
    **kwargs: typing.Any,
) -> None:
    if typing.TYPE_CHECKING:
        assert isinstance(command, discord.SlashCommand)

    for o in command.options:
        if o._parameter_name != o.name:
            kwargs[o.name] = kwargs[o._parameter_name]
            kwargs.pop(o._parameter_name)

    logger.info(
        f"Command Called: {command.qualified_name} with {kwargs = }"  # noqa: G004
    )


class EtcEvents(utils.Cog):
    @discord.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild) -> None:
        if not self.bot.is_ready():
            return

        await models.GuildConfig.get_or_create(guild_id=guild.id)

    @discord.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild) -> None:
        if not self.bot.is_ready():
            return

        await models.GuildConfig.filter(guild_id=guild.id).delete()
        await models.TruthBullet.filter(guild_id=guild.id).delete()

    @discord.Cog.listener("on_application_command_completion")
    async def command_usage_collector(self, ctx: discord.ApplicationContext) -> None:
        if not ctx.command or not isinstance(ctx.command, discord.SlashCommand):
            return

        copy = ctx.command.copy()
        copy._callback = functools.partial(fake_callback, ctx.command)
        copy._cog = ctx.command._cog
        copy.options = ctx.command.options
        await copy._invoke(ctx)


def setup(bot: utils.THIABase) -> None:
    importlib.reload(utils)
    bot.add_cog(EtcEvents(bot))
