"""
Copyright 2021-2026 AstreaTSS.
This file is part of PYTHIA.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

import asyncio
import collections

import discord
import typing_extensions as typing

import common.models as models
import common.utils as utils

# pycord cannot handle subcommands being split across various files
# this causes an issue with manual-trigger, which used to use a lot of bullet_finding code,
# so now we have to put the shared code in a separate file


class BDAInvestigateKwargs(typing.TypedDict, total=False):
    manual_trigger: bool
    finder: discord.User | discord.Member | None


async def check_for_finish(
    bot: utils.THIABase,
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

        bullet_chan = await bot.getch_channel(config.bullets.bullet_chan_id or 0)
        if not bullet_chan or not isinstance(bullet_chan, discord.abc.Messageable):
            config.bullets.bullets_enabled = False
            bot.msg_enabled_bullets_guilds.discard(int(guild.id))
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
    truth_bullet_finder = truth_bullet_finder.replace("{{bullet_name}}", bullet_name)
    best_bullet_finder = config.names.best_bullet_finder.replace(
        "{{bullet_finder}}", truth_bullet_finder
    )

    if config.bullets.show_best_finders:
        str_builder: list[str] = [f"## {best_bullet_finder}"]
        str_builder.extend(f"- <@{person_id}>" for person_id in most_found_people)
        str_builder.append(f"-# Found {most_found_num} {bullet_name}.")

        view = utils.quick_view(
            discord.ui.Container(
                discord.ui.TextDisplay(
                    f"# All {config.names.plural_bullet} have been found.\n"
                    + "\n".join(str_builder)
                ),
                color=discord.Color.green(),
            )
        )
    else:
        view = utils.quick_view(
            discord.ui.Container(
                discord.ui.TextDisplay(
                    f"# All {config.names.plural_bullet} have been found."
                ),
                color=discord.Color.green(),
            )
        )

    try:
        await bullet_chan.send(
            view=view,
            allowed_mentions=(
                discord.AllowedMentions(
                    users=[discord.Object(person_id) for person_id in most_found_people]
                )
            ),
        )
    except discord.HTTPException:
        return
    finally:
        config.bullets.bullets_enabled = False
        await config.bullets.save()
        bot.msg_enabled_bullets_guilds.discard(int(guild.id))

    if config.bullets.best_bullet_finder_role and (
        best_bullet_finder_obj := guild.get_role(config.bullets.best_bullet_finder_role)
    ):
        for person_id in most_found_people:
            try:
                # use an internal method to save on an http request
                # we get to skip out on asking for the member, which was
                # pointless to do for our needs
                # but dont do this unless you're me

                await bot.http.add_role(guild.id, person_id, best_bullet_finder_obj.id)
                await asyncio.sleep(1)  # we don't want to trigger ratelimits
            except discord.HTTPException:
                continue


async def command_investigate(
    ctx: utils.THIASlashContext,
    trigger: str,
    **kwargs: typing.Unpack[BDAInvestigateKwargs],
) -> None:
    config = await ctx.fetch_config(include={"bullets": True, "names": True})
    if typing.TYPE_CHECKING:
        assert config.bullets and isinstance(config.bullets, models.BulletConfig)
        assert config.names and isinstance(config.names, models.Names)

    if not config.bullets.bullets_enabled and not kwargs.get("manual_trigger"):
        ctx.bot.msg_enabled_bullets_guilds.discard(int(ctx.guild_id))
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

    message = await ctx.respond(
        view=truth_bullet.found_view(
            finder.mention, singular_bullet=config.names.singular_bullet
        ),
    )

    if not truth_bullet.hidden and (
        config.bullets.bullet_chan_id or not kwargs.get("manual_trigger")
    ):
        bullet_chan = await ctx.bot.getch_channel(config.bullets.bullet_chan_id or 0)
        if not bullet_chan or not isinstance(bullet_chan, discord.abc.Messageable):
            config.bullets.bullets_enabled = False
            ctx.bot.msg_enabled_bullets_guilds.discard(int(ctx.guild_id))
            config.bullets.bullet_chan_id = None
            await config.bullets.save()
            return

        try:
            await bullet_chan.send(
                view=truth_bullet.found_view(
                    finder.mention,
                    context_url=(
                        message.message.jump_url
                        if isinstance(message, discord.Interaction)
                        else message.jump_url
                    ),
                ),
            )
        except discord.HTTPException:
            raise utils.CustomCheckFailure(
                f"Cannot send messages to {bullet_chan.mention}. Staff, please"
                " check channel permissions."
            ) from None

    await truth_bullet.save(force_update=True)
    await check_for_finish(
        ctx.bot,
        ctx.guild,
        bullet_chan,
        config,
        okay_if_no_chan=kwargs.get("manual_trigger", False),
    )
