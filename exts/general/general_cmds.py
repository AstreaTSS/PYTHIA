"""
Copyright 2021-2026 AstreaTSS.
This file is part of PYTHIA.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

import asyncio
import importlib
import os
import subprocess
import time

import discord

import common.utils as utils


class GeneralCMDs(utils.Cog):
    def __init__(self, bot: utils.THIABase) -> None:
        self.bot = bot
        self.__cog_name__ = "General"

        self.invite_link = ""
        self.bot.create_task(self.when_ready())

    async def when_ready(self) -> None:
        await self.bot.wait_until_ready()
        self.invite_link = (
            f"https://discord.com/api/oauth2/authorize?client_id={self.bot.user.id}"
        )

    def _get_commit_hash(self) -> str | None:
        try:
            if os.environ.get("SOURCE_COMMIT"):
                return os.environ["SOURCE_COMMIT"][:7]

            return (
                subprocess.check_output(["git", "rev-parse", "--short", "HEAD"])
                .decode("ascii")
                .strip()
            )
        except Exception:  # screw it
            return None

    async def get_commit_hash(self) -> str | None:
        return await asyncio.to_thread(self._get_commit_hash)

    @discord.slash_command(
        name="ping",
        description=(
            "Pings the bot. Great way of finding out if the bot's working correctly,"
            " but has no real use."
        ),
        integration_types={
            discord.IntegrationType.guild_install,
            discord.IntegrationType.user_install,
        },
    )
    async def ping(self, ctx: utils.THIASlashContext) -> None:
        start_time = time.perf_counter()
        average_ping = round((self.bot.latency * 1000), 2)
        shard_id = self.bot.get_shard_id(ctx.guild_id) if ctx.guild_id else 0
        shard_ping = round((self.bot.get_shard(shard_id).latency * 1000), 2)

        await ctx.respond(
            view=utils.make_view(
                title="Pong!",
                description=(
                    f"Average Ping: `{average_ping}` ms\nShard Ping: `{shard_ping}`"
                    f" ms\nCalculating RTT...\n-# Shard ID: {shard_id}"
                ),
            )
        )

        # not really rtt ping but shh
        end_time = time.perf_counter()
        rtt_ping = round(((end_time - start_time) * 1000), 2)

        await ctx.edit(
            view=utils.make_view(
                title="Pong!",
                description=(
                    f"Average Ping: `{average_ping}` ms\nShard Ping: `{shard_ping}`"
                    f" ms\nRTT Ping: `{rtt_ping}` ms\n-# Shard ID: {shard_id}"
                ),
            )
        )

    @discord.slash_command(
        name="invite",
        description="Sends instructions on how to set up and invite the bot.",
        integration_types={
            discord.IntegrationType.guild_install,
            discord.IntegrationType.user_install,
        },
    )
    async def invite(self, ctx: utils.THIASlashContext) -> None:
        container = utils.make_container(
            title="Invite Bot",
            description=(
                "If you want to invite me to your server, it's a good idea to use the"
                " Server Setup Guides. However, if you know what you're doing, you can"
                " use the Invite Link instead."
            ),
        )
        container.add_separator(divider=False)
        container.add_row(
            discord.ui.Button(
                style=discord.ButtonStyle.url,
                label="Server Setup Guides",
                url="https://pythia.astrea.cc/setup",
            ),
            discord.ui.Button(
                style=discord.ButtonStyle.url,
                label="Invite Link",
                url=self.invite_link,
            ),
        )
        await ctx.respond(view=utils.quick_designer_view(container))

    @discord.slash_command(
        name="support",
        description="Gives an invite link to the support server.",
        integration_types={
            discord.IntegrationType.guild_install,
            discord.IntegrationType.user_install,
        },
    )
    async def support(self, ctx: utils.THIASlashContext) -> None:
        container = utils.make_container(
            title="Support Server",
            description=(
                "If you need help with the bot, or just want to hang out, join the"
                " support server!"
            ),
        )
        container.add_separator(divider=False)
        container.add_row(
            discord.ui.Button(
                style=discord.ButtonStyle.url,
                label="Join Support Server",
                url="https://discord.gg/NSdetwGjpK",
            )
        )
        await ctx.respond(view=utils.quick_designer_view(container))

    @discord.slash_command(
        name="help",
        description="Sends instructions on how to use the bot.",
        integration_types={
            discord.IntegrationType.guild_install,
            discord.IntegrationType.user_install,
        },
    )
    async def help(self, ctx: utils.THIASlashContext) -> None:
        container = utils.make_container(
            title="Help",
            description=(
                "For regular users, the best way to learn how to use the bot and its"
                " features is to check out the Usage Guides. For server owners and"
                " moderators, the Server Setup Guides provides instructions on how to"
                " configure the bot."
            ),
        )
        container.add_separator(divider=False)
        container.add_row(
            discord.ui.Button(
                style=discord.ButtonStyle.url,
                label="Usage Guides",
                url="https://pythia.astrea.cc/usage",
            ),
            discord.ui.Button(
                style=discord.ButtonStyle.url,
                label="Server Setup Guides",
                url="https://pythia.astrea.cc/setup",
            ),
        )
        await ctx.respond(view=utils.quick_designer_view(container))

    @discord.slash_command(
        name="about",
        description="Gives information about the bot.",
        integration_types={
            discord.IntegrationType.guild_install,
            discord.IntegrationType.user_install,
        },
    )
    async def about(self, ctx: utils.THIASlashContext) -> None:
        msg_list: list[str] = [
            (
                '> "Hello. I am PYTHIA, the Ultimate Robotic Assistant. I look forward'
                ' to assisting you in whatever tasks you may have."'
            ),
            (
                "PYTHIA is a bot meant to assist with Danganronpa/Killing Game"
                " roleplays. It serves as a way of automating many systems which would"
                " be otherwise quite complex or repetitive to do."
            ),
            (
                "To learn more and see all of the features PYTHIA currently has, feel"
                " free to take a look at the [PYTHIA"
                " website](https://pythia.astrea.cc)."
            ),
        ]

        about_embed = discord.Embed(
            color=self.bot.color,
            description="# About\n" + "\n\n".join(msg_list),
        )
        about_embed.set_thumbnail(
            url=(
                ctx.guild.me.display_avatar.url
                if ctx.guild
                else self.bot.user.display_avatar.url
            )
        )

        commit_hash = await self.get_commit_hash()
        command_num = len(self.bot.all_commands)  # TODO: how accurate is this?

        num_shards = len(self.bot.shards)
        shards_str = f"{num_shards} shards" if num_shards != 1 else "1 shard"

        about_embed.add_field(
            name="Stats",
            value="\n".join(
                (
                    f"Servers: {self.bot.guild_count} ({shards_str})",
                    f"Commands: {command_num} ",
                    (
                        "Startup Time:"
                        f" {discord.utils.format_dt(self.bot.start_time, style='R')}"
                    ),
                    (
                        "Commit Hash:"
                        f" [{commit_hash}](https://github.com/AstreaTSS/PYTHIA/commit/{commit_hash})"
                        if commit_hash
                        else "Commit Hash: N/A"
                    ),
                    (
                        "Pycord Version:"
                        f" [{discord.__version__}](https://github.com/Pycord-Development/pycord/tree/v{discord.__version__})"
                    ),
                    (
                        f"Python Version: {utils.PYTHON_IMPLEMENTATION}"
                        f" {utils.PYTHON_VERSION[0]}.{utils.PYTHON_VERSION[1]}"
                    ),
                    "Made By: [AstreaTSS](https://astrea.cc)",
                )
            ),
            inline=True,
        )

        links = [
            "Website: [Link](https://pythia.astrea.cc)",
            f"Invite Bot: [Link]({self.invite_link})",
            "Support Server: [Link](https://discord.gg/NSdetwGjpK)",
        ]

        if os.environ.get("TOP_GG_TOKEN"):
            links.append(f"Top.gg Page: [Link](https://top.gg/bot/{self.bot.user.id})")

        links.extend(
            (
                "Source Code: [Link](https://github.com/AstreaTSS/PYTHIA)",
                "Terms of Service: [Link](https://pythia.astrea.cc/legal/tos.html)",
                (
                    "Privacy Policy:"
                    " [Link](https://pythia.astrea.cc/legal/privacy_policy.html)"
                ),
            )
        )

        about_embed.add_field(
            name="Links",
            value="\n".join(links),
            inline=True,
        )
        about_embed.timestamp = discord.utils.utcnow()

        shard_id = self.bot.get_shard_id(ctx.guild_id) if ctx.guild_id else 0
        about_embed.set_footer(text=f"Shard ID: {shard_id}")

        await ctx.respond(embed=about_embed)


def setup(bot: utils.THIABase) -> None:
    importlib.reload(utils)
    bot.add_cog(GeneralCMDs(bot))
