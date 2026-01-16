"""
Copyright 2021-2026 AstreaTSS.
This file is part of PYTHIA.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "thiagachaitems"
    ALTER COLUMN "rarity" TYPE varchar;

    ALTER TABLE "thiagachaitems"
    ALTER COLUMN "rarity"
    SET DEFAULT 'COMMON';

    ALTER TABLE "thiaitemrelation"
    ALTER COLUMN "object_type" TYPE varchar;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        """


MODELS_STATE = (
    "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"
)
