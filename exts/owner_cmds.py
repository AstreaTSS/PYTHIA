"""
Copyright 2021-2026 AstreaTSS.
This file is part of PYTHIA.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

import asyncio
import contextlib
import importlib
import io
import platform
import textwrap
import traceback

import discord
import typing_extensions as typing
from discord.ext import commands

import common.classes as classes
import common.utils as utils


def debug_embed(title: str, **kwargs: typing.Any) -> discord.Embed:
    """Create a debug embed with a standard header and footer."""
    e = discord.Embed(
        title=f"Debug: {title}",
        color=utils.BOT_COLOR,
        **kwargs,
    )
    e.set_footer(
        text="PYTHIA Debug Extension",
    )
    return e


async def msg_to_owner(
    bot: "utils.THIABase",
    chunks: (
        list[str]
        | list[discord.Embed]
        | list[str | discord.Embed]
        | str
        | discord.Embed
    ),
) -> None:
    if not isinstance(chunks, list):
        chunks = [chunks]

    # sends a message to the owner
    for chunk in chunks:
        if isinstance(chunk, discord.Embed):
            await bot.owner.send(embed=chunk)
        else:
            await bot.owner.send(chunk)


def line_split(content: str, split_by: int = 20) -> list[list[str]]:
    content_split = content.splitlines()
    return [
        content_split[x : x + split_by] for x in range(0, len(content_split), split_by)
    ]


def error_format(error: Exception) -> str:
    # simple function that formats an exception
    return "".join(
        traceback.format_exception(  # type: ignore
            type(error), value=error, tb=error.__traceback__
        )
    )


class OwnerCMDs(utils.Cog):
    def __init__(self, bot: utils.THIABase) -> None:
        super().__init__(bot)

        self.__cog_name__ = "Owner"

    @commands.group(aliases=["jsk"], invoke_without_command=True)
    async def debug(self, ctx: utils.THIABridgeExtContext) -> None:
        """Get basic information about the bot."""
        e = debug_embed("General")
        e.set_thumbnail(url=self.bot.user.avatar.url)
        e.add_field(name="Operating System", value=platform.platform())

        e.add_field(
            name="Version Info",
            value=(
                f"pycord@{discord.__version__} |"
                f" {utils.PYTHON_IMPLEMENTATION}@{utils.PYTHON_VERSION}"
            ),
        )

        e.add_field(
            name="Start Time", value=discord.utils.format_dt(self.bot.start_time)
        )

        if privileged_intents := [
            n
            for n, v in iter(self.bot.intents)
            if v and n in {"presences", "members", "message_content"}
        ]:
            e.add_field(name="Privileged Intents", value=" | ".join(privileged_intents))

        e.add_field(
            name="Loaded Extensions",
            value=", ".join(self.bot.cogs.keys()),
            inline=False,
        )
        e.add_field(name="Guilds", value=str(len(self.bot.guilds)))

        await ctx.reply(embeds=[e])

    @debug.command(aliases=["restart"])
    async def shutdown(self, ctx: utils.THIABridgeExtContext) -> None:
        """Shuts down the bot."""
        await ctx.reply("Shutting down 😴")
        await self.bot.close()

    @debug.command()
    async def reload(self, ctx: utils.THIABridgeExtContext, *, module: str) -> None:
        """Reloads an extension."""
        self.bot.reload_extension(module)
        await ctx.reply(f"Reloaded `{module}`.")

    @debug.command()
    async def load(self, ctx: utils.THIABridgeExtContext, *, module: str) -> None:
        """Loads an extension."""
        self.bot.load_extension(module)
        await ctx.reply(f"Loaded `{module}`.")

    @debug.command()
    async def unload(self, ctx: utils.THIABridgeExtContext, *, module: str) -> None:
        """Unloads an extension."""
        self.bot.unload_extension(module)
        await ctx.reply(f"Unloaded `{module}`.")

    @debug.command(aliases=["reload_all", "reload-all", "reloadall"])
    async def reload_all_extensions(self, ctx: utils.THIABridgeExtContext) -> None:
        for ext in (e for e in self.bot.extensions):
            self.bot.reload_extension(ext)
        await ctx.reply("All extensions reloaded!")

    @debug.command(aliases=["python", "exc"])
    async def exec(
        self, ctx: utils.THIABridgeExtContext, *, body: str
    ) -> discord.Message:
        """Direct evaluation of Python code."""
        await ctx.channel.trigger_typing()
        env = {
            "bot": self.bot,
            "ctx": ctx,
            "channel": ctx.channel,
            "author": ctx.author,
            "server": ctx.guild,
            "guild": ctx.guild,
            "message": ctx.message,
        } | globals()

        body = (
            "\n".join(body.split("\n")[1:-1])
            if body.startswith("```") and body.endswith("```")
            else body.strip("` \n")
        )

        stdout = io.StringIO()

        to_compile = f"async def func():\n{textwrap.indent(body, ' ')}"
        try:
            exec(to_compile, env)  # noqa: S102
        except SyntaxError:
            return await ctx.reply(f"```py\n{traceback.format_exc()}\n```")

        func = env["func"]
        try:
            with contextlib.redirect_stdout(stdout):
                ret = await func()
        except Exception:
            await ctx.message.add_reaction("❌")
            raise
        else:
            return await self.handle_exec_result(ctx, ret, stdout.getvalue())

    async def handle_exec_result(
        self, ctx: utils.THIABridgeExtContext, result: typing.Any, value: typing.Any
    ) -> discord.Message:
        if result is None:
            result = value or "No Output!"

        await ctx.message.add_reaction("✅")

        if isinstance(result, discord.Message):
            try:
                e = debug_embed(
                    "Exec", timestamp=result.created_at, url=result.jump_url
                )
                e.description = result.content
                e.set_author(
                    name=str(result.author),
                    icon_url=result.author.display_avatar.url,
                )
                e.add_field(
                    name="\u200b",
                    value=f"[Jump To]({result.jump_url})\n{result.channel.mention}",
                )

                return await ctx.message.reply(embeds=e)
            except Exception:
                return await ctx.message.reply(result.jump_url)

        if isinstance(result, discord.Embed):
            return await ctx.message.reply(embed=result)

        if isinstance(result, discord.File):
            return await ctx.message.reply(file=result)

        if hasattr(result, "__iter__"):
            l_result = list(result)
            if all(isinstance(r, discord.Embed) for r in result):
                paginator = classes.EmbedPaginator(*l_result, author_id=ctx.author.id)
                return await paginator.respond(ctx)

        if not isinstance(result, str):
            result = repr(result)

        # prevent token leak
        result = result.replace(self.bot.http.token, "[REDACTED TOKEN]")

        if len(result) <= 2000:
            return await ctx.message.reply(f"```py\n{result}```")

        paginator = classes.ContainerPaginator.create_from_string(
            title="Exec Output",
            author_id=ctx.author.id,
            content=result,
            prefix="```py",
            suffix="```",
        )
        return await ctx.message.reply(view=paginator)

    @debug.command()
    async def shell(
        self, ctx: utils.THIABridgeExtContext, *, cmd: str
    ) -> discord.Message:
        """Executes statements in the system shell."""
        async with ctx.channel.typing():
            process = await asyncio.create_subprocess_shell(
                cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
            )

            output, _ = await process.communicate()
            output_str = output.decode("utf-8")
            output_str += f"\nReturn code {process.returncode}"

        if len(output_str) <= 2000:
            return await ctx.message.reply(f"```sh\n{output_str}```")

        paginator = classes.ContainerPaginator.create_from_string(
            title="Shell Output",
            author_id=ctx.author.id,
            content=output_str,
            prefix="```sh",
            suffix="```",
        )
        return await ctx.message.reply(view=paginator)

    @debug.command()
    async def git(
        self, ctx: utils.THIABridgeExtContext, *, cmd: str | None = None
    ) -> None:
        """Shortcut for 'debug shell git'. Invokes the system shell."""
        await self.shell(ctx, cmd=f"git {cmd}" if cmd else "git")

    @debug.command()
    async def pip(
        self, ctx: utils.THIABridgeExtContext, *, cmd: str | None = None
    ) -> None:
        """Shortcut for 'debug shell pip'. Invokes the system shell."""
        await self.shell(ctx, cmd=f"pip {cmd}" if cmd else "pip")

    @debug.command(aliases=["sync-interactions", "sync-cmds", "sync_cmds", "sync"])
    async def sync_interactions(self, ctx: utils.THIABridgeExtContext) -> None:
        """
        Synchronizes all interaction commands with Discord.

        Should not be used lightly.
        """
        # syncing interactions in inherently intensive and
        # has a high risk of running into the ratelimit
        # while this is fine for a small bot where it's unlikely
        # to even matter, for big bots, running into this ratelimit
        # can cause havoc on other functions

        async with ctx.channel.typing():
            await self.bot.sync_commands()

        await ctx.reply("Done!")

    def cog_check(self, ctx: utils.THIABridgeExtContext) -> bool:
        return ctx.author.id == self.bot.owner.id

    async def cog_command_error(
        self, ctx: utils.THIABridgeExtContext, error: Exception
    ) -> None:
        if isinstance(error, commands.CheckFailure):
            if hasattr(ctx, "send"):
                await ctx.send("Nice try.")
            return

        error_str = error_format(error)
        chunks = line_split(error_str)

        for i in range(len(chunks)):
            chunks[i][0] = f"```py\n{chunks[i][0]}"
            chunks[i][len(chunks[i]) - 1] += "\n```"

        final_chunks = ["\n".join(chunk) for chunk in chunks]
        final_chunks.insert(0, f"Error on: {ctx.message.jump_url}")

        to_send = final_chunks

        await msg_to_owner(self.bot, to_send)
        await ctx.send("An error occured. Please check your DMs.")


def setup(bot: utils.THIABase) -> None:
    importlib.reload(utils)
    OwnerCMDs(bot)
