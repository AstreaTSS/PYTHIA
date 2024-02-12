"""
This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

import asyncio
import collections
import importlib

import interactions as ipy

import common.models as models
import common.utils as utils


class BulletCheck(utils.Extension):
    """The cog that checks for the Truth Bullets."""

    def __init__(self, bot: utils.UIBase) -> None:
        self.bot: utils.UIBase = bot

    async def check_for_finish(
        self,
        guild: ipy.Guild,
        bullet_chan: ipy.GuildText,
        guild_config: models.Config,
    ) -> None:
        if await models.TruthBullet.filter(guild_id=guild.id, found=False).exists():
            return

        counter: collections.Counter[int] = collections.Counter()

        async for bullet in models.TruthBullet.filter(guild_id=guild.id):
            counter[bullet.finder] += 1  # type: ignore

        most_found = counter.most_common(None)
        most_found_num = most_found[0][
            1
        ]  # number of truth bullets found by highest person
        # the next is just fancy code to check for ties and make a list for the top people
        most_found_people = tuple(p[0] for p in most_found if p[1] == most_found_num)

        str_builder: list[str] = [
            "**All Truth Bullets have been found.**",
            "",
            f"Best Truth Bullet Finder(s) (found {most_found_num} Truth Bullets):",
        ]
        str_builder.extend(f"<@{person_id}>" for person_id in most_found_people)

        await bullet_chan.send("\n".join(str_builder))

        guild_config.bullets_enabled = False
        await guild_config.save()

        if guild_config.ult_detective_role and (
            ult_detect_role_obj := guild.get_role(guild_config.ult_detective_role)
        ):
            for person_id in most_found_people:
                try:
                    # use an internal method to save on an http request
                    # we get to skip out on asking for the member, which was
                    # pointless to do for our needs
                    # but dont do this unless you're me

                    await self.bot.http.add_guild_member_role(
                        guild.id, person_id, ult_detect_role_obj.id
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

        guild_config = await models.Config.get_or_none(guild_id=message.guild.id)

        if not guild_config:
            return

        if (
            not guild_config.bullets_enabled
            or not guild_config.player_role
            or not message.author.has_role(guild_config.player_role)
        ):
            return

        bullet_found = await models.find_truth_bullet(
            message.channel.id, message.content
        )
        if not bullet_found:
            return

        bullet_chan: ipy.GuildText | None = await self.bot.fetch_channel(
            guild_config.bullet_chan_id
        )
        if not bullet_chan:
            guild_config.bullets_enabled = False
            guild_config.bullet_chan_id = None
            await guild_config.save()
            return

        bullet_found.found = True
        bullet_found.finder = message.author.id

        embed = bullet_found.found_embed(str(message.author))

        await message.reply(embed=embed)
        await bullet_chan.send(
            embed=embed,
            components=ipy.Button(
                style=ipy.ButtonStyle.LINK,
                label="Triggering Message",
                url=message.jump_url,
            ),
        )

        await bullet_found.save(force_update=True)
        await self.check_for_finish(message.guild, bullet_chan, guild_config)


def setup(bot: utils.UIBase) -> None:
    importlib.reload(utils)
    BulletCheck(bot)
