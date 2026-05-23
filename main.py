"""
Copyright 2021-2026 AstreaTSS.
This file is part of PYTHIA.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

import asyncio
import contextlib
import datetime
import logging
import os
import subprocess
import sys
from collections import defaultdict

import discord
import humanize
import ragwort
import sentry_sdk
import typing_extensions as typing
from discord.ext import commands, tasks
from tortoise import Tortoise

from load_env import load_env

load_env()

import common.models as models
import common.utils as utils
import db_settings

logger = logging.getLogger("discord")
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
        if "discord" in record.name:
            # TODO: find errors to ignore
            pass

    if "exc_info" in hint:
        _, exc_value, __ = hint["exc_info"]
        if isinstance(exc_value, KeyboardInterrupt):
            #  We don't need to report a ctrl+c
            return None
    return event


class HookedTask(tasks.Loop):
    async def _error(self: tasks.Loop, *args: typing.Any) -> None:
        error: Exception = args[-1]
        await utils.error_handle(error)


tasks.Loop._error = HookedTask._error
if utils.SENTRY_ENABLED:
    sentry_sdk.init(dsn=os.environ["SENTRY_DSN"], before_send=default_sentry_filter)


class PYTHIA(utils.THIABase):
    async def on_ready(self) -> None:
        if not self.owner:
            app_info = await self.application_info()
            self.owner = app_info.owner  # type: ignore

        utcnow = discord.utils.utcnow()
        if not self.start_time:
            self.start_time = utcnow
        time_format = f"<t:{int(utcnow.timestamp())}:f>"

        connect_msg = (
            f"Logged in at {time_format}!"
            if self.init_load
            else f"Reconnected at {time_format}!"
        )

        await self.owner.send(connect_msg)

        self.init_load = False

        activity = discord.CustomActivity(
            name="Assisting servers | pythia.astrea.cc",
        )
        await self.change_presence(activity=activity)

    async def on_resumed(self) -> None:
        activity = discord.CustomActivity(
            name="Assisting servers | pythia.astrea.cc",
        )
        await self.change_presence(activity=activity)

    async def on_error(self, _: str, *__: typing.Any, **___: typing.Any) -> None:
        error: Exception = sys.exc_info()[1]
        await utils.error_handle(error)

    async def _pythia_error(
        self, ctx: utils.THIABridgeContext | discord.Interaction, error: Exception
    ) -> None:
        if isinstance(error, commands.CommandOnCooldown):
            delta_wait = datetime.timedelta(seconds=error.retry_after)
            await ctx.respond(
                view=utils.error_view(
                    "You're doing that command too fast! Try again in"
                    f" `{humanize.precisedelta(delta_wait, format='%0.1f')}`."
                )
            )

        elif isinstance(error, utils.CustomCheckFailure | commands.BadArgument):
            await ctx.respond(view=utils.error_view(str(error)))
        elif isinstance(error, discord.CheckFailure):
            if ctx.guild_id:
                await ctx.respond(
                    view=utils.error_view(
                        "You do not have the proper permissions to use that command."
                    )
                )
        else:
            await utils.error_handle(error, ctx=ctx)

    async def on_view_error(
        self, error: Exception, _: discord.ui.ViewItem, interaction: discord.Interaction
    ) -> None:
        await self._pythia_error(interaction, error)

    async def on_modal_error(
        self, error: Exception, interaction: discord.Interaction
    ) -> None:
        await self._pythia_error(interaction, error)

    async def on_application_command_error(
        self, context: utils.THIASlashContext, exception: discord.DiscordException
    ) -> None:
        if context.command and getattr(context.command, "on_error", None):
            return

        if context.cog and context.cog.__class__._get_overridden_method(
            context.cog.cog_command_error
        ):
            return

        await self._pythia_error(context, exception)

    async def on_command_error(
        self, context: utils.THIABridgeExtContext, exception: commands.CommandError
    ) -> None:
        if context.command and getattr(context.command, "on_error", None):
            return

        if context.cog and context.cog.__class__._get_overridden_method(
            context.cog.cog_command_error
        ):
            return
        await self._pythia_error(context, exception)

    async def close(self) -> None:
        await super().close()
        await Tortoise.close_connections()


intents = discord.Intents(
    guilds=True,
    members=True,
    emojis_and_stickers=True,
    messages=True,
    message_content=True,
)
mentions = discord.AllowedMentions.none()


async def start() -> None:
    # have to create it here because of loop shienanigans
    bot = PYTHIA(
        intents=intents,
        allowed_mentions=mentions,
        status=discord.Status.idle,
        activity=discord.CustomActivity(
            name="Loading...",
        ),
        default_command_contexts={
            discord.InteractionContextType.guild,
        },
        default_command_integration_types={
            discord.IntegrationType.guild_install,
        },
        auto_sync_commands=False,
        case_insensitive=True,
        help_command=None,
        max_messages=100,
        chunk_guilds_at_startup=False,
        cache_default_sounds=False,
    )
    ragwort.setup_auto_defer(bot, default=True)
    bot.init_load = True
    bot.start_time = None
    bot.owner = None
    bot.background_tasks = set()
    bot.msg_enabled_bullets_guilds = set()
    bot.gacha_locks = defaultdict(asyncio.Lock)
    bot.color = discord.Color(int(os.environ["BOT_COLOR"]))  # #723fb0 or 7487408

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
        except discord.ExtensionError:
            raise

    try:
        await bot.start(os.environ["MAIN_TOKEN"])
    finally:
        if not bot.is_closed():
            await bot.close()


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
            [sys.executable, "-m", "tortoise", "migrate"],
            check=True,
            env={"DB_URL": os.environ["DB_URL"]},
        )

    with contextlib.suppress(KeyboardInterrupt):
        run_method(start())
