from player import Player

# modified into a class and
# added methods from the original scaffold
ORIGINAL_AUTHOR_ = "Luca Napoli"

BOARD_SIZE = 3
EMPTY = ' '

class Game:
    """
    Represents a Tic-Tac-Toe game between 2 players.

    Game class manages the game board, player turns, checks for
    win and draw conditions, and a method for players to make moves.
    """
    def __init__(self, player1: Player, player2: Player):
        '''
        Init the Game with 2 players and sets up the board.

        Args:
            player1 (Player): The first player 'X'.
            player2 (Player): The second player 'O'.
        '''
        self.board = [[EMPTY for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]
        self.players = [player1, player2]
        self.current_turn = player1
        self.winner = None
        self.is_draw = False
        player1.symbol = 'X'
        player2.symbol = 'O'

    def get_current_turn(self):
        return self.current_turn

    def get_other_player(self):
        return self.players[0] if self.players[1] == self.current_turn else self.players[1]

    def make_move(self, player: Player, col: int, row: int) -> str:
        """
        Assumes that turn validation has been completed prior to calling.

        Args:
            player (Player): The player making the move.
            col (int): The column index for the move.
            row (int): The row index for the move.

        Returns:
            str: 'success' if the move was successful.
        """
        self.board[row][col] = player.symbol

        if self.player_wins(player.symbol):
            self.winner = player

        elif self.players_draw():
            self.is_draw = True

        else:
            self.switch_turn()

        return 'success'

    def switch_turn(self):
        """Switch the current turn to the other player."""
        self.current_turn = self.players[0] if self.current_turn == self.players[1] else self.players[1]

    def players_draw(self) -> bool:
        """Determines whether the players draw on the given board"""
        return all(
            self.board[y][x] != EMPTY
            for y in range(BOARD_SIZE)
            for x in range(BOARD_SIZE)
        )

    def get_board_state(self) -> str:

        symbol_to_char ={
            ' ' : '0',
            'X' : '1',
            'O' : '2'
        }

        return ''.join(symbol_to_char[cell] for row in self.board for cell in row)

    def player_wins(self, symbol: str) -> bool:
        """Determines whether the specified player wins given the board"""
        return (
            self._player_wins_horizontally(symbol) or
            self._player_wins_vertically(symbol) or
            self._player_wins_diagonally(symbol)
        )

    ### private functions, used within class only ###

    def _player_wins_vertically(self, symbol) -> bool:
        return any(
            all(self.board[y][x] == symbol for y in range(BOARD_SIZE))
            for x in range(BOARD_SIZE)
        )


    def _player_wins_horizontally(self, symbol) -> bool:
        return any(
            all(self.board[x][y] == symbol for y in range(BOARD_SIZE))
            for x in range(BOARD_SIZE)
        )


    def _player_wins_diagonally(self, symbol) -> bool:
        return (
            all(self.board[y][y] == symbol for y in range(BOARD_SIZE)) or
            all(self.board[BOARD_SIZE - 1 - y][y] == symbol for y in range(BOARD_SIZE))
        )
    