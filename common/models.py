"""
Copyright 2021-2025 AstreaTSS.
This file is part of PYTHIA.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

import collections
import contextlib
import datetime
import os
import re
import textwrap
from collections import Counter
from enum import IntEnum

import interactions as ipy
import typing_extensions as typing
from httpcore._backends import anyio
from httpcore._backends.asyncio import AsyncioBackend
from prisma import Base64, Json, _builder
from prisma._async_http import Response
from prisma.enums import ItemsRelationType, Rarity
from prisma.models import (
    PrimsaDiceConfig,
    PrismaBulletConfig,
    PrismaDiceEntry,
    PrismaGachaConfig,
    PrismaGachaItem,
    PrismaGachaPlayer,
    PrismaGuildConfig,
    PrismaItemRelation,
    PrismaItemsConfig,
    PrismaItemsSystemItem,
    PrismaItemToPlayer,
    PrismaMessageConfig,
    PrismaMessageLink,
    PrismaNames,
    PrismaTruthBullet,
)
from prisma.types import (
    PrismaGachaPlayerInclude,
    PrismaGuildConfigInclude,
)
from pydantic import field_serializer, field_validator

import common.text_utils as text_utils

__all__ = (
    "FIND_TRUTH_BULLET_EXACT_STR",
    "FIND_TRUTH_BULLET_STR",
    "VALIDATE_TRUTH_BULLET_STR",
    "BulletConfig",
    "DiceConfig",
    "DiceEntry",
    "GachaConfig",
    "GachaItem",
    "GachaPlayer",
    "GuildConfig",
    "InvestigationType",
    "ItemRelation",
    "ItemToPlayer",
    "ItemsConfig",
    "ItemsRelationType",
    "ItemsSystemItem",
    "MessageConfig",
    "MessageLink",
    "Names",
    "Rarity",
    "TruthBullet",
    "code_template",
    "escape_ilike",
    "short_desc",
)


# yes, this is a copy from common.utils
# but circular imports are a thing
def yesno_friendly_str(bool_to_convert: bool) -> str:
    return "yes" if bool_to_convert else "no"


def generate_regexp(attribute: str) -> str:
    return rf"regexp_replace({attribute}, '([\%_])', '\\\1', 'g')"


ILIKE_ESCAPE = re.compile(r"([\%_])")


def escape_ilike(value: str) -> str:
    return ILIKE_ESCAPE.sub(r"\\\1", value)


TEMPLATE_MARKDOWN = re.compile(r"({{(.*)}})")


def code_template(value: str) -> str:
    return TEMPLATE_MARKDOWN.sub(r"`\1`", value)


def short_desc(description: str, length: int = 25) -> str:
    new_description = textwrap.shorten(description, length, placeholder="...")
    if new_description == "...":  # word is too long, lets manually cut it
        return f"{description[:length-3].strip()}..."
    return new_description


class TruthBullet(PrismaTruthBullet):
    aliases: set[str]

    @field_validator("aliases", mode="after")
    @classmethod
    def _transform_aliases_into_set(cls, value: list[str]) -> set[str]:
        return set(value)

    @field_serializer("aliases", when_used="always")
    def _transform_aliases_into_list(self, value: set[str]) -> list[str]:
        return sorted(value)

    @property
    def chan_mention(self) -> str:
        return f"<#{self.channel_id}>"

    def bullet_info(self) -> str:
        str_list = [
            (
                f"Trigger `{text_utils.escape_markdown(self.trigger)}` - in"
                f" {self.chan_mention}"
            ),
            (
                "Aliases:"
                f" {', '.join(f'`{text_utils.escape_markdown(a)}`' for a in self.aliases)}"
                if self.aliases
                else "N/A"
            ),
            f"Hidden: {yesno_friendly_str(self.hidden)}",
            f"Found: {yesno_friendly_str(self.found)}",
        ]

        str_list.extend(
            (
                f"Finder: {f'<@{self.finder}>' if self.finder else 'N/A'}",
                "",
                f"Description: {self.description}",
            )
        )

        return "\n".join(str_list)

    def found_embed(self, username: str, singular_bullet: str) -> ipy.Embed:
        embed = ipy.Embed(
            title=f"{singular_bullet} Discovered",
            timestamp=ipy.Timestamp.utcnow(),
            color=int(os.environ["BOT_COLOR"]),
        )
        embed.description = (
            f"`{text_utils.escape_markdown(self.trigger)}` - from"
            f" {self.chan_mention}\n\n{self.description}"
        )

        footer = f"Found by {username}" if self.finder else "To be found as of"
        embed.set_footer(text=footer)

        if self.image:
            embed.set_image(self.image)

        return embed

    @classmethod
    async def find(
        cls, channel_id: ipy.Snowflake_Type, content: str
    ) -> typing.Self | None:
        return await cls.prisma().query_first(
            FIND_TRUTH_BULLET_STR, int(channel_id), content
        )

    @classmethod
    async def find_exact(
        cls, channel_id: ipy.Snowflake_Type, content: str
    ) -> typing.Self | None:
        return await cls.prisma().query_first(
            FIND_TRUTH_BULLET_EXACT_STR, int(channel_id), content
        )

    @classmethod
    async def find_possible_bullet(
        cls, channel_id: ipy.Snowflake_Type, trigger: str
    ) -> typing.Self | None:
        return await cls.prisma().find_first(
            where={
                "channel_id": int(channel_id),
                "trigger": {"equals": escape_ilike(trigger), "mode": "insensitive"},
            }
        )

    @classmethod
    async def validate(cls, channel_id: ipy.Snowflake_Type, trigger: str) -> bool:
        return (
            await cls.prisma()._client.query_first(
                VALIDATE_TRUTH_BULLET_STR, int(channel_id), trigger
            )
            is not None
        )

    async def save(self) -> None:
        data = self.model_dump()
        await self.prisma().update(where={"id": self.id}, data=data)  # type: ignore


class GetMethodsMixin:
    @classmethod
    async def get(cls, guild_id: int) -> typing.Self:
        return await cls.prisma().find_unique_or_raise(where={"guild_id": guild_id})

    @classmethod
    async def get_or_none(cls, guild_id: int) -> typing.Optional[typing.Self]:
        return await cls.prisma().find_unique(where={"guild_id": guild_id})

    @classmethod
    async def get_or_create(cls, guild_id: int) -> typing.Self:
        return await cls.get_or_none(guild_id) or await cls.prisma().create(
            data={"guild_id": guild_id}
        )


class Names(GetMethodsMixin, PrismaNames):
    main_config: "typing.Optional[GuildConfig]" = None

    def currency_name(self, amount: int) -> str:
        return self.singular_currency_name if amount == 1 else self.plural_currency_name

    async def save(self) -> None:
        data = self.model_dump(exclude={"main_config"})
        await self.prisma().update(where={"guild_id": self.guild_id}, data=data)  # type: ignore


class InvestigationType(IntEnum):
    DEFAULT = 1
    COMMAND_ONLY = 2


class BulletConfig(GetMethodsMixin, PrismaBulletConfig):
    investigation_type: InvestigationType
    main_config: "typing.Optional[GuildConfig]" = None

    @field_validator("investigation_type", mode="after")
    @classmethod
    def _transform_int_into_investigation_type(cls, value: int) -> InvestigationType:
        return InvestigationType(value)

    @field_serializer("investigation_type", when_used="always")
    def _transform_investigation_type_into_int(self, value: InvestigationType) -> int:
        return value.value

    async def save(self) -> None:
        data = self.model_dump(exclude={"main_config"})
        await self.prisma().update(where={"guild_id": self.guild_id}, data=data)  # type: ignore


class ItemToPlayer(PrismaItemToPlayer):
    item: typing.Optional["GachaItem"] = None
    player: typing.Optional["GachaPlayer"] = None

    async def save(self) -> None:
        data = self.model_dump(exclude={"item", "player"})
        await self.prisma().update(where={"id": self.id}, data=data)


class GachaItem(PrismaGachaItem):
    players: "typing.Optional[list[ItemToPlayer]]" = None
    gacha_config: "typing.Optional[GachaConfig]" = None

    def embed(self, *, show_amount: bool = False) -> ipy.Embed:
        embed = ipy.Embed(
            title=self.name,
            description=self.description,
            color=ipy.Color(int(os.environ["BOT_COLOR"])),
            timestamp=ipy.Timestamp.utcnow(),
        )
        if self.image:
            embed.set_thumbnail(self.image)

        if show_amount:
            embed.add_field(
                name="Quantity Remaining",
                value=self.amount if self.amount != -1 else "Unlimited",
                inline=True,
            )

        return embed

    async def save(self) -> None:
        data = self.model_dump(exclude={"gacha_config", "players"})
        await self.prisma().update(where={"id": self.id}, data=data)  # type: ignore


class _GachaHash:
    __slots__ = ("id", "item")

    def __init__(self, item: "GachaItem") -> None:
        self.item = item
        self.id = item.id

    def __hash__(self) -> int:
        return self.id

    def __eq__(self, other: object) -> bool:
        return isinstance(other, _GachaHash) and self.id == other.id


class GachaPlayer(PrismaGachaPlayer):
    items: "typing.Optional[list[ItemToPlayer]]" = None
    gacha_config: "typing.Optional[GachaConfig]" = None

    @classmethod
    async def get(
        cls,
        guild_id: int,
        user_id: int,
        include: PrismaGachaPlayerInclude | None = None,
    ) -> typing.Self:
        return await cls.prisma().find_first_or_raise(
            where={"guild_id": guild_id, "user_id": user_id}, include=include
        )

    @classmethod
    async def get_or_none(
        cls,
        guild_id: int,
        user_id: int,
        include: PrismaGachaPlayerInclude | None = None,
    ) -> typing.Optional[typing.Self]:
        return await cls.prisma().find_first(
            where={"guild_id": guild_id, "user_id": user_id}, include=include
        )

    @classmethod
    async def get_or_create(
        cls,
        guild_id: int,
        user_id: int,
        include: PrismaGachaPlayerInclude | None = None,
    ) -> typing.Self:
        return await cls.get_or_none(
            guild_id, user_id, include=include
        ) or await cls.prisma().create(
            data={"guild_id": guild_id, "user_id": user_id}, include=include
        )

    def create_profile(self, user_display_name: str, names: "Names") -> list[ipy.Embed]:
        str_builder = [
            (
                "Currency:"
                f" {self.currency_amount} {names.currency_name(self.currency_amount)}"
            ),
            "\n**Items:**",
        ]

        if self.items and all(entry.item for entry in self.items):
            counter: Counter[_GachaHash] = Counter()
            for item in self.items:
                counter[_GachaHash(item.item)] += 1

            counter_data = sorted(
                ((name, count) for name, count in counter.items()),
                key=lambda x: x[0].item.name.lower(),
            )

            str_builder.extend(
                f"**{entry.item.name}**{f' (x{count})' if count > 1 else ''} -"
                f" {short_desc(entry.item.description)}"
                for entry, count in counter_data
            )
        else:
            str_builder.append("*No items.*")

        if len(str_builder) <= 30:
            return [
                ipy.Embed(
                    title=f"{user_display_name}'s Gacha Data",
                    description="\n".join(str_builder),
                    color=ipy.Color(int(os.environ["BOT_COLOR"])),
                    timestamp=ipy.Timestamp.utcnow(),
                )
            ]

        chunks = [str_builder[x : x + 30] for x in range(0, len(str_builder), 30)]
        return [
            ipy.Embed(
                title=f"{user_display_name}'s Gacha Data",
                description="\n".join(chunk),
                color=ipy.Color(int(os.environ["BOT_COLOR"])),
                timestamp=ipy.Timestamp.utcnow(),
            )
            for chunk in chunks
        ]

    async def save(self) -> None:
        data = self.model_dump(exclude={"items", "gacha_config", "id", "guild_id"})
        await self.prisma().update(where={"id": self.id}, data=data)


class GachaConfig(GetMethodsMixin, PrismaGachaConfig):
    items: "typing.Optional[list[GachaItem]]" = None
    players: "typing.Optional[list[GachaPlayer]]" = None
    main_config: "typing.Optional[GuildConfig]" = None

    async def save(self) -> None:
        data = self.model_dump(exclude={"items", "players", "main_config"})
        await self.prisma().update(where={"guild_id": self.guild_id}, data=data)  # type: ignore


class MessageLink(PrismaMessageLink):
    message_config: typing.Optional["MessageConfig"] = None


class MessageConfig(PrismaMessageConfig):
    links: typing.Optional[list["MessageLink"]] = None
    main_config: typing.Optional["GuildConfig"] = None

    async def save(self) -> None:
        data = self.model_dump(exclude={"main_config", "links"})
        await self.prisma().update(where={"guild_id": self.guild_id}, data=data)  # type: ignore


class DiceEntry(PrismaDiceEntry):
    dice_config: typing.Optional["DiceConfig"] = None


class DiceConfig(GetMethodsMixin, PrimsaDiceConfig):
    entries: typing.Optional[list[DiceEntry]] = None
    main_config: typing.Optional["GuildConfig"] = None

    async def save(self) -> None:
        data = self.model_dump(exclude={"entries", "main_config"})
        await self.prisma().update(where={"guild_id": self.guild_id}, data=data)  # type: ignore


class ItemRelation(PrismaItemRelation):
    item: typing.Optional["ItemsSystemItem"] = None

    async def save(self) -> None:
        data = self.model_dump(exclude={"item"})
        await self.prisma().update(where={"id": self.id}, data=data)  # type: ignore


class _ItemRelationHash:
    __slots__ = ("id", "relation")

    def __init__(self, relation: "ItemRelation") -> None:
        self.relation = relation
        self.id = relation.object_id

    def __hash__(self) -> int:
        return self.id

    def __eq__(self, other: object) -> bool:
        return isinstance(other, _ItemRelationHash) and self.id == other.id


class ItemsSystemItem(PrismaItemsSystemItem):
    relations: typing.Optional[list[ItemRelation]] = None
    items_config: typing.Optional["ItemsConfig"] = None

    def embeds(self, *, count: int | None = None) -> list[ipy.Embed]:
        embeds: list[ipy.Embed] = []

        embed = ipy.Embed(
            title=f"{self.name}{f' (x{count})' if count else ''}",
            description=self.description,
            color=ipy.Color(int(os.environ["BOT_COLOR"])),
            timestamp=ipy.Timestamp.utcnow(),
        )
        if self.image:
            embed.set_thumbnail(self.image)

        embed.set_footer(f"Takeable: {yesno_friendly_str(self.takeable)}")

        embeds.append(embed)

        if self.relations:
            relation_counter: collections.Counter[_ItemRelationHash] = (
                collections.Counter()
            )

            for relation in self.relations:
                relation_counter[_ItemRelationHash(relation)] += 1

            relation_data = sorted(
                (
                    (relation.relation, count)
                    for relation, count in relation_counter.items()
                ),
                key=lambda x: x[0].object_type,
            )

            str_builder: list[str] = []
            character_count = 0

            for entry, count in relation_data:
                string_to_use = (
                    f"- <#{entry.object_id}> (x{count})"
                    if entry.object_type == ItemsRelationType.CHANNEL
                    else f"- <@{entry.object_id}> (x{count})"
                )

                if character_count + len(string_to_use) > 4000:
                    embeds.append(
                        ipy.Embed(
                            title=f"{self.name} - Possessors",
                            description="\n".join(str_builder),
                            color=ipy.Color(int(os.environ["BOT_COLOR"])),
                            timestamp=ipy.Timestamp.utcnow(),
                        )
                    )

                    str_builder.clear()
                    character_count = 0

                str_builder.append(string_to_use)
                character_count += len(string_to_use)

            if str_builder:
                embeds.append(
                    ipy.Embed(
                        title=f"{self.name} - Possessors",
                        description="\n".join(str_builder),
                        color=ipy.Color(int(os.environ["BOT_COLOR"])),
                        timestamp=ipy.Timestamp.utcnow(),
                    )
                )

        return embeds

    async def save(self) -> None:
        data = self.model_dump(exclude={"items_config", "relations"})
        await self.prisma().update(where={"id": self.id}, data=data)  # type: ignore


class ItemsConfig(GetMethodsMixin, PrismaItemsConfig):
    items: typing.Optional[list[ItemsSystemItem]] = None
    main_config: typing.Optional["GuildConfig"] = None

    async def save(self) -> None:
        data = self.model_dump(exclude={"items", "main_config"})
        await self.prisma().update(where={"guild_id": self.guild_id}, data=data)  # type: ignore


class GuildConfigMixin:
    guild_id: ipy.Snowflake

    if typing.TYPE_CHECKING:
        from prisma import actions

        @classmethod
        def prisma(cls) -> actions.PrismaGuildConfigActions[typing.Self]: ...

        model_dump: typing.Callable[..., dict[str, typing.Any]]

    async def _fill_in_include(
        self, include: PrismaGuildConfigInclude | None
    ) -> typing.Self:
        if not include:
            return self

        for entry in include:
            if entry == "names" and not getattr(self, "names", True):
                self.names = await Names.prisma().create(
                    data={"guild_id": self.guild_id}
                )
            if entry == "bullets" and not getattr(self, "bullets", True):
                self.bullets = await BulletConfig.prisma().create(
                    data={"guild_id": self.guild_id}
                )
            if entry == "gacha" and not getattr(self, "gacha", True):
                self.gacha = await GachaConfig.prisma().create(
                    data={"guild_id": self.guild_id}
                )
            if entry == "messages" and not getattr(self, "messages", True):
                self.messages = await MessageConfig.prisma().create(
                    data={"guild_id": self.guild_id}
                )
            if entry == "dice" and not getattr(self, "dice", True):
                self.dice = await DiceConfig.prisma().create(
                    data={"guild_id": self.guild_id}
                )
            if entry == "items" and not getattr(self, "items", True):
                self.items = await ItemsConfig.prisma().create(
                    data={"guild_id": self.guild_id}
                )

        return self

    @classmethod
    async def get(
        cls, guild_id: int, include: PrismaGuildConfigInclude | None = None
    ) -> typing.Self:
        config = await cls.prisma().find_unique_or_raise(
            where={"guild_id": guild_id},
            include=include,
        )
        return await config._fill_in_include(include)

    @classmethod
    async def get_or_none(
        cls, guild_id: int, include: PrismaGuildConfigInclude | None = None
    ) -> typing.Optional[typing.Self]:
        config = await cls.prisma().find_unique(
            where={"guild_id": guild_id}, include=include
        )

        if config:
            config = await config._fill_in_include(include)

        return config

    @classmethod
    async def get_or_create(
        cls, guild_id: int, include: PrismaGuildConfigInclude | None = None
    ) -> typing.Self:
        config = await cls.prisma().find_unique(
            where={"guild_id": guild_id}, include=include
        ) or await cls.prisma().create(data={"guild_id": guild_id})
        return await config._fill_in_include(include)

    async def save(self) -> None:
        data = self.model_dump(
            exclude={
                "names",
                "names_id",
                "bullets",
                "guild_id",
                "gacha",
                "messages",
                "dice",
                "items",
            }
        )
        await self.prisma().update(where={"guild_id": self.guild_id}, data=data)  # type: ignore


class GuildConfig(GuildConfigMixin, PrismaGuildConfig):
    bullets: typing.Optional[BulletConfig] = None
    gacha: typing.Optional[GachaConfig] = None
    names: typing.Optional[Names] = None
    dice: typing.Optional[DiceConfig] = None
    messages: typing.Optional[MessageConfig] = None
    items: typing.Optional[ItemsConfig] = None


FIND_TRUTH_BULLET_STR: typing.Final[str] = (
    f"""
