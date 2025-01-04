"""
Copyright 2021-2025 AstreaTSS.
This file is part of PYTHIA.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

import importlib
import typing

import interactions as ipy
import tansy

import common.help_tools as help_tools
import common.models as models
import common.utils as utils


async def prefixed_check(ctx: utils.THIAHybridContext) -> bool:
    if isinstance(ctx.inner_context, ipy.SlashContext):
        return True

    if not ctx.bot.slash_perms_cache[int(ctx.guild_id)]:
        await help_tools.process_bulk_slash_perms(ctx.bot, int(ctx.guild_id))

    cmds = help_tools.get_mini_commands_for_scope(ctx.bot, int(ctx.guild_id))

    return await help_tools.can_run(ctx, cmds[ctx.command.resolved_name])


class MessageCMDs(utils.Extension):
    def __init__(self, bot: utils.THIABase) -> None:
        self.name = "Messaging Commands"
        self.bot: utils.THIABase = bot

    message = tansy.HybridSlashCommand(
        name="message",
        description="Hosts public-facing messaging commands.",
        dm_permission=False,
        aliases=["msg"],
    )

    @message.subcommand(
        "send",
        sub_cmd_description=(
            "Non-anonymously message another player's designated channel."
        ),
        aliases=["whisper"],
    )
    @ipy.auto_defer(enabled=False)
    async def message_whisper(
        self,
        ctx: utils.THIAHybridContext,
        user: ipy.Member = tansy.Option("The user to message."),
        message: ipy.ConsumeRest[str] = tansy.Option("The message to send."),
    ) -> None:
        ctx.ephemeral = True
        async with ctx.typing:
            if not await prefixed_check(ctx):
                raise utils.CustomCheckFailure(
                    "You do not have the proper permissions to use that command."
                )

            config = await ctx.fetch_config({"messages": True})
            if typing.TYPE_CHECKING:
                assert config.messages is not None

            if not config.messages.enabled:
                raise utils.CustomCheckFailure(
                    "The messaging system is not enabled for this server."
                )

            ctx_user_link = await models.MessageLink.prisma().find_first(
                where={"guild_id": ctx.guild_id, "user_id": ctx.author_id}
            )
            if not ctx_user_link:
                raise utils.CustomCheckFailure(
                    "You are not set up with the messaging system."
                )

            other_user_link = await models.MessageLink.prisma().find_first(
                where={"guild_id": ctx.guild_id, "user_id": user.id}
            )
            if not other_user_link:
                raise ipy.errors.BadArgument(
                    "The specified user is not set up with the messaging system."
                )

            embed = utils.make_embed(message, title=f"Message from {ctx.author!s}")

            try:
                other_chan = utils.partial_channel(self.bot, other_user_link.channel_id)
                await other_chan.send(
                    content=(
                        f"<@{other_user_link.user_id}>"
                        if config.messages.ping_for_message
                        else None
                    ),
                    embed=embed,
                )
            except ipy.errors.HTTPException:
                raise utils.CustomCheckFailure(
                    "Could not send a message to the specified user's channel."
                ) from None

            try:
                ctx_user_chan = utils.partial_channel(
                    self.bot, ctx_user_link.channel_id
                )
                embed.title = f"Message sent to {user!s}"
                await ctx_user_chan.send(embed=embed)
            except ipy.errors.HTTPException:
                raise utils.CustomCheckFailure(
                    "Message sent, but could not send receipt to your channel."
                ) from None

        await ctx.reply("Sent!", ephemeral=True)

    @message.subcommand(
        "anon",
        sub_cmd_description="Anonymously message another player's designated channel.",
    )
    @ipy.auto_defer(enabled=False)
    async def message_anon(
        self,
        ctx: utils.THIAHybridContext,
        user: ipy.Member = tansy.Option("The user to message."),
        message: ipy.ConsumeRest[str] = tansy.Option("The message to send."),
    ) -> None:
        ctx.ephemeral = True
        async with ctx.typing:
            if not await prefixed_check(ctx):
                raise utils.CustomCheckFailure(
                    "You do not have the proper permissions to use that command."
                )

            config = await ctx.fetch_config({"messages": True})
            if typing.TYPE_CHECKING:
                assert config.messages is not None

            if not config.messages.enabled:
                raise utils.CustomCheckFailure(
                    "The messaging system is not enabled for this server."
                )
            if not config.messages.anon_enabled:
                raise utils.CustomCheckFailure(
                    "Anonymous messages are not enabled for this server."
                )

            ctx_user_link = await models.MessageLink.prisma().find_first(
                where={"guild_id": ctx.guild_id, "user_id": ctx.author_id}
            )
            if not ctx_user_link:
                raise utils.CustomCheckFailure(
                    "You are not set up with the messaging system."
                )

            other_user_link = await models.MessageLink.prisma().find_first(
                where={"guild_id": ctx.guild_id, "user_id": user.id}
            )
            if not other_user_link:
                raise ipy.errors.BadArgument(
                    "The specified user is not set up with the messaging system."
                )

            embed = utils.make_embed(message, title="Anonymous message")

            try:
                other_chan = utils.partial_channel(self.bot, other_user_link.channel_id)
                await other_chan.send(
                    content=(
                        f"<@{other_user_link.user_id}>"
                        if config.messages.ping_for_message
                        else None
                    ),
                    embed=embed,
                )
            except ipy.errors.HTTPException:
                raise utils.CustomCheckFailure(
                    "Could not send a message to the specified user's channel."
                ) from None

            try:
                ctx_user_chan = utils.partial_channel(
                    self.bot, ctx_user_link.channel_id
                )
                embed.title = f"Anonymous message sent to {user!s}"
                await ctx_user_chan.send(embed=embed)
            except ipy.errors.HTTPException:
                raise utils.CustomCheckFailure(
                    "Message sent, but could not send receipt to your channel."
                ) from None

        await ctx.reply("Sent!", ephemeral=True)


def setup(bot: utils.THIABase) -> None:
    importlib.reload(utils)
    importlib.reload(help_tools)
    MessageCMDs(bot)
