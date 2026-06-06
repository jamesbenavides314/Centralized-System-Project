# ControlSoftwarized/tests/test_controller_communication.py
# TC-08 — NFR-05: Verificar que el controller maneja mensajes invalidos
#                  sin crashear y responde con ERROR.
# Ejecutar desde ControlSoftwarized/: python -m pytest tests/test_controller_communication.py -v

import sys
import os
import json
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from network.tcp_server import TCPServer
from shared.messages import decode, TYPE_ERROR, TYPE_ACK


class TestJsonDecoding(unittest.TestCase):
    """
    TC-08 — NFR-05: El modulo shared/messages.py debe rechazar JSON
    malformado levantando ValueError.
    """

    def test_json_valido_retorna_dict(self):
        """TC-08a: Un JSON correcto debe decodificarse sin error."""
        raw = '{"type": "REGISTER_ROUTER", "router_id": "R1"}'
        msg = decode(raw)
        self.assertIsInstance(msg, dict)
        self.assertEqual(msg["type"], "REGISTER_ROUTER")

    def test_json_malformado_lanza_value_error(self):
        """TC-08b: JSON con sintaxis rota debe lanzar ValueError."""
        with self.assertRaises(ValueError):
            decode('{type: REGISTER_ROUTER, router_id: R1')

    def test_string_vacio_lanza_value_error(self):
        """TC-08c: Un string vacio debe lanzar ValueError."""
        with self.assertRaises(ValueError):
            decode("")

    def test_solo_espacios_lanza_value_error(self):
        """TC-08d: Un string con solo espacios debe lanzar ValueError."""
        with self.assertRaises(ValueError):
            decode("   ")

    def test_json_con_comillas_simples_lanza_value_error(self):
        """TC-08e: JSON con comillas simples (invalido) debe lanzar ValueError."""
        with self.assertRaises(ValueError):
            decode("{'type': 'REGISTER_ROUTER'}")


class TestTCPServerErrorHandling(unittest.TestCase):
    """
    TC-08 — NFR-05: El TCPServer debe responder con ERROR al recibir
    JSON invalido sin terminar el proceso del controller.
    Nota: patch sobre builtins.print porque safe_print puede estar en
    utils.safe_print (fix aplicado) o aun no existir en el modulo.
    """

    def _make_server(self):
        handler = MagicMock(return_value=None)
        return TCPServer(host="127.0.0.1", port=9000, message_handler=handler)

    def test_json_invalido_envia_respuesta_error(self):
        """
        TC-08f: Al procesar una linea con JSON invalido, el servidor
        debe llamar sendall con un mensaje de tipo ERROR.
        """
        server = self._make_server()
        mock_conn = MagicMock()
        with patch("builtins.print"):
            server._process_line('{broken json', mock_conn)

        self.assertTrue(mock_conn.sendall.called,
                        "El servidor debe enviar una respuesta de error")
        sent = json.loads(mock_conn.sendall.call_args[0][0].decode("utf-8"))
        self.assertEqual(sent["type"], TYPE_ERROR)

    def test_json_invalido_no_llama_handler(self):
        """
        TC-08g: Un JSON invalido no debe llegar al message_handler.
        """
        mock_handler = MagicMock(return_value=None)
        server = TCPServer("127.0.0.1", 9000, mock_handler)
        mock_conn = MagicMock()
        with patch("builtins.print"):
            server._process_line("not valid json at all", mock_conn)
        mock_handler.assert_not_called()

    def test_mensaje_valido_llega_al_handler(self):
        """TC-08h: Un mensaje JSON valido si debe llegar al handler."""
        mock_handler = MagicMock(return_value={"type": TYPE_ACK, "router_id": "R1", "message": "ok"})
        server = TCPServer("127.0.0.1", 9000, mock_handler)
        mock_conn = MagicMock()
        valid_line = json.dumps({"type": "REGISTER_ROUTER", "router_id": "R1",
                                 "ip": "127.0.0.1", "port": 5001, "status": "ACTIVE"})
        with patch("builtins.print"):
            server._process_line(valid_line, mock_conn)
        mock_handler.assert_called_once()

    def test_excepcion_en_handler_envia_error_al_router(self):
        """
        TC-08i: NFR-05 — Si el handler lanza una excepcion inesperada,
        el servidor debe atraparla y responder con ERROR, sin crashear.
        """
        def handler_roto(msg, conn):
            raise RuntimeError("Error interno simulado")

        server = TCPServer("127.0.0.1", 9000, handler_roto)
        mock_conn = MagicMock()
        valid_line = json.dumps({"type": "REGISTER_ROUTER", "router_id": "R1",
                                 "ip": "127.0.0.1", "port": 5001, "status": "ACTIVE"})
        with patch("builtins.print"):
            try:
                server._process_line(valid_line, mock_conn)
            except Exception as e:
                self.fail(f"El servidor lanzo excepcion no controlada: {e}")

        sent = json.loads(mock_conn.sendall.call_args[0][0].decode("utf-8"))
        self.assertEqual(sent["type"], TYPE_ERROR)


class TestControllerMessageDispatch(unittest.TestCase):
    """
    Pruebas de despacho de mensajes: tipos soportados e invalidos.
    """

    def setUp(self):
        from controller.controller_app_controller import ControllerAppController
        with patch("controller.controller_app_controller.TCPServer"):
            self.ctrl = ControllerAppController(host="127.0.0.1", port=9000)

    def test_tipo_desconocido_retorna_error(self):
        """TC-08j: Un mensaje con type desconocido debe retornar ERROR."""
        msg = {"type": "UNKNOWN_TYPE", "router_id": "R1"}
        response = self.ctrl.handle_message(msg, conn=None)
        self.assertEqual(response["type"], TYPE_ERROR)

    def test_mensaje_sin_type_retorna_error(self):
        """TC-08k: Un mensaje sin campo 'type' debe retornar ERROR."""
        msg = {"router_id": "R1", "ip": "127.0.0.1"}
        response = self.ctrl.handle_message(msg, conn=None)
        self.assertEqual(response["type"], TYPE_ERROR)


if __name__ == "__main__":
    unittest.main(verbosity=2)