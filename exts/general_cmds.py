import asyncio
import importlib
import subprocess
import time

import naff
import tansy

import common.utils as utils


class OtherCMDs(utils.Extension):
    def __init__(self, bot: utils.UIBase):
        self.name = "General"
        self.bot: utils.UIBase = bot
        self.invite_link = ""

        asyncio.create_task(self.when_ready())

    async def when_ready(self) -> None:
        await self.bot.wait_until_ready()
        self.invite_link = f"https://discord.com/api/oauth2/authorize?client_id={self.bot.owner.id}&permissions=8&scope=bot%20applications.commands"

    def _get_commit_hash(self):
        return (
            subprocess.check_output(["git", "rev-parse", "--short", "HEAD"])
            .decode("ascii")
            .strip()
        )

    async def get_commit_hash(self):
        return await asyncio.to_thread(self._get_commit_hash)

    @tansy.slash_command(
        "ping",
        description=(
            "Pings the bot. Great way of finding out if the bot's working correctly,"
            " but has no real use."
        ),
    )
    async def ping(self, ctx: utils.InvestigatorContext) -> None:
        start_time = time.perf_counter()
        ping_discord = round((self.bot.latency * 1000), 2)

        mes = await ctx.send(
            f"Pong!\n`{ping_discord}` ms from Discord.\nCalculating personal ping..."
        )

        end_time = time.perf_counter()
        ping_personal = round(((end_time - start_time) * 1000), 2)

        await ctx.edit(
            message=mes,
            content=(
                f"Pong!\n`{ping_discord}` ms from Discord.\n`{ping_personal}` ms"
                " personally."
            ),
        )

    @tansy.slash_command(
        name="invite",
        description="Sends the link to invite the bot to your server.",
    )
    async def invite(self, ctx: utils.InvestigatorContext):
        await ctx.send(self.invite_link)

    @tansy.slash_command(
        "support",
        description="Gives an invite link to the support server.",
    )
    async def support(self, ctx: utils.InvestigatorContext):
        await ctx.send("Support server:\nhttps://discord.gg/NSdetwGjpK")

    @tansy.slash_command("about", description="Gives information about the bot.")
    async def about(self, ctx: naff.InteractionContext):
        msg_list = [
            (
                "Hi! I'm the Ultimate Investigator, a bot meant to help out with"
                " investigations with Danganronpa RPs. I automate the parts of"
                " investigating that take up time and energy of hosts to make it easier"
                " for them to host the KG."
            ),
            (
                'I can handle anything related to "Truth Bullets" (or you KG'
                " equivalent), managing and sending them out as needed."
            ),
        ]

        about_embed = naff.Embed(
            title="About",
            color=self.bot.color,
            description="\n".join(msg_list),
        )
        about_embed.set_thumbnail(
            ctx.guild.me.display_avatar.url
            if ctx.guild
            else self.bot.user.display_avatar.url
        )

        commit_hash = await self.get_commit_hash()
        command_num = len(self.bot.application_commands) + len(
            self.bot.prefixed_commands
        )

        about_embed.add_field(
            name="Stats",
            value="\n".join(
                (
                    f"Servers: {len(self.bot.guilds)}",
                    f"Commands: {command_num} ",
                    (
                        "Startup Time:"
                        f" {naff.Timestamp.fromdatetime(self.bot.start_time).format(naff.TimestampStyles.RelativeTime)}"
                    ),
                    (
                        "Commit Hash:"
                        f" [{commit_hash}](https://github.com/AstreaTSS/UltimateInvestigator/commit/{commit_hash})"
                    ),
                    (
                        "NAFF Version:"
                        f" [{naff.const.__version__}](https://github.com/NAFTeam/NAFF/tree/NAFF-{naff.const.__version__})"
                    ),
                    "Made By: [AstreaTSS](https://github.com/AstreaTSS)",
                )
            ),
            inline=True,
        )

        links = [
            f"Invite Bot: [Link]({self.invite_link})",
            "Support Server: [Link](https://discord.gg/NSdetwGjpK)",
            "Source Code: [Link](https://github.com/AstreaTSS/UltimateInvestigator)",
        ]

        about_embed.add_field(
            name="Links:",
            value="\n".join(links),
            inline=True,
        )
        about_embed.timestamp = naff.Timestamp.utcnow()

        await ctx.send(embed=about_embed)


def setup(bot):
    importlib.reload(utils)
    OtherCMDs(bot)
