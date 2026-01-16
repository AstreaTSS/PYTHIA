"""
Copyright 2021-2026 AstreaTSS.
This file is part of PYTHIA.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

import interactions as ipy
import rapidfuzz
import typing_extensions as typing
from rapidfuzz import process

import common.models as models
import common.text_utils as text_utils

T = typing.TypeVar("T")


def extract_from_list(
    argument: str,
    list_of_items: typing.Collection[T],
    processors: typing.Iterable[typing.Callable],
    score_cutoff: float = 75,
    scorers: typing.Iterable[typing.Callable] | None = None,
) -> list[list[T]]:
    """Uses multiple scorers and processors for a good mix of accuracy and fuzzy-ness"""
    if scorers is None:
        scorers = [rapidfuzz.fuzz.WRatio]
    combined_list = []

    for scorer in scorers:
        for processor in processors:
            if fuzzy_list := process.extract(
                argument,
                list_of_items,
                scorer=scorer,
                processor=processor,
                score_cutoff=score_cutoff,
            ):
                combined_entries = [e[0] for e in combined_list]
                new_members = [e for e in fuzzy_list if e[0] not in combined_entries]
                combined_list.extend(new_members)

    return combined_list


def get_bullet_name(bullet: models.TruthBullet) -> str:
    return bullet.trigger.lower() if isinstance(bullet, models.TruthBullet) else bullet


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

    channel_bullets = await models.TruthBullet.filter(**where)
    if not channel_bullets:
        return await ctx.send([])

    if not trigger:
        channel_bullets.sort(key=lambda b: b.trigger)
        return await ctx.send(
            [{"name": b.trigger, "value": b.trigger} for b in channel_bullets][:25]
        )

    trigger = text_utils.replace_smart_punc(trigger)

    query: list[list[models.TruthBullet]] = extract_from_list(
        argument=trigger.lower(),
        list_of_items=channel_bullets,
        processors=[get_bullet_name],
    )
    return await ctx.send(
        [{"name": b[0].trigger, "value": b[0].trigger} for b in query][:25]
    )


def get_alias_name(alias: str) -> str:
    return alias.lower()


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
    if not truth_bullet:
        return await ctx.send([])

    if not alias:
        return await ctx.send(
            [{"name": a, "value": a} for a in sorted(truth_bullet.aliases)][:25]
        )

    alias = text_utils.replace_smart_punc(alias)

    query: list[list[str]] = extract_from_list(
        argument=trigger.lower(),
        list_of_items=truth_bullet.aliases or [],
        processors=[get_alias_name],
    )
    return await ctx.send([{"name": a[0], "value": a[0]} for a in query][:25])


def get_gacha_item_name(item: models.GachaItem) -> str:
    return item.name.lower() if isinstance(item, models.GachaItem) else item


async def autocomplete_gacha_item(
    ctx: ipy.AutocompleteContext,
    name: str,
    **kwargs: typing.Any,  # noqa: ARG001
) -> None:
    if not ctx.guild_id:
        return await ctx.send([])

    gacha_items = await models.GachaItem.filter(guild_id=ctx.guild_id)
    if not gacha_items:
        return await ctx.send([])

    if not name:
        gacha_items.sort(key=lambda g: g.name)
        return await ctx.send(
            [{"name": g.name, "value": g.name} for g in gacha_items][:25]
        )

    query: list[list[models.GachaItem]] = extract_from_list(
        argument=name.lower(),
        list_of_items=gacha_items,
        processors=[get_gacha_item_name],
    )
    return await ctx.send([{"name": g[0].name, "value": g[0].name} for g in query][:25])


async def autocomplete_gacha_user_item(
    ctx: ipy.AutocompleteContext,
    name: str,
    **kwargs: typing.Any,  # noqa: ARG001
) -> None:
    if not ctx.guild_id:
        return await ctx.send([])

    unfiltered_items = await models.GachaItem.filter(
        guild_id=ctx.guild_id,
        players__player__guild_id=ctx.guild_id,
        players__player__user_id=ctx.author.id,
    )
    if not unfiltered_items:
        return await ctx.send([])

    filtered_items = list({models.GachaHash(i) for i in unfiltered_items})
    gacha_items = [i.item for i in filtered_items]

    if not name:
        gacha_items.sort(key=lambda g: g.name)
        return await ctx.send(
            [{"name": g.name, "value": g.name} for g in gacha_items][:25]
        )

    query: list[list[models.GachaItem]] = extract_from_list(
        argument=name.lower(),
        list_of_items=gacha_items,
        processors=[get_gacha_item_name],
    )
    return await ctx.send([{"name": g[0].name, "value": g[0].name} for g in query][:25])


async def autocomplete_gacha_optional_user_item(
    ctx: ipy.AutocompleteContext,
    name: str,
    user: ipy.Snowflake_Type | None = None,
    **kwargs: typing.Any,  # noqa: ARG001
) -> None:
    if not ctx.guild_id or not user:
        return await ctx.send([])

    unfiltered_items = await models.GachaItem.filter(
        guild_id=ctx.guild_id,
        players__player__guild_id=ctx.guild_id,
        players__player__user_id=int(user),
    )
    if not unfiltered_items:
        return await ctx.send([])

    filtered_items = list({models.GachaHash(i) for i in unfiltered_items})
    gacha_items = [i.item for i in filtered_items]

    if not name:
        gacha_items.sort(key=lambda g: g.name)
        return await ctx.send(
            [{"name": g.name, "value": g.name} for g in gacha_items][:25]
        )

    query: list[list[models.GachaItem]] = extract_from_list(
        argument=name.lower(),
        list_of_items=gacha_items,
        processors=[get_gacha_item_name],
    )
    return await ctx.send([{"name": g[0].name, "value": g[0].name} for g in query][:25])


def get_dice_name(entry: models.DiceEntry) -> str:
    return entry.name.lower() if isinstance(entry, models.DiceEntry) else entry


async def autocomplete_dice_entries_admin(
    ctx: ipy.AutocompleteContext,
    user: ipy.Snowflake_Type | None,
    name: str,
    **kwargs: typing.Any,  # noqa: ARG001
) -> None:
    if not ctx.guild_id or not user:
        return await ctx.send([])

    dice_entries = await models.DiceEntry.filter(
        guild_id=ctx.guild_id, user_id=int(user)
    )
    if not dice_entries:
        return await ctx.send([])

    if not name:
        dice_entries.sort(key=lambda d: d.name)
        return await ctx.send(
            [{"name": d.name, "value": d.name} for d in dice_entries][:25]
        )

    query: list[list[models.DiceEntry]] = extract_from_list(
        argument=name.lower(),
        list_of_items=dice_entries,
        processors=[get_dice_name],
    )
    return await ctx.send([{"name": g[0].name, "value": g[0].name} for g in query][:25])


async def autocomplete_dice_entries_user(
    ctx: ipy.AutocompleteContext,
    name: str,
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

    dice_entries = await models.DiceEntry.filter(
        guild_id=guild_id, user_id=ctx.author_id
    )
    if not dice_entries:
        return await ctx.send([])

    if not name:
        dice_entries.sort(key=lambda d: d.name)
        return await ctx.send(
            [{"name": d.name, "value": d.name} for d in dice_entries][:25]
        )

    query: list[list[models.DiceEntry]] = extract_from_list(
        argument=name.lower(),
        list_of_items=dice_entries,
        processors=[get_dice_name],
    )
    return await ctx.send([{"name": g[0].name, "value": g[0].name} for g in query][:25])


def get_vesti_item_name(item: models.ItemsSystemItem) -> str:
    return item.name.lower() if isinstance(item, models.ItemsSystemItem) else item


async def autocomplete_item(
    ctx: ipy.AutocompleteContext,
    name: str,
    **_: typing.Any,
) -> None:
    unfiltered_items = await models.ItemsSystemItem.filter(guild_id=ctx.guild_id)
    if not unfiltered_items:
        return await ctx.send([])

    guild_items = [i.item for i in {models.ItemHash(j) for j in unfiltered_items}]

    if not name:
        guild_items.sort(key=lambda i: i.name)
        return await ctx.send(
            [{"name": i.name, "value": i.name} for i in guild_items][:25]
        )

    name = text_utils.replace_smart_punc(name)

    query: list[list[models.ItemsSystemItem]] = extract_from_list(
        argument=name.lower(),
        list_of_items=guild_items,
        processors=[get_vesti_item_name],
    )
    return await ctx.send([{"name": i[0].name, "value": i[0].name} for i in query][:25])


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

    where: dict[str, typing.Any] = {"relations__object_id": int(channel)}
    if check_takeable:
        where["takeable"] = True

    unfiltered_items = await models.ItemsSystemItem.filter(**where)
    if not unfiltered_items:
        return await ctx.send([])

    channel_items = [i.item for i in {models.ItemHash(j) for j in unfiltered_items}]

    if not name:
        return await ctx.send(
            [
                {"name": i.name, "value": i.name}
                for i in sorted(channel_items, key=lambda i: i.name)
            ][:25]
        )

    name = text_utils.replace_smart_punc(name)

    query: list[list[models.ItemsSystemItem]] = extract_from_list(
        argument=name.lower(),
        list_of_items=channel_items,
        processors=[get_vesti_item_name],
    )

    return await ctx.send([{"name": i[0].name, "value": i[0].name} for i in query][:25])


async def autocomplete_item_user(
    ctx: ipy.AutocompleteContext,
    name: str,
    user: ipy.Snowflake_Type | None = None,
    **_: typing.Any,
) -> None:
    if not user:
        return await ctx.send([])

    unfiltered_items = await models.ItemsSystemItem.filter(
        relations__object_id=int(user),
    )
    if not unfiltered_items:
        return await ctx.send([])

    user_items = [i.item for i in {models.ItemHash(i) for i in unfiltered_items}]

    if not name:
        return await ctx.send(
            [
                {"name": i.name, "value": i.name}
                for i in sorted(user_items, key=lambda i: i.name)
            ][:25]
        )

    name = text_utils.replace_smart_punc(name)

    query: list[list[models.ItemsSystemItem]] = extract_from_list(
        argument=name.lower(),
        list_of_items=user_items,
        processors=[get_vesti_item_name],
    )

    return await ctx.send([{"name": i[0].name, "value": i[0].name} for i in query][:25])
