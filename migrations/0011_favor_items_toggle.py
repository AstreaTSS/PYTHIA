"""
Copyright 2021-2026 AstreaTSS.
This file is part of PYTHIA.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

from tortoise import migrations
from tortoise.migrations.operations import RunSQL


class Migration(migrations.Migration):
    dependencies = [("models", "0010_message_threads")]

    initial = False

    operations = [
        RunSQL(
            sql="""ALTER TABLE "thiagachaconfig" ADD "slightly_favor_new_items" BOOL NOT NULL DEFAULT True;""",
            reverse_sql="""ALTER TABLE "thiagachaconfig" DROP COLUMN "slightly_favor_new_items";""",
        )
    ]
