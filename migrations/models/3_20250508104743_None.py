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
        CREATE TABLE IF NOT EXISTS "thiadicenetry" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "user_id" BIGINT NOT NULL,
    "name" TEXT NOT NULL,
    "value" TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS "idx_thiadicenet_guild_i_e65e30" ON "thiadicenetry" ("guild_id", "user_id");
CREATE TABLE IF NOT EXISTS "thiagachaitems" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "name" TEXT NOT NULL,
    "description" TEXT NOT NULL,
    "image" TEXT,
    "rarity" VARCHAR(10) NOT NULL DEFAULT 'COMMON',
    "amount" INT NOT NULL DEFAULT -1
);
CREATE INDEX IF NOT EXISTS "idx_thiagachait_amount_9cb45b" ON "thiagachaitems" ("amount");
COMMENT ON COLUMN "thiagachaitems"."rarity" IS 'COMMON: COMMON\nUNCOMMON: UNCOMMON\nRARE: RARE\nSUPER_RARE: SUPER_RARE\nLEGENDARY: LEGENDARY';
CREATE TABLE IF NOT EXISTS "thiagachaplayers" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "user_id" BIGINT NOT NULL,
    "currency_amount" INT NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS "idx_thiagachapl_guild_i_677538" ON "thiagachaplayers" ("guild_id", "user_id");
CREATE TABLE IF NOT EXISTS "thiaguildconfig" (
    "guild_id" BIGSERIAL NOT NULL PRIMARY KEY,
    "player_role" BIGINT
);
CREATE TABLE IF NOT EXISTS "thiabulletconfig" (
    "bullet_chan_id" BIGINT,
    "best_bullet_finder_role" BIGINT,
    "bullets_enabled" BOOL NOT NULL DEFAULT False,
    "investigation_type" SMALLINT NOT NULL DEFAULT 1,
    "show_best_finders" BOOL NOT NULL DEFAULT True,
    "guild_id" BIGINT NOT NULL PRIMARY KEY REFERENCES "thiaguildconfig" ("guild_id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "thiadiceconfig" (
    "visible" BOOL NOT NULL DEFAULT True,
    "guild_id" BIGINT NOT NULL PRIMARY KEY REFERENCES "thiaguildconfig" ("guild_id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "thiagachaconfig" (
    "enabled" BOOL NOT NULL DEFAULT False,
    "currency_cost" INT NOT NULL DEFAULT 1,
    "draw_duplicates" BOOL NOT NULL DEFAULT True,
    "guild_id" BIGINT NOT NULL PRIMARY KEY REFERENCES "thiaguildconfig" ("guild_id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "thiagachaitemtoplayer" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "item_id" INT NOT NULL REFERENCES "thiagachaitems" ("id") ON DELETE CASCADE,
    "player_id" INT NOT NULL REFERENCES "thiagachaplayers" ("id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "thiaitemsconfig" (
    "enabled" BOOL NOT NULL DEFAULT False,
    "autosuggest" BOOL NOT NULL DEFAULT True,
    "guild_id" BIGINT NOT NULL PRIMARY KEY REFERENCES "thiaguildconfig" ("guild_id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "thiaitemssystemitems" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "name" TEXT NOT NULL,
    "description" TEXT NOT NULL,
    "image" TEXT,
    "takeable" BOOL NOT NULL DEFAULT True
);
CREATE TABLE IF NOT EXISTS "thiaitemrelation" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "guild_id" BIGINT NOT NULL,
    "object_id" BIGINT NOT NULL,
    "object_type" VARCHAR(7) NOT NULL,
    "item_id" INT NOT NULL REFERENCES "thiaitemssystemitems" ("id") ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS "idx_thiaitemrel_guild_i_7e3909" ON "thiaitemrelation" ("guild_id");
CREATE INDEX IF NOT EXISTS "idx_thiaitemrel_object__45289d" ON "thiaitemrelation" ("object_id");
CREATE INDEX IF NOT EXISTS "idx_thiaitemrel_item_id_d2fb82" ON "thiaitemrelation" ("item_id");
COMMENT ON COLUMN "thiaitemrelation"."object_type" IS 'CHANNEL: CHANNEL\nUSER: USER';
CREATE TABLE IF NOT EXISTS "thiamessageconfig" (
    "enabled" BOOL NOT NULL DEFAULT False,
    "anon_enabled" BOOL NOT NULL DEFAULT False,
    "ping_for_message" BOOL NOT NULL DEFAULT False,
    "guild_id" BIGINT NOT NULL PRIMARY KEY REFERENCES "thiaguildconfig" ("guild_id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "thiamessagelink" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "user_id" BIGINT NOT NULL,
    "channel_id" BIGINT NOT NULL
);
CREATE INDEX IF NOT EXISTS "idx_thiamessage_guild_i_acc8ad" ON "thiamessagelink" ("guild_id", "user_id");
CREATE TABLE IF NOT EXISTS "thianames" (
    "singular_bullet" TEXT NOT NULL,
    "plural_bullet" TEXT NOT NULL,
    "singular_truth_bullet_finder" TEXT NOT NULL,
    "plural_truth_bullet_finder" TEXT NOT NULL,
    "best_bullet_finder" TEXT NOT NULL,
    "singular_currency_name" TEXT NOT NULL,
    "plural_currency_name" TEXT NOT NULL,
    "guild_id" BIGINT NOT NULL PRIMARY KEY REFERENCES "thiaguildconfig" ("guild_id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "thiatruthbullets" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "trigger" VARCHAR(100) NOT NULL,
    "aliases" VARCHAR(40)[],
    "description" TEXT NOT NULL,
    "channel_id" BIGINT NOT NULL,
    "guild_id" BIGINT NOT NULL,
    "found" BOOL NOT NULL,
    "finder" BIGINT,
    "hidden" BOOL NOT NULL DEFAULT False,
    "image" TEXT
);
CREATE INDEX IF NOT EXISTS "idx_thiatruthbu_channel_f961d5" ON "thiatruthbullets" ("channel_id");
CREATE INDEX IF NOT EXISTS "idx_thiatruthbu_guild_i_ab26d7" ON "thiatruthbullets" ("guild_id");
CREATE INDEX IF NOT EXISTS "idx_thiatruthbu_found_a493d8" ON "thiatruthbullets" ("found");
CREATE TABLE IF NOT EXISTS "aerich" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "version" VARCHAR(255) NOT NULL,
    "app" VARCHAR(100) NOT NULL,
    "content" JSONB NOT NULL
);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        """
