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

import common.classes as classes
import common.fuzzy as fuzzy
import common.models as models
import common.utils as utils

d20_roll = d20.Roller(d20.RollContext(100)).roll


class DiceManagement(utils.Cog):
    def __init__(self, bot: utils.THIABase) -> None:
        self.bot = bot
        self.__cog_name__ = "Dice Management"

        # i sure do love weird edge cases with race conditions!
        # TODO: locks should be shared with dice_cmds cmds to prevent race conditions
        self.dice_creation_locks: defaultdict[str, asyncio.Lock] = defaultdict(
            asyncio.Lock
        )

    config = ragwort.SlashCommandGroup(
        name="dice-config",
        description="Handles configuration of dice mechanics.",
        default_member_permissions=discord.Permissions(manage_guild=True),
        contexts={
            discord.InteractionContextType.guild,
        },
    )

    @config.command(
        name="info",
        description="Lists out the dice configuration settings for the server.",
    )
    async def dice_info(self, ctx: utils.THIASlashContext) -> None:
        config = await ctx.fetch_config({"dice": True})
        if typing.TYPE_CHECKING:
            assert config.dice and isinstance(config.dice, models.DiceConfig)

        visibility = "public" if config.dice.visible else "hidden"

        await ctx.respond(
            view=utils.make_view(
                f"Dice visibility: {visibility}",
                title="Dice Configuration",
            )
        )

    @config.command(name="visibility", description="Sets the visibility of dice rolls.")
    async def dice_visibility(
        self,
        ctx: utils.THIASlashContext,
        visibility: str = ragwort.Option(
            "The visibility of dice rolls.",
            choices=[
                discord.OptionChoice("Public", "public"),
                discord.OptionChoice("Hidden", "hidden"),
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
            assert config.dice and isinstance(config.dice, models.DiceConfig)

        config.dice.visible = visibility == "public"
        await config.dice.save()

        await ctx.respond(
            view=utils.make_view(f"Dice visibility has been set to {visibility}.")
        )

    @config.command(name="help", description="Tells you how the dice system works.")
    async def dice_help(self, ctx: utils.THIASlashContext) -> None:
        container = utils.make_container(
            "To see how the dice system works, follow the dice management guide below.",
            title="Setup Bot",
        )
        container.add_separator(divider=False)
        container.add_row(
            discord.ui.Button(
                style=discord.ButtonStyle.link,
                label="Dice Management Guide",
                url="https://pythia.astrea.cc/setup/dice_management",
            )
        )
        await ctx.respond(view=utils.quick_view(container))

    manage = ragwort.SlashCommandGroup(
        name="dice-manage",
        description="Handles management of dice mechanics.",
        default_member_permissions=discord.Permissions(manage_guild=True),
        contexts={
            discord.InteractionContextType.guild,
        },
    )

    @manage.command(
        name="roll-registered-for",
        description="Rolls a user's registered dice.",
    )
    async def dice_roll_registered_for(
        self,
        ctx: utils.THIASlashContext,
        user: discord.Member = ragwort.Option("The user who registered the dice."),
        name: str = ragwort.Option(
            "The name of the dice to roll.",
            input_type=utils.ReplaceSmartPuncConverter,
            max_length=100,
        ),
        hidden: str = ragwort.Option(
            "Should the result be shown only to you? Defaults to no.",
            choices=[
                discord.OptionChoice("yes", "yes"),
                discord.OptionChoice("no", "no"),
            ],
            default="no",
        ),
    ) -> None:
        entry = await models.DiceEntry.get_or_none(
            guild_id=ctx.guild_id, user_id=user.id, name=name
        )
        if not entry:
            raise utils.BadArgument(
                "No registered dice found with that name for that user."
            )

        try:
            result = d20_roll(entry.value)
        except d20.errors.RollSyntaxError as e:
            raise utils.BadArgument(f"Invalid dice roll syntax.\n{e!s}") from None
        except d20.errors.TooManyRolls:
            raise utils.BadArgument("Too many dice rolls in the expression.") from None
        except d20.errors.RollValueError:
            raise utils.BadArgument("Invalid dice roll value.") from None

        await ctx.respond(
            view=utils.make_view(result.result), ephemeral=hidden == "yes"
        )

    @manage.command(
        name="register-for",
        description="Registers a dice for a user.",
    )
    async def dice_register_for(
        self,
        ctx: utils.THIASlashContext,
        user: discord.Member = ragwort.Option("The user to register a dice for."),
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
        if (
            await models.DiceEntry.filter(
                guild_id=ctx.guild_id, user_id=user.id
            ).count()
            >= utils.MAX_DICE_ENTRIES
        ):
            raise utils.CustomCheckFailure(
                f"A user can only have up to {utils.MAX_DICE_ENTRIES} dice entries per"
                " server."
            )

        async with self.dice_creation_locks[f"{ctx.guild_id}-{user.id}-{name.lower()}"]:
            if await models.DiceEntry.exists(
                guild_id=ctx.guild_id, user_id=user.id, name__iexact=name
            ):
                raise utils.BadArgument(
                    "A dice with that name already exists for that user."
                )

            await ctx.fetch_config({"dice": True})

            try:
                d20_roll(dice)
            except d20.errors.RollSyntaxError as e:
                raise utils.BadArgument(f"Invalid dice roll syntax.\n{e!s}") from None
            except d20.errors.TooManyRolls:
                raise utils.BadArgument(
                    "Too many dice rolls in the expression."
                ) from None
            except d20.errors.RollValueError:
                raise utils.BadArgument("Invalid dice roll value.") from None

            await models.DiceEntry.create(
                guild_id=ctx.guild_id,
                user_id=user.id,
                name=name,
                value=dice,
            )

        await ctx.respond(
            view=utils.make_view(f"Registered dice {name} for {user.mention}.")
        )

    @manage.command(
        name="list-for",
        description="Lists dice registered for a user.",
    )
    async def dice_list_for(
        self,
        ctx: utils.THIASlashContext,
        user: discord.Member = ragwort.Option("The user to list dice for."),
    ) -> None:
        entries = await models.DiceEntry.filter(guild_id=ctx.guild_id, user_id=user.id)
        if not entries:
            raise utils.BadArgument("No registered dice found for that user.")

        str_builder = [f"- **{e.name}**: {e.value}" for e in entries]
        chunks = [str_builder[x : x + 15] for x in range(0, len(str_builder), 15)]
        pages = [[discord.ui.TextDisplay("\n".join(chunk))] for chunk in chunks]

        pag = classes.ContainerPaginator(
            *pages,
            title=f"Registered dice for {user.display_name}",
            author_id=ctx.author.id,
        )
        await ctx.respond(view=pag)

    @manage.command(
        name="remove-from",
        description="Removes a dice registered from a user.",
    )
    async def dice_remove_from(
        self,
        ctx: utils.THIASlashContext,
        user: discord.Member = ragwort.Option("The user to delete a dice from."),
        name: str = ragwort.Option(
            "The name of the dice to remove.",
            input_type=utils.ReplaceSmartPuncConverter,
            max_length=100,
        ),
    ) -> None:
        if (
            await models.DiceEntry.filter(
                guild_id=ctx.guild_id, user_id=user.id, name=name
            ).delete()
            < 1
        ):
            raise utils.BadArgument(
                "No registered dice found for that user with that name."
            )

        await ctx.respond(
            view=utils.make_view(f"Removed dice {name} from {user.mention}.")
        )

    @manage.command(
        name="clear-for",
        description="Clears all dice registered for a user.",
    )
    async def dice_clear_for(
        self,
        ctx: utils.THIASlashContext,
        user: discord.Member = ragwort.Option("The user to clear dice for."),
    ) -> None:
        if (
            await models.DiceEntry.filter(
                guild_id=ctx.guild_id,
                user_id=user.id,
            ).delete()
            < 1
        ):
            raise utils.BadArgument("No registered dice found for that user.")

        await ctx.respond(view=utils.make_view(f"Cleared all dice for {user.mention}."))

    @manage.command(
        name="clear-everyone",
        description="Clears all dice registered for everyone.",
    )
    async def dice_clear_everyone(
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

        if (
            await models.DiceEntry.filter(
                guild_id=ctx.guild_id,
            ).delete()
            < 1
        ):
            raise utils.BadArgument("No registered dice found for this server.")

        await ctx.respond(view=utils.make_view("Cleared all dice for this server."))

    @dice_remove_from.autocomplete("name")
    @dice_roll_registered_for.autocomplete("name")
    async def dice_name_autocomplete(
        self,
        ctx: discord.AutocompleteContext,
    ) -> list[discord.OptionChoice]:
        return await fuzzy.autocomplete_dice_entries_admin(ctx, **ctx.options)


def setup(bot: utils.THIABase) -> None:
    importlib.reload(utils)
    importlib.reload(fuzzy)
    importlib.reload(classes)
    bot.add_cog(DiceManagement(bot))
