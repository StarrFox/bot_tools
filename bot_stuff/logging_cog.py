import sys
import asyncio
import aiohttp
import discord
import traceback

from discord.ext import commands

import logging

from .Logging_handler import DiscordHandler

class logger(commands.Cog):
    """
    error handler and bot logging
    needs bot_tools bot and channel to be passed in load_extention
    """

    def __init__(self, bot: commands.Bot, webhook_url: str):
        self.bot = bot
        self.logs = logging.getLogger(__name__)
        self.logs.propagate = False
        self.logs.addHandler(
            DiscordHandler(
                webhook_url,
                logging.INFO
            )
        )

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        self.logs.info(f"Joined {guild.name} owned by {guild.owner}({guild.owner.id}) with {guild.member_count} members.")

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        self.logs.info(f"Left {guild.name}({guild.id}) owned by {guild.owner}({guild.owner.id}) with {guild.member_count} members.")

    @commands.Cog.listener("on_message")
    async def pm_logger(self, message):
        if message.guild is None and not message.author == self.bot.user:
            self.logs.info(f"Got PM from {message.author.name}({message.author.id}) with content \"{message.content}\" and id {message.id}")

    @commands.Cog.listener()
    async def on_command_completion(self, ctx):
        self.logs.info(
            f"Ran command {ctx.command.name} in {ctx.guild.name}({ctx.guild.id}) by {ctx.author}({ctx.author.id}) with message id {ctx.message.id}"
        )

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        error = getattr(error, 'original', error)

        if isinstance(error, commands.CommandNotFound):
            return

        elif isinstance(error, commands.CommandOnCooldown):
            return await ctx.send(str(error))

        elif isinstance(error, commands.UserInputError):
            return await ctx.send_help(ctx.command)

        elif isinstance(error, commands.MissingPermissions):
            return await ctx.send(
                f"You're missing the {', '.join(error.missing_perms)} permission(s) needed to run this command"
            )

        elif isinstance(error, commands.BotMissingPermissions):
            return await ctx.send(
                f"I'm missing the {', '.join(error.missing_perms)} permission(s) needed to run this command"
            )

        elif isinstance(error, commands.CheckFailure):
            return await ctx.send("You don't have access to this command")

        self.logs.error(
            f"Errored executing command {ctx.command.name}",
            exc_info=(type(error), error, error.__traceback__)
        )

def setup(bot, **kwargs):
    webhook_url = kwargs.get('webhook_url', None)
    if webhook_url is None:
        raise commands.ExtensionError("Logger requires webhook_url to be passed.", name='bot_stuff.logger')
    bot.add_cog(logger(bot, webhook_url))
