import importlib

import interactions as ipy

import common.models as models
import common.utils as utils


class EtcEvents(ipy.Extension):
    def __init__(self, bot: utils.UIBase) -> None:
        self.bot: utils.UIBase = bot

    @ipy.listen("guild_join")
    async def on_guild_join(self, event: ipy.events.GuildJoin) -> None:
        if not self.bot.is_ready:
            return

        await models.Config.get_or_create(guild_id=int(event.guild_id))

    @ipy.listen("guild_left")
    async def on_guild_left(self, event: ipy.events.GuildLeft) -> None:
        if not self.bot.is_ready:
            return

        await models.Config.filter(guild_id=int(event.guild_id)).delete()


def setup(bot: utils.UIBase) -> None:
    importlib.reload(utils)
    EtcEvents(bot)
