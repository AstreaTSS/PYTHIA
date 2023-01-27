#!/usr/bin/env python3.8
import collections
import functools
import logging
import traceback
import typing
from pathlib import Path

import aiohttp
import naff
import tansy

import common.models as models


@functools.wraps(tansy.slash_command)
def manage_guild_slash_cmd(
    name: str,
    description: naff.Absent[str] = naff.MISSING,
):
    return tansy.slash_command(
        name=name,
        description=description,
        default_member_permissions=naff.Permissions.MANAGE_GUILD,
    )


def error_embed_generate(error_msg: str):
    return naff.Embed(color=naff.RoleColors.RED, description=error_msg)


async def error_handle(
    bot: naff.Client, error: Exception, ctx: naff.Context | None = None
):
    # handles errors and sends them to owner
    if isinstance(error, aiohttp.ServerDisconnectedError):
        to_send = "Disconnected from server!"
    else:
        error_str = error_format(error)
        logging.getLogger("uibot").error(error_str)

        chunks = line_split(error_str, split_by=40)
        for i in range(len(chunks)):
            chunks[i][0] = f"```py\n{chunks[i][0]}"
            chunks[i][-1] += "\n```"

        final_chunks: list[str | naff.Embed] = [
            error_embed_generate("\n".join(chunk)) for chunk in chunks
        ]
        if ctx and hasattr(ctx, "message") and hasattr(ctx.message, "jump_url"):
            final_chunks.insert(0, f"Error on: {ctx.message.jump_url}")

        to_send = final_chunks

    await msg_to_owner(bot, to_send)

    if ctx and isinstance(ctx, naff.SendableContext):
        if isinstance(ctx, naff.PrefixedContext):
            await ctx.reply(
                "An internal error has occured. The bot owner has been notified."
            )
        elif isinstance(ctx, naff.InteractionContext):
            await ctx.send(
                content=(
                    "An internal error has occured. The bot owner has been notified."
                ),
                ephemeral=True,
            )
        else:
            await ctx.send(
                "An internal error has occured. The bot owner has been notified."
            )


async def msg_to_owner(
    bot: "UIBase",
    chunks: list[str] | list[naff.Embed] | list[str | naff.Embed] | str | naff.Embed,
):
    if not isinstance(chunks, list):
        chunks = [chunks]

    # sends a message to the owner
    for chunk in chunks:
        if isinstance(chunk, naff.Embed):
            await bot.owner.send(embeds=chunk)
        else:
            await bot.owner.send(chunk)


def line_split(content: str, split_by=20):
    content_split = content.splitlines()
    return [
        content_split[x : x + split_by] for x in range(0, len(content_split), split_by)
    ]


def embed_check(embed: naff.Embed) -> bool:
    """Checks if an embed is valid, as per Discord's guidelines.
    See https://discord.com/developers/docs/resources/channel#embed-limits for details.
    """
    if len(embed) > 6000:
        return False

    if embed.title and len(embed.title) > 256:
        return False
    if embed.description and len(embed.description) > 4096:
        return False
    if embed.author and embed.author.name and len(embed.author.name) > 256:
        return False
    if embed.footer and embed.footer.text and len(embed.footer.text) > 2048:
        return False
    if embed.fields:
        if len(embed.fields) > 25:
            return False
        for field in embed.fields:
            if field.name and len(field.name) > 1024:
                return False
            if field.value and len(field.value) > 2048:
                return False

    return True


def deny_mentions(user):
    # generates an AllowedMentions object that only pings the user specified
    return naff.AllowedMentions(users=[user])


def error_format(error: Exception):
    # simple function that formats an exception
    return "".join(
        traceback.format_exception(  # type: ignore
            type(error), value=error, tb=error.__traceback__
        )
    )


def string_split(string):
    # simple function that splits a string into 1950-character parts
    return [string[i : i + 1950] for i in range(0, len(string), 1950)]


def file_to_ext(str_path, base_path):
    # changes a file to an import-like string
    str_path = str_path.replace(base_path, "")
    str_path = str_path.replace("/", ".")
    return str_path.replace(".py", "")


def get_all_extensions(str_path, folder="exts"):
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


def toggle_friendly_str(bool_to_convert):
    return "on" if bool_to_convert == True else "off"


def yesno_friendly_str(bool_to_convert):
    return "yes" if bool_to_convert == True else "no"


def role_check(ctx: naff.Context, role: naff.Role):
    top_role = ctx.guild.me.top_role

    if role > top_role:
        raise CustomCheckFailure(
            "The role provided is a role that is higher than the roles I can edit. "
            + "Please move either that role or my role so that "
            + "my role is higher than the role you want to use."
        )

    return role


class ValidRoleConverter(naff.Converter):
    async def convert(self, context: naff.InteractionContext, argument: naff.Role):
        return role_check(context, argument)


class CustomCheckFailure(naff.errors.BadArgument):
    # custom classs for custom prerequisite failures outside of normal command checks
    pass


class GuildMessageable(naff.GuildChannel, naff.MessageableMixin):
    pass


def valid_channel_check(channel: naff.GuildChannel) -> GuildMessageable:
    if not isinstance(channel, naff.MessageableMixin):
        raise naff.errors.BadArgument(f"Cannot send messages in {channel.name}.")

    perms = channel.permissions_for(channel.guild.me)

    if (
        naff.Permissions.VIEW_CHANNEL not in perms
    ):  # technically pointless, but who knows
        raise naff.errors.BadArgument(f"Cannot read messages in {channel.name}.")
    elif naff.Permissions.READ_MESSAGE_HISTORY not in perms:
        raise naff.errors.BadArgument(f"Cannot read message history in {channel.name}.")
    elif naff.Permissions.SEND_MESSAGES not in perms:
        raise naff.errors.BadArgument(f"Cannot send messages in {channel.name}.")
    elif naff.Permissions.EMBED_LINKS not in perms:
        raise naff.errors.BadArgument(f"Cannot send embeds in {channel.name}.")

    return channel  # type: ignore


class ValidChannelConverter(naff.Converter):
    async def convert(self, ctx: naff.InteractionContext, argument: naff.GuildText):
        return valid_channel_check(argument)


async def _global_checks(ctx: naff.Context):
    return bool(ctx.guild) if ctx.bot.is_ready else False


class Extension(naff.Extension):
    def __new__(cls, bot: naff.Client, *args, **kwargs):
        new_cls = super().__new__(cls, bot, *args, **kwargs)
        new_cls.add_ext_check(_global_checks)
        return new_cls


if typing.TYPE_CHECKING:
    from .help_tools import MiniCommand, PermissionsResolver

    class UIBase(naff.Client):
        owner: naff.User
        color: naff.Color
        slash_perms_cache: collections.defaultdict[int, dict[int, PermissionsResolver]]
        mini_commands_per_scope: dict[int, dict[str, MiniCommand]]

else:

    class UIBase(naff.Client):
        pass


@naff.utils.define
class InvestigatorContext(naff.InteractionContext):
    guild_config: typing.Optional[models.Config] = naff.utils.field(default=None)

    @property
    def guild(self) -> naff.Guild:
        return self._client.cache.get_guild(self.guild_id)  # type: ignore

    @property
    def bot(self) -> "UIBase":
        """A reference to the bot instance."""
        return self._client  # type: ignore

    async def fetch_config(self):
        if self.guild_config:
            return self.guild_config

        self.guild_config, _ = await models.Config.get_or_create(guild_id=self.guild.id)
        return self.guild_config

    async def reply(self, **kwargs):
        return await self.send(**kwargs)
