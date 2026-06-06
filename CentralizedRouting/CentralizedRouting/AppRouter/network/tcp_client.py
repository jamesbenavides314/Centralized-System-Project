# AppRouter/network/tcp_client.py
# Capa de red: cliente TCP persistente para comunicación con el controller.
# NFR-05: maneja mensajes inválidos sin crashear.

import socket
import json
import threading
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

from shared.messages import decode

BUFFER_SIZE = 4096


class TCPClient:
    """
    Cliente TCP persistente usado por el router para comunicarse
    con el controller. Mantiene la conexión abierta para recibir
    la tabla de ruteo en cualquier momento (FR-06).
    """

    def __init__(self, controller_host: str, controller_port: int,
                 on_message_callback=None):
        self.controller_host = controller_host
        self.controller_port = controller_port
        self.on_message_callback = on_message_callback
        self._socket = None
        self._listener_thread = None

    def connect(self):
        """Abre la conexión TCP con el controller."""
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.connect((self.controller_host, self.controller_port))

    def start_listener(self):
        """Inicia un hilo que escucha mensajes entrantes del controller."""
        self._listener_thread = threading.Thread(
            target=self._listen, daemon=True
        )
        self._listener_thread.start()

    def _listen(self):
        """Bucle de escucha: procesa mensajes recibidos del controller."""
        buffer = ""
        while True:
            try:
                data = self._socket.recv(BUFFER_SIZE).decode("utf-8")
                if not data:
                    print("[TCP] Conexión cerrada por el controller.")
                    break
                buffer += data
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    if line.strip() and self.on_message_callback:
                        try:
                            msg = decode(line)
                            self.on_message_callback(msg)
                        except ValueError as e:
                            print(f"[TCP] Mensaje inválido ignorado: {e}")
            except (ConnectionResetError, OSError):
                print("[TCP] Conexión con el controller perdida.")
                break

    def send_message(self, message: dict):
        """Envía un mensaje JSON al controller."""
        raw = (json.dumps(message) + "\n").encode("utf-8")
        self._socket.sendall(raw)

    def wait(self):
        """Bloquea el hilo principal hasta que el listener termine."""
        if self._listener_thread:
            self._listener_thread.join()

    def close(self):
        if self._socket:
            self._socket.close()
