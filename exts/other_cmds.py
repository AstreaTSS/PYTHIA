import importlib
import time

import naff

import common.utils as utils


class OtherCMDs(utils.Extension):
    bot: utils.UIBase

    def __init__(self, bot):
        self.name = "Other"
        self.bot = bot

    @naff.slash_command(
        name="ping",
        description=(
            "Pings the bot. Great way of finding out if the bot’s working, but has no"
            " real use."
        ),
    )
    async def ping(self, ctx: naff.InteractionContext):
        await ctx.defer()

        start_time = time.perf_counter()
        ping_discord = round((self.bot.latency * 1000), 2)

        mes = await ctx.send(
            content=(
                f"Pong!\n`{ping_discord}` ms from Discord.\nCalculating personal"
                " ping..."
            ),
        )

        end_time = time.perf_counter()
        ping_personal = round(((end_time - start_time) * 1000), 2)

        await mes.edit(
            content=(
                f"Pong!\n`{ping_discord}` ms from Discord.\n`{ping_personal}` ms"
                " personally."
            )
        )

    @naff.slash_command(
        "support", description="Gives an invite link to the support server."
    )
    async def support(self, ctx: naff.InteractionContext):
        await ctx.send("Support server:\nhttps://discord.gg/NSdetwGjpK")

    @naff.slash_command("about", description="Gives information about the bot.")
    async def about(self, ctx: naff.InteractionContext):
        msg_list = [
            (
                "Hi! I'm the Ultimate Investigator, a bot meant to help out with"
                " investigations with Danganronpa RPs."
            ),
            (
                "Niche, I know, but it was a demand, as otherwise, you would have to do"
                " it all manually."
            ),
            "",
            (
                "This bot was originally a series of custom commands in YAGPDB, but"
                " soon the commands grew too complex for it."
            ),
            "Still would recommend YAG, though. Just don't squeeze it to its limits.",
            "",
            (
                "Also, in case you were wondering, the reason why I don't just use the"
                " Ultimate Assistant is because most people, "
                + "quite frankly, don't need everything the Ultimate Assistant has."
                " It's also rather bloated and cumbersome, in my opinion."
            ),
            "",
            "If you wish to invite me, contact Astrea and she'll talk to you about it.",
            (
                "If you need support for me, maybe take a look at the support server"
                " here:\nhttps://discord.gg/NSdetwGjpK"
            ),
            "",
            "Bot made by Astrea#7171.",
        ]

        about_embed = naff.Embed(
            title="About",
            color=self.bot.color,
            description="\n".join(msg_list),
        )
        about_embed.set_author(
            name=f"{self.bot.user.username}",
            icon_url=f"{ctx.guild.me.display_avatar.url}",
        )

        source_list = [
            (
                "My source code is"
                " [here!](https://github.com/Astrea49/UltimateInvestigator)"
            ),
            (
                "This code might not be the best code out there, but you may have some"
                " use for it."
            ),
            "Note that much of it was based off my other bot, Seraphim.",
        ]

        about_embed.add_field(
            name="Source Code", value="\n".join(source_list), inline=False
        )

        await ctx.send(embed=about_embed)

    @naff.prefixed_command(aliases=["prefix"], ignore_extra=False)
    async def prefixes(self, ctx: naff.PrefixedContext):
        """A way of getting all of the prefixes for this server. You can also add and remove prefixes via this command.
        """

        async with ctx.channel.typing:
            guild_config = self.bot.cached_configs.get(
                ctx.message.id
            ) or await utils.create_or_get(ctx.guild.id)

        if prefixes := tuple(f"`{p}`" for p in guild_config.prefixes):
            await ctx.reply(
                f"My prefixes for this server are: `{', '.join(prefixes)}`, but you can"
                " also mention me."
            )
        else:
            await ctx.reply(
                "I have no prefixes on this server, but you can mention me to run a"
                " command."
            )

    @prefixes.subcommand(ignore_extra=False)
    @utils.proper_permissions()
    async def add(self, ctx: naff.PrefixedContext, prefix: str):
        """Addes the prefix to the bot for the server this command is used in, allowing it to be used for commands of the bot.
        If it's more than one word or has a space at the end, surround the prefix with quotes so it doesn't get lost.
        Requires Manage Guild permissions."""

        if not prefix:
            raise naff.errors.BadArgument("This is an empty string! I cannot use this.")
        if len(prefix) > 40:
            raise naff.errors.BadArgument(
                "This prefix is too long! It must be less than 40 characters"
            )

        async with ctx.channel.typing:
            guild_config = self.bot.cached_configs.get(
                ctx.message.id
            ) or await utils.create_or_get(ctx.guild.id)
            if len(guild_config.prefixes) >= 10:
                raise utils.CustomCheckFailure(
                    "You have too many prefixes! You can only have up to 10 prefixes."
                )

            if prefix in guild_config.prefixes:
                raise naff.errors.BadArgument("The server already has this prefix!")

            guild_config.prefixes.add(prefix)
            ctx.bot.cached_prefixes[ctx.guild.id].add(prefix)
            await guild_config.save()

        await ctx.reply(f"Added `{prefix}`!")

    @prefixes.subcommand(ignore_extra=False, aliases=["delete"])
    @utils.proper_permissions()
    async def remove(self, ctx: naff.PrefixedContext, prefix: str):
        """Deletes a prefix from the bot from the server this command is used in. The prefix must have existed in the first place.
        If it's more than one word or has a space at the end, surround the prefix with quotes so it doesn't get lost.
        Requires Manage Guild permissions."""

        async with ctx.channel.typing:
            try:
                guild_config = self.bot.cached_configs.get(
                    ctx.message.id
                ) or await utils.create_or_get(ctx.guild.id)
                guild_config.prefixes.remove(prefix)
                self.bot.cached_prefixes[ctx.guild.id].remove(prefix)
                await guild_config.save()

            except KeyError:
                raise naff.errors.BadArgument(
                    "The server doesn't have that prefix, so I can't delete it!"
                )

        await ctx.reply(f"Removed `{prefix}`!")


def setup(bot):
    importlib.reload(utils)
    OtherCMDs(bot)
