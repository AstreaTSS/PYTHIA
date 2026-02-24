"""
Copyright 2021-2026 AstreaTSS.
This file is part of PYTHIA.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

from tortoise.migrations.operations import RunSQL
from tortoise.migrations.migration import Migration


class Migration(Migration):
    dependencies = [("models", "0003_rarities")]

    operations = [
        RunSQL(
            sql="""ALTER TABLE "thiaguildconfig" ADD "enabled_beta" BOOL NOT NULL DEFAULT False;""",
            reverse_sql="""ALTER TABLE "thiaguildconfig" DROP COLUMN "enabled_beta";""",
        )
    ]
