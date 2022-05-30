import typing

import naff
from rapidfuzz import fuzz
from rapidfuzz import process

import common.models as models


def extract_from_list(
    argument,
    list_of_items,
    processors,
    score_cutoff=80,
    scorers=None,
):
    """Uses multiple scorers and processors for a good mix of accuracy and fuzzy-ness"""
    if scorers is None:
        scorers = [fuzz.WRatio]
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

                if (
                    processor == fuzz.WRatio
                ):  # WRatio isn't the best, so we add in extra filters to make sure everythings turns out ok
                    new_members = [
                        e
                        for e in fuzzy_list
                        if e[0] not in combined_entries
                        and (len(processor(e[0])) >= 2 or len(argument) <= 2)
                    ]

                else:
                    new_members = [
                        e for e in fuzzy_list if e[0] not in combined_entries
                    ]

                combined_list.extend(new_members)

    return combined_list


def get_bullet_name(bullet: models.TruthBullet):
    return bullet.name.lower() if isinstance(bullet, models.TruthBullet) else bullet


async def autocomplete_bullets(
    ctx: naff.AutocompleteContext,
    name: str,
    channel: typing.Optional[naff.GuildText] = None,
    **kwargs,
):
    if not channel:
        return await ctx.send([])

    channel_bullets = await models.TruthBullet.filter(channel_id=channel.id)

    if not name:
        return await ctx.send([{"name": b.name, "value": b.name} for b in channel_bullets][:25])  # type: ignore

    query: list[list[models.TruthBullet]] = extract_from_list(
        argument=name.lower(),
        list_of_items=channel_bullets,
        processors=[get_bullet_name],
        score_cutoff=60,
    )
    return await ctx.send([{"name": b[0].name, "value": b[0].name} for b in query][:25])  # type: ignore


def get_alias_name(alias: str):
    return alias.lower()


async def autocomplete_aliases(
    ctx: naff.AutocompleteContext,
    alias: str,
    channel: typing.Optional[naff.GuildText] = None,
    name: typing.Optional[str] = None,
    **kwargs,
):
    if not channel or not name:
        return await ctx.send([])

    truth_bullet = await models.TruthBullet.get_or_none(
        channel_id=channel.id, name=name
    )
    if not truth_bullet:
        return await ctx.send([])

    if not alias:
        return await ctx.send([{"name": a, "value": a} for a in truth_bullet.aliases][:25])  # type: ignore

    query: list[list[str]] = extract_from_list(
        argument=name.lower(),
        list_of_items=truth_bullet.aliases,
        processors=[get_alias_name],
        score_cutoff=60,
    )
    return await ctx.send([{"name": a[0], "value": a[0]} for a in query][:25])  # type: ignore
