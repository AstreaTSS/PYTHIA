"""
Copyright 2022-2024 AstreaTSS.
This file is part of Ultimate Investigator.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

import asyncio
import importlib
import subprocess
import time
from importlib.metadata import version as _v

import interactions as ipy
import tansy

import common.utils as utils

IPY_VERSION = _v("discord-py-interactions")


class OtherCMDs(utils.Extension):
    def __init__(self, bot: utils.UIBase) -> None:
        self.name = "General"
        self.bot: utils.UIBase = bot
        self.invite_link = ""

        self.bot.create_task(self.when_ready())

    async def when_ready(self) -> None:
        await self.bot.wait_until_ready()
        self.invite_link = f"https://discord.com/api/oauth2/authorize?client_id={self.bot.owner.id}&permissions=532576332864&scope=bot%20applications.commands"

    def _get_commit_hash(self) -> str | None:
        try:
            return (
                subprocess.check_output(["git", "rev-parse", "--short", "HEAD"])
                .decode("ascii")
                .strip()
            )
        except Exception:  # screw it
            return None

    async def get_commit_hash(self) -> str | None:
        return await asyncio.to_thread(self._get_commit_hash)

    @tansy.slash_command(
        "ping",
        description=(
            "Pings the bot. Great way of finding out if the bot's working correctly,"
            " but has no real use."
        ),
    )
    async def ping(self, ctx: utils.UIInteractionContext) -> None:
        start_time = time.perf_counter()
        average_ping = round((self.bot.latency * 1000), 2)

        embed = ipy.Embed(
            "Pong!", color=self.bot.color, timestamp=ipy.Timestamp.utcnow()
        )
        embed.description = f"Discord Ping: `{average_ping}` ms\nCalculating RTT..."

        mes = await ctx.send(embed=embed)

        end_time = time.perf_counter()
        # not really rtt ping but shh
        rtt_ping = round(((end_time - start_time) * 1000), 2)
        embed.description = (
            f"Discord Ping: `{average_ping}` ms\nRTT Ping: `{rtt_ping}` ms"
        )

        await ctx.edit(message=mes, embed=embed)

    @ipy.slash_command(
        name="invite",
        description="Sends instructions on how to set up and invite the bot.",
    )
    async def invite(self, ctx: utils.UISlashContext) -> None:
        embed = utils.make_embed(
            "If you want to invite me to your server, it's a good idea to use the"
            " Server Setup Guide. However, if you know what you're doing, you can"
            " use the Invite Link instead.",
            title="Invite Bot",
        )
        components = [
            ipy.Button(
                style=ipy.ButtonStyle.URL,
                label="Server Setup Guide",
                url="https://ui.astrea.cc/server_setup.html",
            ),
            ipy.Button(
                style=ipy.ButtonStyle.URL,
                label="Invite Link",
                url=self.invite_link,
            ),
        ]
        await ctx.send(embeds=embed, components=components)

    @ipy.slash_command(
        "support", description="Gives an invite link to the support server."
    )
    async def support(self, ctx: utils.UISlashContext) -> None:
        embed = utils.make_embed(
            "If you need help with the bot, or just want to hang out, join the"
            " support server!",
            title="Support Server",
        )
        button = ipy.Button(
            style=ipy.ButtonStyle.URL,
            label="Join Support Server",
            url="https://discord.gg/NSdetwGjpK",
        )
        await ctx.send(embeds=embed, components=button)

    @tansy.slash_command("about", description="Gives information about the bot.")
    async def about(self, ctx: ipy.InteractionContext) -> None:
        msg_list = [
            (
                "Hi! I'm the Ultimate Investigator, a bot meant to help out with"
                " investigations with Danganronpa RPs. I automate the parts of"
                " investigating that take up time and energy of hosts to make it easier"
                " for them to host the KG."
            ),
            (
                'I can handle anything related to "Truth Bullets" (or your KG\'s'
                " equivalent), managing and sending them out as needed."
            ),
        ]

        about_embed = ipy.Embed(
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
            self.bot.prefixed.commands
        )

        about_embed.add_field(
            name="Stats",
            value="\n".join((
                f"Servers: {len(self.bot.guilds)}",
                f"Commands: {command_num} ",
                (
                    "Startup Time:"
                    f" {ipy.Timestamp.fromdatetime(self.bot.start_time).format(ipy.TimestampStyles.RelativeTime)}"
                ),
                (
                    "Commit Hash:"
                    f" [{commit_hash}](https://github.com/AstreaTSS/UltimateInvestigator/commit/{commit_hash})"
                    if commit_hash
                    else "Commit Hash: N/A"
                ),
                (
                    "Interactions.py Version:"
                    f" [{IPY_VERSION}](https://github.com/interactions-py/interactions.py/tree/{IPY_VERSION})"
                ),
                "Made By: [AstreaTSS](https://astrea.cc)",
            )),
            inline=True,
        )

        links = [
            "Website: [Link](https://ui.astrea.cc)",
            f"Invite Bot: [Link]({self.invite_link})",
            "Support Server: [Link](https://discord.gg/NSdetwGjpK)",
            "Source Code: [Link](https://github.com/AstreaTSS/UltimateInvestigator)",
        ]

        about_embed.add_field(
            name="Links",
            value="\n".join(links),
            inline=True,
        )
        about_embed.timestamp = ipy.Timestamp.utcnow()

        await ctx.send(embed=about_embed)


def setup(bot: utils.UIBase) -> None:
    importlib.reload(utils)
    OtherCMDs(bot)
