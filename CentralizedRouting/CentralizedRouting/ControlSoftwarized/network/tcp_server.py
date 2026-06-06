# ControlSoftwarized/network/tcp_server.py
# Servidor TCP multihilo: acepta conexiones de múltiples routers simultáneamente.
# NFR-05: maneja mensajes inválidos sin crashear.
# NFR-06: soporta 4+ routers en paralelo.

import socket
import threading
import json
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

from shared.messages import decode
from utils.safe_print import safe_print

BUFFER_SIZE = 4096


class TCPServer:
    """
    Servidor TCP multihilo para el controller.
    Cada router conectado se atiende en su propio hilo.
    """

    def __init__(self, host: str, port: int, message_handler):
        """
        message_handler: función callback que recibe (message: dict, conn: socket)
                         y retorna la respuesta (dict) o None si no hay respuesta inmediata.
        """
        self.host = host
        self.port = port
        self.message_handler = message_handler

    def start(self):
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((self.host, self.port))
        server_socket.listen(10)

        safe_print(f"\n[SERVER] Esperando conexiones en {self.host}:{self.port}...")

        while True:
            client_socket, client_address = server_socket.accept()
            safe_print(f"\n[SERVER] Nueva conexión desde {client_address}")
            thread = threading.Thread(
                target=self._handle_client,
                args=(client_socket,),
                daemon=True
            )
            thread.start()

    def _handle_client(self, conn: socket.socket):
        """Maneja todos los mensajes de un router conectado."""
        buffer = ""
        try:
            while True:
                data = conn.recv(BUFFER_SIZE).decode("utf-8")
                if not data:
                    break
                buffer += data
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    if line.strip():
                        self._process_line(line, conn)
        except (ConnectionResetError, OSError):
            safe_print("\n[SERVER] Router desconectado.")
        finally:
            conn.close()

    def _process_line(self, line: str, conn: socket.socket):
        """Decodifica el mensaje y llama al handler."""
        try:
            msg = decode(line)
        except ValueError as e:
            error_resp = json.dumps({
                "type": "ERROR",
                "message": f"JSON inválido: {e}"
            }) + "\n"
            conn.sendall(error_resp.encode("utf-8"))
            return

        try:
            # El handler puede enviar la respuesta directamente usando conn
            response = self.message_handler(msg, conn)
            # Si el handler retorna un dict, se lo enviamos al router
            if response is not None:
                raw = (json.dumps(response) + "\n").encode("utf-8")
                conn.sendall(raw)
        except Exception as error:
            error_resp = json.dumps({
                "type": "ERROR",
                "message": str(error)
            }) + "\n"
            conn.sendall(error_resp.encode("utf-8"))
