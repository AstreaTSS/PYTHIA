"""
Copyright 2021-2026 AstreaTSS.
This file is part of PYTHIA.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

import asyncio
import importlib
from collections import defaultdict

import d20
import discord
import ragwort
import typing_extensions as typing
from discord.ext import commands

import common.classes as classes
import common.exports as exports
import common.fuzzy as fuzzy
import common.models as models
import common.utils as utils

from . import dice_common


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
            result = dice_common.d20_roll(dice)
        except d20.errors.RollSyntaxError as e:
            raise utils.BadArgument(f"Invalid dice roll syntax.\n{e!s}") from None
        except d20.errors.TooManyRolls:
            raise utils.BadArgument("Too many dice rolls in the expression.") from None
        except d20.errors.RollValueError:
            raise utils.BadArgument("Invalid dice roll value.") from None

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
            raise utils.BadArgument("No registered dice found with that name.")

        try:
            result = dice_common.d20_roll(entry.value)
        except d20.errors.RollSyntaxError as e:
            raise utils.BadArgument(f"Invalid dice roll syntax.\n{e!s}") from None
        except d20.errors.TooManyRolls:
            raise utils.BadArgument("Too many dice rolls in the expression.") from None
        except d20.errors.RollValueError:
            raise utils.BadArgument("Invalid dice roll value.") from None

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
                raise utils.BadArgument("A dice with that name already exists.")

            await models.GuildConfig.fetch_create(int(guild_id), {"dice": True})

            try:
                dice_common.d20_roll(dice)
            except d20.errors.RollSyntaxError as e:
                raise utils.BadArgument(f"Invalid dice roll syntax.\n{e!s}") from None
            except d20.errors.TooManyRolls:
                raise utils.BadArgument(
                    "Too many dice rolls in the expression."
                ) from None
            except d20.errors.RollValueError:
                raise utils.BadArgument("Invalid dice roll value.") from None

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
            raise utils.BadArgument(f"No registered dice{extra} found.")

        str_builder = [f"- **{e.name}**: {e.value}" for e in entries]
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
            raise utils.BadArgument("No registered dice found with that name.")
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
            raise utils.BadArgument(
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
            raise utils.BadArgument("You have no registered dice to clear.")
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
        await dice_common.dice_export_actual(ctx)

    @dice.command(name="import", description="Imports dice from a JSON file.")
    @commands.cooldown(1, 60, commands.BucketType.user)
    async def dice_import_items(
        self,
        ctx: utils.THIASlashContext,
        json_file: discord.Attachment = ragwort.Option("The JSON file to import."),
        _override: str = ragwort.Option(
            "Should pre-existing registered dice with the same name be overridden?",
            name="override",
            choices=[
                discord.OptionChoice("yes", "yes"),
                discord.OptionChoice("no", "no"),
            ],
            default="no",
        ),
    ) -> None:
        override = _override == "yes"

        await dice_common.dice_import_actual(ctx, json_file, override=override)

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
    importlib.reload(dice_common)
    bot.add_cog(DiceCMDs(bot))
