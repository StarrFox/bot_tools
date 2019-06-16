import discord
from discord.ext import commands

import aiohttp
import logging
import os
import traceback
import importlib
import sys

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

    def __init__(self, prefix, owners: list, extension_dir: str = None, **options):
        super().__init__(prefix, **options)
        self.logger = logging.getLogger(__name__)
        self.session = aiohttp.ClientSession(loop=self.loop)
        self.first_run = True # make on_ready only run once
        self.extension_dir = extension_dir
        self.owners = owners
        self.paginate = paginate
        self.ready_funcs = []

    def get_message(self, id):
        return discord.utils.get(
            self.cached_messages,
            id = id
        )

    def add_ready_func(self, func):
        self.ready_funcs.append(func)

    async def get_context(self, message, cls = None):
        return await super().get_context(message, cls = cls or subcontext)

    async def on_message_edit(self, before, after):
        if not after.embeds and not after.pinned:
            await self.process_commands(after)

    async def on_ready(self):
        if not self.first_run:
            return
        for func in self.ready_funcs:
            await func
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

    def _load_from_module_spec(self, lib, key, **kwargs):
        try:
            setup = getattr(lib, 'setup')
        except AttributeError:
            del sys.modules[key]
            raise commands.errors.NoEntryPointError(key)

        try:
            if kwargs:
                setup(self, **kwargs)
            else:
                setup(self)
        except Exception as e:
            self._remove_module_references(lib.__name__)
            self._call_module_finalizers(lib, key)
            raise commands.errors.ExtensionFailed(key, e) from e
        else:
            self._BotBase__extensions[key] = lib

    def load_extension(self, name, **kwargs):
        if name in self._BotBase__extensions:
            raise commands.errors.ExtensionAlreadyLoaded(name)

        try:
            lib = importlib.import_module(name)
        except ImportError as e:
            raise commands.errors.ExtensionNotFound(name, e) from e
        else:
            self._load_from_module_spec(lib, name, **kwargs)