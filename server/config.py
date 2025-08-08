import sys
import os
import json

class Config:
    """
    Config class handles loading and validating server configuration and userdb
    """
    def __init__(self, config_path):
        self.config_path = config_path
        self.port = None
        self.user_db_path = None
        self.load_server_config()


    def load_server_config(self):
        """
        Loads and validates the server configuration from the JSON file specified by config_path.
        The configuration file must include 'port' and 'userDatabase' keys.
        The port must be an integer within the range 1024-65535.
        """
        if not os.path.exists(self.config_path):
            print(f"Error: {self.config_path} doesn\'t exist.")
            sys.exit(1)

        try:
            with open(self.config_path, 'r') as file:
                config = json.load(file)
        except json.JSONDecodeError:
            print(f"Error: {self.config_path} is not in a valid JSON format.")
            sys.exit(1)

        required_keys = ['port', 'userDatabase']

        missing_keys=[key for key in required_keys if key not in config]

        if missing_keys:
            missing_keys.sort()
            print(f"Error: {self.config_path} missing key(s): {', '.join(missing_keys)}")
            sys.exit(1)

        self.port = config['port']
        self.user_db_path = os.path.expanduser(config['userDatabase'])

        if not isinstance(self.port, int) or not (1024 <= self.port <= 65535):
            print("Error: Port is not valid. It should be an integer between 1024 and 65535.")
            sys.exit(1)

    def load_user_db(self):
        """
        Loads and validates the user database from the JSON file specified by user_db_path.
        The user database should be a JSON array where
        each element is a dictionary containing username and password keys.
        """
        if not os.path.exists(self.user_db_path):
            print(f"Error: {self.user_db_path} doesn\'t exist.")
            sys.exit(1)
        try:
            with open(self.user_db_path, 'r') as file:
                users = json.load(file)
        except json.JSONDecodeError:
            print(f"Error: {self.user_db_path} is not in a valid JSON format.")
            sys.exit(1)

        if not isinstance(users, list):
            print(f"Error: {self.user_db_path} is not a JSON array.")
            sys.exit(1)

        for user in users:
            if not all(k in user for k in ('username', 'password')):
                print(f"Error: {self.user_db_path} contains invalid user record formats.")
                sys.exit(1)
        return users
