"""
Copyright 2021-2025 AstreaTSS.
This file is part of PYTHIA.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

import asyncio
import contextlib
import functools
import logging
import os
import subprocess
import sys
from collections import defaultdict

import interactions as ipy
import sentry_sdk
import typing_extensions as typing
from interactions.ext import hybrid_commands as hybrid
from interactions.ext import prefixed_commands as prefixed
from tortoise import Tortoise

from load_env import load_env

load_env()

import common.help_tools as help_tools
import common.models as models
import common.utils as utils
import db_settings

if typing.TYPE_CHECKING:
    import discord_typings

logger = logging.getLogger("pythiabot")
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
) -> dict[str, typing.Any] | None:
    if "log_record" in hint:
        record: logging.LogRecord = hint["log_record"]
        if "interactions" in record.name or "pythiabot" in record.name:
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


class MyHookedTask(ipy.Task):
    def on_error_sentry_hook(self: ipy.Task, error: Exception) -> None:
        scope = sentry_sdk.Scope.get_current_scope()

        if isinstance(self.callback, functools.partial):
            scope.set_tag("task", self.callback.func.__name__)
        else:
            scope.set_tag("task", self.callback.__name__)

        scope.set_tag("iteration", self.iteration)
        sentry_sdk.capture_exception(error)


# im so sorry
if utils.SENTRY_ENABLED:
    ipy.Task.on_error_sentry_hook = MyHookedTask.on_error_sentry_hook
    sentry_sdk.init(dsn=os.environ["SENTRY_DSN"], before_send=default_sentry_filter)


class PYTHIA(utils.THIABase):
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
            name="Status",
            type=ipy.ActivityType.CUSTOM,
            state="Assisting servers | pythia.astrea.cc",
        )
        await self.change_presence(activity=activity)

    @ipy.listen("resume")
    async def on_resume_func(self) -> None:
        activity = ipy.Activity(
            name="Status",
            type=ipy.ActivityType.CUSTOM,
            state="Assisting servers | pythia.astrea.cc",
        )
        await self.change_presence(activity=activity)

    # technically, this is in ipy itself now, but its easier for my purposes to do this
    @ipy.listen("raw_application_command_permissions_update")
    async def i_like_my_events_very_raw(
        self, event: ipy.events.RawGatewayEvent
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

    @ipy.listen(is_default_listener=True)
    async def on_error(self, event: ipy.events.Error) -> None:
        await utils.error_handle(event.error, ctx=event.ctx)

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


intents = ipy.Intents.new(
    guilds=True,
    guild_emojis_and_stickers=True,
    messages=True,
    reactions=True,
    message_content=True,
    guild_members=True,
)
mentions = ipy.AllowedMentions.all()

bot = PYTHIA(
    activity=ipy.Activity(
        name="Status", type=ipy.ActivityType.CUSTOM, state="Loading..."
    ),
    status=ipy.Status.IDLE,
    sync_interactions=False,  # big bots really shouldn't have this on
    sync_ext=False,
    disable_dm_commands=True,
    allowed_mentions=mentions,
    intents=intents,
    interaction_context=utils.THIAInteractionContext,
    slash_context=utils.THIASlashContext,
    modal_context=utils.THIAModalContext,
    auto_defer=ipy.AutoDefer(enabled=True, time_until_defer=0),
    message_cache=ipy.utils.TTLCache(30, 50, 150),
    channel_cache=ipy.utils.TTLCache(600, 50, 250),
    scheduled_events_cache=ipy.utils.NullCache(),
    voice_state_cache=ipy.utils.NullCache(),
    logger=logger,
)
bot.init_load = True
bot.slash_perms_cache = defaultdict(dict)
bot.mini_commands_per_scope = {}
bot.background_tasks = set()
bot.msg_enabled_bullets_guilds = set()
bot.color = ipy.Color(int(os.environ["BOT_COLOR"]))  # #723fb0 or 7487408
prefixed.setup(bot, prefixed_context=utils.THIAPrefixedContext)
hybrid.setup(bot, hybrid_context=utils.THIAHybridContext)


async def start() -> None:
    await Tortoise.init(db_settings.TORTOISE_ORM)

    async for model in models.BulletConfig.filter(
        bullets_enabled=True,
        investigation_type__not=models.InvestigationType.COMMAND_ONLY,
    ):
        bot.msg_enabled_bullets_guilds.add(model.guild_id)  # type: ignore

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
    run_method = asyncio.run

    # use uvloop if possible
    with contextlib.suppress(ImportError):
        import uvloop  # type: ignore

        run_method = uvloop.run

    if (
        utils.DOCKER_ENABLED
        and os.environ.get("DO_NOT_MIGRATE") not in utils.OS_TRUE_VALUES
    ):
        import sys

        subprocess.run(
            [sys.executable, "-m", "aerich", "update"],
            check=True,
            env={"DB_URL": os.environ["DB_URL"]},
        )

    with contextlib.suppress(KeyboardInterrupt):
        run_method(start())
