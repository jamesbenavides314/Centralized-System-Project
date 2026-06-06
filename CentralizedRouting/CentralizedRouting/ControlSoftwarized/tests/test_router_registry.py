# ControlSoftwarized/tests/test_router_registry.py
# TC-01 — FR-01: Verificar que el controller registra routers correctamente.
# Ejecutar desde ControlSoftwarized/: python -m pytest tests/test_router_registry.py -v

import sys
import os
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from model.router import Router
from service.registration_service import RouterRegistrationService
from shared.messages import build_register, TYPE_ACK, TYPE_ERROR


class TestRouterRegistry(unittest.TestCase):
    """
    TC-01 — FR-01: Registro del router con el controller.
    Precondición: controller activo (simulado con mock del DAO).
    """

    def setUp(self):
        """Crea un mock del DAO para aislar la lógica del service de MySQL."""
        self.mock_dao = MagicMock()
        self.service = RouterRegistrationService(router_dao=self.mock_dao)

    # ──────────────────────────────────────────
    # CASOS POSITIVOS
    # ──────────────────────────────────────────

    def test_registro_exitoso_retorna_ack(self):
        """
        TC-01a: Un mensaje REGISTER_ROUTER válido debe retornar ACK.
        Criterio de aceptación: el controller almacena R1 y confirma el registro.
        """
        message = build_register(
            router_id="R1",
            ip="127.0.0.1",
            port=5001,
            status="ACTIVE"
        )
        response = self.service.register_router(message)
        self.assertEqual(response["type"], TYPE_ACK)
        self.assertEqual(response["router_id"], "R1")

    def test_registro_guarda_router_en_dao(self):
        """
        TC-01b: El service debe llamar a save_router con los datos correctos.
        Verifica que la información llega al DAO (y por tanto a MySQL).
        """
        message = build_register("R2", "127.0.0.1", 5002)
        self.service.register_router(message)
        self.mock_dao.save_router.assert_called_once()
        router_guardado = self.mock_dao.save_router.call_args[0][0]
        self.assertIsInstance(router_guardado, Router)
        self.assertEqual(router_guardado.router_id, "R2")
        self.assertEqual(router_guardado.ip, "127.0.0.1")
        self.assertEqual(router_guardado.port, 5002)
        self.assertEqual(router_guardado.status, "ACTIVE")

    def test_registro_multiples_routers(self):
        """
        TC-01c: NFR-06 — El controller debe aceptar al menos 4 routers.
        """
        routers = [
            build_register("R1", "127.0.0.1", 5001),
            build_register("R2", "127.0.0.1", 5002),
            build_register("R3", "127.0.0.1", 5003),
            build_register("R4", "127.0.0.1", 5004),
        ]
        for msg in routers:
            response = self.service.register_router(msg)
            self.assertEqual(response["type"], TYPE_ACK,
                             f"Falló para {msg['router_id']}")

        self.assertEqual(self.mock_dao.save_router.call_count, 4)

    # ──────────────────────────────────────────
    # CASOS NEGATIVOS
    # ──────────────────────────────────────────

    def test_registro_sin_router_id_retorna_error(self):
        """
        TC-01d: Mensaje sin router_id debe retornar ERROR sin crashear.
        Criterio: NFR-05 — mensajes inválidos no rompen el sistema.
        """
        message = {"type": "REGISTER_ROUTER", "ip": "127.0.0.1", "port": 5001}
        response = self.service.register_router(message)
        self.assertEqual(response["type"], TYPE_ERROR)
        self.mock_dao.save_router.assert_not_called()

    def test_registro_sin_ip_retorna_error(self):
        """TC-01e: Mensaje sin campo 'ip' debe retornar ERROR."""
        message = {"type": "REGISTER_ROUTER", "router_id": "R1", "port": 5001}
        response = self.service.register_router(message)
        self.assertEqual(response["type"], TYPE_ERROR)

    def test_registro_sin_port_retorna_error(self):
        """TC-01f: Mensaje sin campo 'port' debe retornar ERROR."""
        message = {"type": "REGISTER_ROUTER", "router_id": "R1", "ip": "127.0.0.1"}
        response = self.service.register_router(message)
        self.assertEqual(response["type"], TYPE_ERROR)

    def test_registro_tipo_mensaje_incorrecto_retorna_error(self):
        """TC-01g: Mensaje con type incorrecto debe retornar ERROR."""
        message = {
            "type": "TOPOLOGY_UPDATE",
            "router_id": "R1",
            "ip": "127.0.0.1",
            "port": 5001,
            "status": "ACTIVE"
        }
        response = self.service.register_router(message)
        self.assertEqual(response["type"], TYPE_ERROR)

    def test_registro_mensaje_vacio_retorna_error(self):
        """TC-01h: Mensaje completamente vacío debe retornar ERROR."""
        response = self.service.register_router({})
        self.assertEqual(response["type"], TYPE_ERROR)


if __name__ == "__main__":
    unittest.main(verbosity=2)