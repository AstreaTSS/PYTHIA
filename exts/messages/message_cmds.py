"""
Copyright 2021-2026 AstreaTSS.
This file is part of PYTHIA.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

import importlib
import typing

import discord
import ragwort
from discord.ext import commands

import common.classes as classes
import common.models as models
import common.utils as utils


class MessageCMDs(utils.Cog):
    def __init__(self, bot: utils.THIABase) -> None:
        self.bot = bot
        self.__cog_name__ = "Messaging Commands"

    @ragwort.bridge_group(
        name="message",
        description="Hosts public-facing messaging commands.",
        contexts={discord.InteractionContextType.guild},
        invoke_without_command=True,
        aliases=["msg"],
    )
    @commands.guild_only()
    async def message(self, _: utils.THIABridgeContext) -> None:
        raise utils.CustomCheckFailure("Please specify a subcommand.")

    @message.command(
        name="send",
        description="Non-anonymously message another player's designated channel.",
        aliases=["whisper"],
    )
    @commands.guild_only()
    @ragwort.auto_defer(enabled=False)
    # @help_tools.prefixed_check() TODO: reimplement in some form
    async def message_whisper(
        self,
        ctx: utils.THIABridgeContext,
        user: discord.Member = ragwort.BridgeOption("The user to message."),
        *,
        message: str = ragwort.BridgeOption("The message to send."),
    ) -> None:
        await ctx.defer(ephemeral=True)

        if user.id == ctx.author.id:
            raise utils.CustomCheckFailure("You cannot message yourself.")

        config = await ctx.fetch_config({"messages": True})
        if typing.TYPE_CHECKING:
            assert config.messages and isinstance(config.messages, models.MessageConfig)

        if not config.messages.enabled:
            raise utils.CustomCheckFailure(
                "The messaging system is not enabled for this server."
            )

        ctx_user_link = await models.MessageLink.get_or_none(
            guild_id=ctx.guild_id, user_id=ctx.author.id
        )
        if not ctx_user_link:
            raise utils.CustomCheckFailure(
                "You are not set up with the messaging system."
            )

        other_user_link = await models.MessageLink.get_or_none(
            guild_id=ctx.guild_id, user_id=user.id
        )
        if not other_user_link:
            raise commands.BadArgument(
                "The specified user is not set up with the messaging system."
            )

        try:
            other_chan = self.bot.get_partial_messageable(other_user_link.channel_id)
            container = utils.make_container(
                message, title=f"Message from {ctx.author.mention}"
            )

            if config.messages.ping_for_message:
                view = utils.quick_view(
                    discord.ui.TextDisplay(f"<@{other_user_link.user_id}>"),
                    container,
                )
            else:
                view = utils.quick_view(container)

            await other_chan.send(
                view=view,
                allowed_mentions=discord.AllowedMentions(
                    users=(
                        [discord.Object(other_user_link.user_id)]
                        if config.messages.ping_for_message
                        else False  # type: ignore
                    )
                ),
            )
        except discord.HTTPException:
            raise utils.CustomCheckFailure(
                "Could not send a message to the specified user's channel."
            ) from None

        try:
            ctx_user_chan = self.bot.get_partial_messageable(ctx_user_link.channel_id)
            await ctx_user_chan.send(
                view=utils.make_view(message, title=f"Message sent to {user.mention}")
            )
        except discord.HTTPException:
            raise utils.CustomCheckFailure(
                "Message sent, but could not send receipt to your channel."
            ) from None

        await ctx.respond("Sent!", ephemeral=True)

    @message.command(
        name="anon",
        description="Anonymously message another player's designated channel.",
    )
    @commands.guild_only()
    @ragwort.auto_defer(enabled=False)
    # @help_tools.prefixed_check()
    async def message_anon(
        self,
        ctx: utils.THIABridgeContext,
        user: discord.Member = ragwort.BridgeOption("The user to message."),
        *,
        message: str = ragwort.BridgeOption("The message to send."),
    ) -> None:
        await ctx.defer(ephemeral=True)

        if user.id == ctx.author.id:
            raise utils.CustomCheckFailure("You cannot message yourself.")

        config = await ctx.fetch_config({"messages": True})
        if typing.TYPE_CHECKING:
            assert config.messages and isinstance(config.messages, models.MessageConfig)

        if not config.messages.enabled:
            raise utils.CustomCheckFailure(
                "The messaging system is not enabled for this server."
            )
        if not config.messages.anon_enabled:
            raise utils.CustomCheckFailure(
                "Anonymous messages are not enabled for this server."
            )

        ctx_user_link = await models.MessageLink.get_or_none(
            guild_id=ctx.guild_id, user_id=ctx.author.id
        )
        if not ctx_user_link:
            raise utils.CustomCheckFailure(
                "You are not set up with the messaging system."
            )

        other_user_link = await models.MessageLink.get_or_none(
            guild_id=ctx.guild_id, user_id=user.id
        )
        if not other_user_link:
            raise commands.BadArgument(
                "The specified user is not set up with the messaging system."
            )

        try:
            other_chan = self.bot.get_partial_messageable(other_user_link.channel_id)
            container = utils.make_container(message, title="Anonymous message")

            if config.messages.ping_for_message:
                view = utils.quick_view(
                    discord.ui.TextDisplay(f"<@{other_user_link.user_id}>"),
                    container,
                )
            else:
                view = utils.quick_view(container)

            await other_chan.send(
                view=view,
                allowed_mentions=discord.AllowedMentions(
                    users=(
                        [discord.Object(other_user_link.user_id)]
                        if config.messages.ping_for_message
                        else False  # type: ignore
                    )
                ),
            )
        except discord.HTTPException:
            raise utils.CustomCheckFailure(
                "Could not send a message to the specified user's channel."
            ) from None

        try:
            ctx_user_chan = self.bot.get_partial_messageable(ctx_user_link.channel_id)
            await ctx_user_chan.send(
                view=utils.make_view(
                    message, title=f"Anonymous message sent to {user.mention}"
                )
            )
        except discord.HTTPException:
            raise utils.CustomCheckFailure(
                "Message sent, but could not send receipt to your channel."
            ) from None

        await ctx.respond("Sent!", ephemeral=True)


def setup(bot: utils.THIABase) -> None:
    importlib.reload(utils)
    importlib.reload(classes)
    bot.add_cog(MessageCMDs(bot))
