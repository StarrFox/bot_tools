import os
import sys
import aiohttp
import asyncio
import discord
import logging
import importlib
import traceback

from discord.ext import commands

logging.basicConfig(
    format="[%(asctime)s] [%(levelname)s:%(name)s] %(message)s", level=logging.INFO
)

logger = logging.getLogger(__name__)

async def paginate(message, destination, lang=''):
    paginator = commands.Paginator(prefix=f'```{lang}')
    extra_factor = 1992 - len(lang)
    while message:
        try:
            paginator.add_line(message)
            message = ''
        except:
            paginator.add_line(message[:extra_factor])
            message = message[extra_factor:]
    for page in paginator.pages:
        await destination.send(page)

class subcontext(commands.Context):

    async def send(self, content=None, *, tts=False, embed=None, file=None, files=None, delete_after=None, nonce=None):
        """
        fall back just in case
        """
        if content and len(str(content)) > 2000:
            await self.message.add_reaction("\N{OPEN MAILBOX WITH RAISED FLAG}")
            return await paginate(content, self.author)
        return await super().send(content=content, tts=tts, embed=embed, file=file, files=files, delete_after=delete_after)

    @property
    def created_at(self):
        return self.message.created_at

class Bot(commands.AutoShardedBot):

    def __init__(self, prefix, owners: list, extension_dir: str = None, context = subcontext, **options):
        super().__init__(prefix, **options)
        self.context = context
        self.session = aiohttp.ClientSession(loop=self.loop)
        self.first_run = True # make on_ready only run once
        self.extension_dir = extension_dir
        self.owners = owners
        self.paginate = paginate
        self.ready_funcs = {}
        self.logout_funcs = {}

    def get_message(self, id):
        return discord.utils.get(
            self.cached_messages,
            id = id
        )

    def add_ready_func(self, func, *args, **kwargs):
        self.ready_funcs[func] = {"args": args, "kwargs": kwargs}

    def add_logout_func(self, func, *args, **kwargs):
        self.logout_funcs[func] = {"args": args, "kwargs": kwargs}

    async def process_commands(self, message):
        if message.author.bot:
            return

        ctx = await self.get_context(message, cls=self.context)

        await self.invoke(ctx)

    async def on_message_edit(self, before, after):
        if before.content != after.content:
            await self.process_commands(after)

    async def on_ready(self):
        if not self.first_run:
            return
        for func in self.ready_funcs.keys():
            await discord.utils.maybe_coroutine(
                func,
                *self.ready_funcs[func]["args"],
                **self.ready_funcs[func]["kwargs"]
            )
        if self.extension_dir:
            await self.load_mods()
        self.first_run = False

    async def load_mods(self):
        for ext in os.listdir(self.extension_dir):
            try:
                if not ext.endswith(".py"):
                    continue
                self.load_extension(f"{self.extension_dir}.{ext.replace('.py', '')}")
            except:
                logger.critical(f"Loading {ext} failed.", excinfo=True)

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
        logger.info(f"Loaded {name}.")

    async def logout(self):
        for extension in tuple(self.extensions):
            try:
                self.unload_extension(extension)
            except Exception:
                pass
        for cog in tuple(self.cogs):
            try:
                self.remove_cog(cog)
            except Exception:
                pass
        await asyncio.sleep(5)
        for func in self.logout_funcs.keys():
            await discord.utils.maybe_coroutine(
                func,
                *self.logout_funcs[func]["args"],
                **self.logout_funcs[func]["kwargs"]
            )
        await super().logout()
