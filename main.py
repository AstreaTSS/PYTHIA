"""
Copyright 2021-2024 AstreaTSS.
This file is part of Ultimate Investigator.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

import asyncio
import contextlib
import logging
import os
import sys
import typing
from collections import defaultdict

import interactions as ipy
import sentry_sdk
from interactions.ext import prefixed_commands as prefixed
from interactions.ext.sentry import HookedTask
from tortoise import Tortoise

from load_env import load_env

load_env()

import common.help_tools as help_tools
import common.models as models
import common.utils as utils
from db_settings import TORTOISE_ORM

if typing.TYPE_CHECKING:
    import discord_typings

logger = logging.getLogger("uibot")
logger.setLevel(logging.INFO)
handler = logging.FileHandler(
    filename=os.environ["LOG_FILE_PATH"], encoding="utf-8", mode="a"
)
handler.setFormatter(
    logging.Formatter("%(asctime)s:%(levelname)s:%(name)s: %(message)s")
)
logger.addHandler(handler)
logger.addHandler(logging.StreamHandler(sys.stdout))


def default_sentry_filter(
    event: dict[str, typing.Any], hint: dict[str, typing.Any]
) -> typing.Optional[dict[str, typing.Any]]:
    if "log_record" in hint:
        record: logging.LogRecord = hint["log_record"]
        if "interactions" in record.name or "uibot" in record.name:
            # there are some logging messages that are not worth sending to sentry
            if ": 403" in record.message:
                return None
            if ": 404" in record.message:
                return None
            if record.message.startswith("Ignoring exception in "):
                return None
            if record.message.startswith("Unsupported channel type for "):
                # please shut up
                return None

    if "exc_info" in hint:
        exc_type, exc_value, tb = hint["exc_info"]
        if isinstance(exc_value, KeyboardInterrupt):
            #  We don't need to report a ctrl+c
            return None
    return event


# im so sorry
if utils.SENTRY_ENABLED:
    ipy.Task.on_error_sentry_hook = HookedTask.on_error_sentry_hook
    sentry_sdk.init(dsn=os.environ["SENTRY_DSN"], before_send=default_sentry_filter)


class UltimateInvestigator(utils.UIBase):
    @ipy.listen("ready")
    async def on_ready(self) -> None:
        utcnow = ipy.Timestamp.utcnow()
        time_format = f"<t:{int(utcnow.timestamp())}:f>"

        connect_msg = (
            f"Logged in at {time_format}!"
            if self.init_load
            else f"Reconnected at {time_format}!"
        )

        await self.owner.send(connect_msg)

        self.init_load = False

        activity = ipy.Activity(
            name="Splash Text",
            type=ipy.ActivityType.CUSTOM,
            state="Watching for Truth Bullets!",
        )
        await self.change_presence(activity=activity)

    @ipy.listen("resume")
    async def on_resume_func(self) -> None:
        activity = ipy.Activity(
            name="Splash Text",
            type=ipy.ActivityType.CUSTOM,
            state="Watching for Truth Bullets!",
        )
        await self.change_presence(activity=activity)

    # technically, this is in ipy itself now, but its easier for my purposes to do this
    @ipy.listen("raw_application_command_permissions_update")
    async def i_like_my_events_very_raw(
        self, event: ipy.events.RawGatewayEvent
    ) -> None:
        data: "discord_typings.GuildApplicationCommandPermissionData" = event.data  # type: ignore

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

    @ipy.listen(is_default_listener=True)
    async def on_error(self, event: ipy.events.Error) -> None:
        await utils.error_handle(event.error, ctx=event.ctx)

    @property
    def guild_count(self) -> int:
        return len(self.user._guild_ids or ())

    def create_task(self, coro: typing.Coroutine) -> asyncio.Task:
        # see the "important" note below for why we do this (to prevent early gc)
        # https://docs.python.org/3/library/asyncio-task.html#asyncio.create_task
        task = asyncio.create_task(coro)
        self.background_tasks.add(task)
        task.add_done_callback(self.background_tasks.discard)
        return task

    async def stop(self) -> None:
        await Tortoise.close_connections()
        await super().stop()


# honestly don't think i need the members stuff
intents = ipy.Intents.new(
    guilds=True,
    guild_emojis_and_stickers=True,
    messages=True,
    reactions=True,
    message_content=True,
)
mentions = ipy.AllowedMentions.all()

bot = UltimateInvestigator(
    activity=ipy.Activity(
        name="Status", type=ipy.ActivityType.CUSTOM, state="Loading..."
    ),
    status=ipy.Status.IDLE,
    sync_interactions=False,  # big bots really shouldn't have this on
    sync_ext=False,
    disable_dm_commands=True,
    allowed_mentions=mentions,
    intents=intents,
    interaction_context=utils.UIInteractionContext,
    slash_context=utils.UISlashContext,
    auto_defer=ipy.AutoDefer(enabled=True, time_until_defer=0),
    logger=logger,
)
bot.init_load = True
bot.slash_perms_cache = defaultdict(dict)
bot.mini_commands_per_scope = {}
bot.background_tasks = set()
bot.enabled_bullets_guilds = set()
bot.color = ipy.Color(int(os.environ["BOT_COLOR"]))  # #D92C43 or 14232643
prefixed.setup(bot)


async def start() -> None:
    await Tortoise.init(TORTOISE_ORM)

    async for model in models.Config.filter(bullets_enabled=True):
        bot.enabled_bullets_guilds.add(model.guild_id)

    ext_list = utils.get_all_extensions(os.environ["DIRECTORY_OF_FILE"])
    for ext in ext_list:
        if "voting" in ext and not utils.VOTING_ENABLED:
            continue

        try:
            bot.load_extension(ext)
        except ipy.errors.ExtensionLoadException:
            raise

    await bot.astart(os.environ["MAIN_TOKEN"])


if __name__ == "__main__":
    loop_factory = None

    with contextlib.suppress(ImportError):
        import uvloop  # type: ignore

        loop_factory = uvloop.new_event_loop

    with asyncio.Runner(loop_factory=loop_factory) as runner:
        runner.run(start())
