"""
Copyright 2021-2025 AstreaTSS.
This file is part of PYTHIA.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        UPDATE "thiagachaitems" SET "rarity" = '1' WHERE "rarity" = 'COMMON';
        UPDATE "thiagachaitems" SET "rarity" = '2' WHERE "rarity" = 'UNCOMMON';
        UPDATE "thiagachaitems" SET "rarity" = '3' WHERE "rarity" = 'RARE';
        UPDATE "thiagachaitems" SET "rarity" = '4' WHERE "rarity" = 'SUPER_RARE';
        UPDATE "thiagachaitems" SET "rarity" = '5' WHERE "rarity" = 'LEGENDARY';

        ALTER TABLE "thiagachaitems" ALTER COLUMN "rarity" SET DEFAULT 1;
        ALTER TABLE "thiagachaitems" ALTER COLUMN "rarity" TYPE SMALLINT USING "rarity"::SMALLINT;
        COMMENT ON COLUMN "thiagachaitems"."rarity" IS 'COMMON: 1
UNCOMMON: 2
RARE: 3
EPIC: 4
LEGENDARY: 5';
        CREATE TABLE IF NOT EXISTS "thiagachararities" (
    "common_color" VARCHAR(7) NOT NULL DEFAULT '#979797',
    "uncommon_color" VARCHAR(7) NOT NULL DEFAULT '#6aad0f',
    "rare_color" VARCHAR(7) NOT NULL DEFAULT '#109db9',
    "epic_color" VARCHAR(7) NOT NULL DEFAULT '#ab47b9',
    "legendary_color" VARCHAR(7) NOT NULL DEFAULT '#f4d046',
    "common_odds" DECIMAL(5,4) NOT NULL DEFAULT 0.6,
    "uncommon_odds" DECIMAL(5,4) NOT NULL DEFAULT 0.25,
    "rare_odds" DECIMAL(5,4) NOT NULL DEFAULT 0.1,
    "epic_odds" DECIMAL(5,4) NOT NULL DEFAULT 0.04,
    "legendary_odds" DECIMAL(5,4) NOT NULL DEFAULT 0.01,
    "guild_id" BIGINT NOT NULL PRIMARY KEY REFERENCES "thiagachaconfig" ("guild_id") ON DELETE CASCADE
);
        ALTER TABLE "thianames" ADD "gacha_uncommon_name" TEXT NOT NULL DEFAULT 'Uncommon';
        ALTER TABLE "thianames" ADD "gacha_rare_name" TEXT NOT NULL DEFAULT 'Rare';
        ALTER TABLE "thianames" ADD "gacha_legendary_name" TEXT NOT NULL DEFAULT '***__Legendary__***';
        ALTER TABLE "thianames" ADD "gacha_common_name" TEXT NOT NULL DEFAULT 'Common';
        ALTER TABLE "thianames" ADD "gacha_epic_name" TEXT NOT NULL DEFAULT 'Epic';"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "thianames" DROP COLUMN "gacha_uncommon_name";
        ALTER TABLE "thianames" DROP COLUMN "gacha_rare_name";
        ALTER TABLE "thianames" DROP COLUMN "gacha_legendary_name";
        ALTER TABLE "thianames" DROP COLUMN "gacha_common_name";
        ALTER TABLE "thianames" DROP COLUMN "gacha_epic_name";
        ALTER TABLE "thiagachaitems" ALTER COLUMN "rarity" TYPE VARCHAR(10) USING "rarity"::VARCHAR(10);
        ALTER TABLE "thiagachaitems" ALTER COLUMN "rarity" SET DEFAULT 'COMMON';

        UPDATE "thiagachaitems" SET "rarity" = 'COMMON' WHERE "rarity" = '1';
        UPDATE "thiagachaitems" SET "rarity" = 'UNCOMMON' WHERE "rarity" = '2';
        UPDATE "thiagachaitems" SET "rarity" = 'RARE' WHERE "rarity" = '3';
        UPDATE "thiagachaitems" SET "rarity" = 'SUPER_RARE' WHERE "rarity" = '4';
        UPDATE "thiagachaitems" SET "rarity" = 'LEGENDARY' WHERE "rarity" = '5';

        COMMENT ON COLUMN "thiagachaitems"."rarity" IS 'COMMON: COMMON
UNCOMMON: UNCOMMON
RARE: RARE
SUPER_RARE: SUPER_RARE
LEGENDARY: LEGENDARY';
        DROP TABLE IF EXISTS "thiagachararities";"""
