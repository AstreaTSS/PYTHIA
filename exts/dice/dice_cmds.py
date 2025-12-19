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

d20_roll = d20.Roller(d20.RollContext(100)).roll


class DiceCMDs(ipy.Extension):
    def __init__(self, _: utils.THIABase) -> None:
        self.name = "Dice Commands"

        self.add_ext_auto_defer(ephemeral=True)

    dice = tansy.SlashCommand(
        name="dice",
        description="Hosts public-facing dice commands.",
        integration_types=[
            ipy.IntegrationType.GUILD_INSTALL,
            ipy.IntegrationType.USER_INSTALL,
        ],
        contexts=[
            ipy.ContextType.GUILD,
            ipy.ContextType.BOT_DM,
            ipy.ContextType.PRIVATE_CHANNEL,
        ],
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
        visible = True
        if (
            ctx.authorizing_integration_owners.get(
                ipy.IntegrationType.GUILD_INSTALL, ipy.MISSING
            )
            == ctx.guild_id
        ):
            config = await ctx.fetch_config({"dice": True})
            if typing.TYPE_CHECKING:
                assert config.dice is not None

            visible = config.dice.visible

        await ctx.defer(ephemeral=not visible)

        try:
            result = d20_roll(dice)
        except d20.errors.RollSyntaxError as e:
            raise ipy.errors.BadArgument(f"Invalid dice roll syntax.\n{e!s}") from None
        except d20.errors.TooManyRolls:
            raise ipy.errors.BadArgument(
                "Too many dice rolls in the expression."
            ) from None
        except d20.errors.RollValueError:
            raise ipy.errors.BadArgument("Invalid dice roll value.") from None

        await ctx.send(embed=utils.make_embed(result.result), ephemeral=not visible)

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
        visible = True
        guild_id = 0
        if (
            ctx.authorizing_integration_owners.get(
                ipy.IntegrationType.GUILD_INSTALL, ipy.MISSING
            )
            == ctx.guild_id
        ):
            config = await ctx.fetch_config({"dice": True})
            if typing.TYPE_CHECKING:
                assert config.dice is not None

            visible = config.dice.visible
            guild_id = ctx.guild_id

        await ctx.defer(ephemeral=not visible)

        entry = await models.DiceEntry.get_or_none(
            guild_id=guild_id, user_id=ctx.author.id, name=name
        )
        if not entry:
            raise ipy.errors.BadArgument("No registered dice found with that name.")

        try:
            result = d20_roll(entry.value)
        except d20.errors.RollSyntaxError as e:
            raise ipy.errors.BadArgument(f"Invalid dice roll syntax.\n{e!s}") from None
        except d20.errors.TooManyRolls:
            raise ipy.errors.BadArgument(
                "Too many dice rolls in the expression."
            ) from None
        except d20.errors.RollValueError:
            raise ipy.errors.BadArgument("Invalid dice roll value.") from None

        await ctx.send(embed=utils.make_embed(result.result), ephemeral=not visible)

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
        guild_id = 0
        if (
            ctx.authorizing_integration_owners.get(
                ipy.IntegrationType.GUILD_INSTALL, ipy.MISSING
            )
            == ctx.guild_id
        ):
            guild_id = ctx.guild_id

        if (
            await models.DiceEntry.filter(
                guild_id=guild_id, user_id=ctx.author_id
            ).count()
            >= 25
        ):
            if guild_id != 0:
                raise utils.CustomCheckFailure(
                    "You can only have up to 25 dice entries per server."
                )
            else:
                raise utils.CustomCheckFailure(
                    "You can only have up to 25 dice entries for yourself."
                )

        if await models.DiceEntry.exists(
            guild_id=guild_id, user_id=ctx.author_id, name=name
        ):
            raise ipy.errors.BadArgument("A dice with that name already exists.")

        await models.GuildConfig.fetch_create(guild_id, {"dice": True})

        try:
            d20_roll(dice)
        except d20.errors.RollSyntaxError as e:
            raise ipy.errors.BadArgument(f"Invalid dice roll syntax.\n{e!s}") from None
        except d20.errors.TooManyRolls:
            raise ipy.errors.BadArgument(
                "Too many dice rolls in the expression."
            ) from None
        except d20.errors.RollValueError:
            raise ipy.errors.BadArgument("Invalid dice roll value.") from None

        await models.DiceEntry.create(
            guild_id=guild_id,
            user_id=ctx.author_id,
            name=name,
            value=dice,
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
        guild_id = 0
        extra = ""
        if (
            ctx.authorizing_integration_owners.get(
                ipy.IntegrationType.GUILD_INSTALL, ipy.MISSING
            )
            == ctx.guild_id
        ):
            guild_id = ctx.guild_id
            extra = " for this server"

        entries = await models.DiceEntry.filter(
            guild_id=guild_id, user_id=ctx.author_id
        )
        if not entries:
            raise ipy.errors.BadArgument(f"No registered dice{extra} found.")

        str_builder = [f"**{e.name}**: {e.value}" for e in entries]

        if len(str_builder) <= 15:
            await ctx.send(
                embed=utils.make_embed(
                    "\n".join(str_builder), title=f"Registered dice{extra}:"
                ),
                ephemeral=True,
            )
            return

        chunks = [str_builder[x : x + 15] for x in range(0, len(str_builder), 15)]
        embeds = [
            utils.make_embed("\n".join(chunk), title=f"Registered dice{extra}:")
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
        guild_id = 0
        if (
            ctx.authorizing_integration_owners.get(
                ipy.IntegrationType.GUILD_INSTALL, ipy.MISSING
            )
            == ctx.guild_id
        ):
            guild_id = ctx.guild_id

        if (
            await models.DiceEntry.filter(
                guild_id=guild_id, user_id=ctx.author_id, name=name
            ).delete()
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

        guild_id = 0
        if (
            ctx.authorizing_integration_owners.get(
                ipy.IntegrationType.GUILD_INSTALL, ipy.MISSING
            )
            == ctx.guild_id
        ):
            guild_id = ctx.guild_id

        if (
            await models.DiceEntry.filter(
                guild_id=guild_id,
                user_id=ctx.author_id,
            ).delete()
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
