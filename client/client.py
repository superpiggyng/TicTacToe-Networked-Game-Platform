import sys
import socket
import threading
from shared.ack_status import AckStatus
from client import client_utils

class Client:
    """
    Represents a networked client connected to a server for a multiplayer Tic-Tac-Toe game.
    Manages communications and interactions with a server (receiving and sending).
    """
    def __init__(self, host, port):
        """
        Initializes the Client instance with the server address and port.
        """
        self.host = host
        self.port = port
        self.player_socket = None

        self.receiving_thread = None
        self.game_thread = None
        self.game_start_event = threading.Event()
        self.board_update_event = threading.Event()
        self.turn_lock = threading.Lock()

        self.running = True
        self.username = None
        self.current_turn = None
        self.board = "000000000"
        self.player1 = None
        self.player2 = None
        self.in_game = False
        self.is_viewer = False
        self.just_placed_move = False

        self.roomlist_mode = None
        self.room_name = None  # room that player is in
        self.mode = None  # join game as mode

        self.command_handlers = {
            "LOGIN": self.login,
            "REGISTER": self.register,
            "ROOMLIST": self.roomlist,
            "CREATE": self.create_room,
            "JOIN": self.join_room,
            "QUIT": self.close,
            "PLACE": self.place_piece,
            "FORFEIT": self.forfeit_game,
        }

        self.response_handlers = {
            "LOGIN": self.handle_login_response,
            "REGISTER": self.handle_register_response,
            "ROOMLIST": self.handle_roomlist_response,
            "CREATE": self.handle_create_response,
            "JOIN": self.handle_join_response,
            "BEGIN": self.handle_begin,
            "BOARDSTATUS": self.handle_board_status,
            "GAMEEND": self.handle_gameend_response,
            "INPROGRESS": self.handle_in_progress,
            "BADAUTH": self.handle_badauth,
            "NOROOM": lambda _: print(
                "You're not in a room, you can't send game-related commands."
            ),
        }

    def start_receiving_thread(self):
        """
        Starts the background thread for continuously receiving messages from the server.
        """
        self.receiving_thread = threading.Thread(
            target=self.receive_messages_loop, daemon=True
        )
        self.receiving_thread.start()

    def start_game_thread(self):
        """
        Starts the game loop in a separate background thread. This is started when
        a client creates/joins a room.
        """
        self.game_thread = threading.Thread(target=self.play_game_loop, daemon=True)
        self.game_thread.start()

    def connect(self):
        """
        Connects the client to the server. Terminates the program if the connection fails.
        """
        try:
            self.player_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.player_socket.connect((self.host, self.port))

        except ConnectionRefusedError:
            print(f"Error: cannot connect to server at {self.host} and {self.port}.")
            sys.exit(1)

    def send_message(self, message):
        """
        Formats message with a newline at the end and sends the message
        to the server.
        """
        message += "\n"
        return self.player_socket.sendall(message.encode("utf-8"))

    def receive_message(self):
        """
        Receives message from the server
        """
        return self.player_socket.recv(8192).decode("utf-8")

    def receive_messages_loop(self):
        """
        Continuously listens for messages from the server and handles them.
        """
        buffer = ""
        while self.running:
            try:
                message = self.receive_message()
                if message:
                    buffer += message
                    while "\n" in buffer:
                        message, buffer = buffer.split("\n", 1)
                        message = message.strip()
                        if message:
                            self.handle_server_message(message)
                else:
                    print("Server has closed the connection.")
                    self.running = False
                    break

            except Exception as e:
                print(f"Error receiving message: {e}")
                self.running = False
                break

    def handle_server_message(self, message):
        """
        Determines the appropriate handler for a server message and processes it.
        """
        response_type = message.split(":")[0]
        handler = self.response_handlers.get(response_type, self.handle_unknown_message)
        handler(message)

    def close(self):
        """
        Closes the client's connection to the server.
        """
        print("Connection closed.")
        self.running = False
        if self.player_socket:
            self.player_socket.close()
            self.player_socket = None

    # --- user commands ---
    def login(self):
        """
        Prompts the user to enter a username and password to log in to the server.
        """
        self.username = input("Enter Username: ").strip()
        password = input("Enter password: ").strip()
        self.send_message(f"LOGIN:{self.username}:{password}")

    def register(self):
        """
        Prompts the user to enter a username and password to register a new account.
        Continues prompting if the username or password length exceeds 20 characters.
        """
        while True:
            self.username = input("Enter username: ").strip()
            if len(self.username) > 20:
                print("Username is too long, try again.")
                continue

            password = input("Enter password: ").strip()
            if len(password) > 20:
                print("Password is too long, please try again")
                continue

            self.send_message(f"REGISTER:{self.username}:{password}")
            break

    def roomlist(self):
        """
        Requests a list of available rooms to join(given the mode) from the server.
        """
        self.roomlist_mode = input(
            "Do you want to have a room list as player or viewer? (player/viewer) "
        ).strip()
        self.send_message(f"ROOMLIST:{self.roomlist_mode}")

    def create_room(self):
        """
        Creates a new room and blocks the current thread until the game starts.

        Sends a request to the server to create a room with the specified name.

        The thread is blocked until the game_start_event is set.
        Once the event is set (indicating that the game has started) - BEGIN
        it clears the event and starts the game thread.
        """
        self.room_name = input("Enter room name you want to create: ").strip()
        self.send_message(f"CREATE:{self.room_name}")
        self.game_start_event.wait()  # pauses main thread
        self.game_start_event.clear()  # after main thread is unblocked, ends up here
        self.start_game_thread()

    def join_room(self):
        """
        Joins an existing room and blocks the current thread until the game starts.

        Sends a request to the server to join a room with the specified name and mode
        (Player or Viewer).

        The thread is blocked until the game_start_event is set,
        indicating that the game has started. (BEGIN/INPROGRESS)
        Once the event is set, it clears the event and starts the game thread.
        """
        self.room_name = input("Enter room name to join: ").strip()
        self.mode = input("Join as (Player/Viewer): ").strip()
        self.send_message(f"JOIN:{self.room_name}:{self.mode}")
        self.game_start_event.wait()  # for player who joins the room
        self.game_start_event.clear()
        self.start_game_thread()

    def place_piece(self):
        """
        Prompts the player to enter a column and row to place their piece on the board.
        Continues to ask for input until a valid move is made.

        If client is not in a game, they still can send a place message to the server,
        and server will respond accordingly with a NOROOM message.
        """
        while True:
            try:
                col, row = int(input("Col: ")), int(input("Row: "))
                validation_result = client_utils.valid_move(self, row, col)
                if validation_result == "valid":
                    self.send_message(f"PLACE:{col}:{row}")
                    self.just_placed_move = True
                    break  # exit loop on valid move
                if validation_result == "not_your_turn":
                    print("It is not your turn, wait for your turn")
                    break
                else:
                    print("Invalid move, try again")

            except ValueError:
                print("(Column/Row) values must be an integer between 0 and 2")
                continue

    def forfeit_game(self):
        self.send_message("FORFEIT")

    # --- response handlers ---
    def handle_badauth(self, message):
        """
        Handles the BADAUTH response from the server.

        Unblocks any waiting threads by setting the game_start_event and
        prints an error message indicating that the user must be logged in
        to perform the given action.
        """
        self.game_start_event.set() # to prevent infinite waiting
        print("Error: You must be logged in to perform this action", file=sys.stderr)

    def handle_unknown_message(self, message):
        """
        Handles an unknown message received from the server.

        If the message is not in the response_handler dictionary,
        disconnects client from the server.
        """
        print("Unknown message received from server. Exiting...")
        self.close()

    def handle_login_response(self, message):
        """
        Prints the appropriate messages for the Ackstatus sent by server
        """
        ack_status = int(message.split(":")[2])
        actions = {
            AckStatus.SUCCESS.value: lambda: (print(f"Welcome {self.username}"), True),
            AckStatus.LOGIN_USER_NOT_FOUND.value: lambda: print(
                f"Error: User {self.username} not found", file=sys.stderr
            ),
            AckStatus.LOGIN_PASSWORD_MISMATCH.value: lambda: print(
                f"Error: Wrong password for user {self.username}", file=sys.stderr
            ),
            AckStatus.LOGIN_INVALID_FORMAT.value: lambda: None,
        }

        action = actions.get(
            ack_status, lambda: print("An unexpected error occured.", file=sys.stderr)
        )
        action()

    def handle_register_response(self, message):
        """
        Prints the appropriate messages for the Ackstatus sent by server
        """
        ack_status = int(message.split(":")[2])

        actions = {
            AckStatus.SUCCESS.value: lambda: print(
                f"Successfully created user account {self.username}"
            ),
            AckStatus.REGISTER_USER_ALREADY_EXISTS.value: lambda: print(
                f"Error: User {self.username} already exists", file=sys.stderr
            ),
            AckStatus.REGISTER_INVALID_FORMAT.value: lambda: None,
        }

        action = actions.get(
            ack_status, lambda: print("An unexpected error occured", file=sys.stderr)
        )
        action()

    def handle_roomlist_response(self, message):
        """
        Prints the appropriate messages for the Ackstatus sent by server
        """
        response = message.split(":")
        ack_status = int(response[2])
        if len(response) == 4:
            rooms = response[3]
        actions = {
            AckStatus.SUCCESS.value: lambda: (
                print(f"Rooms available to join as {self.roomlist_mode}: {rooms}")
            ),
            AckStatus.ROOMLIST_INVALID_INPUT.value: lambda: (
                print("Error: Please input a valid mode.")
            ),
        }
        action = actions.get(
            ack_status, lambda: print("An unexpected error occured", file=sys.stderr)
        )
        action()

    def handle_create_response(self, message):
        """
        Prints the appropriate messages for the Ackstatus sent by server.

        If the room creation is not successful, sets the 'game_start_event' to unblock
        the waiting thread and avoid infinite waiting. If the creation is successful,
        it waits for the "BEGIN" message from the server and does not unblock waiting
        thread.
        """
        response = message.split(":")
        ack_status = int(response[2])
        actions = {
            AckStatus.SUCCESS.value: lambda: print(
                f"Successfully created room {self.room_name}\nWaiting for other player..."
            ),
            AckStatus.CR_INVALID_ROOM_NAME.value: lambda: (
                print(f"Error: {self.room_name} is invalid", file=sys.stderr)
            ),
            AckStatus.CR_ROOM_ALREADY_EXISTS.value: lambda: (
                print(f"Error: Room {self.room_name} already exists", file=sys.stderr)
            ),
            AckStatus.CR_MAX_ROOM_CAP.value: lambda: (
                print(
                    "Error: Server already contains a maximum of 256 rooms",
                    file=sys.stderr,
                )
            ),
        }

        action = actions.get(
            ack_status, lambda: print("An unexpected error occured", file=sys.stderr)
        )
        action()

        if ack_status == AckStatus.SUCCESS.value:
            self.current_turn = self.username
            self.in_game = True

        if ack_status != AckStatus.SUCCESS.value:
            # only for unblocking wait, as begin message will never be reached
            self.game_start_event.set()

    def handle_join_response(self, message):
        """
        Prints the appropriate messages for the Ackstatus sent by server.

        If the room join is not successful, sets the 'game_start_event' to unblock
        the waiting thread and avoid infinite waiting. If the creation is successful,
        it waits for the "BEGIN/INPROGRESS" message from the server
        and does not unblock waiting thread.
        """
        response = message.split(":")
        ack_status = int(response[2])

        actions = {
            AckStatus.SUCCESS.value: lambda: (
                print(f"Successfully joined room {self.room_name} as a {self.mode}")
            ),
            AckStatus.JOIN_ROOM_DNE.value: lambda: (
                print(f"Error: No room named {self.room_name} ", file=sys.stderr)
            ),
            AckStatus.JOIN_ROOM_FULL.value: lambda: (
                print(
                    f"Error: The room {self.room_name} already has 2 players",
                    file=sys.stderr,
                )
            ),
        }

        action = actions.get(
            ack_status, lambda: print("An unexpected error occured", file=sys.stderr)
        )
        action()

        if ack_status != AckStatus.SUCCESS.value:
            # only for unblocking wait, as begin message will never be reached
            self.game_start_event.set()

    def handle_begin(self, message):
        """
        Handles the BEGIN message from the server, indicating the start of a game.

        Identifies the players involved in the game, sets the initial turns.
        Notifies the client of the initial turns.

        For viewers, it prints a message about the ongoing match.

        Unblocks the 'game_start_event' waiting thread in join/create room
        by setting it.
        """
        self.player1, self.player2 = message.split(":")[1:3]  # didnt strip
        self.in_game = True
        if self.just_placed_move:
            self.current_turn = (
                self.player2 if self.username == self.player1 else self.player1
            )
        else:
            self.current_turn = self.player1

        if self.username == self.player1 or self.username == self.player2:
            if self.current_turn == self.username:
                print("It's your turn, Please place marker")
            elif self.current_turn != self.username:
                print("It is the opposing player's turn")
        else:
            self.is_viewer = True
            print(
                f"match between {self.player1} and {self.player2} will commence, it is currently {self.player1}'s turn."
            )

        self.game_start_event.set()

    def handle_board_status(self, message):
        """
        Handles the BOARDSTATUS message from the server by updating
        the board state and current turn.

        Uses a locking mechanism to ensure that 'play_game_loop' does
        not access the turn at the same time, preventing race conditions.

        Displays the updated board and informs the user of the turn status,
        with different messages for players and viewers.
        Sets the 'board_update_event' for the waiting thread in 'play_game_loop'.
        """

        with self.turn_lock:
            self.board = message.split(":")[1].strip()
            client_utils.display_board(self.board)
            if not self.is_viewer:
                if self.just_placed_move:
                    self.current_turn = (
                        self.player2 if self.username == self.player1 else self.player1
                    )
                    self.just_placed_move = False
                else:
                    self.current_turn = self.username

                if self.current_turn == self.username:
                    print("It is the current player's turn")
                else:
                    print("It is the opposing player's turn")
            else:
                # viewer logic
                self.current_turn = (
                    self.player2 if self.current_turn == self.player1 else self.player1
                )
                print(f"It is currently {self.current_turn}'s turn.")

            self.board_update_event.set()

    def handle_in_progress(self, message):
        """
        Handles the INPROGRESS message from the server for a viewer.

        Identifies the players, and notifies the client whose turn it is.
        Initial turn settings for a client who joins INPROGRESS is determined here.

        Sets the 'game_start_event' for the waiting thread in 'join_room'
        for viewers joining during an INPROGRESS game.
        """
        self.player1, self.player2 = message.split(":")[1:3]
        self.current_turn = self.player1
        self.in_game = True
        self.is_viewer = True
        print(
            f"Match between {self.player1} and {self.player2} is currently in progress, it is {self.player1}'s turn"
        )
        self.game_start_event.set()

    def handle_gameend_response(self, message):
        """
        Processes the GAMEEND response message from the server.

        Displays the final board state, and outcome of the game (win/draw/forfeit).

        Sets the 'board_update_event' for the waiting thread in 'play_game_loop'.
        Resets the client's game-related attributes in preparation to join a new game.
        """
        response = message.split(":")
        ack_status = int(response[2])
        winner_username = response[3] if len(response) > 3 else None
        board_state = response[1]
        client_utils.display_board(board_state)

        if ack_status == AckStatus.GAMEEND_BOARDSTATUS_WINNER.value:
            if self.is_viewer:
                print(f"{winner_username} has won this game.")
            else:
                if self.username == winner_username:
                    print("Congratulations you won!")
                else:
                    print("Sorry you lost. Good luck next time.")
        elif ack_status == AckStatus.GAMEEND_BOARDSTATUS_DRAW.value:
            print("Game ended in a draw.")
        elif ack_status == AckStatus.GAMEEND_BOARDSTATUS_FORFEIT.value:
            print(f"{winner_username} won due to the opposing player forfeiting")
        else:
            print("Unknown Game end status.")

        self.board_update_event.set()
        self.reset_client_game_state()

    # --- main loop --- #
    def main(self):  # main thread
        """
        Main loop for a client.

        Starts the background thread for receiving messages from the server.

        Takes commands from the client while not in-game.

        Handles EOF errors.
        """
        self.start_receiving_thread()

        while self.running:

            if not self.in_game:
                try:
                    command = input("").strip()

                    if command in self.command_handlers:
                        result = self.command_handlers[command]()
                        if result:  # for quit command
                            break
                    else:
                        print(f"Unknown command: {command}")
                        continue

                except EOFError:
                    self.close()
                    break

                except Exception as e:
                    print(f"Error in game loop: {e}")

    # --- game loop ---
    def play_game_loop(self):
        """
        Game loop for handling in-game commands.

        Uses a locking mechanism to ensure that 'handle_board_status' does not
        access the turn at the same time, preventing race conditions.

        Prompts the player for actions (PLACE/FORFEIT) while the game is ongoing.

        Waits for board update events (BOARDSTATUS/GAMEEND) before continuing/terminating.
        """
        while self.in_game:
            try:
                with self.turn_lock:

                    if self.current_turn == self.username:
                        command = input(
                            "Type place to make a move, forfeit to end game: "
                        ).strip()
                        if command == "PLACE":
                            self.place_piece()  # Call handle_place to prompt and send the move
                        elif command == "FORFEIT":
                            self.forfeit_game()
                        else:
                            continue

                self.board_update_event.clear()
                self.board_update_event.wait()
                continue

            except EOFError:
                self.close()
                break

    # --- end game reset ---

    def reset_client_game_state(self):
        """
        Ensures that the client is ready for a new game by:
            - Resetting game-related attributes to initial state,
            - Clearing threading events
            - Terminating the game thread if it is still active.
        """
        print("resetting all variables")
        self.in_game = False
        self.is_viewer = False
        self.current_turn = None
        self.board = "000000000"
        self.player1 = None
        self.player2 = None
        self.just_placed_move = False
        self.roomlist_mode = None
        self.room_name = None
        self.mode = None
        self.game_start_event.clear()
        self.board_update_event.clear()

        if self.game_thread and self.game_thread.is_alive():
            self.game_thread.join()

        self.game_thread = None


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Error: Expecting 2 arguments: <server address> <port>")
        sys.exit(1)

    server_host = sys.argv[1]
    server_port = int(sys.argv[2])

    client = Client(server_host, server_port)
    try:
        client.connect()
        client.main()
    finally:
        client.close()
