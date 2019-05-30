import discord
from discord.ext import commands

import aiohttp
import logging
import os
import traceback

logging.basicConfig(
    format="[%(asctime)s] [%(levelname)s:%(name)s] %(message)s", level=logging.INFO
)

async def paginate(log, destination):
    paginator = commands.Paginator()
    while log:
        try:
            paginator.add_line(log)
            log = ''
        except:
            paginator.add_line(log[:1992])
            log = log[1992:]
        for page in paginator.pages:
            await destination.send(page)

class subcontext(commands.Context):

    async def send(self, content=None, *, tts=False, embed=None, file=None, files=None, delete_after=None, nonce=None):
        """
        Messages with content over 2000 get paginated and DMed
        """
        if content and len(str(content)) > 2000:
            await self.message.add_reaction("\N{OPEN MAILBOX WITH RAISED FLAG}")
            return await paginate(content, self.author)
        return await super().send(content=content, tts=tts, embed=embed, file=file, files=files, delete_after=delete_after)

    @property
    def created_at(self):
        return self.message.created_at

class Bot(commands.Bot):
    """
    Default bot
    """

    def __init__(self, prefix: str, owners: list, extension_dir: str = None, **options):
        super().__init__(prefix, **options)
        self.logger = logging.getLogger(__name__)
        self.session = aiohttp.ClientSession(loop=self.loop)
        self.first_run = True # make on_ready only run once
        self.extension_dir = extension_dir
        self.owners = owners

    async def get_context(self, message, cls = None):
        return await super().get_context(message, cls = cls or subcontext)

    async def on_ready(self):
        if not self.first_run:
            return
        if self.extension_dir:
            await self.load_extensions()
        self.first_run = False

    async def load_extensions(self):
        for ext in os.listdir('cogs'):
            try:
                if not ext.endswith(".py"):
                    continue
                self.load_extension(f"cogs.{ext.replace('.py', '')}")
                self.logger.info(f"Loaded {ext}")
            except:
                self.logger.critical(f"{ext} failed:\n{traceback.format_exc()}")
