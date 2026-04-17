"""
Copyright 2021-2026 AstreaTSS.
This file is part of PYTHIA.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

import interactions as ipy
import typing_extensions as typing
from tortoise.connection import get_connection
from tortoise.functions import Lower

import common.models as models
import common.text_utils as text_utils


async def autocomplete_bullets(
    ctx: ipy.AutocompleteContext,
    trigger: str,
    channel: str | None = None,
    only_not_found: bool = False,
    **kwargs: typing.Any,  # noqa: ARG001
) -> None:
    if not channel:
        return await ctx.send([])

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
        return await ctx.send(
            [{"name": entry, "value": entry} for entry in channel_bullets]
        )

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
        values=[int(channel), text_utils.replace_smart_punc(trigger)],
    )
    return await ctx.send(
        [{"name": entry["trigger"], "value": entry["trigger"]} for entry in data]
    )


async def autocomplete_aliases(
    ctx: ipy.AutocompleteContext,
    alias: str,
    channel: str | None = None,
    trigger: str | None = None,
    **kwargs: typing.Any,  # noqa: ARG001,
) -> None:
    if not channel or not trigger:
        return await ctx.send([])

    trigger = text_utils.replace_smart_punc(trigger)

    truth_bullet = await models.TruthBullet.find_via_trigger(channel, trigger)
    if not truth_bullet or not truth_bullet.aliases:
        return await ctx.send([])

    if not alias:
        return await ctx.send(
            [{"name": a, "value": a} for a in sorted(truth_bullet.aliases)]
        )

    # TODO: replace with proper fuzzy search in the future
    alias = text_utils.replace_smart_punc(alias)
    return await ctx.send(
        [
            {"name": entry, "value": entry}
            for entry in truth_bullet.aliases
            if alias.lower() in entry.lower()
        ]
    )


async def autocomplete_gacha_item(
    ctx: ipy.AutocompleteContext,
    name: str,
    **kwargs: typing.Any,  # noqa: ARG001
) -> None:
    if not ctx.guild_id:
        return await ctx.send([])

    if not name:
        gacha_items = (
            await models.GachaItem.annotate(name_lower=Lower("name"))
            .filter(guild_id=ctx.guild_id)
            .order_by("name_lower")
            .limit(25)
            .values_list("name", flat=True)
        )
        return await ctx.send(
            [{"name": entry, "value": entry} for entry in gacha_items]
        )

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
        values=[int(ctx.guild_id), text_utils.replace_smart_punc(name)],
    )
    return await ctx.send(
        [{"name": entry["name"], "value": entry["name"]} for entry in data]
    )


async def autocomplete_gacha_user_item(
    ctx: ipy.AutocompleteContext,
    name: str,
    user: ipy.Snowflake_Type | None = None,
    **kwargs: typing.Any,  # noqa: ARG001
) -> None:
    if not ctx.guild_id:
        return await ctx.send([])

    if not user:
        user = int(ctx.author_id)

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
            values=[int(ctx.guild_id), int(user)],
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
            values=[int(ctx.guild_id), int(user), text_utils.replace_smart_punc(name)],
        )
    return await ctx.send(
        [{"name": entry["name"], "value": entry["name"]} for entry in data]
    )


async def autocomplete_gacha_optional_user_item(
    ctx: ipy.AutocompleteContext,
    name: str,
    user: ipy.Snowflake_Type | None = None,
    **kwargs: typing.Any,
) -> None:
    if not user:
        return await ctx.send([])

    return await autocomplete_gacha_user_item(ctx, name, user, **kwargs)


async def autocomplete_dice_entries_user(
    ctx: ipy.AutocompleteContext,
    name: str,
    user: ipy.Snowflake_Type | None = None,
    **kwargs: typing.Any,  # noqa: ARG001
) -> None:
    guild_id = 0
    if (
        ctx.authorizing_integration_owners.get(
            ipy.IntegrationType.GUILD_INSTALL, ipy.MISSING
        )
        == ctx.guild_id
    ):
        guild_id = ctx.guild_id

    if not user:
        user = int(ctx.author_id)

    if not name:
        dice_entries = (
            await models.DiceEntry.annotate(name_lower=Lower("name"))
            .filter(guild_id=guild_id, user_id=user)
            .order_by("name_lower")
            .limit(25)
            .values_list("name", flat=True)
        )
        return await ctx.send(
            [{"name": entry, "value": entry} for entry in dice_entries]
        )

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
        values=[int(ctx.guild_id), int(user), text_utils.replace_smart_punc(name)],
    )
    return await ctx.send(
        [{"name": entry["name"], "value": entry["name"]} for entry in data]
    )


async def autocomplete_dice_entries_admin(
    ctx: ipy.AutocompleteContext,
    user: ipy.Snowflake_Type | None,
    name: str,
    **kwargs: typing.Any,
) -> None:
    if not user:
        return await ctx.send([])

    return await autocomplete_dice_entries_user(ctx, name, user, **kwargs)


async def autocomplete_item(
    ctx: ipy.AutocompleteContext,
    name: str,
    **_: typing.Any,
) -> None:
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
            values=[int(ctx.guild_id)],
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
            values=[int(ctx.guild_id), text_utils.replace_smart_punc(name)],
        )

    return await ctx.send(
        [{"name": entry["name"], "value": entry["name"]} for entry in data]
    )


async def autocomplete_item_channel(
    ctx: ipy.AutocompleteContext,
    name: str,
    channel: str | None = None,
    investigate_variant: bool = False,
    check_takeable: bool = False,
    **_: typing.Any,
) -> None:
    if not channel:
        return await ctx.send([])

    if investigate_variant:
        config = await models.ItemsConfig.get_or_none(guild_id=ctx.guild_id)
        if not config:
            return await ctx.send([])

        if not config.autosuggest:
            return await ctx.send([])

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
            values=[int(channel), text_utils.replace_smart_punc(name)],
        )

    return await ctx.send(
        [{"name": entry["name"], "value": entry["name"]} for entry in data]
    )


async def autocomplete_item_user(
    ctx: ipy.AutocompleteContext,
    name: str,
    user: ipy.Snowflake_Type | None = None,
    **_: typing.Any,
) -> None:
    if not user or not ctx.guild_id:
        return await ctx.send([])

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
            values=[int(ctx.guild_id), int(user)],
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
            values=[int(ctx.guild_id), int(user), text_utils.replace_smart_punc(name)],
        )
    return await ctx.send(
        [{"name": entry["name"], "value": entry["name"]} for entry in data]
    )