SELECT
    {', '.join(TruthBullet.model_fields)}
FROM
    thiatruthbullets
WHERE
    channel_id = $1
    AND found = false
    AND (
        $2 ILIKE CONCAT('%', {generate_regexp('trigger')}, '%')
        OR EXISTS (
            SELECT 1
            FROM unnest(aliases) AS alias
            WHERE $2 ILIKE CONCAT('%', {generate_regexp('alias')}, '%')
        )
    );
""".strip()  # noqa: S608
)

VALIDATE_TRUTH_BULLET_STR: typing.Final[str] = (
    """
SELECT
    1
FROM
    thiatruthbullets
WHERE
    channel_id = $1
    AND (
        UPPER($2) = UPPER(trigger)
        OR EXISTS (
            SELECT 1
            FROM unnest(aliases) AS alias
            WHERE UPPER($2) = UPPER(alias)
        )
    );
""".strip()
)

FIND_TRUTH_BULLET_EXACT_STR: typing.Final[str] = (
    f"""
SELECT
    {', '.join(TruthBullet.model_fields)}
FROM
    thiatruthbullets
WHERE
    channel_id = $1
    AND (
        UPPER($2) = UPPER(trigger)
        OR EXISTS (
            SELECT 1
            FROM unnest(aliases) AS alias
            WHERE UPPER($2) = UPPER(alias)
        )
    );
