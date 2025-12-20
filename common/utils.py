"""
Copyright 2021-2025 AstreaTSS.
This file is part of PYTHIA.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

import functools
import logging
import os
import traceback
from copy import copy
from pathlib import Path

import aiohttp
import interactions as ipy
import sentry_sdk
import tansy
import typing_extensions as typing
from interactions.ext import hybrid_commands as hybrid
from interactions.ext import prefixed_commands as prefixed
from interactions.ext.hybrid_commands.hybrid_slash import RangeConverter
from tansy.slash_commands import tansy_parse_parameters

import common.models as models

OS_TRUE_VALUES = frozenset({"true", "True", "TRUE", "t", "T", "1"})
SENTRY_ENABLED = bool(os.environ.get("SENTRY_DSN", False))  # type: ignore
VOTING_ENABLED = bool(os.environ.get("TOP_GG_TOKEN") or os.environ.get("DBL_TOKEN"))
DOCKER_ENABLED = os.environ.get("DOCKER_MODE") in OS_TRUE_VALUES
BOT_COLOR = ipy.Color(int(os.environ["BOT_COLOR"]))
MAX_DICE_ENTRIES: typing.Final[int] = 50

logger = logging.getLogger("pythiabot")


SlashCommandT = typing.TypeVar("SlashCommandT", bound=ipy.SlashCommand)


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


def _generate_parse_parameters(
    command: tansy.TansySlashCommand,
    other_cmd: tansy.TansySlashCommand,
) -> typing.Callable[[], None]:
    def _parse_parameters() -> None:
        if other_cmd._inspect_signature:
            command._inspect_signature = other_cmd._inspect_signature
        if other_cmd.options:
            command.options = other_cmd.options
        tansy_parse_parameters(command)

    return _parse_parameters


def alias(
    command: SlashCommandT,
    name: str,
    description: str,
    *,
    base_command: ipy.SlashCommand | None = None,
) -> SlashCommandT:
    alias = copy(command)

    if base_command:
        alias.description = base_command.description
        alias.dm_permission = base_command.dm_permission
        alias.default_member_permissions = base_command.default_member_permissions
        alias.scopes = base_command.scopes
        alias.integration_types = base_command.integration_types
        alias.contexts = base_command.contexts

    names = name.split()

    if len(names) == 1:
        alias.name = name
        alias.description = description
    elif len(names) == 2:
        alias.name = names[0]
        alias.sub_cmd_name = names[1]
        alias.sub_cmd_description = description
    else:
        alias.name = names[0]
        alias.group_name = names[1]
        alias.sub_cmd_name = names[2]
        alias.sub_cmd_description = description

    # i heard you like references
    # here we're abusing them so editing the original version's attributes
    # also affects the alias, which is nice
    alias.checks = command.checks
    alias.options = command.options
    alias.autocomplete_callbacks = command.autocomplete_callbacks

    if isinstance(command, tansy.TansySlashCommand):
        alias.parameters = command.parameters
        alias._parse_parameters = _generate_parse_parameters(alias, command)
        command._parse_parameters = _generate_parse_parameters(command, alias)
    else:
        alias.parameters = command.parameters.copy()

    return alias


def error_embed_generate(error_msg: str) -> ipy.Embed:
    return ipy.Embed(
        title="Error",
        description=error_msg,
        color=ipy.MaterialColors.ORANGE,
        timestamp=ipy.Timestamp.utcnow(),
    )


def make_embed(description: str, *, title: str | None = None) -> ipy.Embed:
    return ipy.Embed(
        title=title,
        description=description,
        color=BOT_COLOR,
        timestamp=ipy.Timestamp.utcnow(),
    )


async def error_handle(error: Exception, *, ctx: ipy.BaseContext | None = None) -> None:
    if not isinstance(error, aiohttp.ServerDisconnectedError):
        if SENTRY_ENABLED:
            scope = sentry_sdk.Scope.get_current_scope()
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
    bot: "THIABase",
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


def toggle_friendly_str(bool_to_convert: bool) -> typing.Literal["on", "off"]:
    return "on" if bool_to_convert else "off"


def yesno_friendly_str(bool_to_convert: bool) -> typing.Literal["yes", "no"]:
    return "yes" if bool_to_convert else "no"


def convert_to_bool(argument: str) -> bool:
    lowered = argument.lower()
    if lowered in {"yes", "y", "true", "t", "1", "enable", "on"}:
        return True
    if lowered in {"no", "n", "false", "f", "0", "disable", "off"}:
        return False
    raise ipy.errors.BadArgument(f"{argument} is not a recognised boolean option.")


def partial_channel(bot: "THIABase", channel_id: ipy.Snowflake_Type) -> ipy.GuildText:
    return ipy.GuildText(
        client=bot, id=ipy.to_snowflake(channel_id), type=ipy.ChannelType.GUILD_TEXT
    )  # type: ignore


def role_check(ctx: ipy.BaseContext, role: ipy.Role) -> ipy.Role:
    top_role = ctx.guild.me.top_role

    if role > top_role:
        raise CustomCheckFailure(
            "The role provided is a role that is higher than the roles I can edit. "
            + "Please move either that role or my role so that "
            + "my role is higher than the role you want to use."
        )

    return role


AsyncT = typing.TypeVar("AsyncT", bound=ipy.const.AsyncCallable)


def modal_event_error_handler(func: AsyncT) -> AsyncT:
    async def wrapper(
        self: typing.Any,
        unknown: ipy.events.ModalCompletion,
        *args: typing.Any,
        **kwargs: typing.Any,
    ) -> None:
        ctx = unknown.ctx

        try:
            await func(self, unknown, *args, **kwargs)
        except ipy.errors.BadArgument as e:
            await ctx.send(embeds=error_embed_generate(str(e)), ephemeral=True)
        except Exception as e:
            await error_handle(e, ctx=ctx)

    return wrapper  # type: ignore


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
    bot: "THIABase"

    def __new__(
        cls, bot: ipy.Client, *args: typing.Any, **kwargs: typing.Any
    ) -> "typing.Self":
        new_cls = super().__new__(cls, bot, *args, **kwargs)
        new_cls.add_ext_check(_global_checks)
        return new_cls


if typing.TYPE_CHECKING:
    import asyncio
    import collections

    from interactions.ext.prefixed_commands import PrefixedManager

    from .help_tools import MiniCommand, PermissionsResolver

    class THIABase(ipy.AutoShardedClient):
        prefixed: PrefixedManager
        hybrid: hybrid.HybridManager
        owner: ipy.User
        color: ipy.Color
        background_tasks: set[asyncio.Task]
        slash_perms_cache: collections.defaultdict[int, dict[int, PermissionsResolver]]
        mini_commands_per_scope: dict[int, dict[str, MiniCommand]]
        msg_enabled_bullets_guilds: set[int]
        gacha_locks: collections.defaultdict[str, asyncio.Lock]

        def create_task(self, coro: typing.Coroutine) -> asyncio.Task: ...

else:

    class THIABase(ipy.AutoShardedClient):
        pass


class THIAContextMixin:
    guild_config: models.GuildConfig | None
    guild_id: ipy.Snowflake

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        self.guild_config = None
        super().__init__(*args, **kwargs)

    @property
    def guild(self) -> ipy.Guild:
        return self.client.cache.get_guild(self.guild_id)  # type: ignore

    @property
    def bot(self) -> "THIABase":
        """A reference to the bot instance."""
        return self.client  # type: ignore

    async def fetch_config(
        self,
        include: models.GuildConfigInclude | None = None,
    ) -> models.GuildConfig:
        """
        Gets the configuration for the context's guild.

        Returns:
            The guild config.
        """
        if self.guild_config:
            return self.guild_config

        config = await models.GuildConfig.fetch_create(self.guild_id, include)
        self.guild_config = config
        return config


class THIABaseContext(THIAContextMixin, ipy.BaseContext):
    pass


class THIAModalContext(THIAContextMixin, ipy.ModalContext):
    pass


class THIAInteractionContext(THIAContextMixin, ipy.InteractionContext):
    pass


class THIAComponentContext(THIAContextMixin, ipy.ComponentContext):
    pass


class THIASlashContext(THIAContextMixin, ipy.SlashContext):
    pass


class THIAHybridContext(THIAContextMixin, hybrid.HybridContext):
    pass


class THIAPrefixedContext(THIAContextMixin, prefixed.PrefixedContext):
    pass


class FixedRangeConverter(ipy.Converter[float | int]):
    def __init__(
        self,
        number_type: int,
        min_value: float | int | None,
        max_value: float | int | None,
    ) -> None:
        self.number_type = number_type
        self.min_value = min_value
        self.max_value = max_value

        self.number_convert = int if number_type == ipy.OptionType.INTEGER else float

    async def convert(self, _: ipy.BaseContext, argument: str) -> float | int:
        try:
            converted: float | int = await ipy.utils.maybe_coroutine(
                self.number_convert, argument
            )

            if self.min_value and converted < self.min_value:
                raise ipy.errors.BadArgument(
                    f'Value "{argument}" is less than {self.min_value}.'
                )
            if self.max_value and converted > self.max_value:
                raise ipy.errors.BadArgument(
                    f'Value "{argument}" is greater than {self.max_value}.'
                )

            return converted
        except ValueError:
            type_name = (
                "number" if self.number_type == ipy.OptionType.NUMBER else "integer"
            )

            if type_name.startswith("i"):
                raise ipy.errors.BadArgument(
                    f'Argument "{argument}" is not an {type_name}.'
                ) from None
            raise ipy.errors.BadArgument(
                f'Argument "{argument}" is not a {type_name}.'
            ) from None
        except ipy.errors.BadArgument:
            raise


RangeConverter.convert = FixedRangeConverter.convert
