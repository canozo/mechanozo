from discord.ext import commands
from .utils.chess import Chess
from typing import Dict
import discord
import json
import math
import asyncio
import random


class Game:
    """Commands for chess games."""

    def __init__(self, bot):
        self.bot = bot
        self.last_game_id = 0
        self.games = {}  # type: Dict[int, Chess]
        self.ranks = {}  # type: Dict[int, Dict[int, float]]
        self.requests = {}  # type: Dict[int, Dict[int, int]]

        try:
            with open('ranks.json', 'r') as ranks_file:
                raw_dict = json.loads(ranks_file.read())
                self.ranks = {
                    int(g): {
                        int(i): e for i, e in raw_dict[g].items()
                    }
                    for g, r in raw_dict.items()
                }

        except FileNotFoundError:
            pass

    async def verify_game(self, ctx, game_id, user_id, guild_id):
        if game_id not in self.games:
            await ctx.send(f'No games with id {game_id} found. '
                           f'Say `{self.bot.command_prefix}remember` '
                           f'to see your games!')
            return False

        elif self.games[game_id].guild_id != guild_id:
            await ctx.send('This game does not correspond to this guild. '
                           'Please go back to the guild where '
                           'this game started!')
            return False

        elif user_id not in (self.games[game_id].white,
                             self.games[game_id].black):
            await ctx.send('You don\'t belong to that game. '
                           f'Say `{self.bot.command_prefix}remember` '
                           f'to see your games!')
            return False

        else:
            return True

    def new_game(self, white, black, guild_id, guild_name):
        self.last_game_id += 1

        if guild_id not in self.ranks:
            self.ranks[guild_id] = {}

        guild_ranks = self.ranks[guild_id]

        if white not in guild_ranks:
            guild_ranks[white] = 1000.0
        if black not in guild_ranks:
            guild_ranks[black] = 1000.0

        white_name = str(self.bot.usernames[white])
        black_name = str(self.bot.usernames[black])

        self.games[self.last_game_id] = \
            Chess(white, black, self.last_game_id,
                  guild_id, guild_name,
                  white_name, black_name,
                  int(guild_ranks[white]), int(guild_ranks[black]))

        print(f'New match starting on guild {guild_id}:')
        print(f'id {self.last_game_id}, '
              f'{self.bot.usernames[white]}(id {white})(white) '
              f'vs {self.bot.usernames[black]}(id {black})(black)')
        print('__________________')

    def update_ranks(self, guild_id, stalemate, winner, loser):
        guild_ranks = self.ranks[guild_id]
        ows = guild_ranks[winner]
        ols = guild_ranks[loser]

        tr_winner = math.pow(10, guild_ranks[winner] / 400)
        tr_loser = math.pow(10, guild_ranks[loser] / 400)

        prop_w = tr_winner / (tr_winner + tr_loser)
        prop_l = tr_loser / (tr_winner + tr_loser)

        if not stalemate:
            guild_ranks[winner] = guild_ranks[winner] + 32 * (1 - prop_w)
            guild_ranks[loser] = guild_ranks[loser] - 32 * prop_l
        else:
            guild_ranks[winner] = guild_ranks[winner] + 32 * (0.5 - prop_w)
            guild_ranks[loser] = guild_ranks[loser] + 32 * (0.5 - prop_l)

        print(f'{self.bot.usernames[winner]} '
              f'score change: {ows} -> {guild_ranks[winner]}')
        print(f'{self.bot.usernames[loser]} '
              f'score change: {ols} -> {guild_ranks[loser]}')
        print('__________________')

        with open('ranks.json', 'w') as file:
            json.dump(self.ranks, file)
            print('Ranks saved to \'ranks.json\'!')
            print('__________________')

    @staticmethod
    async def timeout(ctx, guild_reqs, clr, cld):
        guild_reqs[clr] = cld
        await asyncio.sleep(60)

        if clr in guild_reqs and guild_reqs[clr] == cld:
            guild_reqs.pop(clr)
            await ctx.send(f'Challenge by <@{clr}> timed out!')

    @commands.command()
    async def challenge(self, ctx, user: discord.Member = None):
        """Request an user to play a game, must specify the user."""
        if user is None:
            await ctx.send('You have to specify who you\'re challenging! '
                           f'(ex: `{self.bot.command_prefix}challenge '
                           f'@{ctx.author}`)')
        else:
            author_id = ctx.author.id
            guild_id = ctx.guild.id

            if guild_id not in self.requests:
                self.requests[guild_id] = {}

            guild_reqs = self.requests[guild_id]

            if author_id in guild_reqs and guild_reqs[author_id] == user.id:
                await ctx.send('You\'re already challenging this user!')

            elif author_id == user.id:
                await ctx.send('You can\'t challenge yourself!')

            elif user.id == self.bot.user.id:
                await ctx.send('I don\'t know how to play chess (yet)!')

            else:
                await ctx.send(f'Challenging {user.name}! Say '
                               f'`{self.bot.command_prefix}accept` to accept.')
                await self.timeout(ctx, guild_reqs, author_id, user.id)

    @commands.command()
    async def accept(self, ctx):
        """Accept all the game requests you have."""
        user_id = ctx.author.id
        guild_id = ctx.guild.id

        if guild_id not in self.requests:
            self.requests[guild_id] = {}

        guild_reqs = self.requests[guild_id]

        if user_id not in guild_reqs.values():
            await ctx.send('You don\'t have any requests!')
        else:
            for clr, cld in guild_reqs.copy().items():
                if user_id == cld:
                    # start game
                    if clr not in self.bot.usernames:
                        self.bot.usernames[clr] = \
                            await self.bot.get_user_info(clr)
                    if cld not in self.bot.usernames:
                        self.bot.usernames[cld] = ctx.author

                    players = [clr, cld]
                    random.shuffle(players)
                    white, black = players

                    self.new_game(white, black, guild_id, ctx.guild.name)
                    guild_reqs.pop(clr)

                    msg = f'New match started: id `{self.last_game_id}`, ' \
                          f'<@{white}> (white) vs <@{black}> (black). ' \
                          f'Say `{self.bot.command_prefix}help move` ' \
                          f'to learn how to move!'

                    board_normal, _ = \
                        self.games[self.last_game_id].get_images()
                    await ctx.send(
                        msg, file=discord.File(board_normal, 'board.png'))

    @commands.command()
    async def remember(self, ctx):
        """Show all the games you're part of."""
        user_id = ctx.author.id
        embed = discord.Embed(
            title=f'{ctx.author.name}\'s games',
            type='rich',
            colour=discord.Colour.magenta())
        embed.description = f'You are playing {len(self.games)} games!'

        for _, game in self.games.items():
            if user_id in (game.white, game.black):
                value = f'`{self.bot.usernames[game.white]}(w) ' \
                        f'vs {self.bot.usernames[game.black]}(b)`'
                embed.add_field(
                    name=f'game id: {game.game_id}',
                    value=value,
                    inline=False)

        await ctx.send(embed=embed)

    @commands.command(name='ranks')
    async def rankings(self, ctx):
        """Shows the ranks in your guild. Play a match to get a rank!"""
        guild_id = ctx.guild.id

        if guild_id not in self.ranks:
            self.ranks[guild_id] = {}

        guild_ranks = self.ranks[guild_id]

        for user_id in guild_ranks:
            if user_id not in self.bot.usernames:
                self.bot.usernames[user_id] = \
                    await self.bot.get_user_info(user_id)

        rank = 1
        embed = discord.Embed(
            title=f'{ctx.guild.name}\'s rankings',
            type='rich',
            colour=discord.Colour.magenta())

        for user_id in sorted(guild_ranks, key=guild_ranks.get, reverse=True):
            name = f'{rank}. {self.bot.usernames[user_id]}'
            embed.add_field(
                name=name,
                value=f'`{int(guild_ranks[user_id])}`',
                inline=False)
            rank += 1

        await ctx.send(embed=embed)

    @commands.command()
    async def board(self, ctx, game_id: int):
        """Show the game board, must specify the game id."""
        user_id = ctx.author.id
        guild_id = ctx.guild.id

        if await self.verify_game(ctx, game_id, user_id, guild_id):
            match = self.games[game_id]
            board_normal, board_flipped = match.get_images()

            if match.white_turn:
                msg = 'White turn:'
            else:
                msg = 'Black turn:'

            if user_id == match.white:
                await ctx.send(
                    msg, file=discord.File(board_normal, 'board.png'))
            else:
                await ctx.send(
                    msg, file=discord.File(board_flipped, 'board.png'))

    @commands.command()
    async def surrender(self, ctx, game_id: int):
        """Forfeit and end one of your games, must specify the game id."""
        user_id = ctx.author.id
        guild_id = ctx.guild.id

        if await self.verify_game(ctx, game_id, user_id, guild_id):
            match = self.games[game_id]
            winner = match.surrender(user_id)
            await ctx.send(f'<@{user_id}> surrenders, <@{winner}> wins! '
                           f'PGN:\n```{match.get_pgn()}```')

            self.update_ranks(guild_id, False, winner, user_id)
            self.games.pop(game_id)

    @commands.command()
    async def move(self, ctx,
                   game_id: int,
                   move_from: str,
                   move_into: str,
                   promotion: str=None):
        """Make a move, must specify the game id as well as where
        you're moving from and into (Ex: `a1 h8`, `c2 c4`).
        If you can promote, you must specify what piece you're promoting to
        (`queen`, `knight`, `rook` or `bishop`)."""
        user_id = ctx.author.id
        guild_id = ctx.guild.id

        if await self.verify_game(ctx, game_id, user_id, guild_id):
            match = self.games[game_id]
            error = match.move(user_id, move_from, move_into, promotion)

            if not error:
                board_normal, board_flipped = match.get_images()
                gameover, stalemate = match.status()

                if user_id == match.white:
                    player_two = match.black
                else:
                    player_two = match.white

                if stalemate:
                    msg = f'<@{player_two}> and <@{user_id}> tied! ' \
                          f'PGN:\n```{match.get_pgn()}```'
                    self.update_ranks(guild_id, stalemate, user_id, player_two)
                    self.games.pop(game_id)

                elif gameover:
                    msg = f'<@{player_two}> got checkmated, <@{user_id}> ' \
                          f'wins! PGN:\n```{match.get_pgn()}```'
                    self.update_ranks(guild_id, stalemate, user_id, player_two)
                    self.games.pop(game_id)

                elif match.white_turn:
                    msg = 'Move executed! White turn:'
                else:
                    msg = 'Move executed! Black turn:'

                if match.white_turn:
                    await ctx.send(
                        msg, file=discord.File(board_normal, 'board.png'))
                else:
                    await ctx.send(
                        msg, file=discord.File(board_flipped, 'board.png'))

            elif error == 1:
                # not the players turn
                await ctx.send('It\'s not your turn yet!')

            elif error == 2:
                # wrote move incorrectly
                await ctx.send(
                    f'`{move_from} {move_into}` is not a valid move. '
                    'Moves are formatted like such: '
                    '`d2 d4`, `b8 c6`, `a1 h8` etc.')

            elif error == 3:
                # made an illegal move
                await ctx.send(
                    f'`{move_from} {move_into}` is an illegal move!')

    @commands.command()
    async def takeback(self, ctx, game_id: int):
        """Request to undo the last move.
        Both players have to agree to undo a move."""
        user_id = ctx.author.id
        guild_id = ctx.guild.id

        if await self.verify_game(ctx, game_id, user_id, guild_id):
            match = self.games[game_id]
            if not match.takeback(user_id):
                await ctx.send('You have requested a takeback!')
            else:
                board_normal, board_flipped = match.get_images()
                if match.white_turn:
                    msg = 'Takeback accepted! White turn:'
                else:
                    msg = 'Takeback accepted! Black turn:'

                if match.white_turn:
                    await ctx.send(
                        msg, file=discord.File(board_normal, 'board.png'))
                else:
                    await ctx.send(
                        msg, file=discord.File(board_flipped, 'board.png'))

    @commands.command()
    async def draw(self, ctx, game_id: int):
        """Offer the other player a draw
        (or accept if an offer has already been made)."""
        user_id = ctx.author.id
        guild_id = ctx.guild.id

        if await self.verify_game(ctx, game_id, user_id, guild_id):
            match = self.games[game_id]
            if not match.draw(user_id):
                await ctx.send('You have requested a draw!')
            else:
                await ctx.send(f'<@{match.black}> and <@{match.white}> '
                               f'have agreed a draw! '
                               f'PGN:\n```{match.get_pgn()}```')
                self.update_ranks(guild_id, True, match.black, match.white)
                self.games.pop(game_id)

    @commands.command()
    async def pgn(self, ctx, game_id: int):
        """Get the Portable Game Notation of one of your games."""
        user_id = ctx.author.id
        guild_id = ctx.guild.id

        if await self.verify_game(ctx, game_id, user_id, guild_id):
            match = self.games[game_id]
            if match.board.move_count > 0:
                await ctx.send(f'```{match.get_pgn()}```')


def setup(bot):
    bot.add_cog(Game(bot))
