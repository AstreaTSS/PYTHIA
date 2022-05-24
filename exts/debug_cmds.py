import asyncio
import contextlib
import importlib
import io
import logging
import platform
import textwrap
import traceback
import typing

import naff
from naff.ext import paginators
from naff.ext.debug_extension.utils import debug_embed
from naff.ext.debug_extension.utils import get_cache_state

log = logging.getLogger(naff.const.logger_name)


class DebugExtension(naff.Extension):
    """A reimplementation of naff's native debug commands."""

    def __init__(self, bot):
        self.name = "Debug"
        self.add_ext_check(naff.checks.is_owner())

    @naff.prefixed_command(aliases=["jsk"])
    async def debug(self, ctx: naff.PrefixedContext):
        """Get basic information about the bot."""
        uptime = naff.Timestamp.fromdatetime(self.bot.start_time)
        e = debug_embed("General")
        e.set_thumbnail(self.bot.user.avatar.url)
        e.add_field("Operating System", platform.platform())

        e.add_field(
            "Version Info",
            f"NAFF@{naff.__version__} | Py@{naff.__py_version__}",
        )

        e.add_field("Start Time", f"{uptime.format(naff.TimestampStyles.RelativeTime)}")

        if privileged_intents := [
            i.name for i in self.bot.intents if i in naff.Intents.PRIVILEGED
        ]:
            e.add_field("Privileged Intents", " | ".join(privileged_intents))

        e.add_field("Loaded Extensions", ", ".join(self.bot.ext))

        e.add_field("Guilds", str(len(self.bot.guilds)))

        await ctx.reply(embeds=[e])

    @debug.subcommand(aliases=["cache"])
    async def cache_info(self, ctx: naff.PrefixedContext):
        """Get information about the current cache state."""
        e = debug_embed("Cache")

        e.description = f"```prolog\n{get_cache_state(self.bot)}\n```"
        await ctx.reply(embeds=[e])

    @debug.subcommand()
    async def shutdown(self, ctx: naff.PrefixedContext) -> None:
        """Shuts down the bot."""
        await ctx.reply("Shutting down 😴")
        await self.bot.stop()

    @debug.subcommand()
    async def reload(self, ctx: naff.PrefixedContext, *, module: str):
        """Regrows an extension."""
        self.bot.reload_extension(module)
        await ctx.reply(f"Reloaded `{module}`.")

    @debug.subcommand()
    async def load(self, ctx: naff.PrefixedContext, *, module: str):
        """Grows a scale."""
        self.bot.load_extension(module)
        await ctx.reply(f"Loaded `{module}`.")

    @debug.subcommand(aliases=["unload"])
    async def unload(self, ctx: naff.PrefixedContext, *, module: str) -> None:
        """Sheds a scale."""
        self.bot.unload_extension(module)
        await ctx.reply(f"Unloaded `{module}`.")

    @naff.prefixed_command(aliases=["reloadallextensions"])
    async def reload_all_extensions(self, ctx: naff.PrefixedContext):
        for ext in self.bot.ext:
            self.bot.reload_extension(ext)
        await ctx.reply("All extensions reloaded!")

    @reload.error
    @load.error
    @unload.error
    async def extension_error(self, error: Exception, ctx: naff.PrefixedContext, *args):
        if isinstance(error, naff.errors.CommandCheckFailure):
            return await ctx.reply(
                "You do not have permission to execute this command."
            )
        elif isinstance(
            error, (naff.errors.ExtensionLoadException, naff.errors.ExtensionNotFound)
        ):
            return await ctx.reply(str(error))
        raise

    @debug.subcommand(aliases=["python", "exc"])
    async def exec(self, ctx: naff.PrefixedContext, *, body: str):
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
        self, ctx: naff.PrefixedContext, result: typing.Any, value: typing.Any
    ):
        if not result:
            result = value or "No Output!"

        await ctx.message.add_reaction("✅")

        if isinstance(result, naff.Message):
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

        if isinstance(result, naff.Embed):
            return await ctx.message.reply(embeds=result)

        if isinstance(result, naff.File):
            return await ctx.message.reply(file=result)

        if isinstance(result, paginators.Paginator):
            return await result.send(ctx)

        if hasattr(result, "__iter__"):
            l_result = list(result)
            if all(isinstance(r, naff.Embed) for r in result):
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
    async def shell(self, ctx: naff.PrefixedContext, *, cmd: str):
        """Executes statements in the system shell."""
        async with ctx.channel.typing:
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
    async def git(self, ctx: naff.PrefixedContext, *, cmd: str):
        """Shortcut for 'debug shell git'. Invokes the system shell."""
        await self.shell.callback(ctx, cmd=f"git {cmd}")

    @debug.subcommand()
    async def pip(self, ctx: naff.PrefixedContext, *, cmd: str):
        """Shortcut for 'debug shell pip'. Invokes the system shell."""
        await self.shell.callback(ctx, cmd=f"pip {cmd}")


def setup(bot) -> None:
    DebugExtension(bot)
