# TicTacToe - Networked-Game-Platform

This project is a networked, real-time multiplayer Tic-Tac-Toe game implemented in Python.
It allows players to log in, create or join game rooms, play live matches, or watch games as viewers.
The system uses a **custom text-based protocol** over TCP sockets and supports concurrent clients.
Testing: Verified server responses using Wireshark (to capture and inspect TCP traffic between client and server, verifying protocol message format and sequence) and both Netcat (nc) and Ncat (ncat) to test server and client sides;see test report.

## Features
- **User Authentication**
  - Register new accounts with password hashing (bcrypt)
  - Login with existing credentials
- **Room Management**
  - Create rooms with custom names
  - Join rooms as a player or viewer
  - Room list filtering by mode
- **Real-Time Gameplay**
  - Live turn-based Tic-Tac-Toe play
  - Viewers see moves as they happen
  - Move validation and turn enforcement
- **Game Outcomes**
  - Win, draw, or forfeit detection
  - Automatic cleanup of finished games
- **Concurrency**
  - Multiple games run in parallel
  - Uses Python `selectors` for non-blocking server I/O
  - Threaded client-side loops for receiving and gameplay

Running the project:
This project needs Python 3.10+ and bcrypt
Start server: python3 -m server.server server/config.json
Start client: python3 -m client.client localhost 6507

Client Commands:

Before joining a game:

REGISTER to create account

LOGIN to log in

ROOMLIST to list available rooms (player or viewer)

CREATE to create a room (waits for another player)

JOIN to join a room (PLAYER or VIEWIER)

QUIT to exit

In-game:

PLACE to make a move (prompts for col & row 0–2)

FORFEIT to concede the game

Start a new game by entering any of the Out-of-Game Commands.

See test report for sample on how to use commands.