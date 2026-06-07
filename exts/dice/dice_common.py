"""
Copyright 2021-2026 AstreaTSS.
This file is part of PYTHIA.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

import asyncio
import io

import aiohttp
import d20
import discord
import msgspec
import orjson
from tortoise.transactions import in_transaction

import common.exports as exports
import common.models as models
import common.utils as utils

d20_roll = d20.Roller(d20.RollContext(100)).roll


async def dice_export_actual(
    ctx: utils.THIASlashContext,
    *,
    user: discord.User | discord.Member | None = None,
) -> None:
    extra_user = f" for {user.mention}" if user else ""
    if user is None:
        user = ctx.author

    guild_id = 0
    extra = ""
    if (
        ctx.interaction.authorizing_integration_owners.guild_id
        and ctx.interaction.authorizing_integration_owners.guild_id == ctx.guild_id
    ):
        guild_id = ctx.guild_id
        extra = " for this server"

    entries = await models.DiceEntry.filter(guild_id=guild_id, user_id=user.id)
    if not entries:
        raise utils.BadArgument(f"No registered dice{extra} found.")

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
            f"dice_{user.id}_{guild_id or 'account'}_{int(ctx.interaction.created_at.timestamp())}.json"
        ),
    )

    container = utils.make_container(
        f"Exported registered dice{extra_user} to JSON file.", title="Dice Export"
    )
    container.add_separator(divider=False)
    container.add_file(url=f"attachment://{entries_file.filename}")

    try:
        await ctx.respond(
            view=utils.quick_view(container),
            file=entries_file,
            ephemeral=user == ctx.author,
        )
    finally:
        entries_io.close()


async def dice_import_actual(
    ctx: utils.THIASlashContext,
    json_file: discord.Attachment,
    *,
    user: discord.User | discord.Member | None = None,
    override: bool = False,
) -> None:
    extra_user = f" for {user.mention}" if user else ""
    if not user:
        user = ctx.author

    if not json_file.content_type or not json_file.content_type.startswith(
        "application/json"
    ):
        raise utils.BadArgument("The file must be a JSON file.")

    async with aiohttp.ClientSession() as session:
        async with session.get(json_file.url) as response:
            if response.status != 200:
                raise utils.BadArgument("Failed to fetch the file.")

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
                raise utils.BadArgument("Dice entry names cannot be empty.")
            if not entry.value:
                raise utils.BadArgument(
                    f"Dice entry value for `{entry.name}` cannot be empty."
                )

            if len(entry.name) > 100:
                raise utils.BadArgument(
                    f"Dice entry name `{entry.name}` is too long. Names must be 100"
                    " characters or fewer."
                )
            if len(entry.value) > 100:
                raise utils.BadArgument(
                    f"Dice entry value for `{entry.name}` is too long. Values must"
                    " be 100 characters or fewer."
                )

    except msgspec.DecodeError:
        raise utils.BadArgument("The file is not in the correct format.") from None

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
            guild_id=guild_id, user_id=user.id
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
            user_id=user.id,
            name__in=[entry.name for entry in entries],
        ):
            if override:
                await models.DiceEntry.filter(
                    guild_id=guild_id,
                    user_id=user.id,
                    name__in=[entry.name for entry in entries],
                ).delete()
            else:
                raise utils.BadArgument(
                    "One or more die in the file shares a name with an existing"
                    " registered die."
                )

        to_create: list[models.DiceEntry] = []

        for entry in entries:
            try:
                d20_roll(entry.value)
            except d20.errors.RollSyntaxError as e:
                raise utils.BadArgument(
                    "Invalid dice roll syntax for"
                    f" `{discord.utils.escape_markdown(entry.name)}`.\n{e!s}"
                ) from None
            except d20.errors.TooManyRolls:
                raise utils.BadArgument(
                    "Too many dice rolls in the expression for"
                    f" `{discord.utils.escape_markdown(entry.name)}`."
                ) from None
            except d20.errors.RollValueError:
                raise utils.BadArgument(
                    "Invalid dice roll value for"
                    f" `{discord.utils.escape_markdown(entry.name)}`."
                ) from None

            to_create.append(
                models.DiceEntry(
                    guild_id=guild_id,
                    user_id=user.id,
                    name=entry.name,
                    value=entry.value,
                )
            )

        await models.DiceEntry.bulk_create(to_create)

    await ctx.respond(
        view=utils.make_view(
            f"Imported dice from JSON file{extra_user}.", title="Dice Import"
        ),
        ephemeral=user == ctx.author,
    )
