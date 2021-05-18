import time

import discord
from discord.ext import commands


class NormCMDs(commands.Cog, name="Normal"):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def ping(self, ctx):
        """Pings the bot. Great way of finding out if the bot’s working correctly, but otherwise has no real use."""

        start_time = time.perf_counter()
        ping_discord = round((self.bot.latency * 1000), 2)

        mes = await ctx.reply(
            f"Pong!\n`{ping_discord}` ms from Discord.\nCalculating personal ping..."
        )

        end_time = time.perf_counter()
        ping_personal = round(((end_time - start_time) * 1000), 2)

        await mes.edit(
            content=f"Pong!\n`{ping_discord}` ms from Discord.\n`{ping_personal}` ms personally."
        )

    @commands.command()
    async def support(self, ctx):
        """Gives an invite link to the support server."""
        await ctx.reply("Support server:\nhttps://discord.gg/NSdetwGjpK")

    @commands.command()
    async def invite(self, ctx):
        """Gives an invite link to invite the bot... or not.
        It's a private bot. I can't let this thing grow exponentially."""
        await ctx.reply("Contact Sonic49 in order to invite me.")

    @commands.command()
    async def about(self, ctx):
        """Gives information about the bot."""

        msg_list = [
            "Hi! I'm the Ultimate Investigator, a bot meant to help out with investigations with Danganronpa RPs.",
            "Niche, I know, but it was a demand, as otherwise, you would have to do it all manually.",
            "This bot was originally a series of custom commands in YAGPDB, but soon the commands grew too complex for it.",
            "Still would recommend YAG, though. Just don't squeeze it to its limits.",
            (
                "Also, in case you were wondering, the reason why I don't just use the Ultimate Assistant is because most people, "
                + "quite frankly, don't need everything the Ultimate Assistant has. It's also rather bloated and cumbersome, in my opinion."
            ),
            "Made by Sonic49#7171.",
            "",
            "If you wish to invite me, contact Sonic49 and he'll talk to you about it.",
            "If you need support for me, maybe take a look at the support server here:\nhttps://discord.gg/NSdetwGjpK",
        ]

        about_embed = discord.Embed(
            title="About",
            colour=discord.Colour(14232643),
            description="\n".join(msg_list),
        )
        about_embed.set_author(
            name=f"{self.bot.user.name}",
            icon_url=f"{str(ctx.guild.me.avatar_url_as(format=None,static_format='png', size=128))}",
        )

        source_list = [
            "My source code is [here!](https://github.com/Sonic4999/UltimateInvestigator)",
            "This code might not be the best code out there, but you may have some use for it.",
            "Note that much of it was based off my other bot, Seraphim.",
        ]

        about_embed.add_field(
            name="Source Code", value="\n".join(source_list), inline=False
        )

        await ctx.reply(embed=about_embed)

    @commands.command()
    async def prefix(self, ctx):
        """Gives the prefix of the bot."""
        await ctx.reply(f"My prefix is `u!`, but you can also mention me.")


def setup(bot):
    bot.add_cog(NormCMDs(bot))
