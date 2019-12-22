import logging

import aiohttp

from .utils.paginators import BreakPaginator

import asyncio

class EmojiFormatter(logging.Formatter):
    DEFAULTEMOJI = {
        'notset': '',
        'debug': '\N{BLACK QUESTION MARK ORNAMENT}',
        'info': '\N{INFORMATION SOURCE}\N{VARIATION SELECTOR-16}',
        'warn': '\N{WARNING SIGN}\N{VARIATION SELECTOR-16}',
        'warning': '\N{WARNING SIGN}\N{VARIATION SELECTOR-16}',
        'error': '\N{DOUBLE EXCLAMATION MARK}\N{VARIATION SELECTOR-16}',
        'fatal': '\N{RADIOACTIVE SIGN}\N{VARIATION SELECTOR-16}',
        'critical': '\N{RADIOACTIVE SIGN}\N{VARIATION SELECTOR-16}'
    }

    # TODO: add exception info adding (See super class record.exc_info)
    def format(self, record):
        s = super().format(record)
        levelname = record.levelname
        return self.DEFAULTEMOJI[levelname.lower()] + ' ' + s


class DiscordHandler(logging.Handler):

    def __init__(self,
                 webhook_url: str,
                 level: int = logging.NOTSET,
                 session: aiohttp.ClientSession = None,
                 formatter: logging.Formatter = None,
                 **webhook_json
                 ):
        super().__init__(level=level)
        self.webhook_url = webhook_url
        self.session = session or aiohttp.ClientSession()
        self.formatter = formatter or EmojiFormatter(fmt="`[%(asctime)s] [%(levelname)s:%(name)s] %(message)s`")
        self.webhook_json = webhook_json

    async def send_task(self, message: str, name: str):

        paginator = BreakPaginator(prefix=None, suffix=None)
        paginator.add_line(message)

        for page in paginator.pages:

            data = {'content': page}

            if self.webhook_json:
                data.update(self.webhook_json)

            if 'username' not in data:
                data['username'] = name

            await self.session.post(
                self.webhook_url,
                json=data
            )

    def emit(self, record):
        message = self.format(record)
        asyncio.create_task(
            self.send_task(message, record.name)
        )
