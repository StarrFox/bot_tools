from jishaku import cog
from jishaku.exception_handling import attempt_add_reaction, do_after_sleep, ReplResponseReactor

import asyncio
import collections
import contextlib
import datetime
import inspect
import itertools
import os
import os.path
import re
import sys
import time
import traceback
import typing
import platform
import subprocess

import discord
import humanize
from discord.ext import commands

from jishaku.codeblocks import Codeblock, CodeblockConverter
from jishaku.meta import __version__
from jishaku.models import copy_context_with
from jishaku.functools import AsyncSender
from jishaku.modules import ExtensionConverter, package_version
from jishaku.paginators import PaginatorInterface, WrappedFilePaginator, WrappedPaginator
from jishaku.repl import AsyncCodeExecutor, Scope, all_inspections, get_var_dict_from_ctx
from jishaku.shell import ShellReader
from jishaku.voice import BasicYouTubeDLSource, connected_check, playing_check, vc_check, youtube_dl

try:
    import psutil
except ImportError:
    psutil = None

def get_arg_dict(ctx):
    raw_var_dict = {
        'author': ctx.author,
        'bot': ctx.bot,
        'channel': ctx.channel,
        'ctx': ctx,
        'guild': ctx.guild,
        'message': ctx.message,
        'msg': ctx.message,
        'get': discord.utils.get,
        'send': ctx.send
    }
    return {f'{settings["scope_prefix"]}{k}': v for k, v in raw_var_dict.items()}

def get_traceback(verbosity: int, *exc_info):
    etype, value, trace = exc_info
    traceback_content = "".join(traceback.format_exception(etype, value, trace, verbosity)).replace("``", "`\u200b`")
    paginator = commands.Paginator(prefix='```py')
    for line in traceback_content.split('\n'):
        paginator.add_line(line)
    return paginator

async def traceback_sender(msg, bot, *exc_info):
    await attempt_add_reaction(msg, emojis["tracebacks"])
    paginator = get_traceback(8, *exc_info)
    try:
        await bot.wait_for(
            "reaction_add",
            check = lambda r, u: u == msg.author and str(r) == emojis["tracebacks"] and r.message.id == msg.id,
            timeout = 60
        )
        message = None
        for page in paginator.pages:
            await msg.channel.send(page)
        return message
    except:
        pass

async def send_traceback(destination: discord.abc.Messageable, verbosity: int, *exc_info):
    paginator = get_traceback(verbosity, *exc_info)
    message = None
    for page in paginator.pages:
        message = await destination.send(page)
    return message

class ReactorSub(ReplResponseReactor):

    def __init__(self, message:discord.Message, bot):
        self.message = message
        self.bot = bot
        self.loop = asyncio.get_event_loop()
        self.handle = None
        self.raised = False

    async def __aenter__(self):
        self.handle = self.loop.create_task(do_after_sleep(1, attempt_add_reaction, self.message, emojis["task"]))
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.handle:
            self.handle.cancel()
        if not exc_val:
            await attempt_add_reaction(self.message, emojis["done"])
            return
        self.raised = True
        if isinstance(exc_val, (asyncio.TimeoutError, subprocess.TimeoutExpired)):
            await attempt_add_reaction(self.message, emojis["timeout"])
            await send_traceback(self.message.channel, 0, exc_type, exc_val, exc_tb)
        elif isinstance(exc_val, SyntaxError):
            await attempt_add_reaction(self.message, emojis["syntax"])
            await send_traceback(self.message.channel, 0, exc_type, exc_val, exc_tb)
        else:
            await attempt_add_reaction(self.message, emojis["error"])
            if not settings["channel_tracebacks"]:
                await send_traceback(self.message.author, 8, exc_type, exc_val, exc_tb)
            else:
                self.loop.create_task(traceback_sender(self.message, self.bot, exc_type, exc_val, exc_tb))
        return True

