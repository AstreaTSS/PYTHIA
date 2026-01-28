"""
Copyright 2021-2026 AstreaTSS.
This file is part of PYTHIA.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

import importlib

import interactions as ipy

import common.models as models
import common.utils as utils


class EtcEvents(ipy.Extension):
    @ipy.listen("guild_join")
    async def on_guild_join(self, event: ipy.events.GuildJoin) -> None:
        if not self.bot.is_ready:
            return

        await models.GuildConfig.get_or_create(guild_id=event.guild_id)

    @ipy.listen("guild_left")
    async def on_guild_left(self, event: ipy.events.GuildLeft) -> None:
        if not self.bot.is_ready:
            return

        await models.GuildConfig.filter(guild_id=int(event.guild_id)).delete()
        await models.TruthBullet.filter(guild_id=int(event.guild_id)).delete()


def setup(bot: utils.THIABase) -> None:
    importlib.reload(utils)
    EtcEvents(bot)
