class Player:
    """
    Represents an authenticated user.
    Once a client logs in they are automatically associated
    with a player object

    Notable Attribute:
        message_queue (list): A queue of pending moves that is stored when the player
        sends a move while not in turn. Move is performed once turn changes.
    """
    def __init__(self, username, socket):
        self.username = username
        self.socket = socket
        self.symbol = None  # 'X' or 'O', assigned when the game starts
        self.current_room = None  # Room object
        self.message_queue = []

    def get_current_room(self):
        """return the room that the player is currently associated with."""
        return self.current_room

    def send_message(self, message):
        """send a message to the player's socket."""
        try:
            self.socket.sendall(message)
        except Exception:
            pass

    def cleanup_after_game(self):
        """
        Clean up player's state after the game ends or the player forfeits.

        Should be called when the game concludes, whether due to a
        win, draw, or player forfeit.
        """
        self.current_room = None
        self.symbol = None
