"""
Copyright 2021-2026 AstreaTSS.
This file is part of PYTHIA.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

import discord
import typing_extensions as typing
from tortoise.connection import get_connection
from tortoise.functions import Lower

import common.models as models
import common.utils as utils


async def autocomplete_bullets(
    trigger: str,
    channel: str | None = None,
    only_not_found: bool = False,
    **_: typing.Any,
) -> list[discord.OptionChoice]:
    if not channel:
        return []

    where: dict[str, typing.Any] = {"channel_id": int(channel)}

    if only_not_found:
        where["found"] = False

    if not trigger:
        channel_bullets = (
            await models.TruthBullet.annotate(trigger_lower=Lower("trigger"))
            .filter(**where)
            .order_by("trigger_lower")
            .limit(25)
            .values_list("trigger", flat=True)
        )
        return [
            discord.OptionChoice(name=entry, value=entry) for entry in channel_bullets
        ]

    conn = get_connection("default")
    data = await conn.execute_query_dict(
        f"""
        SELECT
            trigger, strict_word_similarity($2, trigger) AS sml
        FROM thiatruthbullets
            WHERE channel_id = $1 {"AND found = FALSE" if only_not_found else ""}
            AND $2 <% trigger
        ORDER BY sml DESC LIMIT 25;
        """.strip(),  # noqa: S608
        values=[int(channel), utils.replace_smart_punc(trigger)],
    )
    return [
        discord.OptionChoice(name=entry["trigger"], value=entry["trigger"])
        for entry in data
    ]


async def autocomplete_aliases(
    alias: str,
    channel: str | None = None,
    trigger: str | None = None,
    **_: typing.Any,
) -> list[discord.OptionChoice]:
    if not channel or not trigger:
        return []

    trigger = utils.replace_smart_punc(trigger)

    truth_bullet = await models.TruthBullet.find_via_trigger(
        channel, trigger, prefetch_aliases=True
    )
    if (
        not truth_bullet
        or not truth_bullet.aliases._fetched
        or not truth_bullet.aliases
    ):
        return []

    if not alias:
        return [
            discord.OptionChoice(name=a.alias, value=a.alias)
            for a in sorted(truth_bullet.aliases, key=lambda a: a.alias.lower())
        ]

    # TODO: replace with proper fuzzy search in the future
    alias = utils.replace_smart_punc(alias)
    return [
        discord.OptionChoice(name=entry.alias, value=entry.alias)
        for entry in truth_bullet.aliases
        if alias.lower() in entry.alias.lower()
    ]


async def autocomplete_gacha_item(
    ctx: discord.AutocompleteContext,
    name: str,
    **_: typing.Any,
) -> list[discord.OptionChoice]:
    if not ctx.interaction.guild_id:
        return []

    if not name:
        gacha_items = (
            await models.GachaItem.annotate(name_lower=Lower("name"))
            .filter(guild_id=ctx.interaction.guild_id)
            .order_by("name_lower")
            .limit(25)
            .values_list("name", flat=True)
        )
        return [discord.OptionChoice(name=entry, value=entry) for entry in gacha_items]

    conn = get_connection("default")
    data = await conn.execute_query_dict(
        """
        SELECT
            name, strict_word_similarity($2, name) AS sml
        FROM thiagachaitems
            WHERE guild_id = $1
            AND $2 <% name
        ORDER BY sml DESC LIMIT 25;
        """.strip(),
        values=[int(ctx.interaction.guild_id), utils.replace_smart_punc(name)],
    )
    return [
        discord.OptionChoice(name=entry["name"], value=entry["name"]) for entry in data
    ]


async def autocomplete_gacha_user_item(
    ctx: discord.AutocompleteContext,
    name: str,
    user: "discord.Snowflake | None" = None,
    **_: typing.Any,
) -> list[discord.OptionChoice]:
    if not ctx.interaction.guild_id:
        return []

    if not user:
        user = int(ctx.interaction.user.id)

    conn = get_connection("default")

    if not name:
        data = await conn.execute_query_dict(
            """
            SELECT
                DISTINCT ON (LOWER(name)) name
            FROM thiagachaitems
                JOIN thiagachaitemtoplayer ON thiagachaitemtoplayer.item_id = thiagachaitems.id
                JOIN thiagachaplayers ON thiagachaplayers.id = thiagachaitemtoplayer.player_id
            WHERE
                thiagachaitems.guild_id = $1
                AND thiagachaplayers.guild_id = $1
                AND thiagachaplayers.user_id = $2
            ORDER BY LOWER(name) LIMIT 25;
            """.strip(),
            values=[int(ctx.interaction.guild_id), int(user)],
        )
    else:
        data = await conn.execute_query_dict(
            """
            SELECT
                name,
                sml
            FROM
                (
                    SELECT
                        DISTINCT ON (thiagachaitems.id) thiagachaitems.id,
                        thiagachaitems.name,
                        strict_word_similarity($3, thiagachaitems.name) AS sml
                    FROM thiagachaitems
                        JOIN thiagachaitemtoplayer ON thiagachaitemtoplayer.item_id = thiagachaitems.id
                        JOIN thiagachaplayers ON thiagachaplayers.id = thiagachaitemtoplayer.player_id
                    WHERE
                        thiagachaitems.guild_id = $1
                        AND thiagachaplayers.guild_id = $1
                        AND thiagachaplayers.user_id = $2
                        AND $3 <% thiagachaitems.name
                    ORDER BY thiagachaitems.id LIMIT 25
                )
            ORDER BY sml DESC;
            """.strip(),
            values=[
                int(ctx.interaction.guild_id),
                int(user),
                utils.replace_smart_punc(name),
            ],
        )
    return [
        discord.OptionChoice(name=entry["name"], value=entry["name"]) for entry in data
    ]


async def autocomplete_gacha_optional_user_item(
    ctx: discord.AutocompleteContext,
    name: str,
    user: "discord.Snowflake | None" = None,
    **_: typing.Any,
) -> list[discord.OptionChoice]:
    if not user:
        return []

    return await autocomplete_gacha_user_item(ctx, name, user)


async def autocomplete_dice_entries_user(
    ctx: discord.AutocompleteContext,
    name: str,
    user: "discord.Snowflake | None" = None,
    **_: typing.Any,
) -> list[discord.OptionChoice]:
    guild_id = 0
    if (
        ctx.interaction.authorizing_integration_owners.guild_id
        and ctx.interaction.authorizing_integration_owners.guild_id
        == ctx.interaction.guild_id
    ):
        guild_id = ctx.interaction.guild_id

    if not user:
        user = int(ctx.interaction.user.id)

    if not name:
        dice_entries = (
            await models.DiceEntry.annotate(name_lower=Lower("name"))
            .filter(guild_id=guild_id, user_id=user)
            .order_by("name_lower")
            .limit(25)
            .values_list("name", flat=True)
        )
        return [discord.OptionChoice(name=entry, value=entry) for entry in dice_entries]

    conn = get_connection("default")
    data = await conn.execute_query_dict(
        """
        SELECT
            name, strict_word_similarity($3, name) AS sml
        FROM thiadicenetry
            WHERE guild_id = $1
            AND user_id = $2
            AND $3 <% name
        ORDER BY sml DESC LIMIT 25;
        """.strip(),
        values=[
            int(ctx.interaction.guild_id),
            int(user),
            utils.replace_smart_punc(name),
        ],
    )
    return [
        discord.OptionChoice(name=entry["name"], value=entry["name"]) for entry in data
    ]


async def autocomplete_dice_entries_admin(
    ctx: discord.AutocompleteContext,
    user: "discord.Snowflake | None",
    name: str,
    **_: typing.Any,
) -> list[discord.OptionChoice]:
    if not user:
        return []

    return await autocomplete_dice_entries_user(ctx, name, user)


async def autocomplete_item(
    ctx: discord.AutocompleteContext,
    name: str,
    **_: typing.Any,
) -> list[discord.OptionChoice]:
    conn = get_connection("default")

    if not name:
        data = await conn.execute_query_dict(
            """
            SELECT
                DISTINCT ON (LOWER(name)) name
            FROM thiaitemssystemitems
                WHERE guild_id = $1
            ORDER BY LOWER(name) LIMIT 25;
            """.strip(),
            values=[int(ctx.interaction.guild_id)],
        )
    else:
        data = await conn.execute_query_dict(
            """
            SELECT
                name, strict_word_similarity($2, name) AS sml
            FROM thiaitemssystemitems
                WHERE guild_id = $1
                AND $2 <% name
            ORDER BY sml DESC LIMIT 25;
            """.strip(),
            values=[int(ctx.interaction.guild_id), utils.replace_smart_punc(name)],
        )

    return [
        discord.OptionChoice(name=entry["name"], value=entry["name"]) for entry in data
    ]


async def autocomplete_item_channel(
    ctx: discord.AutocompleteContext,
    name: str,
    channel: "discord.Snowflake | None" = None,
    investigate_variant: bool = False,
    check_takeable: bool = False,
    **_: typing.Any,
) -> list[discord.OptionChoice]:
    if not channel:
        return []

    if investigate_variant:
        config = await models.ItemsConfig.get_or_none(guild_id=ctx.interaction.guild_id)
        if not config:
            return []

        if not config.autosuggest:
            return []

    conn = get_connection("default")

    if not name:
        data = await conn.execute_query_dict(
            f"""
            SELECT
                DISTINCT ON (LOWER(thiaitemssystemitems.name)) thiaitemssystemitems.name
            FROM thiaitemssystemitems
                JOIN thiaitemrelation ON thiaitemrelation.item_id = thiaitemssystemitems.id
            WHERE
                thiaitemrelation.object_id = $1 {"AND thiaitemssystemitems.takeable = TRUE" if check_takeable else ""}
            ORDER BY LOWER(thiaitemssystemitems.name) LIMIT 25;
            """.strip(),  # noqa: S608
            values=[int(channel)],
        )
    else:
        data = await conn.execute_query_dict(
            f"""
            SELECT
                name,
                sml
            FROM
                (
                    SELECT
                        DISTINCT ON (thiaitemssystemitems.id) thiaitemssystemitems.id,
                        thiaitemssystemitems.name,
                        strict_word_similarity($2, thiaitemssystemitems.name) AS sml
                    FROM thiaitemssystemitems
                        JOIN thiaitemrelation ON thiaitemrelation.item_id = thiaitemssystemitems.id
                    WHERE
                        thiaitemrelation.object_id = $1 {"AND thiaitemssystemitems.takeable = TRUE" if check_takeable else ""}
                        AND $2 <% thiaitemssystemitems.name
                    ORDER BY thiaitemssystemitems.id LIMIT 25
                )
            ORDER BY sml DESC;
            """.strip(),  # noqa: S608
            values=[int(channel), utils.replace_smart_punc(name)],
        )

    return [
        discord.OptionChoice(name=entry["name"], value=entry["name"]) for entry in data
    ]


async def autocomplete_item_user(
    ctx: discord.AutocompleteContext,
    name: str,
    user: "discord.Snowflake | None" = None,
    **_: typing.Any,
) -> list[discord.OptionChoice]:
    if not user or not ctx.interaction.guild_id:
        return []

    conn = get_connection("default")

    if not name:
        data = await conn.execute_query_dict(
            """
            SELECT
                DISTINCT ON (LOWER(thiaitemssystemitems.name)) thiaitemssystemitems.name
            FROM thiaitemssystemitems
                JOIN thiaitemrelation ON thiaitemrelation.item_id = thiaitemssystemitems.id
            WHERE
                thiaitemssystemitems.guild_id = $1
                AND thiaitemrelation.object_id = $2
            ORDER BY LOWER(thiaitemssystemitems.name) LIMIT 25;
            """.strip(),
            values=[int(ctx.interaction.guild_id), int(user)],
        )
    else:
        data = await conn.execute_query_dict(
            """
            SELECT
                name,
                sml
            FROM
                (
                    SELECT
                        DISTINCT ON (thiaitemssystemitems.id) thiaitemssystemitems.id,
                        thiaitemssystemitems.name,
                        strict_word_similarity($3, thiaitemssystemitems.name) AS sml
                    FROM thiaitemssystemitems
                        JOIN thiaitemrelation ON thiaitemrelation.item_id = thiaitemssystemitems.id
                    WHERE
                        thiaitemssystemitems.guild_id = $1
                        AND thiaitemrelation.object_id = $2
                        AND $3 <% thiaitemssystemitems.name
                    ORDER BY id LIMIT 25
                )
            ORDER BY sml DESC;
            """.strip(),
            values=[
                int(ctx.interaction.guild_id),
                int(user),
                utils.replace_smart_punc(name),
            ],
        )

    return [
        discord.OptionChoice(name=entry["name"], value=entry["name"]) for entry in data
    ]
