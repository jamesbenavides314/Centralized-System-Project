# AppRouter/tests/test_router_communication.py
# TC-05 (red) — FR-06: Verificar que el cliente TCP del router
#               envía y recibe mensajes correctamente.
# Ejecutar desde AppRouter/: python -m pytest tests/test_router_communication.py -v

import sys
import os
import json
import unittest
from unittest.mock import MagicMock, patch, call

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from network.tcp_client import TCPClient
from shared.messages import (
    build_register, build_topology, build_routing_table,
    encode, decode, TYPE_ROUTING_TABLE, TYPE_ACK, TYPE_ERROR
)


class TestMessageEncoding(unittest.TestCase):
    """
    NFR-04: Todos los mensajes deben ser JSON válido codificado en UTF-8
    con delimitador de nueva línea.
    """

    def test_encode_produce_bytes(self):
        """TC-NFR04a: encode() debe retornar bytes."""
        msg = build_register("R1", "127.0.0.1", 5001)
        result = encode(msg)
        self.assertIsInstance(result, bytes)

    def test_encode_termina_con_newline(self):
        """TC-NFR04b: El mensaje codificado debe terminar con '\\n'."""
        msg = build_register("R1", "127.0.0.1", 5001)
        result = encode(msg).decode("utf-8")
        self.assertTrue(result.endswith("\n"))

    def test_encode_decode_simetria(self):
        """
        TC-NFR04c: encode() seguido de decode() debe recuperar el dict original.
        """
        original = build_register("R2", "127.0.0.1", 5002)
        encoded = encode(original).decode("utf-8")
        recovered = decode(encoded)
        self.assertEqual(recovered["type"], original["type"])
        self.assertEqual(recovered["router_id"], original["router_id"])
        self.assertEqual(recovered["ip"], original["ip"])
        self.assertEqual(recovered["port"], original["port"])

    def test_mensaje_registro_es_json_valido(self):
        """TC-NFR04d: El mensaje REGISTER_ROUTER debe ser JSON válido."""
        msg = build_register("R1", "127.0.0.1", 5001)
        raw = encode(msg).decode("utf-8").strip()
        parsed = json.loads(raw)
        self.assertEqual(parsed["type"], "REGISTER_ROUTER")

    def test_mensaje_topologia_es_json_valido(self):
        """TC-NFR04e: El mensaje TOPOLOGY_UPDATE debe ser JSON válido."""
        msg = build_topology("R1", [{"neighbor_id": "R2", "cost": 5}])
        raw = encode(msg).decode("utf-8").strip()
        parsed = json.loads(raw)
        self.assertEqual(parsed["type"], "TOPOLOGY_UPDATE")

    def test_mensaje_routing_table_es_json_valido(self):
        """TC-NFR04f: El mensaje ROUTING_TABLE debe ser JSON válido."""
        table = [{"destination": "R2", "next_hop": "R2", "cost": 2}]
        msg = build_routing_table("R1", table)
        raw = encode(msg).decode("utf-8").strip()
        parsed = json.loads(raw)
        self.assertEqual(parsed["type"], "ROUTING_TABLE")
        self.assertIn("table", parsed)


