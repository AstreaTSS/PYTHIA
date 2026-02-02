"""
Copyright 2021-2026 AstreaTSS.
This file is part of PYTHIA.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

import os
import random
from collections import Counter
from decimal import Decimal
from enum import IntEnum
from itertools import accumulate

import interactions as ipy
import typing_extensions as typing
from tortoise import Model, connections, fields

import common.text_utils as text_utils
from common.models.utils import guild_id_model, short_desc

if typing.TYPE_CHECKING:
    from common.models.main_models import GuildConfig, Names


__all__ = (
    "GACHA_RARITIES_LIST",
    "GACHA_ROLL_NO_DUPS_STR",
    "GACHA_ROLL_STR",
    "GachaConfig",
    "GachaHash",
    "GachaItem",
    "GachaPlayer",
    "GachaRarities",
    "ItemToPlayer",
    "Rarity",
)


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
        accumlated_odds = tuple(
            accumulate(
                (
                    self.common_odds,
                    self.uncommon_odds,
                    self.rare_odds,
                    self.epic_odds,
                    self.legendary_odds,
                )
            )
        )

        random_value = random.random()  # noqa: S311

        return next(
            (
                rarity
                for rarity, threshold in zip(
                    GACHA_RARITIES_LIST, accumlated_odds, strict=True
                )
                if Decimal(random_value) < threshold
            ),
            Rarity.LEGENDARY,
        )

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
                f"**{text_utils.escape_markdown(entry.item.name)}**{f' (x{count})' if count > 1 else ''}"
                f" - {short_desc(entry.item.description)}"
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
                f"**{text_utils.escape_markdown(entry.item.name)}**{f' (x{count})' if count > 1 else ''}\n-#"
                f" {names.rarity_name(entry.item.rarity)} ●"
                f" {short_desc(entry.item.description, length=50)}"
                for entry, count in counter_data
            )
        else:
            str_builder.append("*No items.*")

        return self._embedize_str_builder(str_builder, user_display_name, limit=15)

    def create_profile_modern(
        self,
        names: "Names",
        *,
        sort_by: typing.Literal["name", "rarity", "time_gotten"],
    ) -> list[list[ipy.BaseComponent]]:

        component_builder: list[ipy.BaseComponent] = []

        if (
            self.items._fetched
            and self.items
            and all(isinstance(entry.item, GachaItem) for entry in self.items)
        ):
            counter_data = self._organize_gacha_items(sort_by)
            component_builder.extend(
                ipy.TextDisplayComponent(
                    f"**{text_utils.escape_markdown(entry.item.name)}**{f' (x{count})' if count > 1 else ''}\n-#"
                    f" {names.rarity_name(entry.item.rarity)} ●"
                    f" {short_desc(entry.item.description, length=50)}"
                )
                for entry, count in counter_data
            )
        else:
            component_builder.append(ipy.TextDisplayComponent("*No items.*"))

        chunks = [
            component_builder[x : x + 15] for x in range(0, len(component_builder), 15)
        ]
        chunks[0].insert(0, ipy.SeparatorComponent(divider=True))
        chunks[0].insert(
            0,
            ipy.TextDisplayComponent(
                "Balance:"
                f" {self.currency_amount} {names.currency_name(self.currency_amount)}"
            ),
        )
        return chunks

    def create_profile_spacious(
        self,
        names: "Names",
        *,
        sort_by: typing.Literal["name", "rarity", "time_gotten"],
        admin: bool = False,
    ) -> list[list[ipy.BaseComponent]]:

        component_builder: list[ipy.BaseComponent] = [
            ipy.TextDisplayComponent(
                "Balance:"
                f" {self.currency_amount} {names.currency_name(self.currency_amount)}"
            ),
            ipy.SeparatorComponent(divider=True),
        ]

        if (
            self.items._fetched
            and self.items
            and all(isinstance(entry.item, GachaItem) for entry in self.items)
        ):
            counter_data = self._organize_gacha_items(sort_by)
            component_builder.extend(
                ipy.SectionComponent(
                    components=ipy.TextDisplayComponent(
                        f"**{entry.item.name}**{f' (x{count})' if count > 1 else ''}\n-#"
                        f" {names.rarity_name(entry.item.rarity)} ●"
                        f" {short_desc(entry.item.description, length=50)}"
                    ),
                    accessory=ipy.Button(
                        style=ipy.ButtonStyle.GRAY,
                        label="View",
                        custom_id=(
                            f"gacha-item-{entry.item.id}-admin"
                            if admin
                            else f"gacha-item-{entry.item.id}"
                        ),
                    ),
                )
                for entry, count in counter_data
            )
        else:
            component_builder.append(ipy.TextDisplayComponent("*No items.*"))

        return [
            component_builder[x : x + 10] for x in range(0, len(component_builder), 10)
        ]


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


# the weird rarity stuff ensures that items with the same rarity are favored first,
# then rarities lower than the picked rarity, and finally rarities higher than the picked rarity
GACHA_ROLL_STR: typing.Final[str] = f"""
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

GACHA_ROLL_NO_DUPS_STR: typing.Final[str] = f"""
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
