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

import interactions as ipy
import tansy
import typing_extensions as typing
from interactions.client.mixins.send import SendMixin

import common.fuzzy as fuzzy
import common.models as models
import common.text_utils as text_utils
import common.utils as utils


async def player_check(ctx: utils.THIASlashContext) -> bool:
    config = await ctx.fetch_config(include={"bullets": True, "names": True})

    if not config.player_role or not ctx.author.has_role(config.player_role):
        raise utils.CustomCheckFailure("Cannot investigate without the Player role.")

    return True


class BDAInvestigateKwargs(typing.TypedDict, total=False):
    manual_trigger: bool
    finder: ipy.User | ipy.Member | None


class BulletFinding(utils.Extension):
    """The extension that deals with finding Truth Bullets."""

    async def check_for_finish(
        self,
        guild: ipy.Guild,
        bullet_chan: ipy.GuildText | None,
        config: models.GuildConfig,
    ) -> None:
        if await models.TruthBullet.filter(guild_id=guild.id, found=False).exists():
            return

        if typing.TYPE_CHECKING:
            assert config.bullets is not None
            assert config.names is not None

        if not bullet_chan:
            bullet_chan = await self.bot.fetch_channel(config.bullets.bullet_chan_id)
            if not bullet_chan or not isinstance(bullet_chan, SendMixin):
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

            embed = ipy.Embed(
                title=f"All {config.names.plural_bullet} have been found.",
                description="\n".join(str_builder),
                color=ipy.RoleColors.GREEN,
                timestamp=ipy.Timestamp.utcnow(),
            )
            embed.set_footer(text=f"Found {most_found_num} {bullet_name}")
        else:
            embed = ipy.Embed(
                title=f"All {config.names.plural_bullet} have been found.",
                color=ipy.RoleColors.GREEN,
            )

        await bullet_chan.send(content, embed=embed)

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

                    await self.bot.http.add_guild_member_role(
                        guild.id, person_id, best_bullet_finder_obj.id
                    )
                    await asyncio.sleep(1)  # we don't want to trigger ratelimits
                except ipy.errors.HTTPException:
                    continue

    @ipy.listen("message_create")
    async def on_message(self, event: ipy.events.MessageCreate) -> None:
        message = event.message

        # if the message is from a bot, from discord, not from a guild, not a default message or a reply, or is empty
        if (
            message.author.bot
            or message.author.system
            or not message.guild
            or message.type not in {ipy.MessageType.DEFAULT, ipy.MessageType.REPLY}
            or not message.content
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
            assert config.bullets is not None
            assert config.names is not None

        if (
            not config.bullets.bullets_enabled
            or not config.player_role
            or not message.author.has_role(config.player_role)
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
            and isinstance(message.channel, ipy.ThreadChannel)
        ):
            channel_id = message.channel.parent_id
        else:
            channel_id = message.channel.id

        bullet_found = await models.TruthBullet.find(
            channel_id, text_utils.replace_smart_punc(message.content)
        )
        if not bullet_found:
            return

        bullet_found.found = True
        bullet_found.finder = message.author.id

        bullet_chan: ipy.GuildText | None = None
        embed = bullet_found.found_embed(
            str(message.author), config.names.singular_bullet
        )

        if not bullet_found.hidden:
            bullet_chan = await self.bot.fetch_channel(config.bullets.bullet_chan_id)
            if not bullet_chan or not isinstance(bullet_chan, SendMixin):
                config.bullets.bullets_enabled = False
                self.bot.msg_enabled_bullets_guilds.discard(int(message.guild.id))
                config.bullets.bullet_chan_id = None
                await config.bullets.save()
                return

            new_msg = await message.reply(embed=embed)
            await bullet_chan.send(
                embed=embed,
                components=ipy.Button(
                    style=ipy.ButtonStyle.LINK,
                    label="Context",
                    url=new_msg.jump_url,
                ),
            )
        else:
            try:
                await message.author.send(
                    embed=embed,
                    components=ipy.Button(
                        style=ipy.ButtonStyle.LINK,
                        label="Context",
                        url=message.jump_url,
                    ),
                )
            except ipy.errors.HTTPException:
                await message.channel.send(
                    f"{message.author.mention}, I couldn't DM you a(n)"
                    f" {config.names.singular_bullet}. Please enable DMs for this"
                    " server and this bot and try again.",
                    delete_after=5,
                )
                return

        await bullet_found.save(force_update=True)
        await self.check_for_finish(message.guild, bullet_chan, config)

    @tansy.slash_command(
        name="bda-investigate",
        description=(
            "Investigate for items in the current channel for a BDA. An alternative to"
            " sending a message."
        ),
        dm_permission=False,
    )
    @ipy.auto_defer(enabled=False)
    @ipy.check(player_check)
    async def investigate(
        self,
        ctx: utils.THIASlashContext,
        trigger: str = tansy.Option(
            "The trigger to search for in this channel.",
            converter=text_utils.ReplaceSmartPuncConverter,
        ),
        **kwargs: typing.Unpack[BDAInvestigateKwargs],
    ) -> None:
        config = await ctx.fetch_config(include={"bullets": True, "names": True})
        if typing.TYPE_CHECKING:
            assert config.bullets is not None
            assert config.names is not None

        if not config.bullets.bullets_enabled and not kwargs.get("manual_trigger"):
            self.bot.msg_enabled_bullets_guilds.discard(int(ctx.guild_id))
            raise utils.CustomCheckFailure(
                f"{config.names.plural_bullet} are not enabled in this server."
            )

        if (
            config.bullets.thread_behavior == models.BulletThreadBehavior.PARENT
            and isinstance(ctx.channel, ipy.ThreadChannel)
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

        bullet_chan: ipy.GuildText | None = None
        embed = truth_bullet.found_embed(str(finder), config.names.singular_bullet)

        message = await ctx.send(embeds=embed, ephemeral=ctx.ephemeral)

        if not truth_bullet.hidden:
            bullet_chan = await self.bot.fetch_channel(config.bullets.bullet_chan_id)
            if not bullet_chan or not isinstance(bullet_chan, SendMixin):
                config.bullets.bullets_enabled = False
                self.bot.msg_enabled_bullets_guilds.discard(int(ctx.guild_id))
                config.bullets.bullet_chan_id = None
                await config.bullets.save()
                return

            await bullet_chan.send(
                embed=embed,
                components=ipy.Button(
                    style=ipy.ButtonStyle.LINK,
                    label="Context",
                    url=message.jump_url,
                ),
            )

        await truth_bullet.save(force_update=True)
        await self.check_for_finish(ctx.guild, bullet_chan, config)

    config = tansy.SlashCommand(
        name="bullet-manage",
        description="Handles management of Truth Bullets.",
        default_member_permissions=ipy.Permissions.MANAGE_GUILD,
        dm_permission=False,
    )

    @config.subcommand(
        "manual-trigger",
        sub_cmd_description="Manually trigger a Truth Bullet in the current channel.",
    )
    @ipy.auto_defer(enabled=False)
    async def manual_trigger(
        self,
        ctx: utils.THIASlashContext,
        trigger: str = tansy.Option(
            "The trigger of the Truth Bullet to manually trigger.",
            autocomplete=True,
            converter=text_utils.ReplaceSmartPuncConverter,
        ),
        finder: ipy.Member | None = tansy.Option(
            "The person who will find the Truth Bullet.", default=None
        ),
    ) -> None:
        await self.investigate.call_with_binding(
            self.investigate.callback, ctx, trigger, manual_trigger=True, finder=finder
        )

    @manual_trigger.autocomplete("trigger")
    async def _bullet_trigger_autocomplete(self, ctx: ipy.AutocompleteContext) -> None:
        if not ctx.guild_id:
            return await ctx.send([])

        config = await models.BulletConfig.get_or_none(guild_id=ctx.guild_id)

        if (
            config
            and config.thread_behavior == models.BulletThreadBehavior.PARENT
            and isinstance(ctx.channel, ipy.ThreadChannel)
        ):
            channel_id = ctx.channel.parent_id
        else:
            channel_id = ctx.channel_id

        return await fuzzy.autocomplete_bullets(
            ctx, **ctx.kwargs, channel=str(channel_id), only_not_found=True
        )


def setup(bot: utils.THIABase) -> None:
    importlib.reload(utils)
    importlib.reload(fuzzy)
    importlib.reload(text_utils)
    BulletFinding(bot)