""".strip()  # noqa: S608
)

anyio.AnyIOBackend = AsyncioBackend

with contextlib.suppress(ImportError):
    import orjson  # type: ignore

    class FastResponse(Response):
        async def json(self, **kwargs: typing.Any) -> typing.Any:
            return orjson.loads(await self.original.aread(), **kwargs)

    Response.json = FastResponse.json  # type: ignore

    def orjson_default(obj: typing.Any) -> typing.Any:
        if isinstance(obj, Base64):
            return str(obj)
        if isinstance(obj, Json):
            return orjson_dumps(obj.data)
        if isinstance(obj, ipy.Timestamp):
            if obj.tzinfo != datetime.timezone.utc:
                obj = obj.astimezone(datetime.timezone.utc)

            obj = obj.replace(microsecond=int(obj.microsecond / 1000) * 1000)
            return obj.isoformat()
        if isinstance(obj, ipy.Snowflake):
            return int(obj)

        raise NotImplementedError(f"Objects of type {type(obj)} are not supported")

    def orjson_dumps(obj: typing.Any, **_: typing.Any) -> str:
        return orjson.dumps(obj, default=orjson_default).decode()

    if _builder.dumps != orjson_dumps:
        _builder.dumps = orjson_dumps


Names.model_rebuild()
BulletConfig.model_rebuild()
GachaItem.model_rebuild()
GachaConfig.model_rebuild()
GachaPlayer.model_rebuild()
ItemToPlayer.model_rebuild()
MessageLink.model_rebuild()
MessageConfig.model_rebuild()
DiceConfig.model_rebuild()
DiceEntry.model_rebuild()
ItemsConfig.model_rebuild()
ItemsSystemItem.model_rebuild()
ItemRelation.model_rebuild()
