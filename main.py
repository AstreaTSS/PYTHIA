import logging
import os

import dis_snek
import molter
from dotenv import load_dotenv
from tortoise import Tortoise
from tortoise.exceptions import ConfigurationError
from websockets.exceptions import ConnectionClosedOK

import common.utils as utils
import keep_alive
from common.models import Config

load_dotenv()


logger = logging.getLogger("dis.snek")
logger.setLevel(logging.INFO)
handler = logging.FileHandler(
    filename=os.environ.get("LOG_FILE_PATH"), encoding="utf-8", mode="a"
)
handler.setFormatter(
    logging.Formatter("%(asctime)s:%(levelname)s:%(name)s: %(message)s")
)
logger.addHandler(handler)


async def investigator_prefixes(bot: dis_snek.Snake, msg: dis_snek.Message):
    mention_prefixes = {f"<@{bot.user.id}> ", f"<@!{bot.user.id}> "}

    try:
        guild_config = await Config.get(guild_id=msg.guild.id)
        custom_prefixes = guild_config.prefixes
    except AttributeError:
        # prefix handling runs before command checks, so there's a chance there's no guild
        custom_prefixes = {"v!"}
    except ConfigurationError:  # prefix handling also runs before on_ready sometimes
        custom_prefixes = set()
    except KeyError:  # rare possibility, but you know
        custom_prefixes = set()

    return mention_prefixes.union(custom_prefixes)


async def on_init_load():
    await bot.wait_until_ready()

    # you'll have to generate this yourself if you want to
    # run your own instance, but it's super easy to do so
    # just run gen_dbs.py
    await Tortoise.init(
        db_url=os.environ.get("DB_URL"), modules={"models": ["common.models"]}
    )


class UltimateInvestigator(molter.MolterSnake):
    @dis_snek.listen("startup")
    async def on_startup(self):
        # you'll have to generate this yourself if you want to
        # run your own instance, but it's super easy to do so
        # just run gen_dbs.py
        await Tortoise.init(
            db_url=os.environ.get("DB_URL"), modules={"models": ["common.models"]}
        )

    @dis_snek.listen("ready")
    async def on_ready(self):
        utcnow = dis_snek.Timestamp.utcnow()
        time_format = f"<t:{int(utcnow.timestamp())}:f>"

        connect_msg = (
            f"Logged in at {time_format}!"
            if self.init_load == True
            else f"Reconnected at {time_format}!"
        )

        await self.owner.send(connect_msg)

        self.init_load = False

        activity = dis_snek.Activity.create(
            name="for Truth Bullets", type=dis_snek.ActivityType.WATCHING
        )

        try:
            await self.change_presence(activity=activity)
        except ConnectionClosedOK:
            await utils.msg_to_owner(bot, "Reconnecting...")

    @dis_snek.listen("resume")
    async def on_resume(self):
        activity = dis_snek.Activity.create(
            name="for Truth Bullets", type=dis_snek.ActivityType.WATCHING
        )
        await self.change_presence(activity=activity)

    @dis_snek.listen("message_create")
    async def _dispatch_msg_commands(self, event: dis_snek.events.MessageCreate):
        """Determine if a command is being triggered, and dispatch it.

        Annoyingly, unlike d.py, we have to overwrite this whole method
        in order to provide the 'replace _ with -' trick that was in the
        d.py version."""

        message = event.message

        if not message.content:
            return

        if not message.author.bot:
            prefixes = await bot.generate_prefixes(bot, message)

            if isinstance(prefixes, str) or prefixes == dis_snek.const.MENTION_PREFIX:
                # its easier to treat everything as if it may be an iterable
                # rather than building a special case for this
                prefixes = (prefixes,)

            prefix_used = None

            for prefix in prefixes:
                if prefix == dis_snek.const.MENTION_PREFIX:
                    if mention := bot._mention_reg.search(message.content):
                        prefix = mention.group()
                    else:
                        continue

                if message.content.startswith(prefix):
                    prefix_used = prefix
                    break

            if prefix_used:
                context = await bot.get_context(message)
                context.invoked_name = ""
                context.prefix = prefix_used

                content = message.content.removeprefix(prefix_used)
                command = bot

                while True:
                    first_word: str = dis_snek.utils.get_first_word(content)
                    proper_first_word: str = (
                        first_word.replace("-", "_") if first_word else None
                    )
                    if isinstance(command, molter.MolterCommand):
                        new_command = command.command_dict.get(proper_first_word)
                    else:
                        new_command = command.commands.get(proper_first_word)
                    if not new_command or not new_command.enabled:
                        break

                    command = new_command
                    context.invoked_name += f"{first_word} "

                    if not isinstance(command, molter.MolterCommand):
                        # normal message commands can't have subcommands
                        break

                    if command.command_dict and command.hierarchical_checking:
                        await new_command._can_run(context)

                    content = content.removeprefix(first_word).strip()

                if isinstance(command, dis_snek.Snake):
                    command = None

                if command and command.enabled:
                    context.invoked_name = context.invoked_name.strip()
                    context.args = dis_snek.utils.get_args(context.content_parameters)
                    try:
                        if bot.pre_run_callback:
                            await bot.pre_run_callback(context)
                        await command(context)
                        if bot.post_run_callback:
                            await bot.post_run_callback(context)
                    except Exception as e:
                        await bot.on_command_error(context, e)
                    finally:
                        await bot.on_command(context)

    async def on_error(self, source: str, error: Exception, *args, **kwargs) -> None:
        await utils.error_handle(self, error)

    async def stop(self):
        await Tortoise.close_connections()
        await super().stop()


# honestly don't think i need the members stuff
intents = dis_snek.Intents.new(
    guilds=True, guild_emojis_and_stickers=True, messages=True, reactions=True
)
mentions = dis_snek.AllowedMentions.all()

bot = UltimateInvestigator(
    generate_prefixes=investigator_prefixes,
    allowed_mentions=mentions,
    intents=intents,
    auto_defer=dis_snek.AutoDefer(enabled=False),  # we already handle deferring
)
bot.init_load = True
bot.color = dis_snek.Color(int(os.environ.get("BOT_COLOR")))

cogs_list = utils.get_all_extensions(os.environ.get("DIRECTORY_OF_FILE"))
for cog in cogs_list:
    try:
        bot.load_extension(cog)
    except dis_snek.errors.ExtensionLoadException:
        raise

keep_alive.keep_alive()
bot.start(os.environ.get("MAIN_TOKEN"))
