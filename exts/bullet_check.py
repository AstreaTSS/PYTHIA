import asyncio
import collections
import importlib
import typing

import naff
from tortoise.connection import connections

import common.models as models
import common.utils as utils

# a very complicated way of saying
# find a truth bullet that has a channel id of our first value, and either has:
# - the name in the second value (a string) we provide
# - an alias in the second value we provide
BULLET_QUERY = f"""
SELECT *
FROM {models.TruthBullet.Meta.table}
WHERE channel_id=$1 and found = false
AND ($2 ILIKE '%' || name || '%'
OR (EXISTS (SELECT 1 FROM unnest(aliases) a WHERE $2 ILIKE '%' || a || '%')))
""".strip()


class BulletCheck(utils.Extension):
    """The cog that checks for the Truth Bullets."""

    bot: utils.UIBase

    def __init__(self, bot: utils.UIBase):
        self.bot = bot

    async def check_for_finish(
        self,
        guild: naff.Guild,
        bullet_chan: naff.GuildText,
        guild_config: models.Config,
    ):
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

        if guild_config.ult_detective_role:  # if the role had been specified
            if ult_detect_role_obj := guild.get_role(guild_config.ult_detective_role):
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
                    except naff.errors.HTTPException:
                        continue

    @naff.listen("message_create")
    async def on_message(self, event: naff.events.MessageCreate):
        message = event.message

        # if the message is from a bot, from discord, not from a guild, not a default message or a reply, or is empty
        if (
            message.author.bot
            or message.author.system
            or not message.guild
            or message.type not in {naff.MessageTypes.DEFAULT, naff.MessageTypes.REPLY}
            or not message.content
        ):
            return

        guild_config = await models.Config.get_or_none(guild_id=message.guild.id)

        if not guild_config:
            return

        if not (
            guild_config.bullets_enabled
            and guild_config.player_role
            # internal list that has list of ids, faster than using roles property
            and message.author.has_role(guild_config.player_role)
        ):
            return

        bullet_found: typing.Optional[models.TruthBullet] = None

        channel_id = (
            message.channel.parent_channel.id
            if isinstance(message.channel, naff.ThreadChannel)
            else message.channel.id
        )

        possible_bullet = await connections.get("default").execute_query(
            BULLET_QUERY, [channel_id, message.content]
        )

        if possible_bullet[0] == 0:
            return

        bullet_found = models.TruthBullet(**possible_bullet[1][0])

        bullet_chan: naff.GuildText = self.bot.get_channel(guild_config.bullet_chan_id)
        if not bullet_chan:
            guild_config.bullets_enabled = False
            guild_config.bullet_chan_id = None
            await guild_config.save()
            return

        bullet_found.found = True
        bullet_found.finder = message.author.id

        embed = bullet_found.found_embed(str(message.author))

        await message.reply(embed=embed)
        await bullet_chan.send(embed=embed)

        await bullet_found.save(force_update=True)
        await self.check_for_finish(message.guild, bullet_chan, guild_config)


def setup(bot):
    importlib.reload(utils)
    BulletCheck(bot)
