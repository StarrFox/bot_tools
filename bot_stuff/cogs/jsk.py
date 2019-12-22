import asyncio
import collections
import subprocess
import traceback

import discord
from discord.ext import commands
from jishaku import cog_base
from jishaku.codeblocks import Codeblock, codeblock_converter
from jishaku.cog import jsk
from jishaku.exception_handling import attempt_add_reaction, do_after_sleep, ReplResponseReactor, send_traceback
from jishaku.metacog import GroupCogMeta


# Todo: switch to just sending it? replace token like in jsk_py
async def traceback_sender(msg, bot, emoji: str, *exc_info):
    await attempt_add_reaction(msg, emoji)

    etype, value, trace = exc_info

    traceback_content = "".join(traceback.format_exception(etype, value, trace, 8)).replace("``", "`\u200b`")

    paginator = commands.Paginator(prefix='```py')
    for line in traceback_content.split('\n'):
        paginator.add_line(line)

    try:
        await bot.wait_for(
            "reaction_add",
            check=lambda r, u: u == msg.author and str(r) == emoji and r.message.id == msg.id,
            timeout=60
        )
        message = None
        for page in paginator.pages:
            message = await msg.channel.send(page)
        return message
    except (asyncio.TimeoutError, discord.HTTPException):
        pass


# Moddled after https://github.com/Gorialis/jishaku/blob/master/jishaku/paginators.py#L27
EmojiSettings = collections.namedtuple('EmojiSettings', 'task done timeout syntax error traceback')

# Todo: consider if we should remove the emoji stuff
EMOJI_DEFAULT = EmojiSettings(
    task="\N{BLACK RIGHT-POINTING TRIANGLE}",
    done="\N{WHITE HEAVY CHECK MARK}",
    timeout="\N{ALARM CLOCK}",
    syntax="\N{HEAVY EXCLAMATION MARK SYMBOL}",
    error="\N{DOUBLE EXCLAMATION MARK}",
    traceback="\N{BLACK DOWN-POINTING DOUBLE TRIANGLE}"
)


class ReactorSub(ReplResponseReactor):
    emojis = EMOJI_DEFAULT
    channel_tracebacks = True
    bot = None

    async def __aenter__(self):
        self.handle = self.loop.create_task(do_after_sleep(1, attempt_add_reaction, self.message, self.emojis.task))
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.handle:
            self.handle.cancel()

        if not exc_val:
            await attempt_add_reaction(self.message, self.emojis.done)
            return

        self.raised = True
        if isinstance(exc_val, (asyncio.TimeoutError, subprocess.TimeoutExpired)):
            await attempt_add_reaction(self.message, self.emojis.timeout)
            await send_traceback(self.message.channel, 0, exc_type, exc_val, exc_tb)

        elif isinstance(exc_val, SyntaxError):
            await attempt_add_reaction(self.message, self.emojis.syntax)
            await send_traceback(self.message.channel, 0, exc_type, exc_val, exc_tb)

        else:
            await attempt_add_reaction(self.message, self.emojis.error)

            if self.bot and self.channel_tracebacks:
                asyncio.create_task(traceback_sender(self.message,
                                                     self.bot,
                                                     self.emojis.traceback,
                                                     exc_type, exc_val, exc_tb
                                                     ))

            else:
                await send_traceback(self.message.author, 8, exc_type, exc_val, exc_tb)

        return True


class subJishaku(cog_base.JishakuBase, metaclass=GroupCogMeta, command_parent=jsk):

    def __init__(self, bot, retain: bool = False):
        super().__init__(bot)
        self.retain = retain

    # Direct copy of jsk_git with git changed to pip
    @commands.command(name="pip")
    async def jsk_pip(self, ctx: commands.Context, *, argument: codeblock_converter):
        """
        Shortcut for 'jsk sh pip'. Invokes the system shell.
        """
        return await ctx.invoke(self.jsk_shell, argument=Codeblock(argument.language, "pip " + argument.content))


def setup(bot, *, emojis: EmojiSettings = EMOJI_DEFAULT, channel_tracebacks=True, scope_prefix='_', retain=True):
    ReactorSub.bot = bot
    # noinspection PyProtectedMember
    ReactorSub.emojis = emojis
    ReactorSub.channel_tracebacks = channel_tracebacks

    cog_base.ReplResponseReactor = ReactorSub
    cog_base.SCOPE_PREFIX = scope_prefix

    bot.add_cog(subJishaku(bot, retain))
