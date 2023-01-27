import importlib

import naff

import common.models as models
import common.utils as utils


class EtcEvents(naff.Extension):
    def __init__(self, bot: utils.UIBase) -> None:
        self.bot: utils.UIBase = bot

    @naff.listen("guild_join")
    async def on_guild_join(self, event: naff.events.GuildJoin) -> None:
        if not self.bot.is_ready:
            return

        await models.Config.get_or_create(guild_id=int(event.guild_id))

    @naff.listen("guild_left")
    async def on_guild_left(self, event: naff.events.GuildLeft) -> None:
        if not self.bot.is_ready:
            return

        await models.Config.filter(guild_id=int(event.guild.id)).delete()


def setup(bot: utils.UIBase) -> None:
    importlib.reload(utils)
    EtcEvents(bot)
