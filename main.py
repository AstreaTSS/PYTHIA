import asyncio
import datetime
import os

import discord
import discord_slash
from discord.ext import commands
from tortoise import Tortoise
from websockets import ConnectionClosedOK

import common.utils as utils
from common.help_cmd import PaginatedHelpCommand
from keep_alive import keep_alive


def investigator_prefixes(bot: commands.Bot, msg: discord.Message):
    mention_prefixes = [f"{bot.user.mention} ", f"<@!{bot.user.id}> "]
    custom_prefixes = ["u!"]

    return mention_prefixes + custom_prefixes


def global_checks(ctx: commands.Context):
    if not ctx.bot.is_ready():
        return False

    return bool(ctx.guild)


async def on_init_load():
    await bot.wait_until_ready()

    # you'll have to generate this yourself if you want to
    # run your own instance, but it's super easy to do so
    # just run gen_dbs.py
    await Tortoise.init(
        db_url="sqlite://db.sqlite3", modules={"models": ["common.models"]}
    )

    application = await bot.application_info()
    bot.owner = application.owner

    bot.load_extension("jishaku")

    cogs_list = utils.get_all_extensions(os.environ.get("DIRECTORY_OF_FILE"))

    for cog in cogs_list:
        try:
            bot.load_extension(cog)
        except commands.NoEntryPointError:
            pass

    await bot.slash.sync_all_commands()  # need to do this as otherwise slash cmds wont work


class UltimateInvestigator(commands.Bot):
    def __init__(
        self,
        command_prefix,
        help_command=PaginatedHelpCommand(),
        description=None,
        **options,
    ):
        super().__init__(
            command_prefix,
            help_command=help_command,
            description=description,
            **options,
        )
        self._checks.append(global_checks)

    async def on_ready(self):
        utcnow = datetime.datetime.utcnow()
        time_format = utcnow.strftime("%x %X UTC")

        connect_msg = (
            f"Logged in at `{time_format}`!"
            if self.init_load == True
            else f"Reconnected at `{time_format}`!"
        )

        while not hasattr(self, "owner"):
            await asyncio.sleep(0.1)

        await self.owner.send(connect_msg)

        self.init_load = False

        activity = discord.Activity(
            name="for Truth Bullets", type=discord.ActivityType.watching
        )

        try:
            await self.change_presence(activity=activity)
        except ConnectionClosedOK:
            await utils.msg_to_owner(self, "Reconnecting...")

    async def on_resumed(self):
        activity = discord.Activity(
            name="for Truth Bullets", type=discord.ActivityType.watching
        )
        await self.change_presence(activity=activity)

    async def on_error(self, event, *args, **kwargs):
        try:
            raise
        except BaseException as e:
            await utils.error_handle(self, e)

    async def get_context(self, message, *, cls=commands.Context):
        """A simple extension of get_content. If it doesn't manage to get a command, it changes the string used
        to get the command from - to _ and retries. Convenient for the end user."""

        ctx = await super().get_context(message, cls=cls)
        if ctx.command is None and ctx.invoked_with:
            ctx.command = self.all_commands.get(ctx.invoked_with.replace("-", "_"))

        return ctx

    async def close(self):
        await Tortoise.close_connections()
        return await super().close()  # this will complain a bit, just ignore it


# honestly don't think i need the members stuff
intents = discord.Intents.default()
mentions = discord.AllowedMentions.all()

bot = UltimateInvestigator(
    command_prefix=investigator_prefixes, allowed_mentions=mentions, intents=intents,
)
slash = discord_slash.SlashCommand(bot, override_type=True)

keep_alive()
bot.init_load = True
bot.loop.create_task(on_init_load())
bot.run(os.environ.get("MAIN_TOKEN"))
