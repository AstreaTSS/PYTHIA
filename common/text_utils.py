"""
Copyright 2021-2025 AstreaTSS.
This file is part of PYTHIA.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

import re

import interactions as ipy

SINGLE_QUOTE_REGEX = re.compile(r"‘|’")  # noqa: RUF001
DOUBLE_QUOTE_REGEX = re.compile(r"“|”|„|‟|⹂|〝|〞|＂")  # noqa: RUF001
HTTP_URL_REGEX = re.compile(
    r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
)


def replace_smart_punc(text: str) -> str:
    text = SINGLE_QUOTE_REGEX.sub("'", text)
    return DOUBLE_QUOTE_REGEX.sub('"', text)


class ReplaceSmartPuncConverter(ipy.Converter):
    async def convert(self, _: ipy.BaseContext, argument: str) -> str:
        return replace_smart_punc(argument)


def name_shorten(name: str, shorten_amount: int = 16) -> str:
    return f"{name[:shorten_amount].strip()}..." if len(name) > shorten_amount else name


"""
The MIT License (MIT)

Copyright (c) 2015-present Rapptz

Permission is hereby granted, free of charge, to any person obtaining a
copy of this software and associated documentation files (the "Software"),
to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense,
and/or sell copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
DEALINGS IN THE SOFTWARE.
"""

_MARKDOWN_ESCAPE_COMMON = r"^>(?:>>)?\s|\[.+\]\(.+\)|^#{1,3}|^\s*-"

_URL_REGEX = r"(?P<url><[^: >]+:\/[^ >]+>|(?:https?|steam):\/\/[^\s<]+[^<.,:;\"\'\]\s])"

_MARKDOWN_STOCK_REGEX = rf"(?P<markdown>[_\\~|\*`]|{_MARKDOWN_ESCAPE_COMMON})"


def escape_markdown(text: str, *, ignore_links: bool = True) -> str:
    r"""A helper function that escapes Discord's markdown.

    Parameters
    -----------
    text: :class:`str`
        The text to escape markdown from.
    ignore_links: :class:`bool`
        Whether to leave links alone when escaping markdown. For example,
        if a URL in the text contains characters such as ``_`` then it will
        be left alone. This option is not supported with ``as_needed``.
        Defaults to ``True``.

    Returns
    --------
    :class:`str`
        The text with the markdown special characters escaped with a slash.
    """

    def replacement(match: re.Match[str]) -> str:
        groupdict = match.groupdict()
        is_url = groupdict.get("url")
        if is_url:
            return is_url
        return "\\" + groupdict["markdown"]

    regex = _MARKDOWN_STOCK_REGEX
    if ignore_links:
        regex = f"(?:{_URL_REGEX}|{regex})"
    return re.sub(regex, replacement, text, count=0, flags=re.MULTILINE)
