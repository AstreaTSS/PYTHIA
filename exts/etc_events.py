"""
Copyright 2021-2026 AstreaTSS.
This file is part of PYTHIA.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

import importlib

import discord

import common.models as models
import common.utils as utils


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


def setup(bot: utils.THIABase) -> None:
    importlib.reload(utils)
    EtcEvents(bot)
