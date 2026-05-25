"""
Copyright 2021-2026 AstreaTSS.
This file is part of PYTHIA.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

import asyncio
import importlib
import io
from collections import defaultdict

import aiohttp
import d20
import discord
import msgspec
import orjson
import ragwort
import typing_extensions as typing
from discord.ext import commands
from tortoise.transactions import in_transaction

import common.classes as classes
import common.exports as exports
import common.fuzzy as fuzzy
import common.models as models
import common.utils as utils

d20_roll = d20.Roller(d20.RollContext(100)).roll


@ragwort.cog_auto_defer(ephemeral=True)
class DiceCMDs(utils.Cog):
    def __init__(self, bot: utils.THIABase) -> None:
        self.bot = bot
        self.__cog_name__ = "Dice"

        # i sure do love weird edge cases with race conditions!
        # TODO: locks should be shared with dice_admin cmds to prevent race conditions
        self.dice_creation_locks: defaultdict[str, asyncio.Lock] = defaultdict(
            asyncio.Lock
        )

    dice = ragwort.SlashCommandGroup(
        name="dice",
        description="Hosts public-facing dice commands.",
        integration_types={
            discord.IntegrationType.guild_install,
            discord.IntegrationType.user_install,
        },
        contexts={
            discord.InteractionContextType.guild,
            discord.InteractionContextType.bot_dm,
            discord.InteractionContextType.private_channel,
        },
    )

    @dice.command(
        name="roll",
        description="Rolls a dice in d20 notation.",
    )
    @ragwort.auto_defer(enabled=False)
    async def dice_roll(
        self,
        ctx: utils.THIASlashContext,
        dice: str = ragwort.Option(
            "The dice roll to perform in d20 notation. 100 characters max.",
            max_length=100,
        ),
    ) -> None:
        visible = True
        if (
            ctx.interaction.authorizing_integration_owners.guild_id
            and ctx.interaction.authorizing_integration_owners.guild_id == ctx.guild_id
        ):
            config = await ctx.fetch_config({"dice": True})
            if typing.TYPE_CHECKING:
                assert config.dice and isinstance(config.dice, models.DiceConfig)

            visible = config.dice.visible

        await ctx.defer(ephemeral=not visible)

        try:
            result = d20_roll(dice)
        except d20.errors.RollSyntaxError as e:
            raise commands.BadArgument(f"Invalid dice roll syntax.\n{e!s}") from None
        except d20.errors.TooManyRolls:
            raise commands.BadArgument(
                "Too many dice rolls in the expression."
            ) from None
        except d20.errors.RollValueError:
            raise commands.BadArgument("Invalid dice roll value.") from None

        await ctx.respond(view=utils.make_view(result.result), ephemeral=not visible)

    @dice.command(
        name="roll-registered",
        description="Rolls a previously registered dice.",
    )
    @ragwort.auto_defer(enabled=False)
    async def dice_roll_registered(
        self,
        ctx: utils.THIASlashContext,
        name: str = ragwort.Option(
            "The name of the dice to roll.",
            input_type=utils.ReplaceSmartPuncConverter,
            max_length=100,
        ),
    ) -> None:
        visible = True
        guild_id = 0
        if (
            ctx.interaction.authorizing_integration_owners.guild_id
            and ctx.interaction.authorizing_integration_owners.guild_id == ctx.guild_id
        ):
            config = await ctx.fetch_config({"dice": True})
            if typing.TYPE_CHECKING:
                assert config.dice and isinstance(config.dice, models.DiceConfig)

            visible = config.dice.visible
            guild_id = ctx.guild_id

        await ctx.defer(ephemeral=not visible)

        entry = await models.DiceEntry.get_or_none(
            guild_id=guild_id, user_id=ctx.author.id, name=name
        )
        if not entry:
            raise commands.BadArgument("No registered dice found with that name.")

        try:
            result = d20_roll(entry.value)
        except d20.errors.RollSyntaxError as e:
            raise commands.BadArgument(f"Invalid dice roll syntax.\n{e!s}") from None
        except d20.errors.TooManyRolls:
            raise commands.BadArgument(
                "Too many dice rolls in the expression."
            ) from None
        except d20.errors.RollValueError:
            raise commands.BadArgument("Invalid dice roll value.") from None

        await ctx.respond(view=utils.make_view(result.result), ephemeral=not visible)

    @dice.command(
        name="register",
        description="Register a custom dice for you to use.",
    )
    async def dice_register(
        self,
        ctx: utils.THIASlashContext,
        name: str = ragwort.Option(
            "The name of the dice. 100 characters max.",
            input_type=utils.ReplaceSmartPuncConverter,
            max_length=100,
        ),
        dice: str = ragwort.Option(
            "The dice roll to register in d20 notation. 100 characters max.",
            max_length=100,
        ),
    ) -> None:
        guild_id = 0
        if (
            ctx.interaction.authorizing_integration_owners.guild_id
            and ctx.interaction.authorizing_integration_owners.guild_id == ctx.guild_id
        ):
            guild_id = ctx.guild_id

        if (
            await models.DiceEntry.filter(
                guild_id=guild_id, user_id=ctx.author.id
            ).count()
            >= utils.MAX_DICE_ENTRIES
        ):
            if guild_id != 0:
                raise utils.CustomCheckFailure(
                    f"You can only have up to {utils.MAX_DICE_ENTRIES} dice entries per"
                    " server."
                )
            else:
                raise utils.CustomCheckFailure(
                    f"You can only have up to {utils.MAX_DICE_ENTRIES} dice entries for"
                    " yourself."
                )

        async with self.dice_creation_locks[
            f"{guild_id}-{ctx.author.id}-{name.lower()}"
        ]:
            if await models.DiceEntry.exists(
                guild_id=guild_id, user_id=ctx.author.id, name__iexact=name
            ):
                raise commands.BadArgument("A dice with that name already exists.")

            await models.GuildConfig.fetch_create(int(guild_id), {"dice": True})

            try:
                d20_roll(dice)
            except d20.errors.RollSyntaxError as e:
                raise commands.BadArgument(
                    f"Invalid dice roll syntax.\n{e!s}"
                ) from None
            except d20.errors.TooManyRolls:
                raise commands.BadArgument(
                    "Too many dice rolls in the expression."
                ) from None
            except d20.errors.RollValueError:
                raise commands.BadArgument("Invalid dice roll value.") from None

            await models.DiceEntry.create(
                guild_id=guild_id,
                user_id=ctx.author.id,
                name=name,
                value=dice,
            )

        await ctx.respond(
            view=utils.make_view(f"Registered dice {name}."), ephemeral=True
        )

    @dice.command(
        name="list",
        description="Lists your registered dice.",
    )
    async def dice_list(
        self,
        ctx: utils.THIASlashContext,
    ) -> None:
        guild_id = 0
        extra = ""
        if (
            ctx.interaction.authorizing_integration_owners.guild_id
            and ctx.interaction.authorizing_integration_owners.guild_id == ctx.guild_id
        ):
            guild_id = ctx.guild_id
            extra = " for this server"

        entries = await models.DiceEntry.filter(
            guild_id=guild_id, user_id=ctx.author.id
        )
        if not entries:
            raise commands.BadArgument(f"No registered dice{extra} found.")

        str_builder = [f"- **{e.name}**: {e.value}" for e in entries]

        if len(str_builder) <= 15:
            await ctx.respond(
                view=utils.make_view(
                    "\n".join(str_builder), title=f"Registered dice{extra}:"
                ),
                ephemeral=True,
            )
            return

        chunks = [str_builder[x : x + 15] for x in range(0, len(str_builder), 15)]
        pages = [[discord.ui.TextDisplay("\n".join(chunk))] for chunk in chunks]
        pag = classes.ContainerPaginator(
            *pages, title=f"Registered dice{extra}:", author_id=ctx.author.id
        )
        await ctx.respond(view=pag, ephemeral=True)

    @dice.command(
        name="remove",
        description="Removes a registered dice.",
    )
    async def dice_remove(
        self,
        ctx: utils.THIASlashContext,
        name: str = ragwort.Option(
            "The name of the dice to removes.",
            input_type=utils.ReplaceSmartPuncConverter,
            max_length=100,
        ),
    ) -> None:
        guild_id = 0
        if (
            ctx.interaction.authorizing_integration_owners.guild_id
            and ctx.interaction.authorizing_integration_owners.guild_id == ctx.guild_id
        ):
            guild_id = ctx.guild_id

        if (
            await models.DiceEntry.filter(
                guild_id=guild_id, user_id=ctx.author.id, name=name
            ).delete()
            < 1
        ):
            raise commands.BadArgument("No registered dice found with that name.")
        await ctx.respond(view=utils.make_view(f"Removed dice {name}."), ephemeral=True)

    @dice.command(
        name="clear",
        description="Clears all of your registered dice.",
    )
    async def dice_clear(
        self,
        ctx: utils.THIASlashContext,
        confirm: bool = ragwort.Option(
            "Actually clear? Set this to true if you're sure.", default=False
        ),
    ) -> None:
        if not confirm:
            raise commands.BadArgument(
                "Confirm option not set to true. Please set the option `confirm` to"
                " true to continue."
            )

        guild_id = 0
        if (
            ctx.interaction.authorizing_integration_owners.guild_id
            and ctx.interaction.authorizing_integration_owners.guild_id == ctx.guild_id
        ):
            guild_id = ctx.guild_id

        if (
            await models.DiceEntry.filter(
                guild_id=guild_id,
                user_id=ctx.author.id,
            ).delete()
            < 1
        ):
            raise commands.BadArgument("You have no registered dice to clear.")
        await ctx.respond(
            view=utils.make_view("Cleared all registered dice."), ephemeral=True
        )

    @dice.command(
        name="export", description="Exports all registered dice to a JSON file."
    )
    @commands.cooldown(1, 60, commands.BucketType.user)
    async def dice_export(
        self,
        ctx: utils.THIASlashContext,
    ) -> None:
        guild_id = 0
        extra = ""
        if (
            ctx.interaction.authorizing_integration_owners.guild_id
            and ctx.interaction.authorizing_integration_owners.guild_id == ctx.guild_id
        ):
            guild_id = ctx.guild_id
            extra = " for this server"

        entries = await models.DiceEntry.filter(
            guild_id=guild_id, user_id=ctx.author.id
        )
        if not entries:
            raise commands.BadArgument(f"No registered dice{extra} found.")

        entries_dict: list[exports.DiceEntryDict] = [
            {
                "name": entry.name,
                "value": entry.value,
            }
            for entry in entries
        ]
        entries_json = orjson.dumps(
            {"version": 1, "entries": entries_dict}, option=orjson.OPT_INDENT_2
        )

        # how would this happen? no clue
        if len(entries_json) > 10000000:
            raise utils.CustomCheckFailure(
                "The file is too large to send. Please try again with fewer registered"
                " dice."
            )

        entries_io = io.BytesIO(entries_json)
        entries_file = discord.File(
            entries_io,
            filename=(
                f"dice_{ctx.author.id}_{guild_id or 'account'}_{int(ctx.interaction.created_at.timestamp())}.json"
            ),
        )

        try:
            await ctx.respond(
                view=utils.make_view("Exported registered dice to JSON file."),
                file=entries_file,
            )
        finally:
            entries_io.close()

    @dice.command(name="import", description="Imports dice from a JSON file.")
    @commands.cooldown(1, 60, commands.BucketType.user)
    async def dice_import_items(
        self,
        ctx: utils.THIASlashContext,
        json_file: discord.Attachment = ragwort.Option("The JSON file to import."),
        _override: str = ragwort.Option(
            "Should pre-existing registered dice with the same name be overriden?",
            name="override",
            choices=[
                discord.OptionChoice("yes", "yes"),
                discord.OptionChoice("no", "no"),
            ],
            default="no",
        ),
    ) -> None:
        override = _override == "yes"

        if not json_file.content_type or not json_file.content_type.startswith(
            "application/json"
        ):
            raise commands.BadArgument("The file must be a JSON file.")

        async with aiohttp.ClientSession() as session:
            async with session.get(json_file.url) as response:
                if response.status != 200:
                    raise commands.BadArgument("Failed to fetch the file.")

                try:
                    await response.content.readexactly(10485760 + 1)
                    raise utils.CustomCheckFailure(
                        "This file is over 10 MiB, which is not supported by this bot."
                    )
                except asyncio.IncompleteReadError as e:
                    items_json = e.partial

        try:
            entries = exports.handle_dice_entry_data(items_json)

            for entry in entries:
                entry.name = utils.replace_smart_punc(entry.name.strip())
                entry.value = entry.value.strip()

                if not entry.name:
                    raise commands.BadArgument("Dice entry names cannot be empty.")
                if not entry.value:
                    raise commands.BadArgument(
                        f"Dice entry value for `{entry.name}` cannot be empty."
                    )

                if len(entry.name) > 100:
                    raise commands.BadArgument(
                        f"Dice entry name `{entry.name}` is too long. Names must be 100"
                        " characters or fewer."
                    )
                if len(entry.value) > 100:
                    raise commands.BadArgument(
                        f"Dice entry value for `{entry.name}` is too long. Values must"
                        " be 100 characters or fewer."
                    )

        except msgspec.DecodeError:
            raise commands.BadArgument(
                "The file is not in the correct format."
            ) from None

        guild_id = 0
        if (
            ctx.interaction.authorizing_integration_owners.guild_id
            and ctx.interaction.authorizing_integration_owners.guild_id == ctx.guild_id
        ):
            guild_id = ctx.guild_id

        await models.GuildConfig.fetch_create(int(guild_id), {"dice": True})

        if override:
            if len(entries) > utils.MAX_DICE_ENTRIES:
                if guild_id != 0:
                    raise utils.CustomCheckFailure(
                        f"You can only have up to {utils.MAX_DICE_ENTRIES} dice entries"
                        " per server."
                    )
                else:
                    raise utils.CustomCheckFailure(
                        f"You can only have up to {utils.MAX_DICE_ENTRIES} dice entries"
                        " for yourself."
                    )
        else:
            existing_count = await models.DiceEntry.filter(
                guild_id=guild_id, user_id=ctx.author.id
            ).count()
            if existing_count + len(entries) > utils.MAX_DICE_ENTRIES:
                if guild_id != 0:
                    raise utils.CustomCheckFailure(
                        "Importing these dice would exceed the limit of"
                        f" {utils.MAX_DICE_ENTRIES} dice entries per server."
                    )
                else:
                    raise utils.CustomCheckFailure(
                        "Importing these dice would exceed the limit of"
                        f" {utils.MAX_DICE_ENTRIES} dice entries for yourself."
                    )

        async with in_transaction():
            # TODO: this is flawed - how do we do case insensitive unique checks without doing multiple queries?
            if await models.DiceEntry.exists(
                guild_id=guild_id,
                user_id=ctx.author.id,
                name__in=[entry.name for entry in entries],
            ):
                if override:
                    await models.DiceEntry.filter(
                        guild_id=guild_id,
                        name__in=[entry.name for entry in entries],
                    ).delete()
                else:
                    raise commands.BadArgument(
                        "One or more die in the file shares a name with an existing"
                        " registered die."
                    )

            to_create: list[models.DiceEntry] = []

            for entry in entries:
                try:
                    d20_roll(entry.value)
                except d20.errors.RollSyntaxError as e:
                    raise commands.BadArgument(
                        "Invalid dice roll syntax for"
                        f" `{discord.utils.escape_markdown(entry.name)}`.\n{e!s}"
                    ) from None
                except d20.errors.TooManyRolls:
                    raise commands.BadArgument(
                        "Too many dice rolls in the expression for"
                        f" `{discord.utils.escape_markdown(entry.name)}`."
                    ) from None
                except d20.errors.RollValueError:
                    raise commands.BadArgument(
                        "Invalid dice roll value for"
                        f" `{discord.utils.escape_markdown(entry.name)}`."
                    ) from None

                to_create.append(
                    models.DiceEntry(
                        guild_id=guild_id,
                        user_id=ctx.author.id,
                        name=entry.name,
                        value=entry.value,
                    )
                )

            await models.DiceEntry.bulk_create(to_create)

        await ctx.respond(
            view=utils.make_view("Imported dice from JSON file."), ephemeral=True
        )

    @dice.command(
        name="help",
        description="Shows how to use the dice system.",
    )
    async def dice_help(self, ctx: utils.THIASlashContext) -> None:
        container = utils.make_container(
            "To see to use the dice system, follow the dice usage guide below.",
            title="Set Up Dice System",
        )
        container.add_separator(divider=False)
        container.add_row(
            discord.ui.Button(
                style=discord.ButtonStyle.link,
                label="Dice Usage Guide",
                url="https://pythia.astrea.cc/usage/dice",
            )
        )
        await ctx.respond(view=utils.quick_view(container), ephemeral=True)

    @dice_remove.autocomplete("name")
    @dice_roll_registered.autocomplete("name")
    async def dice_name_autocomplete(
        self,
        ctx: discord.AutocompleteContext,
    ) -> list[discord.OptionChoice]:
        return await fuzzy.autocomplete_dice_entries_user(ctx, **ctx.options)


def setup(bot: utils.THIABase) -> None:
    importlib.reload(utils)
    importlib.reload(fuzzy)
    importlib.reload(classes)
    importlib.reload(exports)
    bot.add_cog(DiceCMDs(bot))
