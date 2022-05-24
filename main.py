import asyncio
import logging
import os
import typing
from collections import defaultdict

import naff
from dotenv import load_dotenv
from tortoise import Tortoise
from tortoise.exceptions import ConfigurationError
from websockets.exceptions import ConnectionClosedOK

import common.utils as utils

load_dotenv()


logger = logging.getLogger("dis.naff")
logger.setLevel(logging.INFO)
handler = logging.FileHandler(
    filename=os.environ.get("LOG_FILE_PATH"), encoding="utf-8", mode="a"
)
handler.setFormatter(
    logging.Formatter("%(asctime)s:%(levelname)s:%(name)s: %(message)s")
)
logger.addHandler(handler)


async def _get_prefixes(bot: naff.Client, msg: naff.Message):
    if not msg.guild:
        return set()

    if prefixes := bot.cached_prefixes[msg.guild.id]:
        return prefixes

    guild_config = await utils.create_and_or_get(bot, msg.guild.id, msg.id)
    prefixes = bot.cached_prefixes[msg.guild.id] = guild_config.prefixes
    return prefixes


async def investigator_prefixes(bot: naff.Client, msg: naff.Message):
    mention_prefixes = {f"<@{bot.user.id}> ", f"<@!{bot.user.id}> "}

    try:
        custom_prefixes = await _get_prefixes(bot, msg)
    except AttributeError:
        # prefix handling runs before command checks, so there's a chance there's no guild
        custom_prefixes = {"v!"}
    except ConfigurationError:  # prefix handling also runs before on_ready sometimes
        custom_prefixes = set()
    except KeyError:  # rare possibility, but you know
        custom_prefixes = set()

    return mention_prefixes.union(custom_prefixes)


class UltimateInvestigator(naff.Client):
    @naff.listen("startup")
    async def on_startup(self):
        # you'll have to generate this yourself if you want to
        # run your own instance, but it's super easy to do so
        # just run gen_dbs.py
        await Tortoise.init(
            db_url=os.environ.get("DB_URL"), modules={"models": ["common.models"]}
        )

    @naff.listen("ready")
    async def on_ready(self):
        utcnow = naff.Timestamp.utcnow()
        time_format = f"<t:{int(utcnow.timestamp())}:f>"

        connect_msg = (
            f"Logged in at {time_format}!"
            if self.init_load == True
            else f"Reconnected at {time_format}!"
        )

        await self.owner.send(connect_msg)

        self.init_load = False

        activity = naff.Activity.create(
            name="for Truth Bullets", type=naff.ActivityType.WATCHING
        )

        try:
            await self.change_presence(activity=activity)
        except ConnectionClosedOK:
            await utils.msg_to_owner(bot, "Reconnecting...")

    @naff.listen("resume")
    async def on_resume(self):
        activity = naff.Activity.create(
            name="for Truth Bullets", type=naff.ActivityType.WATCHING
        )
        await self.change_presence(activity=activity)

    @naff.listen("message_create")
    async def _dispatch_prefixed_commands(
        self, event: naff.events.MessageCreate
    ) -> None:
        """Determine if a command is being triggered, and dispatch it.
        Annoyingly, unlike d.py, we have to overwrite this whole method
        in order to provide the 'replace _ with -' trick that was in the
        d.py version."""
        message = event.message

        if not message.content:
            return

        if not message.author.bot:
            prefixes: str | typing.Iterable[str] = await self.generate_prefixes(
                self, message
            )  # type: ingore

            if isinstance(prefixes, str) or prefixes == naff.MENTION_PREFIX:
                prefixes = (prefixes,)  # type: ignore

            prefix_used = None

            for prefix in prefixes:
                if prefix == naff.MENTION_PREFIX:
                    if mention := self._mention_reg.search(message.content):  # type: ignore
                        prefix = mention.group()
                    else:
                        continue

                if message.content.startswith(prefix):
                    prefix_used = prefix
                    break

            if prefix_used:
                context = await self.get_context(message)
                context.prefix = prefix_used

                content_parameters = message.content.removeprefix(prefix_used)  # type: ignore
                command = self  # yes, this is a hack

                while True:
                    first_word: str = naff.utils.get_first_word(content_parameters)  # type: ignore
                    command_first_word: str = (
                        first_word.replace("-", "_") if first_word else first_word
                    )
                    if isinstance(command, naff.PrefixedCommand):
                        new_command = command.subcommands.get(command_first_word)
                    else:
                        new_command = command.prefixed_commands.get(command_first_word)
                    if not new_command or not new_command.enabled:
                        break

                    command = new_command
                    content_parameters = content_parameters.removeprefix(
                        first_word
                    ).strip()

                    if command.subcommands and command.hierarchical_checking:
                        try:
                            await new_command._can_run(
                                context
                            )  # will error out if we can't run this command
                        except Exception as e:
                            if new_command.error_callback:
                                await new_command.error_callback(e, context)
                            elif (
                                new_command.extension
                                and new_command.extension.extension_error
                            ):
                                await new_command.extension.extension_error(context)
                            else:
                                await self.on_command_error(context, e)
                            return

                if not isinstance(command, naff.PrefixedCommand):
                    command = None

                if command and command.enabled:
                    # yeah, this looks ugly
                    context.command = command
                    context.invoke_target = (
                        message.content.removeprefix(prefix_used).removesuffix(content_parameters).strip()  # type: ignore
                    )
                    context.args = naff.utils.get_args(context.content_parameters)
                    try:
                        if self.pre_run_callback:
                            await self.pre_run_callback(context)
                        await self._run_prefixed_command(command, context)
                        if self.post_run_callback:
                            await self.post_run_callback(context)
                    except Exception as e:
                        await self.on_command_error(context, e)
                    finally:
                        await self.on_command(context)

    async def on_error(self, source: str, error: Exception, *args, **kwargs) -> None:
        await utils.error_handle(self, error)

    async def stop(self):
        await Tortoise.close_connections()
        await super().stop()


# honestly don't think i need the members stuff
intents = naff.Intents.new(
    guilds=True,
    guild_emojis_and_stickers=True,
    messages=True,
    reactions=True,
    guild_message_content=True,
)
mentions = naff.AllowedMentions.all()

bot = UltimateInvestigator(
    generate_prefixes=investigator_prefixes,
    allowed_mentions=mentions,
    intents=intents,
    delete_unused_application_cmds=True,
    auto_defer=False,  # we already handle deferring
)
bot.init_load = True
bot.cached_prefixes = defaultdict(set)
bot.cached_configs = naff.utils.TTLCache(ttl=30)
bot.color = naff.Color(int(os.environ.get("BOT_COLOR")))

ext_list = utils.get_all_extensions(os.environ.get("DIRECTORY_OF_FILE"))
for ext in ext_list:
    try:
        bot.load_extension(ext)
    except naff.errors.ExtensionLoadException:
        raise

asyncio.run(bot.astart(os.environ.get("MAIN_TOKEN")))
