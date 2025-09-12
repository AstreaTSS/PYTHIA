"""
Copyright 2021-2025 AstreaTSS.
This file is part of PYTHIA.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

import collections
import os
import random
import re
import textwrap
from collections import Counter
from decimal import Decimal
from enum import Enum, IntEnum
from fractions import Fraction

import interactions as ipy
import typing_extensions as typing
from tortoise import Model, connections, fields
from tortoise.contrib.postgres.fields import ArrayField

import common.text_utils as text_utils


# yes, this is a copy from common.utils
# but circular imports are a thing
def yesno_friendly_str(bool_to_convert: bool) -> str:
    return "yes" if bool_to_convert else "no"


def generate_regexp(attribute: str) -> str:
    return rf"regexp_replace({attribute}, '([\%_])', '\\\1', 'g')"


TEMPLATE_MARKDOWN = re.compile(r"({{(.*)}})")


def code_template(value: str) -> str:
    return TEMPLATE_MARKDOWN.sub(r"`\1`", value)


def short_desc(description: str, length: int = 25) -> str:
    new_description = textwrap.shorten(description, length, placeholder="...")
    if new_description == "...":  # word is too long, lets manually cut it
        return f"{description[:length-3].strip()}..."
    return new_description


class ItemsRelationType(str, Enum):
    CHANNEL = "CHANNEL"
    USER = "USER"


class Rarity(IntEnum):
    COMMON = 1
    UNCOMMON = 2
    RARE = 3
    EPIC = 4
    LEGENDARY = 5


GACHA_RARITIES_LIST: typing.Final[list[Rarity]] = [
    Rarity.COMMON,
    Rarity.UNCOMMON,
    Rarity.RARE,
    Rarity.EPIC,
    Rarity.LEGENDARY,
]


class InvestigationType(IntEnum):
    DEFAULT = 1
    COMMAND_ONLY = 2


def new_init(old_init: typing.Callable) -> typing.Callable:
    def wrapper(self: Model, *args: typing.Any, **kwargs: typing.Any) -> None:
        guild_id = kwargs.pop("guild_id", None)
        old_init(self, *args, **kwargs)
        if guild_id is not None:
            self.guild_id = guild_id

    return wrapper


MODEL_T = typing.TypeVar("MODEL_T", bound=Model)


def guild_id_model(cls: type[MODEL_T]) -> type[MODEL_T]:
    cls._meta.fields_db_projection["guild_id"] = "guild_id"
    cls.__init__ = new_init(cls.__init__)
    return cls


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


class GachaConfig(Model):
    guild: fields.OneToOneRelation["GuildConfig"] = fields.OneToOneField(
        "models.GuildConfig", "gacha", pk=True
    )
    enabled = fields.BooleanField(default=False)
    currency_cost = fields.IntField(default=1)
    draw_duplicates = fields.BooleanField(default=True)

    items: fields.ReverseRelation["GachaItem"]
    players: fields.ReverseRelation["GachaPlayer"]
    rarities: fields.OneToOneNullableRelation["GachaRarities"]

    class Meta:
        table = "thiagachaconfig"


@guild_id_model
class GachaRarities(Model):
    guild: fields.OneToOneRelation["GachaConfig"] = fields.OneToOneField(
        "models.GachaConfig", "rarities", pk=True
    )
    common_color = fields.CharField(max_length=7, default="#979797")
    uncommon_color = fields.CharField(max_length=7, default="#6aad0f")
    rare_color = fields.CharField(max_length=7, default="#109db9")
    epic_color = fields.CharField(max_length=7, default="#ab47b9")
    legendary_color = fields.CharField(max_length=7, default="#f4d046")
    common_odds = fields.DecimalField(
        max_digits=5, decimal_places=4, default=Decimal("0.6")
    )
    uncommon_odds = fields.DecimalField(
        max_digits=5, decimal_places=4, default=Decimal("0.25")
    )
    rare_odds = fields.DecimalField(
        max_digits=5, decimal_places=4, default=Decimal("0.1")
    )
    epic_odds = fields.DecimalField(
        max_digits=5, decimal_places=4, default=Decimal("0.04")
    )
    legendary_odds = fields.DecimalField(
        max_digits=5, decimal_places=4, default=Decimal("0.01")
    )

    def color(self, rarity: Rarity) -> ipy.Color:
        match rarity:
            case Rarity.COMMON:
                return ipy.Color.from_hex(self.common_color)
            case Rarity.UNCOMMON:
                return ipy.Color.from_hex(self.uncommon_color)
            case Rarity.RARE:
                return ipy.Color.from_hex(self.rare_color)
            case Rarity.EPIC:
                return ipy.Color.from_hex(self.epic_color)
            case Rarity.LEGENDARY:
                return ipy.Color.from_hex(self.legendary_color)
            case _:
                raise ValueError(f"Invalid rarity: {rarity}")

    def roll_rarity(self) -> Rarity:
        value = random.choices(  # noqa: S311
            GACHA_RARITIES_LIST,
            (
                Fraction(self.common_odds),
                Fraction(self.uncommon_odds),
                Fraction(self.rare_odds),
                Fraction(self.epic_odds),
                Fraction(self.legendary_odds),
            ),
            k=1,
        )
        return value[0]

    class Meta:
        table = "thiagachararities"


@guild_id_model
class GachaItem(Model):
    id = fields.IntField(pk=True)
    guild: fields.ForeignKeyRelation[GachaConfig] = fields.ForeignKeyField(
        "models.GachaConfig", "items", db_index=True
    )
    name = fields.TextField()
    description = fields.TextField()
    image: fields.Field[str | None] = fields.TextField(null=True)
    rarity = fields.IntEnumField(Rarity, default=Rarity.COMMON, db_index=True)
    amount = fields.IntField(default=-1, db_index=True)

    players: fields.ReverseRelation["ItemToPlayer"]

    class Meta:
        table = "thiagachaitems"

    def embed(
        self,
        names: "Names",
        rarities: "GachaRarities",
        *,
        show_rarity: bool = True,
        show_amount: bool = False,
    ) -> ipy.Embed:
        embed = ipy.Embed(
            title=self.name,
            description=self.description,
            color=rarities.color(self.rarity),
            timestamp=ipy.Timestamp.utcnow(),
        )
        if self.image:
            embed.set_thumbnail(self.image)

        if show_rarity:
            embed.add_field("Rarity", names.rarity_name(self.rarity), inline=True)

        if show_amount:
            embed.add_field(
                name="Quantity",
                value=self.amount if self.amount != -1 else "Unlimited",
                inline=True,
            )

        return embed

    @classmethod
    async def roll(cls, guild_id: int, rarity: Rarity) -> typing.Self | None:
        conn = connections.get("default")
        data = await conn.execute_query_dict(
            GACHA_ROLL_STR, values=[guild_id, rarity.value]
        )
        return cls(**data[0]) if data else None

    @classmethod
    async def roll_no_duplicates(
        cls, guild_id: int, player_id: int, rarity: Rarity
    ) -> typing.Self | None:
        conn = connections.get("default")
        data = await conn.execute_query_dict(
            GACHA_ROLL_NO_DUPS_STR, values=[guild_id, player_id, rarity.value]
        )
        return cls(**data[0]) if data else None


class GachaHash:
    __slots__ = ("id", "item", "relation_id")

    def __init__(self, item: "GachaItem", relation_id: int | None = None) -> None:
        self.item = item
        self.id = item.id
        self.relation_id = relation_id

    def __hash__(self) -> int:
        return self.id

    def __eq__(self, other: object) -> bool:
        return isinstance(other, GachaHash) and self.id == other.id


@guild_id_model
class GachaPlayer(Model):
    id = fields.IntField(pk=True)
    guild: fields.ForeignKeyRelation[GachaConfig] = fields.ForeignKeyField(
        "models.GachaConfig", "players", db_index=True
    )
    user_id = fields.BigIntField()
    currency_amount = fields.IntField(default=0)

    items: fields.ReverseRelation["ItemToPlayer"]

    class Meta:
        table = "thiagachaplayers"
        indexes: typing.ClassVar[list[tuple[str, ...]]] = [("guild_id", "user_id")]

    def _organize_gacha_items(
        self, sort_by: typing.Literal["name", "rarity", "time_gotten"]
    ) -> list[tuple[GachaHash, int]]:
        counter: Counter[GachaHash] = Counter()
        for item in self.items:
            counter[GachaHash(item.item, item.id)] += 1

        if sort_by == "rarity":
            return sorted(
                ((name, count) for name, count in counter.items()),
                key=lambda x: (x[0].item.rarity, x[0].item.name.lower()),
            )
        if sort_by == "time_gotten":
            return sorted(
                ((name, count) for name, count in counter.items()),
                key=lambda x: x[0].relation_id if x[0].relation_id is not None else 0,
            )
        return sorted(
            ((name, count) for name, count in counter.items()),
            key=lambda x: x[0].item.name.lower(),
        )

    def _embedize_str_builder(
        self, str_builder: list[str], user_display_name: str, *, limit: int
    ) -> list[ipy.Embed]:
        if len(str_builder) <= limit:
            return [
                ipy.Embed(
                    title=f"{user_display_name}'s Gacha Profile",
                    description="\n".join(str_builder),
                    color=ipy.Color(int(os.environ["BOT_COLOR"])),
                    timestamp=ipy.Timestamp.utcnow(),
                )
            ]
        chunks = [str_builder[x : x + limit] for x in range(0, len(str_builder), limit)]
        return [
            ipy.Embed(
                title=f"{user_display_name}'s Gacha Profile",
                description="\n".join(chunk),
                color=ipy.Color(int(os.environ["BOT_COLOR"])),
                timestamp=ipy.Timestamp.utcnow(),
            )
            for chunk in chunks
        ]

    def create_profile_compact(
        self,
        user_display_name: str,
        names: "Names",
        *,
        sort_by: typing.Literal["name", "rarity", "time_gotten"],
    ) -> list[ipy.Embed]:
        str_builder = [
            (
                "Balance:"
                f" {self.currency_amount} {names.currency_name(self.currency_amount)}"
            ),
            "\n**Items:**",
        ]

        if (
            self.items._fetched
            and self.items
            and all(isinstance(entry.item, GachaItem) for entry in self.items)
        ):
            counter_data = self._organize_gacha_items(sort_by)
            str_builder.extend(
                f"**{entry.item.name}**{f' (x{count})' if count > 1 else ''} -"
                f" {short_desc(entry.item.description)}"
                for entry, count in counter_data
            )
        else:
            str_builder.append("*No items.*")

        return self._embedize_str_builder(str_builder, user_display_name, limit=30)

    def create_profile_cozy(
        self,
        user_display_name: str,
        names: "Names",
        *,
        sort_by: typing.Literal["name", "rarity", "time_gotten"],
    ) -> list[ipy.Embed]:
        str_builder = [
            (
                "Balance:"
                f" {self.currency_amount} {names.currency_name(self.currency_amount)}"
            ),
            "## Items",
        ]

        if (
            self.items._fetched
            and self.items
            and all(isinstance(entry.item, GachaItem) for entry in self.items)
        ):
            counter_data = self._organize_gacha_items(sort_by)
            str_builder.extend(
                f"**{entry.item.name}**{f' (x{count})' if count > 1 else ''}\n-#"
                f" {names.rarity_name(entry.item.rarity)} ●"
                f" {short_desc(entry.item.description, length=50)}"
                for entry, count in counter_data
            )
        else:
            str_builder.append("*No items.*")

        return self._embedize_str_builder(str_builder, user_display_name, limit=15)


class ItemToPlayer(Model):
    id = fields.IntField(pk=True)
    item: fields.ForeignKeyRelation[GachaItem] = fields.ForeignKeyField(
        "models.GachaItem", "players"
    )
    player: fields.ForeignKeyRelation[GachaPlayer] = fields.ForeignKeyField(
        "models.GachaPlayer", "items"
    )

    class Meta:
        table = "thiagachaitemtoplayer"


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


FIND_TRUTH_BULLET_STR: typing.Final[str] = (
    f"""
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
)

# the weird rarity stuff ensures that items with the same rarity are favored first,
# then rarities lower than the picked rarity, and finally rarities higher than the picked rarity
GACHA_ROLL_STR: typing.Final[str] = (
    f"""
SELECT
    {', '.join(GachaItem._meta.fields_db_projection)}
FROM
    thiagachaitems
WHERE
    guild_id = $1
    AND amount != 0
ORDER BY
    (
        CASE WHEN rarity <= $2 THEN $2 - rarity ELSE rarity + $2 END
    ) ASC,
    RANDOM()
    LIMIT 1;
""".strip()  # noqa: S608
)

GACHA_ROLL_NO_DUPS_STR: typing.Final[str] = (
    f"""
SELECT
    {', '.join(GachaItem._meta.fields_db_projection)}
FROM
    thiagachaitems
WHERE
    guild_id = $1
    AND amount != 0
    AND id NOT IN (
    SELECT
        item_id
    FROM
        thiagachaitemtoplayer
    WHERE
        player_id = $2
    )
ORDER BY
    (
        CASE WHEN rarity <= $3 THEN $3 - rarity ELSE rarity + $3 END
    ) ASC,
    RANDOM()
    LIMIT 1;
""".strip()  # noqa: S608
)
