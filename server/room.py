from server.game import Game
from shared.ack_status import AckStatus


class Room:
    """
    Represents a game room where players can join to play a game and viewers can watch.
    """

    def __init__(self, name):
        self.name = name
        self.players = []
        self.viewers = []
        self.game = None
        self.game_begun = False

    def can_add_player(self):
        """Check if a player can be added to the room."""
        return len(self.players) < 2

    def is_ready_to_start(self):
        """Check if the room has enough players to start the game."""
        return len(self.players) == 2

    def add_player(self, player):
        """Add a player to the room if there's space."""
        if not self.can_add_player():
            return False
        self.players.append(player)
        player.current_room = self
        return True

    def add_viewer(self, player):
        """Add a viewer to the room."""
        self.viewers.append(player)
        player.current_room = self
        if self.game_begun:
            current_turn = self.game.current_turn.username
            other_player = self.game.get_other_player().username
            player.send_message(
                f"INPROGRESS:{current_turn}:{other_player}\n".encode("utf-8")
            )

    def start_game(self):
        """Start the game, function is called from server.py"""
        self.game = Game(self.players[0], self.players[1])
        self.game_begun = True
        player1_username = self.players[0].username
        player2_username = self.players[1].username
        self.broadcast(f"BEGIN:{player1_username}:{player2_username}")

        for player in self.players:
            self.process_player_queue(player)

    def handle_place(self, player, col, row):
        result = self.game.make_move(player, col, row)

        if result == "success":
            board_status = self.game.get_board_state()
            if self.game.winner:
                self.broadcast(
                    f"GAMEEND:{board_status}:{AckStatus.GAMEEND_BOARDSTATUS_WINNER}:{self.game.winner.username}"
                )
                print("the game has ended and player has won")
                self.reset_room()
                return True

            elif self.game.is_draw:
                self.broadcast(
                    f"GAMEEND:{board_status}:{AckStatus.GAMEEND_BOARDSTATUS_DRAW}"
                )
                return True

            else:
                # board to be sent at each turn
                self.broadcast(f"BOARDSTATUS:{board_status}")
                next_player = self.game.current_turn
                self.process_player_queue(next_player)
                return False

    def process_player_queue(self, player):
        """
        Process queued actions of a player (FIFO)
        and pops the move once the action is processed.
        """
        while player.message_queue:
            action = player.message_queue.pop(0)
            if action[0] == "PLACE":
                col, row = int(action[1]), int(action[2])
                game_ended = self.handle_place(player, col, row)
                if game_ended:
                    break

            elif action[0] == "FORFEIT":
                forfeit = self.handle_forfeit(player)
                if forfeit:
                    # there should be only 1 move per player queued
                    # should clean up room at the end
                    break

    def handle_forfeit(self, player):
        """
        Handles a player forfeiting the game by calling
        self.remove_participant(player) to remove them from the room.
        """
        if player not in self.players:
            return False

        self.remove_participant(player)
        return True

    def broadcast(self, message):
        message += "\n"
        for participant in self.players + self.viewers:
            participant.send_message(message.encode("utf-8"))

    def remove_participant(self, participant):
        """
        Remove a participant (player or viewer) from the room
        """
        if participant in self.players and self.game:
            board_status = self.game.get_board_state()
            other_player = self.game.get_other_player()

            self.broadcast(
                f"GAMEEND:{board_status}:{AckStatus.GAMEEND_BOARDSTATUS_FORFEIT}:{other_player.username}"
            )
            participant.cleanup_after_game()
            other_player.cleanup_after_game()
            self.players.remove(participant)

        if participant in self.viewers and self.game:
            self.viewers.remove(participant)
            participant.current_room = None

    def reset_room(self):
        """
        Reset the room's state after a game ends prior to deleting the room.
        """
        self.game = None
        self.players = []
        self.viewers = []
