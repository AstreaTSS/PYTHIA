import asyncio
import contextlib
import logging
import os
import typing
from collections import defaultdict

import discord_typings
import naff
from dotenv import load_dotenv
from tortoise import Tortoise
from websockets.exceptions import ConnectionClosedOK

import common.help_tools as help_tools
import common.utils as utils

load_dotenv()


logger = logging.getLogger("uibot")
logger.setLevel(logging.INFO)
handler = logging.FileHandler(
    filename=os.environ["LOG_FILE_PATH"], encoding="utf-8", mode="a"
)
handler.setFormatter(
    logging.Formatter("%(asctime)s:%(levelname)s:%(name)s: %(message)s")
)
logger.addHandler(handler)


class UltimateInvestigator(utils.UIBase):
    @naff.listen("ready")
    async def on_ready(self):
        utcnow = naff.Timestamp.utcnow()
        time_format = f"<t:{int(utcnow.timestamp())}:f>"

        connect_msg = (
            f"Logged in at {time_format}!"
            if self.init_load == True
            else f"Reconnected at {time_format}!"
        )

        await self.owner.send(connect_msg)

        self.init_load = False

        activity = naff.Activity.create(
            name="for Truth Bullets", type=naff.ActivityType.WATCHING
        )

        try:
            await self.change_presence(activity=activity)
        except ConnectionClosedOK:
            await utils.msg_to_owner(bot, "Reconnecting...")

    @naff.listen("resume")
    async def on_resume_func(self):
        activity = naff.Activity.create(
            name="for Truth Bullets", type=naff.ActivityType.WATCHING
        )
        await self.change_presence(activity=activity)

    # technically, this is in naff itself now, but its easier for my purposes to do this
    @naff.listen("raw_application_command_permissions_update")
    async def i_like_my_events_very_raw(
        self, event: naff.events.RawGatewayEvent
    ) -> None:
        data: discord_typings.GuildApplicationCommandPermissionData = event.data  # type: ignore

        guild_id = int(data["guild_id"])

        if not self.slash_perms_cache[guild_id]:
            await help_tools.process_bulk_slash_perms(self, guild_id)
            return

        cmds = help_tools.get_commands_for_scope_by_ids(self, guild_id)
        if cmd := cmds.get(int(data["id"])):
            self.slash_perms_cache[guild_id][
                int(data["id"])
            ] = help_tools.PermissionsResolver(
                cmd.default_member_permissions, guild_id, data["permissions"]  # type: ignore
            )

    @naff.listen(is_default_listener=True)
    async def on_error(self, event: naff.events.Error) -> None:
        await utils.error_handle(self, event.error)

    def load_extension(
        self, name: str, package: str | None = None, **load_kwargs: typing.Any
    ) -> None:
        super().load_extension(name, package, **load_kwargs)

        # naff forgets to do this lol
        if not self.sync_ext and self._ready.is_set():
            asyncio.create_task(self._cache_interactions(warn_missing=False))

    async def stop(self):
        await Tortoise.close_connections()
        await super().stop()


# honestly don't think i need the members stuff
intents = naff.Intents.new(
    default=False,
    guilds=True,
    guild_emojis_and_stickers=True,
    messages=True,
    reactions=True,
    guild_message_content=True,
)
mentions = naff.AllowedMentions.all()

bot = UltimateInvestigator(
    sync_interactions=False,  # big bots really shouldn't have this on
    sync_ext=False,
    disable_dm_commands=True,
    allowed_mentions=mentions,
    intents=intents,
    interaction_context=utils.InvestigatorContext,
    auto_defer=naff.AutoDefer(enabled=True, time_until_defer=0),
    logger=logger,
)
bot.init_load = True
bot.slash_perms_cache = defaultdict(dict)
bot.mini_commands_per_scope = {}
bot.color = naff.Color(int(os.environ["BOT_COLOR"]))  # #D92C43 or 14232643


async def start() -> None:
    await Tortoise.init(
        db_url=os.environ.get("DB_URL"), modules={"models": ["common.models"]}
    )

    ext_list = utils.get_all_extensions(os.environ["DIRECTORY_OF_FILE"])
    for ext in ext_list:
        try:
            bot.load_extension(ext)
        except naff.errors.ExtensionLoadException:
            raise

    await bot.astart(os.environ["MAIN_TOKEN"])


if __name__ == "__main__":
    loop_factory = None

    with contextlib.suppress(ImportError):
        import uvloop  # type: ignore

        loop_factory = uvloop.new_event_loop

    with asyncio.Runner(loop_factory=loop_factory) as runner:
        asyncio.run(start())
