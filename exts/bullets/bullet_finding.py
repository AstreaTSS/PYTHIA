"""
Copyright 2021-2026 AstreaTSS.
This file is part of PYTHIA.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

import importlib

import discord
import ragwort
import typing_extensions as typing
from discord.ext import commands

import common.fuzzy as fuzzy
import common.models as models
import common.utils as utils

from . import bullet_common


async def player_check(ctx: utils.THIASlashContext) -> bool:
    config = await ctx.fetch_config(include={"bullets": True, "names": True})

    if not config.player_role or not ctx.author.get_role(config.player_role):
        raise utils.CustomCheckFailure("Cannot investigate without the Player role.")

    return True


class BulletFinding(utils.Cog):
    """The extension that deals with finding Truth Bullets."""

    def __init__(self, bot: utils.THIABase) -> None:
        self.bot = bot
        self.__cog_name__ = "BDA Investigation Finding"

    @discord.Cog.listener("on_message")
    async def on_message(self, message: discord.Message) -> None:
        # if the message is from a bot, from discord, not from a guild, not a default message or a reply, or is empty
        if (
            message.author.bot
            or message.author.system
            or not message.guild
            or message.type
            not in {discord.MessageType.default, discord.MessageType.reply}
            or not message.content
            or not message.channel
        ):
            return

        if int(message.guild.id) not in self.bot.msg_enabled_bullets_guilds:
            return

        config = await models.GuildConfig.fetch(
            message.guild.id, include={"bullets": True, "names": True}
        )
        if not config:
            return

        if typing.TYPE_CHECKING:
            assert config.bullets and isinstance(config.bullets, models.BulletConfig)
            assert config.names and isinstance(config.names, models.Names)

        if (
            not config.bullets.bullets_enabled
            or not config.player_role
            or not message.author.get_role(config.player_role)
            or config.bullets.investigation_type
            == models.InvestigationType.COMMAND_ONLY
        ):
            if (
                not config.bullets.bullets_enabled
                or config.bullets.investigation_type
                == models.InvestigationType.COMMAND_ONLY
            ):
                self.bot.msg_enabled_bullets_guilds.discard(int(message.guild.id))
            return

        if (
            config.bullets.thread_behavior == models.BulletThreadBehavior.PARENT
            and isinstance(message.channel, discord.Thread)
        ):
            channel_id = message.channel.parent_id
        else:
            channel_id = message.channel.id

        bullet_found = await models.TruthBullet.find(
            channel_id, utils.replace_smart_punc(message.content)
        )
        if not bullet_found:
            return

        bullet_found.found = True
        bullet_found.finder = message.author.id

        bullet_chan: discord.TextChannel | discord.Thread | None = None

        if not bullet_found.hidden:
            bullet_chan = await utils.getch_channel(
                message.guild, config.bullets.bullet_chan_id
            )
            if not bullet_chan or not isinstance(bullet_chan, discord.abc.Messageable):
                config.bullets.bullets_enabled = False
                self.bot.msg_enabled_bullets_guilds.discard(int(message.guild.id))
                config.bullets.bullet_chan_id = None
                await config.bullets.save()
                return

            try:
                new_msg = await message.channel.send(
                    view=bullet_found.found_view(
                        message.author.mention,
                        singular_bullet=config.names.singular_bullet,
                    ),
                    reference=message.to_reference(fail_if_not_exists=False),
                    allowed_mentions=discord.AllowedMentions(replied_user=True),
                )
                await bullet_chan.send(
                    view=bullet_found.found_view(
                        message.author.mention, context_url=new_msg.jump_url
                    )
                )
            except discord.HTTPException:
                return  # can't do anything here, unforunately
        else:
            try:
                await message.author.send(
                    view=bullet_found.found_view(
                        message.author.mention,
                        singular_bullet=config.names.singular_bullet,
                        context_url=message.jump_url,
                    ),
                )
            except discord.HTTPException:
                await message.channel.send(
                    f"{message.author.mention}, I couldn't DM you a(n)"
                    f" {config.names.singular_bullet}. Please enable DMs for this"
                    " server and this bot and try again.",
                    delete_after=5,
                )
                return

        await bullet_found.save(force_update=True)
        await bullet_common.check_for_finish(
            self.bot, message.guild, bullet_chan, config
        )

    @ragwort.slash_command(
        name="bda-investigate",
        description=(
            "Investigate for items in the current channel for a BDA. An alternative to"
            " sending a message."
        ),
    )
    @ragwort.auto_defer(enabled=False)
    @commands.check(player_check)
    async def investigate(
        self,
        ctx: utils.THIASlashContext,
        trigger: str = ragwort.Option(
            "The trigger to search for in this channel.",
            input_type=utils.ReplaceSmartPuncConverter,
        ),
    ) -> None:
        await bullet_common.command_investigate(ctx, trigger)


def setup(bot: utils.THIABase) -> None:
    importlib.reload(utils)
    importlib.reload(fuzzy)
    importlib.reload(bullet_common)
    bot.add_cog(BulletFinding(bot))
