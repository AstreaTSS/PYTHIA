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
    ALTER TABLE "thiagachaitems"
    ALTER COLUMN "rarity" TYPE varchar;

    ALTER TABLE "thiagachaitems"
    ALTER COLUMN "rarity"
    SET DEFAULT 'COMMON';

    ALTER TABLE "thiaitemrelation"
    ALTER COLUMN "object_type" TYPE varchar;
        """


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        """