class TestTCPClientSend(unittest.TestCase):
    """
    TC-05 (red) — FR-06: El TCPClient debe enviar mensajes JSON
    correctamente por el socket.
    """

    def _make_client_with_mock_socket(self):
        client = TCPClient("127.0.0.1", 9000)
        mock_socket = MagicMock()
        client._socket = mock_socket
        return client, mock_socket

    def test_send_message_llama_sendall(self):
        """TC-05-net-a: send_message debe llamar sendall en el socket."""
        client, mock_socket = self._make_client_with_mock_socket()
        msg = build_register("R1", "127.0.0.1", 5001)
        client.send_message(msg)
        mock_socket.sendall.assert_called_once()

    def test_send_message_envia_bytes(self):
        """TC-05-net-b: El argumento de sendall debe ser bytes."""
        client, mock_socket = self._make_client_with_mock_socket()
        client.send_message(build_register("R1", "127.0.0.1", 5001))
        sent = mock_socket.sendall.call_args[0][0]
        self.assertIsInstance(sent, bytes)

    def test_send_message_json_decodificable(self):
        """TC-05-net-c: Los bytes enviados deben ser JSON decodificable."""
        client, mock_socket = self._make_client_with_mock_socket()
        msg = build_topology("R1", [{"neighbor_id": "R2", "cost": 3}])
        client.send_message(msg)
        sent_bytes = mock_socket.sendall.call_args[0][0]
        parsed = json.loads(sent_bytes.decode("utf-8").strip())
        self.assertEqual(parsed["type"], "TOPOLOGY_UPDATE")

    def test_send_registro_preserva_datos(self):
        """TC-05-net-d: Los datos enviados deben coincidir con el mensaje original."""
        client, mock_socket = self._make_client_with_mock_socket()
        msg = build_register("R3", "10.0.0.3", 5003)
        client.send_message(msg)
        sent_bytes = mock_socket.sendall.call_args[0][0]
        parsed = json.loads(sent_bytes.decode("utf-8").strip())
        self.assertEqual(parsed["router_id"], "R3")
        self.assertEqual(parsed["ip"], "10.0.0.3")
        self.assertEqual(parsed["port"], 5003)


class TestTCPClientReceive(unittest.TestCase):
    """
    TC-05 / TC-06 (red) — FR-06, FR-07: El TCPClient debe invocar el callback
    al recibir mensajes del controller y manejar JSON inválido sin crashear.
    """

    def test_callback_invocado_al_recibir_routing_table(self):
        """
        TC-05-net-e: Al recibir un mensaje ROUTING_TABLE válido,
        on_message_callback debe ser invocado con el dict correcto.
        """
        received = []
        client = TCPClient("127.0.0.1", 9000, on_message_callback=received.append)
        mock_socket = MagicMock()
        table_msg = build_routing_table("R1", [
            {"destination": "R2", "next_hop": "R2", "cost": 2}
        ])
        encoded_line = json.dumps(table_msg) + "\n"
        # Simular recv: primera llamada devuelve el mensaje, segunda devuelve vacío
        mock_socket.recv.side_effect = [
            encoded_line.encode("utf-8"),
            b""
        ]
        client._socket = mock_socket
        client._listen()

        self.assertEqual(len(received), 1)
        self.assertEqual(received[0]["type"], TYPE_ROUTING_TABLE)

    def test_json_invalido_no_crashea_listener(self):
        """
        TC-08 (AppRouter) — NFR-05: El listener debe ignorar líneas con JSON
        inválido sin terminar el hilo ni lanzar excepción.
        """
        received = []
        client = TCPClient("127.0.0.1", 9000, on_message_callback=received.append)
        mock_socket = MagicMock()
        mock_socket.recv.side_effect = [
            b"{broken json\n",
            b""
        ]
        client._socket = mock_socket
        try:
            client._listen()
        except Exception as e:
            self.fail(f"_listen lanzó excepción con JSON inválido: {e}")
        self.assertEqual(len(received), 0,
                         "El callback no debe ser invocado con JSON inválido")

    def test_multiples_mensajes_en_buffer(self):
        """
        TC-05-net-f: El listener debe manejar múltiples mensajes llegando
        en un solo recv (fragmentación TCP inversa).
        """
        received = []
        client = TCPClient("127.0.0.1", 9000, on_message_callback=received.append)
        mock_socket = MagicMock()

        msg1 = json.dumps({"type": TYPE_ACK, "router_id": "R1", "message": "ok"}) + "\n"
        msg2 = json.dumps(build_routing_table("R1", [
            {"destination": "R2", "next_hop": "R2", "cost": 1}
        ])) + "\n"

        mock_socket.recv.side_effect = [
            (msg1 + msg2).encode("utf-8"),
            b""
        ]
        client._socket = mock_socket
        client._listen()

        self.assertEqual(len(received), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)