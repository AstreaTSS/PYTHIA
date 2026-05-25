"""
Copyright 2021-2026 AstreaTSS.
This file is part of PYTHIA.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

import asyncio
import collections
import importlib

import discord
import ragwort
import typing_extensions as typing
from discord.ext import commands

import common.fuzzy as fuzzy
import common.models as models
import common.utils as utils

from ._bullet_common import bullet_manage


async def player_check(ctx: utils.THIASlashContext) -> bool:
    config = await ctx.fetch_config(include={"bullets": True, "names": True})

    if not config.player_role or not ctx.author.get_role(config.player_role):
        raise utils.CustomCheckFailure("Cannot investigate without the Player role.")

    return True


class BDAInvestigateKwargs(typing.TypedDict, total=False):
    manual_trigger: bool
    finder: discord.User | discord.Member | None


class BulletFinding(utils.Cog):
    """The extension that deals with finding Truth Bullets."""

    def __init__(self, bot: utils.THIABase) -> None:
        self.bot = bot
        self.__cog_name__ = "BDA Investigation Finding"

    async def check_for_finish(
        self,
        guild: discord.Guild,
        bullet_chan: discord.TextChannel | discord.Thread | None,
        config: models.GuildConfig,
        *,
        okay_if_no_chan: bool = False,
    ) -> None:
        if await models.TruthBullet.filter(guild_id=guild.id, found=False).exists():
            return

        if typing.TYPE_CHECKING:
            assert config.bullets and isinstance(config.bullets, models.BulletConfig)
            assert config.names and isinstance(config.names, models.Names)

        if not bullet_chan:
            if okay_if_no_chan:
                return

            bullet_chan = await self.bot.getch_channel(
                config.bullets.bullet_chan_id or 0
            )
            if not bullet_chan or not isinstance(bullet_chan, discord.abc.Messageable):
                config.bullets.bullets_enabled = False
                self.bot.msg_enabled_bullets_guilds.discard(int(guild.id))
                config.bullets.bullet_chan_id = None
                await config.bullets.save()
                return

        counter: collections.Counter[int] = collections.Counter()

        async for bullet in models.TruthBullet.filter(guild_id=guild.id):
            counter[bullet.finder] += 1  # type: ignore

        most_found = counter.most_common(None)

        # number of truth bullets found by highest person
        most_found_num = most_found[0][1]
        # the next is just fancy code to check for ties and make a list for the top people
        most_found_people = tuple(p[0] for p in most_found if p[1] == most_found_num)

        bullet_name = (
            config.names.singular_bullet
            if most_found_num == 1
            else config.names.plural_bullet
        )
        truth_bullet_finder = (
            config.names.singular_truth_bullet_finder
            if len(most_found_people) == 1
            else config.names.plural_truth_bullet_finder
        )
        truth_bullet_finder = truth_bullet_finder.replace(
            "{{bullet_name}}", bullet_name
        )
        best_bullet_finder = config.names.best_bullet_finder.replace(
            "{{bullet_finder}}", truth_bullet_finder
        )

        content: str | None = None

        if config.bullets.show_best_finders:
            str_builder: list[str] = [f"## {best_bullet_finder}"]
            str_builder.extend(f"- <@{person_id}>" for person_id in most_found_people)
            content = " ".join(f"<@{person_id}>" for person_id in most_found_people)

            embed = discord.Embed(
                title=f"All {config.names.plural_bullet} have been found.",
                description="\n".join(str_builder),
                color=discord.Color.green(),
            )
            embed.set_footer(text=f"Found {most_found_num} {bullet_name}")
        else:
            embed = discord.Embed(
                title=f"All {config.names.plural_bullet} have been found.",
                color=discord.Color.green(),
            )

        try:
            await bullet_chan.send(content, embed=embed)
        except discord.HTTPException:
            return
        finally:
            config.bullets.bullets_enabled = False
            await config.bullets.save()
            self.bot.msg_enabled_bullets_guilds.discard(int(guild.id))

        if config.bullets.best_bullet_finder_role and (
            best_bullet_finder_obj := guild.get_role(
                config.bullets.best_bullet_finder_role
            )
        ):
            for person_id in most_found_people:
                try:
                    # use an internal method to save on an http request
                    # we get to skip out on asking for the member, which was
                    # pointless to do for our needs
                    # but dont do this unless you're me

                    await self.bot.http.add_role(
                        guild.id, person_id, best_bullet_finder_obj.id
                    )
                    await asyncio.sleep(1)  # we don't want to trigger ratelimits
                except discord.HTTPException:
                    continue

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
        embed = bullet_found.found_embed(
            message.author.mention, config.names.singular_bullet
        )

        if not bullet_found.hidden:
            bullet_chan = await self.bot.getch_channel(config.bullets.bullet_chan_id)
            if not bullet_chan or not isinstance(bullet_chan, discord.abc.Messageable):
                config.bullets.bullets_enabled = False
                self.bot.msg_enabled_bullets_guilds.discard(int(message.guild.id))
                config.bullets.bullet_chan_id = None
                await config.bullets.save()
                return

            try:
                new_msg = await message.reply(embed=embed)
                embed.title = None
                await bullet_chan.send(
                    embed=embed,
                    view=discord.ui.View(
                        discord.ui.Button(
                            style=discord.ButtonStyle.link,
                            label="Context",
                            url=new_msg.jump_url,
                        ),
                        store=False,
                    ),
                )
            except discord.HTTPException:
                return  # can't do anything here, unforunately
        else:
            try:
                await message.author.send(
                    embed=embed,
                    view=discord.ui.View(
                        discord.ui.Button(
                            style=discord.ButtonStyle.link,
                            label="Context",
                            url=message.jump_url,
                        ),
                        store=False,
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
        await self.check_for_finish(message.guild, bullet_chan, config)

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
        await self._internal_investigate(ctx, trigger)

    async def _internal_investigate(
        self,
        ctx: utils.THIASlashContext,
        trigger: str,
        **kwargs: typing.Unpack[BDAInvestigateKwargs],
    ) -> None:
        config = await ctx.fetch_config(include={"bullets": True, "names": True})
        if typing.TYPE_CHECKING:
            assert config.bullets and isinstance(config.bullets, models.BulletConfig)
            assert config.names and isinstance(config.names, models.Names)

        if not config.bullets.bullets_enabled and not kwargs.get("manual_trigger"):
            self.bot.msg_enabled_bullets_guilds.discard(int(ctx.guild_id))
            raise utils.CustomCheckFailure(
                f"{config.names.plural_bullet} are not enabled in this server."
            )

        if (
            config.bullets.thread_behavior == models.BulletThreadBehavior.PARENT
            and isinstance(ctx.channel, discord.Thread)
        ):
            channel_id = ctx.channel.parent_id
        else:
            channel_id = ctx.channel_id

        truth_bullet = await models.TruthBullet.find_exact(channel_id, trigger)
        if not truth_bullet:
            raise utils.CustomCheckFailure(
                f"No {config.names.singular_bullet} found with this trigger."
            )

        if truth_bullet.found:
            raise utils.CustomCheckFailure(
                f"This {config.names.singular_bullet} has already been found."
            )

        await ctx.defer(ephemeral=truth_bullet.hidden)

        finder = the_finder if (the_finder := kwargs.get("finder")) else ctx.author

        truth_bullet.found = True
        truth_bullet.finder = finder.id

        bullet_chan: discord.TextChannel | discord.Thread | None = None
        embed = truth_bullet.found_embed(finder.mention, config.names.singular_bullet)

        message = await ctx.respond(embed=embed, ephemeral=truth_bullet.hidden)

        if not truth_bullet.hidden and (
            config.bullets.bullet_chan_id or not kwargs.get("manual_trigger")
        ):
            bullet_chan = await self.bot.getch_channel(
                config.bullets.bullet_chan_id or 0
            )
            if not bullet_chan or not isinstance(bullet_chan, discord.abc.Messageable):
                config.bullets.bullets_enabled = False
                self.bot.msg_enabled_bullets_guilds.discard(int(ctx.guild_id))
                config.bullets.bullet_chan_id = None
                await config.bullets.save()
                return

            embed.title = None

            try:
                await bullet_chan.send(
                    embed=embed,
                    view=discord.ui.View(
                        discord.ui.Button(
                            style=discord.ButtonStyle.link,
                            label="Context",
                            url=(
                                message.message.jump_url
                                if isinstance(message, discord.Interaction)
                                else message.jump_url
                            ),
                        ),
                        store=False,
                    ),
                )
            except discord.HTTPException:
                raise utils.CustomCheckFailure(
                    f"Cannot send messages to {bullet_chan.mention}. Staff, please"
                    " check channel permissions."
                ) from None

        await truth_bullet.save(force_update=True)
        await self.check_for_finish(
            ctx.guild,
            bullet_chan,
            config,
            okay_if_no_chan=kwargs.get("manual_trigger", False),
        )

    @bullet_manage.command(
        name="manual-trigger",
        description="Manually trigger a Truth Bullet in the current channel.",
    )
    @ragwort.auto_defer(enabled=False)
    async def manual_trigger(
        self,
        ctx: utils.THIASlashContext,
        trigger: str = ragwort.Option(
            "The trigger of the Truth Bullet to manually trigger.",
            input_type=utils.ReplaceSmartPuncConverter,
        ),
        finder: discord.Member | None = ragwort.Option(
            "The person who will find the Truth Bullet.", default=None
        ),
    ) -> None:
        await self._internal_investigate(
            ctx, trigger, manual_trigger=True, finder=finder
        )

    @manual_trigger.autocomplete("trigger")
    async def _bullet_trigger_autocomplete(
        self, ctx: discord.AutocompleteContext
    ) -> list[discord.OptionChoice]:
        if not ctx.interaction.guild_id:
            return []

        config = await models.BulletConfig.get_or_none(
            guild_id=ctx.interaction.guild_id
        )

        if (
            config
            and config.thread_behavior == models.BulletThreadBehavior.PARENT
            and isinstance(ctx.interaction.channel, discord.Thread)
        ):
            channel_id = ctx.interaction.channel.parent_id
        else:
            channel_id = ctx.interaction.channel_id

        return await fuzzy.autocomplete_bullets(
            ctx.options["trigger"], channel=str(channel_id), only_not_found=True
        )


def setup(bot: utils.THIABase) -> None:
    importlib.reload(utils)
    importlib.reload(fuzzy)
    bot.add_cog(BulletFinding(bot))
