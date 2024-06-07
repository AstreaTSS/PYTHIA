"""
Copyright 2021-2024 AstreaTSS.
This file is part of Ultimate Investigator.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

import asyncio
import collections
import importlib
import time
import typing

import cachetools
import interactions as ipy
import tansy
from interactions.client.mixins.send import SendMixin
from tortoise.expressions import Q

import common.models as models
import common.utils as utils


class BulletMsgCache(typing.NamedTuple):
    jump_url: str
    msg: ipy.Message | None = None


T = typing.TypeVar("T")
KT = typing.TypeVar("KT")
VT = typing.TypeVar("VT")


class LockedTTLDict(cachetools.TTLCache[KT, VT]):
    def __init__(
        self,
        maxsize: float,
        ttl: float,
        timer: typing.Callable[[], float] = time.monotonic,
        getsizeof: None = None,
    ) -> None:
        self.locks: collections.defaultdict[KT, asyncio.Lock] = collections.defaultdict(
            lambda: asyncio.Lock()
        )
        super().__init__(maxsize, ttl, timer, getsizeof)

    async def async_getitem(self, key: KT) -> VT:
        async with self.locks[key]:
            return self.__getitem__(key)

    @typing.overload
    async def async_get(self, key: KT) -> VT | None: ...

    @typing.overload
    async def async_get(self, key: KT, default: T) -> VT | T: ...

    async def async_get(self, key: KT, default: T | None = None) -> VT | T | None:
        async with self.locks[key]:
            return self.get(key, default)

    async def async_set(self, key: KT, value: VT) -> None:
        async with self.locks[key]:
            self.__setitem__(key, value)

    @typing.overload
    async def async_pop(self, key: KT) -> VT: ...

    @typing.overload
    async def async_pop(self, key: KT, default: T) -> VT | T: ...

    async def async_pop(self, key: KT, default: T | None = None) -> VT | T | None:
        async with self.locks[key]:
            data = self.pop(key, default)

        self.locks.pop(key, None)
        return data

    def expire(self, time: float | None = None) -> None:
        if time is None:
            time = self.timer()
        root = self._TTLCache__root  # type: ignore
        curr = root.next
        links = self._TTLCache__links  # type: ignore
        cache_delitem = cachetools.Cache.__delitem__
        while curr is not root and not (time < curr.expires):
            cache_delitem(self, curr.key)
            self.locks.pop(curr.key, None)
            del links[curr.key]
            our_next = curr.next
            curr.unlink()
            curr = our_next


class BulletFinding(utils.Extension):
    """The cog that deals with finding Truth Bullets."""

    def __init__(self, bot: utils.UIBase) -> None:
        self.bot: utils.UIBase = bot
        self.msg_cache: LockedTTLDict[ipy.Snowflake_Type, BulletMsgCache] = (
            LockedTTLDict(50, 60)
        )

    async def check_for_proxy(
        self,
        message: ipy.Message,
    ) -> None:
        def check(event: ipy.events.MessageCreate) -> bool:
            return event.message.content == message.content and bool(
                event.message.webhook_id
            )

        try:
            msg_event: ipy.events.MessageCreate = self.bot.wait_for(
                ipy.events.MessageCreate, checks=check, timeout=5
            )

            data = await self.msg_cache.async_get(message)
            if not data:
                return

            if data.msg:
                await data.msg.edit(
                    components=ipy.Button(
                        style=ipy.ButtonStyle.LINK,
                        label="Triggering Message",
                        url=msg_event.message.jump_url,
                    )
                )
                await self.msg_cache.async_pop(message)
                return

            await self.msg_cache.async_set(
                message, data._replace(jump_url=msg_event.message.jump_url)
            )

        except TimeoutError:
            await self.msg_cache.async_pop(message)

    async def check_for_finish(
        self,
        guild: ipy.Guild,
        bullet_chan: ipy.GuildText | None,
        guild_config: models.Config,
    ) -> None:
        if await models.TruthBullet.filter(guild_id=guild.id, found=False).exists():
            return

        counter: collections.Counter[int] = collections.Counter()

        async for bullet in models.TruthBullet.filter(guild_id=guild.id):
            counter[bullet.finder] += 1  # type: ignore

        most_found = counter.most_common(None)

        # number of truth bullets found by highest person
        most_found_num = most_found[0][1]
        # the next is just fancy code to check for ties and make a list for the top people
        most_found_people = tuple(p[0] for p in most_found if p[1] == most_found_num)

        plural = "" if len(most_found_people) == 1 else "s"

        str_builder: list[str] = [
            "**All Truth Bullets have been found.**",
            "",
            f"Best Truth Bullet Finder{plural} (found {most_found_num} Truth Bullets):",
        ]
        str_builder.extend(f"<@{person_id}>" for person_id in most_found_people)

        if not bullet_chan:
            bullet_chan = await self.bot.fetch_channel(guild_config.bullet_chan_id)
            if not bullet_chan or not isinstance(bullet_chan, SendMixin):
                guild_config.bullets_enabled = False
                self.bot.msg_enabled_bullets_guilds.discard(int(guild.id))
                guild_config.bullet_chan_id = None
                await guild_config.save()
                return

        await bullet_chan.send("\n".join(str_builder))

        guild_config.bullets_enabled = False
        await guild_config.save()
        self.bot.msg_enabled_bullets_guilds.discard(int(guild.id))

        if guild_config.best_bullet_finder_role and (
            best_bullet_finder_obj := guild.get_role(
                guild_config.best_bullet_finder_role
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

        guild_config = await models.Config.get_or_none(guild_id=message.guild.id)

        if not guild_config:
            return

        if (
            not guild_config.bullets_enabled
            or not guild_config.player_role
            or not message.author.has_role(guild_config.player_role)
            or guild_config.investigation_type == models.InvestigationType.COMMAND_ONLY
        ):
            if (
                not guild_config.bullets_enabled
                or guild_config.investigation_type
                == models.InvestigationType.COMMAND_ONLY
            ):
                self.bot.msg_enabled_bullets_guilds.discard(int(message.guild.id))
            return

        self.bot.create_task(self.check_for_proxy(message))

        bullet_found = await models.find_truth_bullet(
            message.channel.id, message.content
        )
        if not bullet_found:
            return

        await self.msg_cache.async_set(message, BulletMsgCache(message.jump_url))

        bullet_found.found = True
        bullet_found.finder = message.author.id

        bullet_chan: ipy.GuildText | None = None
        embed = bullet_found.found_embed(str(message.author))

        if not bullet_found.hidden:
            bullet_chan = await self.bot.fetch_channel(guild_config.bullet_chan_id)
            if not bullet_chan or not isinstance(bullet_chan, SendMixin):
                guild_config.bullets_enabled = False
                self.bot.msg_enabled_bullets_guilds.discard(int(message.guild.id))
                guild_config.bullet_chan_id = None
                await guild_config.save()
                return

            await message.reply(embed=embed)

            data = await self.msg_cache.async_getitem(message)
            new_msg = await bullet_chan.send(
                embed=embed,
                components=ipy.Button(
                    style=ipy.ButtonStyle.LINK,
                    label="Triggering Message",
                    url=data.jump_url,
                ),
            )
            await self.msg_cache.async_set(message, data._replace(msg=new_msg))
        else:
            try:
                data = await self.msg_cache.async_getitem(message)
                new_msg = await message.author.send(
                    embed=embed,
                    components=ipy.Button(
                        style=ipy.ButtonStyle.LINK,
                        label="Triggering Message",
                        url=data.jump_url,
                    ),
                )
                await self.msg_cache.async_set(message, data._replace(msg=new_msg))
            except ipy.errors.HTTPException:
                await message.channel.send(
                    f"{message.author.mention}, I couldn't DM you a Truth Bullet."
                    " Please enable DMs for this server and this bot and try again.",
                    delete_after=5,
                )
                return

        await bullet_found.save(force_update=True)
        await self.check_for_finish(message.guild, bullet_chan, guild_config)

    @tansy.slash_command(
        name="investigate",
        description=(
            "Investigate for Truth Bullets in the current channel. An alternative to"
            " sending a message."
        ),
    )
    @ipy.auto_defer(enabled=False)
    async def investigate(
        self,
        ctx: utils.UISlashContext,
        trigger: str = tansy.Option("The trigger to search for in this channel."),
    ) -> None:
        guild_config = await models.Config.get_or_none(guild_id=ctx.guild_id)

        if not guild_config or not guild_config.bullets_enabled:
            if guild_config:
                self.bot.msg_enabled_bullets_guilds.discard(int(ctx.guild_id))
            raise utils.CustomCheckFailure(
                "Truth Bullets are not enabled in this server."
            )

        if not guild_config.player_role or not ctx.author.has_role(
            guild_config.player_role
        ):
            raise utils.CustomCheckFailure(
                "Cannot investigate without the Player role."
            )

        truth_bullet = await models.TruthBullet.get_or_none(
            Q(channel_id=ctx.channel_id)
            & Q(Q(trigger__iexact=trigger) | Q(aliases__icontains=trigger))
        )
        if not truth_bullet:
            raise utils.CustomCheckFailure("No Truth Bullet found with this trigger.")

        await ctx.defer(ephemeral=truth_bullet.hidden)

        truth_bullet.found = True
        truth_bullet.finder = ctx.author.id

        bullet_chan: ipy.GuildText | None = None
        embed = truth_bullet.found_embed(str(ctx.author))

        message = await ctx.send(embed=embed, ephemeral=ctx.ephemeral)

        if not truth_bullet.hidden:
            bullet_chan = await self.bot.fetch_channel(guild_config.bullet_chan_id)
            if not bullet_chan or not isinstance(bullet_chan, SendMixin):
                guild_config.bullets_enabled = False
                self.bot.msg_enabled_bullets_guilds.discard(int(ctx.guild_id))
                guild_config.bullet_chan_id = None
                await guild_config.save()
                return

            await bullet_chan.send(
                embed=embed,
                components=ipy.Button(
                    style=ipy.ButtonStyle.LINK,
                    label="Triggering Message",
                    url=message.jump_url,
                ),
            )

        await truth_bullet.save(force_update=True)
        await self.check_for_finish(ctx.guild, bullet_chan, guild_config)


def setup(bot: utils.UIBase) -> None:
    importlib.reload(utils)
    BulletFinding(bot)
