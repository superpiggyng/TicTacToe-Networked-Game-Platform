import sys
import json
import socket
import selectors
import re
from typing import Dict
import bcrypt

from ack_status import AckStatus
from player import Player
from room import Room
from config import Config


class Server:
    """
    Represents a game server that manages client connections,
    user authentication, room creation, and game logic.
    """

    def __init__(self, config):
        """
        Initialises the Server instance with the specified configuration.
        """
        self.config = config
        self.sel = selectors.DefaultSelector()
        self.port = config.port
        self.users = config.load_user_db()
        self.host = "localhost"
        self.server_socket = None
        self.authenticated_clients: Dict[socket.socket, Player] = {}
        self.rooms: Dict[str, Room] = {}
        self.max_rooms = 256

    def login_user(self, username, password):
        """
        Validates the login credentials and returns an integer status.
        Returns:
            0 - Success (username found and password matches)
            1 - Username not found
            2 - Username found but password mismatch
        """
        for user in self.users:
            if user["username"] == username:
                if bcrypt.checkpw(
                    password.encode("utf-8"), user["password"].encode("utf-8")
                ):
                    return 0
                return 2
        return 1

    def register_user(self, username, password):
        """
        Registers a new user in the user database.
        Returns:
            int: Status code indicating the registration outcome:
                 0 - Success (user registered successfully)
                 1 - Username already exists
        """
        for user in self.users:
            if user["username"] == username:
                return 1
        hashed_password = bcrypt.hashpw(
            password.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")
        new_user = {"username": username, "password": hashed_password}
        self.users.append(new_user)

        with open(self.config.user_db_path, "w") as file:
            json.dump(self.users, file, indent=4)
        return 0

    def accept_client(self, server_socket):
        """
        Accepts a new client connection and registers the client socket for monitoring read events.
        Args:
            server_socket (socket): The server's listening socket used
                                    to accept incoming client connections.

        If no client connection is ready, a BlockingIOError is caught and ignored,
        allowing the server to continue running without being stuck waiting for a client to connect.
        """
        try:
            client_socket, addr = server_socket.accept()
            client_socket.setblocking(False)
            # client socket is monitored for read events
            # which occurs when the client sends data
            self.sel.register(client_socket, selectors.EVENT_READ, self.handle_client)
        except BlockingIOError:
            pass

    def handle_sendback(self, action, ack_status_value, additional_info=None):
        """
        Constructs the response message to be sent to client.
        Adds newline at the end.
        """
        message = f"{action}:ACKSTATUS:{ack_status_value}"
        if additional_info is not None:
            message += f":{additional_info}"
        message += "\n"
        return message.encode("utf-8")

    def handle_login(self, client_socket, username, password):
        """
        Handles login request from a client.
        """
        login_status = self.login_user(username, password)

        actions = {
            0: lambda: self.login_success(client_socket, username),
            1: lambda: client_socket.sendall(
                self.handle_sendback("LOGIN", AckStatus.LOGIN_USER_NOT_FOUND.value)
            ),
            2: lambda: client_socket.sendall(
                self.handle_sendback("LOGIN", AckStatus.LOGIN_PASSWORD_MISMATCH.value)
            ),
        }

        action = actions.get(login_status, lambda: None)
        action()

    def login_success(self, client_socket, username):
        """
        This function is called upon successful login
        """
        player = Player(username=username, socket=client_socket)
        self.authenticated_clients[client_socket] = player
        client_socket.sendall(self.handle_sendback("LOGIN", AckStatus.SUCCESS.value))

    def handle_register(self, client_socket, username, password):
        """
        Handles registration request from client.
        """
        register_status = self.register_user(username, password)

        actions = {
            0: lambda: client_socket.sendall(
                self.handle_sendback("REGISTER", AckStatus.SUCCESS.value)
            ),
            1: lambda: client_socket.sendall(
                self.handle_sendback(
                    "REGISTER", AckStatus.REGISTER_USER_ALREADY_EXISTS.value
                )
            ),
        }

        action = actions.get(register_status, lambda: None)
        action()

    def is_authenticated(self, client_socket):
        """
        Checks if a client is authenticated.
        """
        return client_socket in self.authenticated_clients

    # ONLY AFTER AUTHENTICATION
    def handle_roomlist(self, client_socket, mode):
        """
        Handles ROOMLIST command by sending the list of available rooms based on player's mode.
        """
        player = self.authenticated_clients[client_socket]

        if mode not in ["PLAYER", "VIEWER"]:
            player.send_message(
                self.handle_sendback("ROOMLIST", AckStatus.ROOMLIST_INVALID_INPUT.value)
            )
            return

        if mode == "VIEWER":
            room_list = ",".join(self.rooms.keys()) if self.rooms else ""
        elif mode == "PLAYER":
            available_player_rooms = [
                room_name
                for room_name, room_data in self.rooms.items()
                if len(room_data.players) < 2
            ]
            room_list = (
                ",".join(available_player_rooms) if available_player_rooms else ""
            )

        player.send_message(
            self.handle_sendback("ROOMLIST", AckStatus.SUCCESS.value, room_list)
        )

    def valid_room_name(self, room_name):
        """
        Checks if a given room name is valid based on allowed characters and length.
        - contain alphanumeric characters (a-z, A-Z, 0-9), dashes, spaces, and underscores.
        - maximum of 20 characters in length
        """
        if re.match(r"^[a-zA-Z0-9 _-]+$", room_name) and 0 < len(room_name) <= 20:
            return True
        return False

    def handle_create_room(self, client_socket, room_name):
        """
        Handles the CREATE command by attempting to create a new room.
        """
        player = self.authenticated_clients[client_socket]

        if not self.valid_room_name(room_name):
            return player.send_message(
                self.handle_sendback("CREATE", AckStatus.CR_INVALID_ROOM_NAME.value)
            )

        if room_name in self.rooms:
            return player.send_message(
                self.handle_sendback("CREATE", AckStatus.CR_ROOM_ALREADY_EXISTS.value)
            )

        if len(self.rooms) >= self.max_rooms:
            return player.send_message(
                self.handle_sendback("CREATE", AckStatus.CR_MAX_ROOM_CAP.value)
            )

        new_room = Room(room_name)
        self.rooms[room_name] = new_room
        new_room.add_player(player)
        player.send_message(self.handle_sendback("CREATE", AckStatus.SUCCESS.value))

    def handle_join_room(self, client_socket, room_name, mode):
        """
        Handles the JOIN command by adding the client to the specified room as either
        a player or a viewer (mode)
        """
        player = self.authenticated_clients[client_socket]

        if room_name not in self.rooms:
            return player.send_message(
                self.handle_sendback("JOIN", AckStatus.JOIN_ROOM_DNE.value)
            )

        room = self.rooms[room_name]

        if mode == "PLAYER":
            if not room.can_add_player():
                return player.send_message(
                    self.handle_sendback("JOIN", AckStatus.JOIN_ROOM_FULL.value)
                )
            room.add_player(player)
            player.send_message(self.handle_sendback("JOIN", AckStatus.SUCCESS.value))

            if room.is_ready_to_start():
                room.start_game()

        elif mode == "VIEWER":
            player.send_message(self.handle_sendback("JOIN", AckStatus.SUCCESS.value))
            room.add_viewer(player)
        else:
            player.send_message(
                self.handle_sendback("CREATE", AckStatus.JOIN_INVALID_FORMAT.value)
            )

    def handle_unauthenticated(self, client_socket, action):
        """
        Handles authentication relation commands(LOGIN/REGISTER) sent by unauthenticated clients.
        """
        if action[0] in ["LOGIN", "REGISTER"]:
            if len(action) != 3:
                if action[0] == "LOGIN":
                    client_socket.sendall(
                        self.handle_sendback(
                            action[0], AckStatus.LOGIN_INVALID_FORMAT.value
                        )
                    )
                    return
                if action[0] == "REGISTER":
                    client_socket.sendall(
                        self.handle_sendback(
                            action[0], AckStatus.REGISTER_INVALID_FORMAT.value
                        )
                    )
                    return

            _, username, password = action
            if action[0] == "LOGIN":
                self.handle_login(client_socket, username, password)
            elif action[0] == "REGISTER":
                self.handle_register(client_socket, username, password)
        else:
            client_socket.sendall("BADAUTH\n".encode("utf-8"))

    def handle_authenticated(self, client_socket, action):
        """
        Handles commands that can only be performed by authenticated clients.
        """
        player = self.authenticated_clients[client_socket]
        command = action[0]
        command_handlers = {
            "ROOMLIST": lambda: self._handle_roomlist_command(player, action),
            "CREATE": lambda: self._handle_create_command(player, action),
            "JOIN": lambda: self._handle_join_command(player, action),
            "PLACE": lambda: self._handle_game_command(player, action),
            "FORFEIT": lambda: self._handle_game_command(player, action),
        }

        handler = command_handlers.get(command, lambda: None)
        handler()

    def _handle_roomlist_command(self, player, action):
        if len(action) != 2:
            player.send_message(
                self.handle_sendback("ROOMLIST", AckStatus.ROOMLIST_INVALID_INPUT.value)
            )
        else:
            self.handle_roomlist(player.socket, action[1])

    def _handle_create_command(self, player, action):
        if len(action) != 2:
            player.send_message(
                self.handle_sendback("CREATE", AckStatus.CR_INVALID_CREATE_FORMAT.value)
            )
        else:
            self.handle_create_room(player.socket, action[1])

    def _handle_join_command(self, player, action):
        if len(action) != 3 or action[2] not in ["PLAYER", "VIEWER"]:
            player.send_message(
                self.handle_sendback("JOIN", AckStatus.JOIN_INVALID_FORMAT.value)
            )
        else:
            room_name = action[1]
            mode = action[2]
            self.handle_join_room(player.socket, room_name, mode)

    def _handle_game_command(self, player, action):
        """
        Handles game-related commands (PLACE and FORFEIT) for a player in a room.
        Sends appropriate responses, or NOROOM if Player is not currently in a room.
        """
        if player.get_current_room() is None:
            player.send_message("NOROOM\n".encode("utf-8"))
            return

        if player in player.current_room.viewers:
            print("ignoring as its viewer")
            return

        room = player.current_room

        if self.can_process_action(player, action):
            if action[0] == "PLACE":
                col, row = int(action[1]), int(action[2])
                room = player.current_room
                game_ended = room.handle_place(player, col, row)
                if game_ended:
                    self.cleanup_room(room)

            elif action[0] == "FORFEIT":
                room = player.current_room
                forfeit = room.handle_forfeit(player)
                if forfeit:
                    self.cleanup_room(room)
        else:
            # if player is not currently in turn the move is added to the queue
            # and performed when turn changes.
            player.message_queue.append(action)

    def handle_client(self, client_socket):
        """
        Handles incoming data from a client and processes the
        corresponding commands based on authentication state.
        """
        try:
            data = client_socket.recv(8192).decode("utf-8")
            print(f"Received data from client: {data}")
            if data:
                action = data.strip().split(":")

                if not self.is_authenticated(client_socket):
                    self.handle_unauthenticated(client_socket, action)
                else:
                    self.handle_authenticated(client_socket, action)
            else:
                raise EOFError("Client disconnected")

        except (ConnectionResetError, EOFError) as e:
            print(f"Client disconnected: {e}")
            self.handle_client_disconnect(client_socket)

        except Exception as e:
            print(f"Unexpected error handling client: {e}")
            self.handle_client_disconnect(client_socket)

    def can_process_action(self, player, action):
        """
        Determines whether the player is currently in turn
        to perform a move in the game.
        """
        if action[0] == "PLACE":
            room = player.get_current_room()
            if room and room.game_begun and room.game.get_current_turn() == player:
                return True
            return False
        if action[0] == "FORFEIT":
            return True

    def handle_client_disconnect(self, client_socket):
        """
        Handles disconnection of client by unregistering it and cleaning up resources.
        """
        self.sel.unregister(client_socket)
        client_socket.close()

        if client_socket in self.authenticated_clients:
            player = self.authenticated_clients.pop(client_socket)
            room = player.current_room

            if room:
                room.remove_participant(player)
                self.cleanup_room(room)

        print("Client disconnected and cleaned up")

    def cleanup_room(self, room):
        """
        Cleans up and deletes the room instance.
        """
        if room.name in self.rooms:
            del self.rooms[room.name]
            print(f"Room '{room.name}' has been cleaned up and deleted.")

    def start_server(self):
        """
        Starts the server and listens for incoming client connections.

        Sets up a non-blocking server socket for handling client connections and data.

        Registers the server socket with selector for monitoring read events

        Continuously waits for events and handles client connections and data sent.

        Shuts down the server socket when the selector is closed.
        """
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind((self.host, self.port))
            server_socket.listen(5)
            server_socket.setblocking(False)
            # accept_client is the callback function that will be invoked whenever
            # read events (when a client tries to connect to the server socket) occurs
            self.sel.register(server_socket, selectors.EVENT_READ, self.accept_client)
            print(f"Server is listening on {self.host}:{self.port}")

            try:
                while True:
                    # events to monitor on the socket
                    events = self.sel.select(timeout=None)
                    for key, _ in events:
                        callback = key.data
                        # fileobj is the socket, data is the associated callback function
                        callback(key.fileobj)
            except Exception as e:
                print(f"server shutting down, {e}")
            finally:
                if self.sel:
                    self.sel.close()


def main(args: list[str]) -> None:
    if len(args) != 1:
        print("Error: Expecting 1 argument: <server config path>.")
        return
    config = Config(args[0])
    server = Server(config)
    server.start_server()


if __name__ == "__main__":
    main(sys.argv[1:])
