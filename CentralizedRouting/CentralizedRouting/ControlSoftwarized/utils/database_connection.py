# ControlSoftwarized/utils/database_connection.py
# Utilidad: crea conexiones MySQL usando mysql-connector-python.
# La base de datos se llama centralized_routing_db.

import json
from pathlib import Path

import mysql.connector
from mysql.connector import Error


class DatabaseConnection:
    """
    Clase utilitaria responsable de crear conexiones MySQL.
    Lee la configuración desde config/database_config.json.
    """

    def __init__(self, config_path: str = "config/database_config.json"):
        self.config_path = config_path
        self.config = self._load_config()

    def _load_config(self) -> dict:
        config_file = Path(self.config_path)
        if not config_file.exists():
            raise FileNotFoundError(
                f"Archivo de configuración de BD no encontrado: {self.config_path}"
            )
        with open(config_file, "r", encoding="utf-8") as file:
            return json.load(file)

    def get_connection(self):
        """
        Retorna una nueva conexión MySQL.
        Lanza ConnectionError si no puede conectar.
        """
        try:
            connection = mysql.connector.connect(
                host=self.config["host"],
                port=self.config["port"],
                user=self.config["user"],
                password=self.config["password"],
                database=self.config["database"]
            )
            return connection
        except Error as error:
            raise ConnectionError(
                f"Error al conectar con MySQL: {error}"
            )
