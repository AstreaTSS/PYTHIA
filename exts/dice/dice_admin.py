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


class DiceManagement(utils.Extension):
    def __init__(self, _: utils.THIABase) -> None:
        self.name = "Dice Management"

    config = tansy.SlashCommand(
        name="dice-config",
        description="Handles configuration of dice mechanics.",
        default_member_permissions=ipy.Permissions.MANAGE_GUILD,
        dm_permission=False,
    )

    @config.subcommand(
        "info",
        sub_cmd_description="Lists out the dice configuration settings for the server.",
    )
    async def dice_info(self, ctx: utils.THIASlashContext) -> None:
        config = await ctx.fetch_config({"dice": True})
        if typing.TYPE_CHECKING:
            assert config.dice is not None

        visibility = "public" if config.dice.visible else "hidden"

        await ctx.send(
            embed=utils.make_embed(
                f"Dice visibility: {visibility}",
                title=f"Dice config for {ctx.guild.name}",
            )
        )

    @config.subcommand(
        "visibility", sub_cmd_description="Sets the visibility of dice rolls."
    )
    async def dice_visibility(
        self,
        ctx: utils.THIASlashContext,
        visibility: str = tansy.Option(
            "The visibility of dice rolls.",
            choices=[
                ipy.SlashCommandChoice("Public", "public"),
                ipy.SlashCommandChoice("Hidden", "hidden"),
            ],
        ),
    ) -> None:
        visibility = visibility.lower()
        if visibility not in ("public", "hidden"):
            raise utils.CustomCheckFailure(
                "Visibility must be either public or hidden."
            )

        config = await ctx.fetch_config({"dice": True})
        if typing.TYPE_CHECKING:
            assert config.dice is not None

        config.dice.visible = visibility == "public"
        await config.dice.save()

        await ctx.send(
            embed=utils.make_embed(f"Dice visibility has been set to {visibility}.")
        )

    @config.subcommand(
        "help", sub_cmd_description="Tells you how the dice system works."
    )
    async def dice_help(self, ctx: utils.THIASlashContext) -> None:
        embed = utils.make_embed(
            "To see how the dice system works, follow the dice management guide below.",
            title="Setup Bot",
        )
        button = ipy.Button(
            style=ipy.ButtonStyle.LINK,
            label="Dice Management Guide",
            url="https://pythia.astrea.cc/setup/dice_management",
        )
        await ctx.send(embeds=embed, components=button)

    manage = tansy.SlashCommand(
        name="dice-manage",
        description="Handles management of dice mechanics.",
        default_member_permissions=ipy.Permissions.MANAGE_GUILD,
        dm_permission=False,
    )

    @manage.subcommand(
        "roll-registered-for",
        sub_cmd_description="Rolls a user's registered dice.",
    )
    async def dice_roll_registered_for(
        self,
        ctx: utils.THIASlashContext,
        user: ipy.Member = tansy.Option("The user who registered the dice."),
        name: str = tansy.Option(
            "The name of the dice to roll.", max_length=100, autocomplete=True
        ),
        hidden: bool = tansy.Option(
            "Should the result be shown only to you? Defaults to no.",
            choices=[
                ipy.SlashCommandChoice("yes", "yes"),
                ipy.SlashCommandChoice("no", "no"),
            ],
            default="no",
        ),
    ) -> None:
        entry = await models.DiceEntry.get_or_none(
            guild_id=ctx.guild_id, user_id=user.id, name=name
        )
        if not entry:
            raise ipy.errors.BadArgument(
                "No registered dice found with that name for that user."
            )

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

        await ctx.send(embed=utils.make_embed(result.result), ephemeral=hidden == "yes")

    @manage.subcommand(
        "register-for",
        sub_cmd_description="Registers a dice for a user.",
    )
    async def dice_register_for(
        self,
        ctx: utils.THIASlashContext,
        user: ipy.Member = tansy.Option("The user to register a dice for."),
        name: str = tansy.Option(
            "The name of the dice. 100 characters max.", max_length=100
        ),
        dice: str = tansy.Option(
            "The dice roll to register in d20 notation. 100 characters max.",
            max_length=100,
        ),
    ) -> None:
        if (
            await models.DiceEntry.filter(
                guild_id=ctx.guild_id, user_id=user.id
            ).count()
            >= 25
        ):
            raise utils.CustomCheckFailure(
                "A user can only have up to 25 dice entries per server."
            )

        if await models.DiceEntry.exists(
            guild_id=ctx.guild_id, user_id=user.id, name=name
        ):
            raise ipy.errors.BadArgument(
                "A dice with that name already exists for that user."
            )

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

        await models.DiceEntry.create(
            guild_id=ctx.guild_id,
            user_id=user.id,
            name=name,
            value=dice,
        )

        await ctx.send(
            embed=utils.make_embed(f"Registered dice {name} for {user.mention}.")
        )

    @manage.subcommand(
        "list-for",
        sub_cmd_description="Lists dice registered for a user.",
    )
    async def dice_list_for(
        self,
        ctx: utils.THIASlashContext,
        user: ipy.Member = tansy.Option("The user to list dice for."),
    ) -> None:
        entries = await models.DiceEntry.filter(guild_id=ctx.guild_id, user_id=user.id)
        if not entries:
            raise ipy.errors.BadArgument("No registered dice found for that user.")

        str_builder = [f"**{e.name}**: {e.value}" for e in entries]

        if len(str_builder) <= 15:
            await ctx.send(
                embed=utils.make_embed(
                    "\n".join(str_builder),
                    title=f"Registered dice for {user.display_name}",
                )
            )
            return

        chunks = [str_builder[x : x + 15] for x in range(0, len(str_builder), 15)]
        embeds = [
            utils.make_embed(
                "\n".join(chunk), title=f"Registered for {user.display_name}"
            )
            for chunk in chunks
        ]
        pag = help_tools.HelpPaginator.create_from_embeds(
            self.bot, *embeds, timeout=120
        )
        pag.show_callback_button = False
        await pag.send(ctx)

    @manage.subcommand(
        "remove-from",
        sub_cmd_description="Removes a dice registered from a user.",
    )
    async def dice_remove_from(
        self,
        ctx: utils.THIASlashContext,
        user: ipy.Member = tansy.Option("The user to delete a dice from."),
        name: str = tansy.Option(
            "The name of the dice to remove.", max_length=100, autocomplete=True
        ),
    ) -> None:
        if (
            await models.DiceEntry.filter(
                guild_id=ctx.guild_id, user_id=user.id, name=name
            ).delete()
            < 1
        ):
            raise ipy.errors.BadArgument(
                "No registered dice found for that user with that name."
            )
        await ctx.send(
            embed=utils.make_embed(f"Removed dice {name} from {user.mention}.")
        )

    @manage.subcommand(
        "clear-for",
        sub_cmd_description="Clears all dice registered for a user.",
    )
    async def dice_clear_for(
        self,
        ctx: utils.THIASlashContext,
        user: ipy.Member = tansy.Option("The user to clear dice for."),
    ) -> None:
        if (
            await models.DiceEntry.filter(
                guild_id=ctx.guild_id,
                user_id=user.id,
            ).delete()
            < 1
        ):
            raise ipy.errors.BadArgument("No registered dice found for that user.")
        await ctx.send(embed=utils.make_embed(f"Cleared all dice for {user.mention}."))

    @manage.subcommand(
        "clear-everyone",
        sub_cmd_description="Clears all dice registered for everyone.",
    )
    async def dice_clear_everyone(
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
            await models.DiceEntry.filter(
                guild_id=ctx.guild_id,
            ).delete()
            < 1
        ):
            raise ipy.errors.BadArgument("No registered dice found for this server.")

        await ctx.send(embed=utils.make_embed("Cleared all dice for this server."))

    @dice_remove_from.autocomplete("name")
    @dice_roll_registered_for.autocomplete("name")
    async def dice_name_autocomplete(
        self,
        ctx: ipy.AutocompleteContext,
    ) -> None:
        return await fuzzy.autocomplete_dice_entries_admin(ctx, **ctx.kwargs)


def setup(bot: utils.THIABase) -> None:
    importlib.reload(utils)
    importlib.reload(fuzzy)
    importlib.reload(help_tools)
    DiceManagement(bot)
