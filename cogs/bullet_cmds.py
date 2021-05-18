import collections
import importlib

import discord
from discord.ext import commands

import common.models as models
import common.utils as utils


class BulletCMDs(commands.Cog, name="Bullet"):
    """Commands for using and modifying Truth Bullets."""

    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @utils.proper_permissions()
    async def add_bullet(
        self,
        ctx: commands.Context,
        channel: discord.TextChannel,
        name: str,
        *,
        description: str,
    ):
        possible_duplicate = await models.TruthBullet.exists(
            channel_id=channel.id, name=name
        )
        if possible_duplicate:
            raise commands.BadArgument(f"Truth Bullet `{name}` already exists!")

        await models.TruthBullet.create(
            name=name,
            description=description,
            channel_id=channel.id,
            guild_id=ctx.guild.id,
            found=False,
            finder=0,
        )

        await ctx.reply("Added Truth Bullet!")

    @commands.command()
    @utils.proper_permissions()
    async def remove_bullet(
        self, ctx: commands.Context, channel: discord.TextChannel, name: str,
    ):
        num_deleted = await models.TruthBullet.filter(
            channel_id=channel.id, name=name
        ).delete()

        if num_deleted > 0:
            await ctx.reply(f"`{name}` deleted!")
        else:
            raise commands.BadArgument(f"Truth Bullet `{name}` does not exists!")

    @commands.command()
    @utils.proper_permissions()
    async def clear_bullets(self, ctx: commands.Context):
        num_deleted = await models.TruthBullet.filter(guild_id=ctx.guild.id).delete()

        # just to give a more clear indication to users
        # technically everything's fine without this
        if num_deleted > 0:
            await ctx.reply("Cleared all Truth Bullets for this server!")
        else:
            raise utils.CustomCheckFailure(
                "There's no Truth Bullets to delete for this server!"
            )

    @commands.command()
    @utils.proper_permissions()
    async def list_bullets(self, ctx: commands.Context):
        guild_bullets = await models.TruthBullet.filter(guild_id=ctx.guild.id)

        bullet_dict = collections.defaultdict(list)
        for bullet in guild_bullets:
            bullet_dict[bullet.channel_id].append(bullet)

        str_builder = collections.deque()

        for channel_id in bullet_dict.keys():
            str_builder.append(f"<#{channel_id}>:")
            for bullet in bullet_dict[channel_id]:
                str_builder.append(
                    f"\t- `{bullet.name}`{'' if not bullet.found else ' (found)'}"
                )

            str_builder.append("")

        chunks = utils.line_split("\n".join(str_builder), split_by=30)
        for chunk in chunks:
            await ctx.reply("\n".join(chunk))

    @commands.command()
    @utils.proper_permissions()
    async def bullet_info(
        self, ctx: commands.Context, channel: discord.TextChannel, name: str,
    ):
        possible_bullet = await models.TruthBullet.filter(
            channel_id=channel.id, name=name
        ).first()

        if possible_bullet is None:
            raise commands.BadArgument(f"Truth Bullet `{name}` does not exist!")

        await ctx.reply(
            str(possible_bullet), allowed_mentions=utils.deny_mentions(ctx.author)
        )

    @commands.command()
    @utils.proper_permissions()
    async def edit_bullet(
        self,
        ctx: commands.Context,
        channel: discord.TextChannel,
        name: str,
        *,
        description: str,
    ):
        possible_bullet = await models.TruthBullet.filter(
            channel_id=channel.id, name=name
        ).first()
        if possible_bullet is None:
            raise commands.BadArgument(f"Truth Bullet `{name}` does not exist!")

        possible_bullet.description = description
        await possible_bullet.save()

        await ctx.reply("Edited Truth Bullet!")

    @commands.command()
    @utils.proper_permissions()
    async def unfind_bullet(
        self, ctx: commands.Context, channel: discord.TextChannel, name: str
    ):
        possible_bullet = await models.TruthBullet.filter(
            channel_id=channel.id, name=name
        ).first()
        if possible_bullet is None:
            raise commands.BadArgument(f"Truth Bullet `{name}` does not exist!")

        if not possible_bullet.found:
            raise commands.BadArgument(f"Truth Bullet `{name}` has not been found!")

        possible_bullet.found = True
        possible_bullet.finder = 0
        await possible_bullet.save()

        await ctx.reply("Truth Bullet un-found!")

    @commands.command()
    @utils.proper_permissions()
    async def override_bullet(
        self,
        ctx: commands.Context,
        channel: discord.TextChannel,
        name: str,
        user: discord.Member,
    ):
        possible_bullet = await models.TruthBullet.filter(
            channel_id=channel.id, name=name
        ).first()
        if possible_bullet is None:
            raise commands.BadArgument(f"Truth Bullet `{name}` does not exist!")

        possible_bullet.found = True
        possible_bullet.finder = user.id
        await possible_bullet.save()

        await ctx.reply("Truth Bullet overrided and found!")


def setup(bot):
    importlib.reload(utils)
    bot.add_cog(BulletCMDs(bot))
