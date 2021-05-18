import importlib
import typing

import discord
from discord.ext import commands

import common.models as models
import common.utils as utils


class ServerCMDs(commands.Cog, name="Server"):
    """Commands for using and modifying server settings."""

    def __init__(self, bot):
        self.bot = bot

    async def create_and_or_get(self, guild_id) -> models.Config:
        possible_guild = await models.Config.filter(guild_id=guild_id).first()
        if possible_guild is None:
            return await models.Config.create(
                guild_id=guild_id,
                bullet_chan_id=0,
                ult_detective_role=0,
                player_role=0,
                bullets_enabled=False,
            )
        else:
            return possible_guild

    @commands.command(aliases=["config"])
    @utils.proper_permissions()
    async def list_config(self, ctx: commands.Context):
        # sourcery skip: merge-list-append
        async with ctx.typing():
            guild_config = await self.create_and_or_get(ctx.guild.id)

            str_builder = []
            str_builder.append(
                f"Truth Bullets: {utils.toggle_friendly_str(guild_config.bullets_enabled)}"
            )
            str_builder.append(
                f"Truth Bullet channel: {f'<#{guild_config.bullet_chan_id}>' if guild_config.bullet_chan_id > 0 else 'None'}"
            )
            str_builder.append("")
            str_builder.append(
                f"Player role: {f'<@&{guild_config.player_role}>' if guild_config.player_role > 0 else 'None'}"
            )
            str_builder.append(
                f"Best Detective role: {f'<@&{guild_config.ult_detective_role}>' if guild_config.ult_detective_role > 0 else 'None'}"
            )

            embed = discord.Embed(
                title=f"Server config for {ctx.guild.name}",
                description="\n".join(str_builder),
                color=14232643,
            )
        await ctx.reply(embed=embed)

    @commands.command(aliases=["set_bull_chan", "set_bullets_channel"])
    @utils.proper_permissions()
    async def set_bullet_channel(
        self, ctx: commands.Context, channel: discord.TextChannel
    ):
        async with ctx.typing():
            guild_config = await self.create_and_or_get(ctx.guild.id)
            guild_config.bullet_chan_id = channel.id
            await guild_config.save()

        await ctx.reply(f"Truth Bullet channel set to {channel.mention}!")

    def check_for_none(self, argument: str):
        if argument.lower() == "none":
            return discord.Object(
                0
            )  # little hack so we don't have to do as much instance checking
        raise commands.BadArgument("Not 'none'!")

    @commands.command(
        aliases=[
            "set_ult_detect_role",
            "set_ult_detective_role",
            "set_ult_detect",
            "set_ult_detective",
            "set_ultimate_detective_role",
            "set_best_detect_role",
            "set_best_detect",
        ]
    )
    @utils.proper_permissions()
    async def set_best_detective_role(
        self, ctx: commands.Context, role: typing.Union[discord.Role, check_for_none]
    ):

        async with ctx.typing():
            guild_config = await self.create_and_or_get(ctx.guild.id)
            guild_config.ult_detective_role = role.id
            await guild_config.save()

        if isinstance(role, discord.Role):
            await ctx.reply(
                f"Best Detective role set to {role.mention}!",
                allowed_mentions=discord.AllowedMentions.none(),
            )
        else:
            await ctx.reply("Best Detective role unset!")

    @commands.command()
    @utils.proper_permissions()
    async def set_player_role(self, ctx: commands.Context, role: discord.Role):
        async with ctx.typing():
            guild_config = await self.create_and_or_get(ctx.guild.id)
            guild_config.player_role = role.id
            await guild_config.save()

        await ctx.reply(
            f"Player role set to {role.mention}!",
            allowed_mentions=discord.AllowedMentions.none(),
        )

    def enable_check(self, config: models.Config):
        if not config.player_role > 0:
            raise utils.CustomCheckFailure(
                "You still need to set a player role for this server!"
            )
        elif not config.bullet_chan_id > 0:
            raise utils.CustomCheckFailure(
                "You still need to set a Truth Bullets channel!"
            )

    @commands.command(aliases=["toggle_bullet"])
    @utils.proper_permissions()
    async def toggle_bullets(self, ctx: commands.Context):

        async with ctx.typing():
            guild_config = await self.create_and_or_get(ctx.guild.id)

            if (
                not guild_config.bullets_enabled
            ):  # if truth bullets will be enabled by this
                self.enable_check(guild_config)
            guild_config.bullets_enabled = not guild_config.bullets_enabled
            await guild_config.save()

        await ctx.reply(
            f"Truth Bullets turned {utils.toggle_friendly_str(guild_config.bullets_enabled)}!"
        )

    @commands.command(aliases=["enable_bullet"])
    @utils.proper_permissions()
    async def enable_bullets(self, ctx: commands.Context):
        async with ctx.typing():
            guild_config = await self.create_and_or_get(ctx.guild.id)

            self.enable_check(guild_config)
            guild_config.bullets_enabled = True
            await guild_config.save()

        await ctx.reply("Truth Bullets enabled!")

    @commands.command(aliases=["disable_bullet"])
    @utils.proper_permissions()
    async def disable_bullets(self, ctx: commands.Context):
        async with ctx.typing():
            guild_config = await self.create_and_or_get(ctx.guild.id)
            guild_config.bullets_enabled = False
            await guild_config.save()

        await ctx.reply("Truth Bullets disabled!")


def setup(bot):
    importlib.reload(utils)
    bot.add_cog(ServerCMDs(bot))
