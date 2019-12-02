from discord import Member
from discord.ext.commands import Bot
from jishaku.paginators import PaginatorInterface, WrappedPaginator

def caps_each_word(entry: str):
    return ' '.join(
        [word.capitalize() for word in str(entry).split()]
    )

def get_prolog_pager(bot: Bot, data: dict, owner: Member):

    paginator = WrappedPaginator(prefix=f"```prolog\n", max_size=500)

    def recursively_translate_to_headers(data: dict, paginator: WrappedPaginator):
        for key, value in data.items():
            if isinstance(value, dict):
                paginator.add_line(f"\n===== {caps_each_word(key)} =====\n")
                recursively_translate_to_headers(value, paginator)
            else:
                paginator.add_line(f"{caps_each_word(key):16.16} :: {value}")

    recursively_translate_to_headers(data, paginator)

    return PaginatorInterface(bot, paginator, owner=owner)