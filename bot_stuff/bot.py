import asyncio
import importlib
import logging
import os
import sys

import aiohttp
import discord
from discord.ext import commands
from jishaku.paginators import PaginatorInterface

from bot_stuff import BreakPaginator

logging.basicConfig(
    format="[%(asctime)s] [%(levelname)s:%(name)s] %(message)s", level=logging.INFO
)

logger = logging.getLogger(__name__)


class subcontext(commands.Context):

    async def send(self, content=None, *, tts=False, embed=None, file=None, files=None, delete_after=None, nonce=None):
        """
        fall back just in case
        """
        if content and len(str(content)) > 2000:

            paginator = BreakPaginator(max_size=1985)
            paginator.add_line(content)

            interface = PaginatorInterface(self.bot, paginator, owner=self.author)

            return (await interface.send_to(self)).message

        else:

            return await super().send(
                content=content,
                tts=tts,
                embed=embed,
                file=file,
                files=files,
                delete_after=delete_after
            )

    @property
    def created_at(self):
        return self.message.created_at


class Bot(commands.AutoShardedBot):

    def __init__(self, prefix, *, extension_dir: str = None, context: commands.context = subcontext, **options):
        super().__init__(prefix, **options)
        self.context = context
        self.session = aiohttp.ClientSession()
        if extension_dir:
            self.load_extensions_from_dir(extension_dir)

    def get_message(self, message_id: int):
        """
        Gets a message from cache
        """
        return discord.utils.get(
            self.cached_messages,
            id=message_id
        )

    async def process_commands(self, message):
        if message.author.bot:
            return

        ctx = await self.get_context(message, cls=self.context)

        await self.invoke(ctx)

    async def on_message_edit(self, before, after):
        if before.content != after.content:
            await self.process_commands(after)

    def load_extensions_from_dir(self, directory: str):
        """
        Loads any python files in a directory as extensions
        """
        for ext in os.listdir(directory):
            try:
                if not ext.endswith(".py"):
                    continue
                self.load_extension(f"{directory}.{ext.replace('.py', '')}")
            except commands.ExtensionError:
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
            except commands.ExtensionFailed:
                pass
        for cog in tuple(self.cogs):
            self.remove_cog(cog)
        await asyncio.sleep(5)
        for func in self.logout_funcs.keys():
            await discord.utils.maybe_coroutine(
                func,
                *self.logout_funcs[func]["args"],
                **self.logout_funcs[func]["kwargs"]
            )
        await super().logout()
