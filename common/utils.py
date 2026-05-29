"""
Copyright 2021-2026 AstreaTSS.
This file is part of PYTHIA.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

import logging
import os
import platform
import re
import textwrap
import traceback
from pathlib import Path

import aiohttp
import discord
import sentry_sdk
import typing_extensions as typing
from discord.ext import commands

from common.core import *

OS_TRUE_VALUES = frozenset({"true", "True", "TRUE", "t", "T", "1"})
SENTRY_ENABLED = bool(os.environ.get("SENTRY_DSN", False))  # type: ignore
VOTING_ENABLED = bool(os.environ.get("TOP_GG_TOKEN") or os.environ.get("DBL_TOKEN"))
DOCKER_ENABLED = os.environ.get("DOCKER_MODE") in OS_TRUE_VALUES
BOT_COLOR = discord.Color(int(os.environ["BOT_COLOR"]))
MAX_DICE_ENTRIES: typing.Final[int] = 50
PYTHON_VERSION = platform.python_version_tuple()
PYTHON_IMPLEMENTATION = platform.python_implementation()

logger = logging.getLogger("discord")

CogT = typing.TypeVar("CogT", bound=discord.Cog)

if typing.TYPE_CHECKING:
    ChannelT = typing.TypeVar("ChannelT", bound=discord.abc.MessageableChannel)
    SlashCommandT = typing.TypeVar("SlashCommandT", bound=discord.SlashCommand)

SINGLE_QUOTE_REGEX = re.compile(r"‘|’")  # noqa: RUF001
DOUBLE_QUOTE_REGEX = re.compile(r"“|”|„|‟|⹂|〝|〞|＂")  # noqa: RUF001
HTTP_URL_REGEX = re.compile(
    r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
)


def toggle_friendly_str(bool_to_convert: bool) -> typing.Literal["on", "off"]:
    return "on" if bool_to_convert else "off"


def yesno_friendly_str(bool_to_convert: bool) -> typing.Literal["yes", "no"]:
    return "yes" if bool_to_convert else "no"


def replace_smart_punc(text: str) -> str:
    text = SINGLE_QUOTE_REGEX.sub("'", text)
    return DOUBLE_QUOTE_REGEX.sub('"', text)


def short_string(string: str, length: int = 25) -> str:
    new_description = textwrap.shorten(string, length, placeholder="...")
    if new_description == "...":  # word is too long, lets manually cut it
        return f"{string[:length-3].strip()}..."
    return new_description


def user_string(user: discord.User | discord.Member) -> str:
    if isinstance(user, discord.Member):
        user = user._user

    if user.is_migrated:
        return f"@{user.name}"
    return f"{user.name}#{user.discriminator}"


def parse_hex_number(hex_number: str) -> discord.Color:
    if hex_number.startswith("#"):
        hex_number = hex_number[1:]

    arg = "".join(i * 2 for i in hex_number) if len(hex_number) == 3 else hex_number
    value = int(arg, base=16)
    return discord.Color(value=value)


def convert_to_bool(argument: str) -> bool:
    lowered = argument.lower()
    if lowered in {"yes", "y", "true", "t", "1", "enable", "on"}:
        return True
    if lowered in {"no", "n", "false", "f", "0", "disable", "off"}:
        return False
    raise commands.BadArgument(f"{argument} is not a recognised boolean option.")


def file_to_ext(str_path: str, base_path: str) -> str:
    # changes a file to an import-like string
    str_path = str_path.replace(base_path, "")
    str_path = str_path.replace("/", ".")
    return str_path.replace(".py", "")


def get_all_extensions(str_path: str, folder: str = "exts") -> list[str]:
    # gets all extensions in a folder
    ext_files: list[str] = []
    location_split = str_path.split(folder)
    base_path = location_split[0]

    if base_path == str_path:
        base_path = base_path.replace("main.py", "")
    base_path = base_path.replace("\\", "/")

    if base_path[-1] != "/":
        base_path += "/"

    pathlist = Path(f"{base_path}/{folder}").glob("**/*.py")
    for path in pathlist:
        str_path = str(path.as_posix())
        str_path = file_to_ext(str_path, base_path)
        ext_files.append(str_path)

    return ext_files


def quick_view(
    *items: discord.ui.ViewItem,
) -> discord.ui.DesignerView:
    return discord.ui.DesignerView(*items, store=False)


def make_container(
    description: str, *, title: str | None = None
) -> discord.ui.Container:
    return discord.ui.Container(
        discord.ui.TextDisplay(
            description if not title else f"# {title}\n{description}"
        ),
        color=BOT_COLOR,
    )


def make_view(description: str, *, title: str | None = None) -> discord.ui.DesignerView:
    return quick_view(
        make_container(description, title=title),
    )


def error_view(error_msg: str) -> discord.ui.DesignerView:
    return quick_view(
        discord.ui.Container(
            discord.ui.TextDisplay(f"# Error\n{error_msg}"),
            color=parse_hex_number("#FF9800"),
        )
    )


def role_check(ctx: THIASlashContext, role: discord.Role) -> discord.Role:
    top_role = ctx.guild.me.top_role

    if role > top_role:
        raise CustomCheckFailure(
            "The role provided is a role that is higher than the roles I can edit. "
            + "Please move either that role or my role so that "
            + "my role is higher than the role you want to use."
        )

    return role


def valid_channel_check(channel: "ChannelT", perms: discord.Permissions) -> "ChannelT":
    if not perms:
        raise commands.BadArgument(f"Cannot resolve permissions for {channel.name}.")

    if not perms.is_superset(discord.Permissions(view_channel=True)):
        raise commands.BadArgument(f"Cannot read messages in {channel.name}.")
    elif not perms.is_superset(discord.Permissions(read_message_history=True)):
        raise commands.BadArgument(f"Cannot read message history in {channel.name}.")
    elif not perms.is_superset(discord.Permissions(embed_links=True)):
        raise commands.BadArgument(f"Cannot send embeds in {channel.name}.")
    elif not perms.is_superset(discord.Permissions(attach_files=True)):
        raise commands.BadArgument(f"Cannot attach files in {channel.name}.")

    if isinstance(channel, discord.Thread):
        if not perms.is_superset(discord.Permissions(send_messages_in_threads=True)):
            raise commands.BadArgument(f"Cannot send messages in {channel.name}.")
    elif not perms.is_superset(discord.Permissions(send_messages=True)):
        raise commands.BadArgument(f"Cannot send messages in {channel.name}.")

    return channel


def alias(
    command: "SlashCommandT",
    *,
    name: str,
    description: str,
    parent: discord.SlashCommandGroup | None = None,
) -> "SlashCommandT":
    parent = parent or command.parent
    new_cmd = command.copy()
    new_cmd.name = name
    new_cmd.description = description
    new_cmd.parent = parent

    if parent:
        parent.add_command(new_cmd)
    return new_cmd


async def error_handle(
    error: Exception, *, ctx: THIABridgeContext | discord.Interaction | None = None
) -> None:
    if not isinstance(error, aiohttp.ServerDisconnectedError):
        if SENTRY_ENABLED:
            scope = sentry_sdk.Scope.get_current_scope()
            if ctx:
                if isinstance(ctx, THIABridgeApplicationContext):
                    scope.set_context(
                        type(ctx).__name__,
                        {
                            "options": ctx.options,
                            "message": ctx.message,
                        },
                    )
                elif isinstance(ctx, THIABridgeExtContext):
                    scope.set_context(
                        type(ctx).__name__,
                        {
                            "args": ctx.args,
                            "kwargs": ctx.kwargs,
                            "message": ctx.message,
                        },
                    )
                elif isinstance(ctx, discord.Interaction):
                    scope.set_context(
                        type(ctx).__name__,
                        {
                            "data": ctx.data,
                            "type": ctx.type,
                        },
                    )
            sentry_sdk.capture_exception(error)
        else:
            traceback.print_exception(error)
            logger.error("An error occured.", exc_info=error)
    if ctx and isinstance(
        ctx,
        (THIABridgeApplicationContext, THIABridgeExtContext, discord.Interaction),
    ):
        await ctx.respond(
            view=error_view(
                "An internal error has occured. The bot owner has been notified and"
                " will likely fix the issue soon."
            )
        )


def parse_modal_responses(view: discord.ui.DesignerModal) -> dict[str, typing.Any]:
    return {
        child.item.custom_id: getattr(
            child.item, "values", getattr(child.item, "value", None)
        )
        for child in view.children
        if isinstance(child, discord.ui.Label)
    }


def button_handler(
    custom_id: str | None = None,
    custom_id_prefix: str | None = None,
) -> typing.Callable[
    [typing.Callable[[CogT, Interaction, str], typing.Awaitable[None]]],
    typing.Callable[[CogT, Interaction], typing.Awaitable[None]],
]:
    if not custom_id and not custom_id_prefix:
        raise ValueError("Either custom_id or custom_id_prefix must be provided.")
    if custom_id and custom_id_prefix:
        raise ValueError("custom_id and custom_id_prefix cannot both be provided.")

    def inner(
        func: typing.Callable[[CogT, Interaction, str], typing.Awaitable[None]],
    ) -> typing.Callable[[CogT, Interaction], typing.Awaitable[None]]:
        async def wrapper(self: CogT, inter: Interaction) -> None:
            if inter.type != discord.InteractionType.component or not inter.data:
                return

            if inter.data["component_type"] != discord.ComponentType.button.value:
                return

            if custom_id and inter.data["custom_id"] != custom_id:
                return
            if custom_id_prefix and not inter.data["custom_id"].startswith(
                custom_id_prefix
            ):
                return

            try:
                await func(
                    self,
                    inter,
                    inter.data["custom_id"],
                )
            except Exception as error:
                inter.client.dispatch("view_error", error, None, inter)

        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return discord.Cog.listener("on_interaction")(wrapper)

    return inner


class ReplaceSmartPuncConverter(commands.Converter):
    async def convert(self, _: THIABridgeContext, argument: str) -> str:
        return replace_smart_punc(argument)


BadArgument = commands.BadArgument


class CustomCheckFailure(discord.CheckFailure):
    # custom class for custom prerequisite failures outside of normal command checks
    pass
