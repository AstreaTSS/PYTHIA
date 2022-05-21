#!/usr/bin/env python3.8
import collections
import logging
import traceback
import typing
from pathlib import Path

import aiohttp
import dis_snek
import molter

import common.models as models


def bullet_proper_perms() -> typing.Any:
    async def predicate(ctx: dis_snek.MessageContext):
        guild_config = await create_and_or_get(ctx.bot, ctx.guild.id, ctx.message.id)

        default_perms = False
        if guild_config.bullet_default_perms_check:
            # checks if author has admin or manage guild perms or is the owner
            default_perms = ctx.author.has_permission(dis_snek.Permissions.MANAGE_GUILD)

        # checks to see if the internal role list for the user has any of the roles specified in the roles specified
        if guild_config.bullet_custom_perm_roles:
            role_perms = ctx.author.has_role(*guild_config.bullet_custom_perm_roles)
        else:
            role_perms = False

        return bool(default_perms or role_perms)

    return dis_snek.check(predicate)


def proper_permissions() -> typing.Any:
    async def predicate(ctx: dis_snek.MessageContext):
        return ctx.author.has_permission(dis_snek.Permissions.MANAGE_GUILD)

    return dis_snek.check(predicate)


async def error_handle(
    bot: dis_snek.Snake, error: Exception, ctx: dis_snek.Context = None
):
    # handles errors and sends them to owner
    if isinstance(error, aiohttp.ServerDisconnectedError):
        to_send = "Disconnected from server!"
        split = True
    else:
        error_str = error_format(error)
        logging.getLogger(dis_snek.const.logger_name).error(error_str)

        chunks = line_split(error_str)
        for i in range(len(chunks)):
            chunks[i][0] = f"```py\n{chunks[i][0]}"
            chunks[i][len(chunks[i]) - 1] += "\n```"

        final_chunks = ["\n".join(chunk) for chunk in chunks]
        if ctx and hasattr(ctx, "message") and hasattr(ctx.message, "jump_url"):
            final_chunks.insert(0, f"Error on: {ctx.message.jump_url}")

        to_send = final_chunks
        split = False

    await msg_to_owner(bot, to_send, split)

    if ctx:
        if isinstance(ctx, dis_snek.MessageContext):
            await ctx.reply(
                "An internal error has occured. The bot owner has been notified."
            )
        elif isinstance(ctx, dis_snek.InteractionContext):
            await ctx.send(
                content=(
                    "An internal error has occured. The bot owner has been notified."
                )
            )


async def msg_to_owner(bot: dis_snek.Snake, content, split=True):
    # sends a message to the owner
    string = str(content)

    str_chunks = string_split(string) if split else content
    for chunk in str_chunks:
        await bot.owner.send(f"{chunk}")


async def create_and_or_get(bot, guild_id, msg_id) -> models.Config:
    bot.cached_configs.expire()

    if config := bot.cached_configs.get(msg_id):
        return config

    defaults = {
        "bullet_chan_id": 0,
        "ult_detective_role": 0,
        "player_role": 0,
        "bullets_enabled": False,
        "prefixes": {"v!"},
        "bullet_default_perms_check": True,
        "bullet_custom_perm_roles": set(),
    }
    config, _ = await models.Config.get_or_create(guild_id=guild_id, defaults=defaults)
    bot.cached_configs[msg_id] = config
    return config


def line_split(content: str, split_by=20):
    content_split = content.splitlines()
    return [
        content_split[x : x + split_by] for x in range(0, len(content_split), split_by)
    ]


def embed_check(embed: dis_snek.Embed) -> bool:
    """Checks if an embed is valid, as per Discord's guidelines.
    See https://discord.com/developers/docs/resources/channel#embed-limits for details."""
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
    return dis_snek.AllowedMentions(users=[user])


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


def get_all_extensions(str_path, folder="cogs"):
    # gets all extensions in a folder
    ext_files = collections.deque()
    loc_split = str_path.split("cogs")
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

        if str_path != "cogs.db_handler":
            ext_files.append(str_path)

    return ext_files


def toggle_friendly_str(bool_to_convert):
    return "on" if bool_to_convert == True else "off"


def yesno_friendly_str(bool_to_convert):
    return "yes" if bool_to_convert == True else "no"


def role_check(ctx: dis_snek.MessageContext, role: dis_snek.Role):
    top_role = ctx.guild.me.top_role

    if role.position > top_role.position:
        raise CustomCheckFailure(
            "The role provided is a role that is higher than the roles I can edit. "
            + "Please move either that role or my role so that "
            + "my role is higher than the role you want to use."
        )


class CustomCheckFailure(molter.BadArgument):
    # custom classs for custom prerequisite failures outside of normal command checks
    pass


class ValidChannelConverter(molter.GuildTextConverter):
    """The text channel converter, but we do a few checks to make sure we can do what we need to do in the channel."""

    async def convert(self, ctx: dis_snek.MessageContext, argument: str):
        chan = await super().convert(ctx, argument)
        perms = ctx.guild.me.channel_permissions(chan)

        if (
            dis_snek.Permissions.VIEW_CHANNEL not in perms
        ):  # technically pointless, but who knows
            raise molter.BadArgument(f"Cannot read messages in {chan.name}.")
        elif dis_snek.Permissions.READ_MESSAGE_HISTORY not in perms:
            raise molter.BadArgument(f"Cannot read message history in {chan.name}.")
        elif dis_snek.Permissions.SEND_MESSAGES not in perms:
            raise molter.BadArgument(f"Cannot send messages in {chan.name}.")
        elif dis_snek.Permissions.EMBED_LINKS not in perms:
            raise molter.BadArgument(f"Cannot send embeds in {chan.name}.")

        return chan


async def _global_checks(ctx: dis_snek.Context):
    return bool(ctx.guild) if ctx.bot.is_ready else False


class Scale(molter.MolterScale):
    def __new__(cls, bot: dis_snek.Snake, *args, **kwargs):
        new_cls = super().__new__(cls, bot, *args, **kwargs)
        new_cls.add_scale_check(_global_checks)
        return new_cls
