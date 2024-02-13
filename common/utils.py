"""
Copyright 2022-2024 AstreaTSS.
This file is part of Ultimate Investigator.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

import collections
import functools
import logging
import os
import traceback
import typing
from pathlib import Path

import aiohttp
import interactions as ipy
import sentry_sdk
import tansy
from interactions.ext import prefixed_commands as prefixed

import common.models as models

SENTRY_ENABLED = bool(os.environ.get("SENTRY_DSN", False))  # type: ignore

logger = logging.getLogger("uibot")


@functools.wraps(tansy.slash_command)
def manage_guild_slash_cmd(
    name: str,
    description: ipy.Absent[str] = ipy.MISSING,
) -> typing.Callable[[ipy.const.AsyncCallable], tansy.TansySlashCommand]:
    return tansy.slash_command(
        name=name,
        description=description,
        default_member_permissions=ipy.Permissions.MANAGE_GUILD,
    )


def error_embed_generate(error_msg: str) -> ipy.Embed:
    return ipy.Embed(
        title="Error",
        description=error_msg,
        color=ipy.MaterialColors.ORANGE,
        timestamp=ipy.Timestamp.utcnow(),
    )


_bot_color = ipy.Color(int(os.environ["BOT_COLOR"]))


def make_embed(description: str, *, title: str | None = None) -> ipy.Embed:
    return ipy.Embed(
        title=title,
        description=description,
        color=_bot_color,
        timestamp=ipy.Timestamp.utcnow(),
    )


async def error_handle(
    error: Exception, *, ctx: typing.Optional[ipy.BaseContext] = None
) -> None:
    if not isinstance(error, aiohttp.ServerDisconnectedError):
        if SENTRY_ENABLED:
            with sentry_sdk.configure_scope() as scope:
                if ctx:
                    scope.set_context(
                        type(ctx).__name__,
                        {
                            "args": ctx.args,  # type: ignore
                            "kwargs": ctx.kwargs,  # type: ignore
                            "message": ctx.message,
                        },
                    )
                sentry_sdk.capture_exception(error)
        else:
            traceback.print_exception(error)
            logger.error("An error occured.", exc_info=error)
    if ctx:
        if isinstance(ctx, prefixed.PrefixedContext):
            await ctx.reply(
                embed=error_embed_generate(
                    "An internal error has occured. The bot owner has been notified "
                    "and will likely fix the issue soon."
                )
            )
        elif isinstance(ctx, ipy.InteractionContext):
            await ctx.send(
                embed=error_embed_generate(
                    "An internal error has occured. The bot owner has been notified "
                    "and will likely fix the issue soon."
                ),
                ephemeral=ctx.ephemeral,
            )


async def msg_to_owner(
    bot: "UIBase",
    chunks: list[str] | list[ipy.Embed] | list[str | ipy.Embed] | str | ipy.Embed,
) -> None:
    if not isinstance(chunks, list):
        chunks = [chunks]

    # sends a message to the owner
    for chunk in chunks:
        if isinstance(chunk, ipy.Embed):
            await bot.owner.send(embeds=chunk)
        else:
            await bot.owner.send(chunk)


def line_split(content: str, split_by: int = 20) -> list[list[str]]:
    content_split = content.splitlines()
    return [
        content_split[x : x + split_by] for x in range(0, len(content_split), split_by)
    ]


def deny_mentions(user: ipy.Snowflake_Type) -> ipy.AllowedMentions:
    # generates an AllowedMentions object that only pings the user specified
    return ipy.AllowedMentions(users=[user])


def error_format(error: Exception) -> str:
    # simple function that formats an exception
    return "".join(
        traceback.format_exception(  # type: ignore
            type(error), value=error, tb=error.__traceback__
        )
    )


def file_to_ext(str_path: str, base_path: str) -> str:
    # changes a file to an import-like string
    str_path = str_path.replace(base_path, "")
    str_path = str_path.replace("/", ".")
    return str_path.replace(".py", "")


def get_all_extensions(str_path: str, folder: str = "exts") -> collections.deque[str]:
    # gets all extensions in a folder
    ext_files = collections.deque()
    loc_split = str_path.split(folder)
    base_path = loc_split[0]

    if base_path == str_path:
        base_path = base_path.replace("main.py", "")
    base_path = base_path.replace("\\", "/")

    if base_path[-1] != "/":
        base_path += "/"

    pathlist = Path(f"{base_path}/{folder}").glob("**/*.py")
    for path in pathlist:
        str_path = str(path.as_posix())
        str_path = file_to_ext(str_path, base_path)

        if str_path != "exts.db_handler":
            ext_files.append(str_path)

    return ext_files


def toggle_friendly_str(bool_to_convert: bool) -> str:
    return "on" if bool_to_convert else "off"


def yesno_friendly_str(bool_to_convert: bool) -> str:
    return "yes" if bool_to_convert else "no"


def role_check(ctx: ipy.BaseContext, role: ipy.Role) -> ipy.Role:
    top_role = ctx.guild.me.top_role

    if role > top_role:
        raise CustomCheckFailure(
            "The role provided is a role that is higher than the roles I can edit. "
            + "Please move either that role or my role so that "
            + "my role is higher than the role you want to use."
        )

    return role


class ValidRoleConverter(ipy.Converter):
    async def convert(
        self, context: ipy.InteractionContext, argument: ipy.Role
    ) -> ipy.Role:
        return role_check(context, argument)


class CustomCheckFailure(ipy.errors.BadArgument):
    # custom classs for custom prerequisite failures outside of normal command checks
    pass


class GuildMessageable(ipy.GuildChannel, ipy.MessageableMixin):
    pass


def valid_channel_check(
    channel: ipy.GuildChannel, perms: ipy.Permissions
) -> GuildMessageable:
    if not isinstance(channel, ipy.MessageableMixin):
        raise ipy.errors.BadArgument(f"Cannot send messages in {channel.name}.")

    if not perms:
        raise ipy.errors.BadArgument(f"Cannot resolve permissions for {channel.name}.")

    if (
        ipy.Permissions.VIEW_CHANNEL not in perms
    ):  # technically pointless, but who knows
        raise ipy.errors.BadArgument(f"Cannot read messages in {channel.name}.")
    elif ipy.Permissions.READ_MESSAGE_HISTORY not in perms:
        raise ipy.errors.BadArgument(f"Cannot read message history in {channel.name}.")
    elif ipy.Permissions.SEND_MESSAGES not in perms:
        raise ipy.errors.BadArgument(f"Cannot send messages in {channel.name}.")
    elif ipy.Permissions.EMBED_LINKS not in perms:
        raise ipy.errors.BadArgument(f"Cannot send embeds in {channel.name}.")

    return channel  # type: ignore


class ValidChannelConverter(ipy.Converter):
    async def convert(
        self, ctx: ipy.InteractionContext, argument: ipy.GuildText
    ) -> GuildMessageable:
        return valid_channel_check(argument, ctx.app_permissions)


async def _global_checks(ctx: ipy.BaseContext) -> bool:
    return bool(ctx.guild) if ctx.bot.is_ready else False


class Extension(ipy.Extension):
    def __new__(
        cls, bot: ipy.Client, *args: typing.Any, **kwargs: typing.Any
    ) -> "typing.Self":
        new_cls = super().__new__(cls, bot, *args, **kwargs)
        new_cls.add_ext_check(_global_checks)
        return new_cls


if typing.TYPE_CHECKING:
    import asyncio

    from interactions.ext.prefixed_commands import PrefixedInjectedClient

    from .help_tools import MiniCommand, PermissionsResolver

    class UIBase(PrefixedInjectedClient):
        owner: ipy.User
        color: ipy.Color
        background_tasks: set[asyncio.Task]
        slash_perms_cache: collections.defaultdict[int, dict[int, PermissionsResolver]]
        mini_commands_per_scope: dict[int, dict[str, MiniCommand]]

        @property
        def guild_count(self) -> int: ...
        def create_task(self, coro: typing.Coroutine) -> asyncio.Task: ...

else:

    class UIBase(ipy.Client):
        pass


class UIContextMixin:
    guild_config: typing.Optional[models.Config]
    guild_id: ipy.Snowflake

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        self.guild_config = None
        super().__init__(*args, **kwargs)

    @property
    def guild(self) -> ipy.Guild:
        return self.client.cache.get_guild(self.guild_id)  # type: ignore

    @property
    def bot(self) -> "UIBase":
        """A reference to the bot instance."""
        return self.client  # type: ignore

    async def fetch_config(self) -> models.Config:
        """
        Gets the configuration for the context's guild.

        Returns:
            GuildConfig: The guild config.
        """
        if self.guild_config:
            return self.guild_config

        config, _ = await models.Config.get_or_create(guild_id=self.guild_id)

        self.guild_config = config
        return config


class UIBaseContext(UIContextMixin, ipy.BaseContext):
    pass


class UIInteractionContext(UIContextMixin, ipy.InteractionContext):
    pass


class UISlashContext(UIContextMixin, ipy.SlashContext):
    pass