class sub_jsk(cog.Jishaku, command_attrs=dict(hidden=True)):

    def __init__(self, bot):
        self.bot = bot
        self._scope = Scope()
        self.retain = settings["retain"]
        self.last_result = None
        self.start_time = datetime.datetime.now()
        self.tasks = collections.deque()
        self.task_count = 0

    def bot_level(self):
        """
        Brings all the commands to the bot level
        """
        just_jsk = self.bot.remove_command("jishaku")
        just_jsk.all_commands = {}
        for cmd in self.__cog_commands__:
            if isinstance(cmd, commands.core.Group) or cmd.name == "hide":
                continue
            cmd.parent = None
            cmd.cog = self
            self.bot.add_command(cmd)
        self.bot.add_command(just_jsk)

    @commands.group(name="jishaku", aliases=["jsk"], hidden=True, invoke_without_command=True, ignore_extra=False)
    async def jsk(self, ctx):
        """
        The Jishaku debug and diagnostic commands.
        This command on its own gives a status brief.
        All other functionality is within its subcommands.
        """
        summary = [
            f"Jishaku: v{__version__}, loaded {humanize.naturaltime(self.load_time)}",
            f"Python: {sys.version}".replace("\n", ""),
            f"HostOS: {platform.platform()}",
            f"Discord.py: v{package_version('discord.py')}",
            ""
        ]
        if psutil:
            proc = psutil.Process()
            with proc.oneshot():
                mem = proc.memory_full_info()
                summary.append(f"Memory: {humanize.naturalsize(mem.rss)} physical, "
                               f"{humanize.naturalsize(mem.vms)} virtual, "
                               f"{humanize.naturalsize(mem.uss)} unique to this process")
                name = proc.name()
                pid = proc.pid
                thread_count = proc.num_threads()
                summary.append(f"Process: name {name}, id {pid}, threads {thread_count}")
                summary.append("")  # blank line
        if isinstance(self.bot, discord.AutoShardedClient):
            mode = "autosharded"
        elif self.bot.shard_count:
            mode = "manually sharded"
        else:
            mode = "unsharded"
        summary.append(f"Bot stats: {mode}, {len(self.bot.commands)} command(s), {len(self.bot.cogs)} cog(s), "
                       f"{len(self.bot.guilds)} guild(s), {len(self.bot.users)} user(s)")
        summary.append(f"Ping: {round(self.bot.latency * 1000, 2)}ms")
        await ctx.send("\n".join(summary))

    @jsk.command(name="py", aliases=["python"])
    async def jsk_python(self, ctx: commands.Context, *, argument: CodeblockConverter):
        """
        Direct evaluation of Python code.
        """
        arg_dict = get_arg_dict(ctx)
        arg_dict["_"] = self.last_result
        scope = self.scope
        try:
            async with ReactorSub(ctx.message, self.bot):
                with self.submit(ctx):
                    executor = AsyncCodeExecutor(argument.content, scope, arg_dict=arg_dict)
                    async for send, result in AsyncSender(executor):
                        if result is None:
                            continue
                        self.last_result = result
                        if isinstance(result, discord.File):
                            send(await ctx.send(file=result))
                        elif isinstance(result, discord.Embed):
                            send(await ctx.send(embed=result))
                        elif isinstance(result, PaginatorInterface):
                            send(await result.send_to(ctx))
                        else:
                            if not isinstance(result, str):
                                result = repr(result)
                            # Char limit - codeblock
                            if len(result) > 1992:
                                paginator = WrappedPaginator(prefix='```py', suffix='```', max_size=1985)
                                paginator.add_line(result)
                                interface = PaginatorInterface(ctx.bot, paginator, owner=ctx.author)
                                send(await interface.send_to(ctx))
                            else:
                                if result.strip() == '':
                                    result = "\u200b"
                                send(await ctx.send(f"```py\n{result.replace(self.bot.http.token, '[token omitted]')}```"))
        finally:
            scope.clear_intersection(arg_dict)

    @jsk.command(name="py_inspect", aliases=["pyi", "python_inspect", "pythoninspect"])
    async def jsk_python_inspect(self, ctx: commands.Context, *, argument: CodeblockConverter):
        """
        Evaluation of Python code with inspect information.
        """
        arg_dict = get_arg_dict(ctx)
        arg_dict["_"] = self.last_result
        scope = self.scope
        try:
            async with ReactorSub(ctx.message, self.bot):
                with self.submit(ctx):
                    executor = AsyncCodeExecutor(argument.content, scope, arg_dict=arg_dict)
                    async for send, result in AsyncSender(executor):
                        self.last_result = result
                        header = repr(result).replace("``", "`\u200b`").replace(self.bot.http.token, "[token omitted]")
                        if len(header) > 485:
                            header = header[0:482] + "..."
                        paginator = WrappedPaginator(prefix=f"```prolog\n=== {header} ===\n", max_size=1985)
                        for name, res in all_inspections(result):
                            paginator.add_line(f"{name:16.16} :: {res}")
                        interface = PaginatorInterface(ctx.bot, paginator, owner=ctx.author)
                        send(await interface.send_to(ctx))
        finally:
            scope.clear_intersection(arg_dict)

    @jsk.command(name="debug", aliases=["dbg"])
    async def jsk_debug(self, ctx: commands.Context, *, command_string: str):
        """
        Run a command timing execution and catching exceptions.
        """
        alt_ctx = await copy_context_with(ctx, content=ctx.prefix + command_string)
        if alt_ctx.command is None:
            return await ctx.send(f'Command "{alt_ctx.invoked_with}" is not found')
        start = time.perf_counter()
        async with ReactorSub(ctx.message, self.bot):
            with self.submit(ctx):
                await alt_ctx.command.invoke(alt_ctx)
        end = time.perf_counter()
        return await ctx.send(f"Command `{alt_ctx.command.qualified_name}` finished in {end - start:.3f}s.")

emojis = {}
settings = {}
def setup(bot, **kwargs):
    emojis["task"] = kwargs.get("task") or "\N{BLACK RIGHT-POINTING TRIANGLE}"
    emojis["done"] = kwargs.get("done") or "\N{WHITE HEAVY CHECK MARK}"
    emojis["timeout"] = kwargs.get("timeout") or "\N{ALARM CLOCK}"
    emojis["error"] = kwargs.get("error") or "\N{DOUBLE EXCLAMATION MARK}"
    emojis["syntax"] = kwargs.get("syntax") or "\N{HEAVY EXCLAMATION MARK SYMBOL}"
    emojis["tracebacks"] = kwargs.get("tracebacks") or "\N{BLACK DOWN-POINTING DOUBLE TRIANGLE}"
    settings["retain"] = kwargs.get("retain") if not kwargs.get("retain") is None else True
    settings["scope_prefix"] = kwargs.get("scope_prefix") if not kwargs.get("scope_prefix") is None else "_"
    settings["channel_tracebacks"] = kwargs.get("channel_tracebacks") or False
    bot.add_cog(sub_jsk(bot))
    if kwargs.get("bot_level_cmds"):
        bot.get_cog("sub_jsk").bot_level()