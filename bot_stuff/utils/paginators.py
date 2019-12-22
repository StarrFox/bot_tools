import discord

from discord.ext import commands

from jishaku.paginators import PaginatorInterface

# TODO: rewrite old code to use this
class PrologPaginator(commands.Paginator):

    def __init__(self,
                 prefix: str = '```prolog',
                 suffix: str = '```',
                 max_size: int = 500,
                 right_align: bool = True):
        """
        :param right_align: If key strings should be right aligned
        """
        super().__init__(prefix, suffix, max_size)
        self.right_align = right_align

    @staticmethod
    def caps_each_word(entry: str):
        return ' '.join(
            [word.capitalize() for word in str(entry).split()]
        )

    def recursively_add_dictonary(self, dictonary: dict):
        for key, value in dictonary.items():
            if isinstance(value, dict):
                self.add_header(key)
                self.recursively_add_dictonary(value)
            else:
                self.add_key_value_pair(key, value)

    def add_header(self, header: str):
        """
        :param header: The new header to add
        """
        self.add_line(f"\n===== {self.caps_each_word(header)} =====\n")

    # TODO: consider if the 16 should be able to be changed
    def add_key_value_pair(self, key: str, value: str):
        """
        :param key: The key to add
        :param value: The value to add
        """
        if self.right_align:
            self.add_line(f"{self.caps_each_word(key):>16.16} :: {value}")
        else:
            self.add_line(f"{self.caps_each_word(key):16.16} :: {value}")

class BreakPaginator(commands.Paginator):
    """
    Breaks lines up to fit in the paginator
    """

    def add_line(self, line='', *, empty=False):
        max_page_size = self.max_size - self._prefix_len - self._suffix_len - 2

        while len(line) > max_page_size:
            super().add_line(line[:max_page_size], empty=empty)
            line = line[max_page_size:]

        super().add_line(line, empty=empty)


class EmbedDictPaginator(commands.Paginator):

    def __init__(self, title: str = None, max_fields: int = 25):

        if not (0 <= max_fields <= 25):
            raise ValueError("max_fields must be between 0 and 25.")

        self.title = title or discord.Embed.Empty
        self.max_fields = max_fields
        self.clear()

    @property
    def default_embed(self):
        return discord.Embed(title=self.title)

    @property
    def _prefix_len(self):
        return len(self.title)

    # noinspection PyAttributeOutsideInit
    def clear(self):
        """Clears the paginator to have no pages."""
        self._current_page = self.default_embed
        self._count = 0
        self._pages = []

    def add_line(self, line='', *, empty=False):
        raise NotImplementedError(self.add_line)

    def add_fields(self, data: dict):
        for name, value in data.items():
            self.add_field(name, value)

    def add_field(self, name: str, value: str):
        max_page_size = 6_000

        if len(name) > 256:
            raise RuntimeError('Name exceeds maximum field name size 256')
        elif len(value) > 1_024:
            raise RuntimeError('Value exceeds maximum field value size 1,024')

        if len(self._current_page) + len(name + value) > max_page_size:
            self.close_page()
        elif self._count >= self.max_fields:
            self.close_page()
        else:
            self._current_page.add_field(name=name, value=value, inline=False)
            self._count += 1

    # noinspection PyAttributeOutsideInit
    def close_page(self):
        """Prematurely terminate a page."""
        self._pages.append(self._current_page)
        self._current_page = self.default_embed
        self._count = 0

    def __len__(self):
        total = sum(len(p) for p in self._pages)
        return total

    @property
    def pages(self):
        """Returns the rendered list of pages."""
        # we have more than just the prefix in our current page
        if self._count > 0:
            self.close_page()
        return self._pages

    def __repr__(self):
        return f'<Paginator pages: {len(self._pages)} length: {len(self)} count: {self._count}>'


class EmbedDictInterface(PaginatorInterface):
    max_page_size = 25

    # noinspection PyProtectedMember
    @property
    def pages(self):
        """
        Returns the paginator's pages without prematurely closing the active page.
        """
        # protected access has to be permitted here to not close the paginator's pages

        # pylint: disable=protected-access
        paginator_pages = list(self.paginator._pages)
        if self.paginator._count > 0:
            paginator_pages.append(self.paginator._current_page)
        # pylint: enable=protected-access

        return paginator_pages

    @property
    def send_kwargs(self):
        display_page = self.display_page
        page_num = f'Page {display_page + 1}/{self.page_count}'
        embed = self.pages[display_page].set_footer(text=page_num)
        return {'embed': embed}

    @property
    def page_size(self):
        return self.paginator.max_fields
