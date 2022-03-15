import asyncio
import contextlib
import io
import logging
import platform
import textwrap
import traceback
import typing

import dis_snek
import molter
from dis_snek.ext import paginators
from dis_snek.ext.debug_scale.utils import debug_embed
from dis_snek.ext.debug_scale.utils import get_cache_state

log = logging.getLogger(dis_snek.const.logger_name)


class DebugScale(molter.MolterScale):
    """A reimplementation of dis_snek's native debug commands."""

    def __init__(self, bot):
        self.display_name = "Debug"
        self.add_scale_check(dis_snek.checks.is_owner())

    @molter.msg_command(aliases=["jsk"])
    async def debug(self, ctx: dis_snek.MessageContext):
        """Get basic information about the bot."""
        uptime = dis_snek.Timestamp.fromdatetime(self.bot.start_time)
        e = debug_embed("General")
        e.set_thumbnail(self.bot.user.avatar.url)
        e.add_field("Operating System", platform.platform())

        e.add_field(
            "Version Info",
            f"Dis-Snek@{dis_snek.__version__} | Py@{dis_snek.__py_version__}",
        )

        e.add_field(
            "Start Time", f"{uptime.format(dis_snek.TimestampStyles.RelativeTime)}"
        )

        if privileged_intents := [
            i.name for i in self.bot.intents if i in dis_snek.Intents.PRIVILEGED
        ]:
            e.add_field("Privileged Intents", " | ".join(privileged_intents))

        e.add_field("Loaded Scales", ", ".join(self.bot.scales))

        e.add_field("Guilds", str(len(self.bot.guilds)))

        await ctx.reply(embeds=[e])

    @debug.subcommand(aliases=["cache"])
    async def cache_info(self, ctx: dis_snek.MessageContext):
        """Get information about the current cache state."""
        e = debug_embed("Cache")

        e.description = f"```prolog\n{get_cache_state(self.bot)}\n```"
        await ctx.reply(embeds=[e])

    @debug.subcommand()
    async def shutdown(self, ctx: dis_snek.MessageContext) -> None:
        """Shuts down the bot."""
        await ctx.reply("Shutting down 😴")
        await self.bot.stop()

    @debug.subcommand(aliases=["reload"])
    async def regrow(self, ctx: dis_snek.MessageContext, *, module: str):
        """Regrows a scale."""
        try:
            await self.shed_scale.callback(ctx, module=module)
        except (
            dis_snek.errors.ExtensionLoadException,
            dis_snek.errors.ScaleLoadException,
        ):
            pass
        await self.grow_scale.callback(ctx, module=module)

    @debug.subcommand(aliases=["load"])
    async def grow_scale(self, ctx: dis_snek.MessageContext, *, module: str):
        """Grows a scale."""
        self.bot.grow_scale(module)
        await ctx.message.add_reaction("🪴")

    @debug.subcommand(aliases=["unload"])
    async def shed_scale(self, ctx: dis_snek.MessageContext, *, module: str) -> None:
        """Sheds a scale."""
        self.bot.shed_scale(module)
        await ctx.message.add_reaction("💥")

    @regrow.error
    @grow_scale.error
    @shed_scale.error
    async def regrow_error(self, error: Exception, ctx: dis_snek.MessageContext, *args):
        if isinstance(error, dis_snek.errors.CommandCheckFailure):
            return await ctx.reply("You do not have permission to execute this command")
        elif isinstance(error, dis_snek.errors.ExtensionLoadException):
            return await ctx.reply(str(error))
        raise

    @debug.subcommand(aliases=["python", "exc"])
    async def exec(self, ctx: dis_snek.MessageContext, *, body: str):
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

        if body.startswith("```") and body.endswith("```"):
            body = "\n".join(body.split("\n")[1:-1])
        else:
            body = body.strip("` \n")

        stdout = io.StringIO()

        to_compile = "async def func():\n%s" % textwrap.indent(body, "  ")
        try:
            exec(to_compile, env)  # noqa: S102
        except SyntaxError:
            return await ctx.reply(f"```py\n{traceback.format_exc()}\n```")

        func = env["func"]
        try:
            with contextlib.redirect_stdout(stdout):
                ret = await func()  # noqa
        except Exception:
            await ctx.message.add_reaction("❌")
            return await ctx.message.reply(
                f"```py\n{stdout.getvalue()}{traceback.format_exc()}\n```"
            )
        else:
            return await self.handle_exec_result(ctx, ret, stdout.getvalue())

    async def handle_exec_result(
        self, ctx: dis_snek.MessageContext, result: typing.Any, value: typing.Any
    ):
        if not result:
            result = value or "No Output!"

        await ctx.message.add_reaction("✅")

        if isinstance(result, dis_snek.Message):
            try:
                e = debug_embed(
                    "Exec", timestamp=result.created_at, url=result.jump_url
                )
                e.description = result.content
                e.set_author(
                    result.author.tag,
                    icon_url=(result.author.guild_avatar or result.author.avatar).url,
                )
                e.add_field(
                    "\u200b", f"[Jump To]({result.jump_url})\n{result.channel.mention}"
                )

                return await ctx.message.reply(embeds=e)
            except Exception:
                return await ctx.message.reply(result.jump_url)

        if isinstance(result, dis_snek.Embed):
            return await ctx.message.reply(embeds=result)

        if isinstance(result, dis_snek.File):
            return await ctx.message.reply(file=result)

        if isinstance(result, paginators.Paginator):
            return await result.send(ctx)

        if hasattr(result, "__iter__"):
            l_result = list(result)
            if all(isinstance(r, dis_snek.Embed) for r in result):
                paginator = paginators.Paginator.create_from_embeds(self.bot, *l_result)
                return await paginator.send(ctx)

        if not isinstance(result, str):
            result = repr(result)

        # prevent token leak
        result = result.replace(self.bot.http.token, "[REDACTED TOKEN]")

        if len(result) <= 2000:
            return await ctx.message.reply(f"```py\n{result}```")

        paginator = paginators.Paginator.create_from_string(
            self.bot, result, prefix="```py", suffix="```", page_size=4000
        )
        return await paginator.send(ctx)

    @debug.subcommand()
    async def shell(self, ctx: dis_snek.MessageContext, *, cmd: str):
        """Executes statements in the system shell."""
        await ctx.channel.trigger_typing()

        process = await asyncio.create_subprocess_shell(
            cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
        )

        output, _ = await process.communicate()
        output_str = output.decode("utf-8")
        output_str += f"\nReturn code {process.returncode}"

        if len(output_str) <= 2000:
            return await ctx.message.reply(f"```sh\n{output_str}```")

        paginator = paginators.Paginator.create_from_string(
            self.bot, output_str, prefix="```sh", suffix="```", page_size=4000
        )
        return await paginator.send(ctx)

    @debug.subcommand()
    async def git(self, ctx: dis_snek.MessageContext, *, cmd: str):
        """Shortcut for 'debug shell git'. Invokes the system shell."""
        await self.shell.callback(ctx, cmd=f"git {cmd}")

    @debug.subcommand()
    async def pip(self, ctx: dis_snek.MessageContext, *, cmd: str):
        """Shortcut for 'debug shell pip'. Invokes the system shell."""
        await self.shell.callback(ctx, cmd=f"pip {cmd}")


def setup(bot) -> None:
    DebugScale(bot)
