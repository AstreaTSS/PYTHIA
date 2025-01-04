"""
Copyright 2021-2025 AstreaTSS.
This file is part of PYTHIA.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

import importlib

import d20
import interactions as ipy
import tansy
import typing_extensions as typing

import common.fuzzy as fuzzy
import common.help_tools as help_tools
import common.models as models
import common.utils as utils


class DiceCMDs(utils.Extension):
    def __init__(self, bot: utils.THIABase) -> None:
        self.name = "Dice Commands"
        self.bot: utils.THIABase = bot

        self.add_ext_auto_defer(ephemeral=True)

    dice = tansy.SlashCommand(
        name="dice",
        description="Hosts public-facing dice commands.",
        dm_permission=False,
    )

    @dice.subcommand(
        "roll",
        sub_cmd_description="Rolls a dice in d20 notation.",
    )
    @ipy.auto_defer(enabled=False)
    async def dice_roll(
        self,
        ctx: utils.THIASlashContext,
        dice: str = tansy.Option(
            "The dice roll to perform in d20 notation. 100 characters max.",
            max_length=100,
        ),
    ) -> None:
        config = await ctx.fetch_config({"dice": True})
        if typing.TYPE_CHECKING:
            assert config.dice is not None

        await ctx.defer(ephemeral=not config.dice.visible)

        try:
            result = d20.roll(dice)
        except d20.errors.RollSyntaxError as e:
            raise ipy.errors.BadArgument(f"Invalid dice roll syntax.\n{e!s}") from None
        except d20.errors.TooManyRolls:
            raise ipy.errors.BadArgument(
                "Too many dice rolls in the expression."
            ) from None
        except d20.errors.RollValueError:
            raise ipy.errors.BadArgument("Invalid dice roll value.") from None

        await ctx.send(
            embed=utils.make_embed(result.result), ephemeral=not config.dice.visible
        )

    @dice.subcommand(
        "roll-registered",
        sub_cmd_description="Rolls a previously registered dice.",
    )
    @ipy.auto_defer(enabled=False)
    async def dice_roll_registered(
        self,
        ctx: utils.THIASlashContext,
        name: str = tansy.Option(
            "The name of the dice to roll.", max_length=100, autocomplete=True
        ),
    ) -> None:
        config = await ctx.fetch_config({"dice": True})
        if typing.TYPE_CHECKING:
            assert config.dice is not None

        await ctx.defer(ephemeral=not config.dice.visible)

        entry = await models.DiceEntry.prisma().find_first(
            where={"guild_id": ctx.guild_id, "user_id": ctx.author.id, "name": name}
        )
        if not entry:
            raise ipy.errors.BadArgument("No registered dice found with that name.")

        try:
            result = d20.roll(entry.value)
        except d20.errors.RollSyntaxError as e:
            raise ipy.errors.BadArgument(f"Invalid dice roll syntax.\n{e!s}") from None
        except d20.errors.TooManyRolls:
            raise ipy.errors.BadArgument(
                "Too many dice rolls in the expression."
            ) from None
        except d20.errors.RollValueError:
            raise ipy.errors.BadArgument("Invalid dice roll value.") from None

        await ctx.send(
            embed=utils.make_embed(result.result), ephemeral=bool(config.dice.visible)
        )

    @dice.subcommand(
        "register",
        sub_cmd_description="Register a custom dice for you to use.",
    )
    async def dice_register(
        self,
        ctx: utils.THIASlashContext,
        name: str = tansy.Option(
            "The name of the dice. 100 characters max.", max_length=100
        ),
        dice: str = tansy.Option(
            "The dice roll to register in d20 notation. 100 characters max.",
            max_length=100,
        ),
    ) -> None:
        if (
            await models.DiceEntry.prisma().count(
                where={"guild_id": ctx.guild_id, "user_id": ctx.author.id}
            )
            >= 25
        ):
            raise utils.CustomCheckFailure(
                "You can only have up to 25 dice entries per server."
            )

        if await models.DiceEntry.prisma().count(
            where={"guild_id": ctx.guild_id, "user_id": ctx.author.id, "name": name}
        ):
            raise ipy.errors.BadArgument("A dice with that name already exists.")

        await ctx.fetch_config({"dice": True})

        try:
            d20.roll(dice)
        except d20.errors.RollSyntaxError as e:
            raise ipy.errors.BadArgument(f"Invalid dice roll syntax.\n{e!s}") from None
        except d20.errors.TooManyRolls:
            raise ipy.errors.BadArgument(
                "Too many dice rolls in the expression."
            ) from None
        except d20.errors.RollValueError:
            raise ipy.errors.BadArgument("Invalid dice roll value.") from None

        await models.DiceEntry.prisma().create(
            data={
                "guild_id": ctx.guild_id,
                "user_id": ctx.author.id,
                "name": name,
                "value": dice,
            }
        )

        await ctx.send(
            embed=utils.make_embed(f"Registered dice {name}."), ephemeral=True
        )

    @dice.subcommand(
        "list",
        sub_cmd_description="Lists your registered dice.",
    )
    async def dice_list(
        self,
        ctx: utils.THIASlashContext,
    ) -> None:
        entries = await models.DiceEntry.prisma().find_many(
            where={"guild_id": ctx.guild_id, "user_id": ctx.author.id}
        )
        if not entries:
            raise ipy.errors.BadArgument("No registered dice found.")

        str_builder = [f"**{e.name}**: {e.value}" for e in entries]

        if len(str_builder) <= 15:
            await ctx.send(
                embed=utils.make_embed(
                    "\n".join(str_builder), title="Registered dice:"
                ),
                ephemeral=True,
            )
            return

        chunks = [str_builder[x : x + 15] for x in range(0, len(str_builder), 15)]
        embeds = [
            utils.make_embed("\n".join(chunk), title="Registered dice")
            for chunk in chunks
        ]
        pag = help_tools.HelpPaginator.create_from_embeds(
            self.bot, *embeds, timeout=120
        )
        pag.show_callback_button = False
        await pag.send(ctx, ephemeral=True)

    @dice.subcommand(
        "remove",
        sub_cmd_description="Removes a registered dice.",
    )
    async def dice_remove(
        self,
        ctx: utils.THIASlashContext,
        name: str = tansy.Option(
            "The name of the dice to removes.", max_length=100, autocomplete=True
        ),
    ) -> None:
        if (
            await models.DiceEntry.prisma().delete_many(
                where={"guild_id": ctx.guild_id, "user_id": ctx.author.id, "name": name}
            )
            < 1
        ):
            raise ipy.errors.BadArgument("No registered dice found with that name.")
        await ctx.send(embed=utils.make_embed(f"Removed dice {name}."), ephemeral=True)

    @dice.subcommand(
        "clear",
        sub_cmd_description="Clears all of your registered dice.",
    )
    async def dice_clear(
        self,
        ctx: utils.THIASlashContext,
        confirm: bool = tansy.Option(
            "Actually clear? Set this to true if you're sure.", default=False
        ),
    ) -> None:
        if not confirm:
            raise ipy.errors.BadArgument(
                "Confirm option not set to true. Please set the option `confirm` to"
                " true to continue."
            )

        if (
            await models.DiceEntry.prisma().delete_many(
                where={"guild_id": ctx.guild_id, "user_id": ctx.user.id}
            )
            < 1
        ):
            raise ipy.errors.BadArgument("You have no registered dice to clear.")
        await ctx.send(embed=utils.make_embed("Cleared all registered dice."))

    @dice.subcommand(
        "help",
        sub_cmd_description="Shows how to use the dice system.",
    )
    async def dice_help(self, ctx: utils.THIASlashContext) -> None:
        embed = utils.make_embed(
            "To see to use the dice system, follow the dice usage guide below.",
            title="Setup Bot",
        )
        button = ipy.Button(
            style=ipy.ButtonStyle.LINK,
            label="Dice Usage Guide",
            url="https://pythia.astrea.cc/usage/dice",
        )
        await ctx.send(embeds=embed, components=button)

    @dice_remove.autocomplete("name")
    @dice_roll_registered.autocomplete("name")
    async def dice_name_autocomplete(
        self,
        ctx: ipy.AutocompleteContext,
    ) -> None:
        return await fuzzy.autocomplete_dice_entries_user(ctx, **ctx.kwargs)


def setup(bot: utils.THIABase) -> None:
    importlib.reload(utils)
    importlib.reload(fuzzy)
    importlib.reload(help_tools)
    DiceCMDs(bot)
