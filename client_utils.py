def valid_move(client, row, col):
    """
    This function checks if a move is valid based on the board's constraints,
    regardless of whether the player is currently in a game. If the player
    is not in a game, the move will still be sent to the server if it meets
    the criteria for being a valid board move.
    """
    print(f"Validating move: row {row}, col {col}")
    if client.in_game:
        if client.username != client.current_turn:
            return 'not_your_turn'
    if not (0 <= row < 3) or not (0 <= col < 3):
        return 'invalid_position'
    if client.board[row * 3 + col] != '0':
        return 'position_occupied'
    return 'valid'

def display_board(board_state):
    """
    Display the current state of the board.

    Takes a boardstatus string, maps each character
    to its corresponding symbol, and presents a visual representation
    of the board.

    Example from terminal:
        -------------
        |   |   |   |
        -------------
        | X |   |   |
        -------------
        |   |   |   |
        -------------
    """
    print(f"Displaying board: {board_state}")

    char_to_symbol = {
        '0' : ' ',
        '1' : 'X',
        '2' : 'O'
    }

    board = []
    for i in range(0, len(board_state), 3):
        row = [char_to_symbol[board_state[i]],
            char_to_symbol[board_state[i+1]],
            char_to_symbol[board_state[i+2]]]
        board.append(row)

    board_size = 3
    cell_size = 5

    row_separator = '-'
    column_separator = '|'
    n_row_separators = cell_size + (cell_size - 1) * (board_size - 1)

    print(row_separator * n_row_separators)
    for row in board:
        for value in row:
            print(f"{column_separator} {value} ", end='')
        print(column_separator)
        print(row_separator * n_row_separators)
    print("\n")
