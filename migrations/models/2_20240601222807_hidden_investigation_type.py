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
        ALTER TABLE "uinewconfig" ADD "investigation_type" SMALLINT NOT NULL  DEFAULT 1;
        ALTER TABLE "uinewtruthbullets" ADD "hidden" BOOL NOT NULL  DEFAULT False;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "uinewconfig" DROP COLUMN "investigation_type";
        ALTER TABLE "uinewtruthbullets" DROP COLUMN "hidden";"""
