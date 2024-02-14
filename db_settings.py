"""
Copyright 2021-2024 AstreaTSS.
This file is part of Ultimate Investigator.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

import os

from load_env import load_env

load_env()

__all__ = ("TORTOISE_ORM",)

TORTOISE_ORM = {
    "connections": {"default": os.environ["DB_URL"]},
    "apps": {
        "models": {
            "models": ["common.models", "aerich.models"],
        }
    },
}
