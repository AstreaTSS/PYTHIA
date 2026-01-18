"""
Copyright 2021-2026 AstreaTSS.
This file is part of PYTHIA.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

import collections
import os
from enum import Enum, IntEnum

import interactions as ipy
import typing_extensions as typing
from tortoise import Model, connections, fields
from tortoise.contrib.postgres.fields import ArrayField

import common.text_utils as text_utils
from common.models.gacha_models import GachaConfig, Rarity
from common.models.utils import (
    generate_regexp,
    guild_id_model,
    short_desc,
    yesno_friendly_str,
)

__all__ = (
    "FIND_TRUTH_BULLET_EXACT_STR",
    "FIND_TRUTH_BULLET_STR",
    "VALIDATE_TRUTH_BULLET_STR",
    "BulletConfig",
    "BulletThreadBehavior",
    "DiceConfig",
    "DiceEntry",
    "GuildConfig",
    "GuildConfigInclude",
    "InvestigationType",
    "ItemHash",
    "ItemRelation",
    "ItemsConfig",
    "ItemsRelationType",
    "ItemsSystemItem",
    "MessageConfig",
    "MessageLink",
    "Names",
    "TruthBullet",
)


class BulletThreadBehavior(IntEnum):
    """
    DISTINCT: Threads are treated distinctly from their parent channel.
    PARENT: Threads are treated as their parent channel.
    """

    DISTINCT = 1
    PARENT = 2


class ItemsRelationType(str, Enum):
    CHANNEL = "CHANNEL"
    USER = "USER"


class InvestigationType(IntEnum):
    DEFAULT = 1
    COMMAND_ONLY = 2


class Names(Model):
    guild: fields.OneToOneRelation["GuildConfig"] = fields.OneToOneField(
        "models.GuildConfig", "names", pk=True
    )
    singular_bullet = fields.TextField(default="Truth Bullet")
    plural_bullet = fields.TextField(default="Truth Bullets")
    singular_truth_bullet_finder = fields.TextField(default="{{bullet_name}} Finder")
    plural_truth_bullet_finder = fields.TextField(default="{{bullet_name}} Finders")
    best_bullet_finder = fields.TextField(default="Best {{bullet_finder}}")
    singular_currency_name = fields.TextField(default="Coin")
    plural_currency_name = fields.TextField(default="Coins")
    gacha_common_name = fields.TextField(default="Common")
    gacha_uncommon_name = fields.TextField(default="Uncommon")
    gacha_rare_name = fields.TextField(default="Rare")
    gacha_epic_name = fields.TextField(default="Epic")
    gacha_legendary_name = fields.TextField(default="***__Legendary__***")

    class Meta:
        table = "thianames"

    def currency_name(self, amount: int) -> str:
        return self.singular_currency_name if amount == 1 else self.plural_currency_name

    def rarity_name(self, rarity: "Rarity") -> str:
        match rarity:
            case Rarity.COMMON:
                return self.gacha_common_name
            case Rarity.UNCOMMON:
                return self.gacha_uncommon_name
            case Rarity.RARE:
                return self.gacha_rare_name
            case Rarity.EPIC:
                return self.gacha_epic_name
            case Rarity.LEGENDARY:
                return self.gacha_legendary_name
            case _:
                raise ValueError(f"Invalid rarity: {rarity}")


class BulletConfig(Model):
    guild: fields.OneToOneRelation["GuildConfig"] = fields.OneToOneField(
        "models.GuildConfig", "bullets", pk=True
    )
    bullet_chan_id: fields.Field[int | None] = fields.BigIntField(null=True)
    best_bullet_finder_role: fields.Field[int | None] = fields.BigIntField(null=True)
    bullets_enabled = fields.BooleanField(default=False)
    investigation_type = fields.SmallIntField(default=1)
    show_best_finders = fields.BooleanField(default=True)
    thread_behavior = fields.IntEnumField(
        BulletThreadBehavior, default=BulletThreadBehavior.DISTINCT
    )

    @property
    def thread_behavior_desc(self) -> str:
        match self.thread_behavior:
            case BulletThreadBehavior.DISTINCT:
                return "Distinct entity from parent channel"
            case BulletThreadBehavior.PARENT:
                return "Treated as the parent channel"
            case _:
                raise ValueError(f"Invalid thread behavior: {self.thread_behavior}")

    @property
    def investigation_type_enum(self) -> InvestigationType:
        return InvestigationType(self.investigation_type)

    class Meta:
        table = "thiabulletconfig"


class ItemsConfig(Model):
    guild: fields.OneToOneRelation["GuildConfig"] = fields.OneToOneField(
        "models.GuildConfig", "items", pk=True
    )
    enabled = fields.BooleanField(default=False)
    autosuggest = fields.BooleanField(default=True)

    items: fields.ReverseRelation["ItemsSystemItem"]

    class Meta:
        table = "thiaitemsconfig"


class _ItemRelationHash:
    __slots__ = ("id", "relation")

    def __init__(self, relation: "ItemRelation") -> None:
        self.relation = relation
        self.id = relation.object_id

    def __hash__(self) -> int:
        return self.id

    def __eq__(self, other: object) -> bool:
        return isinstance(other, _ItemRelationHash) and self.id == other.id


class ItemHash:
    __slots__ = ("id", "item")

    def __init__(self, item: "ItemsSystemItem") -> None:
        self.item = item
        self.id = item.id

    def __hash__(self) -> int:
        return self.id

    def __eq__(self, other: object) -> bool:
        return isinstance(other, ItemHash) and self.id == other.id


@guild_id_model
class ItemsSystemItem(Model):
    id = fields.IntField(pk=True)
    guild: fields.ForeignKeyRelation[ItemsConfig] = fields.ForeignKeyField(
        "models.ItemsConfig", "items", db_index=True
    )
    name = fields.TextField()
    description = fields.TextField()
    image: fields.Field[str | None] = fields.TextField(null=True)
    takeable = fields.BooleanField(default=True)

    relations: fields.ReverseRelation["ItemRelation"]

    class Meta:
        table = "thiaitemssystemitems"

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

        if self.relations._fetched and self.relations:
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


class ItemRelation(Model):
    id = fields.IntField(pk=True)
    item: fields.ForeignKeyRelation["ItemsSystemItem"] = fields.ForeignKeyField(
        "models.ItemsSystemItem", "relations"
    )
    guild_id = fields.BigIntField(db_index=True)
    object_id = fields.BigIntField(db_index=True)
    object_type = fields.CharEnumField(ItemsRelationType)

    class Meta:
        table = "thiaitemrelation"
        indexes: typing.ClassVar[list[tuple[str]]] = [
            ("item_id",),
            ("guild_id",),
            ("object_id",),
        ]

    @classmethod
    async def items_for_channel_display(
        cls,
        channel_id: ipy.Snowflake_Type,
        mode: str,
    ) -> list[list[str]]:
        if mode not in ("cozy", "compact"):
            raise ipy.errors.BadArgument("Invalid mode.")

        channel_items = await cls.filter(
            object_id=channel_id,
        ).prefetch_related("item")
        if not channel_items:
            raise ipy.errors.BadArgument("This channel has no items placed in it.")

        items_counter: collections.Counter[ItemHash] = collections.Counter()

        for item in channel_items:
            items_counter[ItemHash(item.item)] += 1

        str_builder: list[str] = []

        for k, v in sorted(items_counter.items(), key=lambda i: i[0].item.name.lower()):
            if mode == "compact":
                str_builder.append(
                    f"**{text_utils.escape_markdown(k.item.name)}**{f' (x{v})' if v > 1 else ''}:"
                    f" {short_desc(k.item.description)}"
                )
            else:
                str_builder.append(
                    f"**{text_utils.escape_markdown(k.item.name)}**{f' (x{v})' if v > 1 else ''}\n-#"
                    f" {short_desc(k.item.description, 70)}"
                )

        limit = 15 if mode == "cozy" else 30
        return [str_builder[x : x + limit] for x in range(0, len(str_builder), limit)]


class MessageConfig(Model):
    guild: fields.OneToOneRelation["GuildConfig"] = fields.OneToOneField(
        "models.GuildConfig", "messages", pk=True
    )
    enabled = fields.BooleanField(default=False)
    anon_enabled = fields.BooleanField(default=False)
    ping_for_message = fields.BooleanField(default=False)

    links: fields.ReverseRelation["MessageLink"]

    class Meta:
        table = "thiamessageconfig"


@guild_id_model
class MessageLink(Model):
    id = fields.IntField(pk=True)
    guild: fields.ForeignKeyRelation[MessageConfig] = fields.ForeignKeyField(
        "models.MessageConfig", "links", db_index=True
    )
    user_id = fields.BigIntField()
    channel_id = fields.BigIntField()

    class Meta:
        table = "thiamessagelink"
        indexes: typing.ClassVar[list[tuple[str, ...]]] = [("guild_id", "user_id")]


class DiceConfig(Model):
    guild: fields.OneToOneRelation["GuildConfig"] = fields.OneToOneField(
        "models.GuildConfig", "dice", pk=True
    )
    visible = fields.BooleanField(default=True)

    entries: fields.ReverseRelation["DiceEntry"]

    class Meta:
        table = "thiadiceconfig"


@guild_id_model
class DiceEntry(Model):
    id = fields.IntField(pk=True)
    guild: fields.ForeignKeyRelation[DiceConfig] = fields.ForeignKeyField(
        "models.DiceConfig", "entries", db_index=True
    )
    user_id = fields.BigIntField()
    name = fields.TextField()
    value = fields.TextField()

    class Meta:
        table = "thiadicenetry"
        indexes: typing.ClassVar[list[tuple[str, ...]]] = [("guild_id", "user_id")]


class TruthBullet(Model):
    id = fields.IntField(pk=True)
    trigger = fields.CharField(max_length=100)
    aliases: fields.Field[list[str] | None] = ArrayField("VARCHAR(40)", null=True)
    description = fields.TextField()
    channel_id = fields.BigIntField(db_index=True)
    guild_id = fields.BigIntField(db_index=True)
    found = fields.BooleanField(db_index=True)
    finder: fields.Field[int | None] = fields.BigIntField(null=True)
    hidden = fields.BooleanField(default=False)
    image: fields.Field[str | None] = fields.TextField(null=True)

    class Meta:
        table = "thiatruthbullets"

    @property
    def chan_mention(self) -> str:
        return f"<#{self.channel_id}>"

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
        conn = connections.get("default")
        data = await conn.execute_query_dict(
            FIND_TRUTH_BULLET_STR, values=[int(channel_id), content]
        )
        return cls(**data[0]) if data else None

    @classmethod
    async def find_exact(
        cls, channel_id: ipy.Snowflake_Type, content: str
    ) -> typing.Self | None:
        conn = connections.get("default")
        data = await conn.execute_query_dict(
            FIND_TRUTH_BULLET_EXACT_STR, values=[int(channel_id), content]
        )
        return cls(**data[0]) if data else None

    @classmethod
    async def find_via_trigger(
        cls, channel_id: ipy.Snowflake_Type, trigger: str
    ) -> typing.Self | None:
        return await cls.filter(
            channel_id=int(channel_id),
            trigger__iexact=trigger,
        ).first()

    @classmethod
    async def validate(cls, channel_id: ipy.Snowflake_Type, trigger: str) -> bool:
        conn = connections.get("default")
        data = await conn.execute_query_dict(
            VALIDATE_TRUTH_BULLET_STR, values=[int(channel_id), trigger]
        )
        return bool(data)


class GuildConfigInclude(typing.TypedDict, total=False):
    names: bool
    bullets: bool
    gacha: bool
    messages: bool
    dice: bool
    items: bool


class GuildConfig(Model):
    guild_id = fields.BigIntField(pk=True)
    player_role: fields.Field[int | None] = fields.BigIntField(null=True)

    names: fields.OneToOneNullableRelation["Names"]
    bullets: fields.OneToOneNullableRelation["BulletConfig"]
    gacha: fields.OneToOneNullableRelation["GachaConfig"]
    messages: fields.OneToOneNullableRelation["MessageConfig"]
    dice: fields.OneToOneNullableRelation["DiceConfig"]
    items: fields.OneToOneNullableRelation["ItemsConfig"]

    class Meta:
        table = "thiaguildconfig"

    async def _fill_in_include(self, include: GuildConfigInclude | None) -> typing.Self:
        if not include:
            return self

        for entry in include:
            # the normal relational attributes are properties
            # we need to change the underlying attribute instead, hence the _ prefix
            if entry == "names" and not getattr(self, "names", True):
                self._names = await Names.create(guild_id=self.guild_id)
            if entry == "bullets" and not getattr(self, "bullets", True):
                self._bullets = await BulletConfig.create(guild_id=self.guild_id)
            if entry == "gacha" and not getattr(self, "gacha", True):
                self._gacha = await GachaConfig.create(guild_id=self.guild_id)
            if entry == "messages" and not getattr(self, "messages", True):
                self._messages = await MessageConfig.create(guild_id=self.guild_id)
            if entry == "dice" and not getattr(self, "dice", True):
                self._dice = await DiceConfig.create(guild_id=self.guild_id)
            if entry == "items" and not getattr(self, "items", True):
                self._items = await ItemsConfig.create(guild_id=self.guild_id)

        return self

    @classmethod
    async def fetch_create(
        cls, guild_id: int, include: GuildConfigInclude | None = None
    ) -> typing.Self:
        queryset = cls.get_or_none(guild_id=guild_id)
        if include:
            queryset = queryset.prefetch_related(*include.keys())
        config = await queryset

        if not config:
            config = await cls.create(guild_id=guild_id)
            if include:
                for field in include.keys():
                    setattr(config, f"_{field}", None)

        return await config._fill_in_include(include)

    @classmethod
    async def fetch(
        cls, guild_id: int, include: GuildConfigInclude
    ) -> typing.Self | None:
        config = await cls.get_or_none(guild_id=guild_id).prefetch_related(
            *include.keys()
        )
        return await config._fill_in_include(include) if config else config


FIND_TRUTH_BULLET_STR: typing.Final[str] = f"""
SELECT
    {', '.join(TruthBullet._meta.fields)}
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

VALIDATE_TRUTH_BULLET_STR: typing.Final[str] = """
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

FIND_TRUTH_BULLET_EXACT_STR: typing.Final[str] = f"""
SELECT
    {', '.join(TruthBullet._meta.fields)}
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
