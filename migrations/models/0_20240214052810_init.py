"""
Copyright 2021-2024 AstreaTSS.
This file is part of Ultimate Investigator.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "uinewconfig" (
    "guild_id" BIGSERIAL NOT NULL PRIMARY KEY,
    "bullet_chan_id" BIGINT,
    "ult_detective_role" BIGINT,
    "player_role" BIGINT,
    "bullets_enabled" BOOL NOT NULL  DEFAULT False
);
CREATE TABLE IF NOT EXISTS "uinewtruthbullets" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "name" VARCHAR(100) NOT NULL,
    "aliases" VARCHAR(40)[] NOT NULL,
    "description" TEXT NOT NULL,
    "channel_id" BIGINT NOT NULL,
    "guild_id" BIGINT NOT NULL,
    "found" BOOL NOT NULL,
    "finder" BIGINT
);
CREATE INDEX IF NOT EXISTS "idx_uinewtruthb_name_37580d" ON "uinewtruthbullets" ("name", "channel_id", "guild_id", "found");
CREATE TABLE IF NOT EXISTS "aerich" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "version" VARCHAR(255) NOT NULL,
    "app" VARCHAR(100) NOT NULL,
    "content" JSONB NOT NULL
);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        """
