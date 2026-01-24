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
        ALTER TABLE "thiaguildconfig" ADD "enabled_beta" BOOL NOT NULL DEFAULT False;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "thiaguildconfig" DROP COLUMN "enabled_beta";"""


MODELS_STATE = (
    "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"
)
