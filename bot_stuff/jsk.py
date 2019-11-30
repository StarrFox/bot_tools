import asyncio
import discord
import traceback
import subprocess

from discord.ext import commands
from jishaku.cog import jsk
from jishaku import cog_base
from jishaku.metacog import GroupCogMeta
from jishaku.exception_handling import attempt_add_reaction, do_after_sleep, ReplResponseReactor

try:
    import psutil
except ImportError:
    psutil = None

class get_arg_dict:

    def __init__(self, prefix: str = ''):
        self.prefix = prefix

    def __call__(self, ctx: commands.Context, _):
        arg_dict = {
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
        return {f'{self.prefix}{k}': v for k, v in arg_dict.items()}

def get_traceback(verbosity: int, *exc_info):
    etype, value, trace = exc_info
    traceback_content = "".join(traceback.format_exception(etype, value, trace, verbosity)).replace("``", "`\u200b`")
    paginator = commands.Paginator(prefix='```py')
    for line in traceback_content.split('\n'):
        paginator.add_line(line)
    return paginator

async def traceback_sender(msg, bot, emoji: str, *exc_info):
    await attempt_add_reaction(msg, emoji)
    paginator = get_traceback(8, *exc_info)
    try:
        await bot.wait_for(
            "reaction_add",
            check = lambda r, u: u == msg.author and str(r) == emoji and r.message.id == msg.id,
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

    def __init__(self, message: discord.Message):
        self.loop = asyncio.get_event_loop()
        self.handle = None
        self.raised = False
        self.message = message

    async def __aenter__(self):
        self.handle = self.loop.create_task(do_after_sleep(1, attempt_add_reaction, self.message, self.emojis["task"]))
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.handle:
            self.handle.cancel()
        if not exc_val:
            await attempt_add_reaction(self.message, self.emojis["done"])
            return
        self.raised = True
        if isinstance(exc_val, (asyncio.TimeoutError, subprocess.TimeoutExpired)):
            await attempt_add_reaction(self.message, self.emojis["timeout"])
            await send_traceback(self.message.channel, 0, exc_type, exc_val, exc_tb)
        elif isinstance(exc_val, SyntaxError):
            await attempt_add_reaction(self.message, self.emojis["syntax"])
            await send_traceback(self.message.channel, 0, exc_type, exc_val, exc_tb)
        else:
            await attempt_add_reaction(self.message, self.emojis["error"])
            if not self.channel_tracebacks:
                await send_traceback(self.message.author, 8, exc_type, exc_val, exc_tb)
            else:
                self.loop.create_task(traceback_sender(self.message, self.bot, self.emojis['tracebacks'], exc_type, exc_val, exc_tb))
        return True

class subJishaku(cog_base.JishakuBase, metaclass=GroupCogMeta, command_parent=jsk, command_attrs=dict(hidden=True)):

    def __init__(self, bot, retain: bool):
        super().__init__(bot)
        self.retain = retain

def setup(bot, **kwargs):
    emojis = {}
    emojis["task"] = kwargs.pop("task", "\N{BLACK RIGHT-POINTING TRIANGLE}")
    emojis["done"] = kwargs.pop("done", "\N{WHITE HEAVY CHECK MARK}")
    emojis["timeout"] = kwargs.pop("timeout", "\N{ALARM CLOCK}")
    emojis["error"] = kwargs.pop("error", "\N{DOUBLE EXCLAMATION MARK}")
    emojis["syntax"] = kwargs.pop("syntax", "\N{HEAVY EXCLAMATION MARK SYMBOL}")
    emojis["tracebacks"] = kwargs.pop("tracebacks", "\N{BLACK DOWN-POINTING DOUBLE TRIANGLE}")

    ReactorSub.bot = bot
    ReactorSub.emojis = emojis
    ReactorSub.channel_tracebacks = kwargs.get('channel_tracebacks', True)

    cog_base.ReplResponseReactor = ReactorSub
    cog_base.get_var_dict_from_ctx = get_arg_dict(kwargs.get('scope_prefix', '_'))

    bot.add_cog(subJishaku(bot, kwargs.get('retain', True)))
