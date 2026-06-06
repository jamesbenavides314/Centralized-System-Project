# AppRouter/tests/test_registration.py
# TC-01 (lado router) — FR-01: Verificar que el router construye y envía
#                               correctamente el mensaje de registro.
# Ejecutar desde AppRouter/: python -m pytest tests/test_registration.py -v

import sys
import os
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from model.router import Router, Neighbor
from service.registration_service import (
    RegistrationService, TopologyService, LinkUpdateService
)
from shared.messages import TYPE_REGISTER, TYPE_TOPOLOGY, TYPE_LINK_UPDATE


class TestRegistrationService(unittest.TestCase):
    """
    TC-01 (AppRouter) — FR-01: El router debe construir un mensaje
    REGISTER_ROUTER con router_id, ip y port correctos.
    """

    def _make_router(self, router_id="R1", ip="127.0.0.1", port=5001):
        return Router(router_id=router_id, ip=ip, port=port, status="ACTIVE")

    def test_mensaje_registro_tiene_type_correcto(self):
        """TC-01a: El mensaje debe tener type = REGISTER_ROUTER."""
        router = self._make_router()
        msg = RegistrationService.create_registration_message(router)
        self.assertEqual(msg["type"], TYPE_REGISTER)

    def test_mensaje_registro_contiene_router_id(self):
        """TC-01b: El mensaje debe incluir el router_id correcto."""
        router = self._make_router("R2")
        msg = RegistrationService.create_registration_message(router)
        self.assertEqual(msg["router_id"], "R2")

    def test_mensaje_registro_contiene_ip(self):
        """TC-01c: El mensaje debe incluir la IP del router."""
        router = self._make_router(ip="192.168.1.10")
        msg = RegistrationService.create_registration_message(router)
        self.assertEqual(msg["ip"], "192.168.1.10")

    def test_mensaje_registro_contiene_port(self):
        """TC-01d: El mensaje debe incluir el puerto del router."""
        router = self._make_router(port=5003)
        msg = RegistrationService.create_registration_message(router)
        self.assertEqual(msg["port"], 5003)

    def test_mensaje_registro_contiene_status(self):
        """TC-01e: El mensaje debe incluir el status del router."""
        router = self._make_router()
        msg = RegistrationService.create_registration_message(router)
        self.assertIn("status", msg)
        self.assertEqual(msg["status"], "ACTIVE")

    def test_mensaje_registro_es_dict(self):
        """TC-01f: El resultado debe ser un dict (serializable a JSON)."""
        router = self._make_router()
        msg = RegistrationService.create_registration_message(router)
        self.assertIsInstance(msg, dict)

    def test_campos_obligatorios_presentes(self):
        """TC-01g: El mensaje debe contener exactamente los campos requeridos."""
        router = self._make_router()
        msg = RegistrationService.create_registration_message(router)
        for campo in ["type", "router_id", "ip", "port", "status"]:
            self.assertIn(campo, msg, f"Campo faltante: {campo}")


class TestTopologyServiceRouter(unittest.TestCase):
    """
    TC-02 (AppRouter) — FR-02: El router debe construir correctamente
    el mensaje TOPOLOGY_UPDATE con la lista de vecinos y costos.
    """

    def test_mensaje_topologia_type_correcto(self):
        """TC-02a: El mensaje debe tener type = TOPOLOGY_UPDATE."""
        router = Router(
            router_id="R1", ip="127.0.0.1", port=5001, status="ACTIVE",
            neighbors=[Neighbor("R2", 10), Neighbor("R3", 5)]
        )
        msg = TopologyService.create_topology_message(router)
        self.assertEqual(msg["type"], TYPE_TOPOLOGY)

    def test_mensaje_topologia_incluye_vecinos(self):
        """TC-02b: El mensaje debe incluir la lista de vecinos con sus costos."""
        router = Router(
            router_id="R1", ip="127.0.0.1", port=5001, status="ACTIVE",
            neighbors=[Neighbor("R2", 10), Neighbor("R3", 5)]
        )
        msg = TopologyService.create_topology_message(router)
        self.assertEqual(len(msg["neighbors"]), 2)

    def test_mensaje_topologia_formato_vecinos(self):
        """TC-02c: Cada vecino debe tener neighbor_id y cost."""
        router = Router(
            router_id="R1", ip="127.0.0.1", port=5001, status="ACTIVE",
            neighbors=[Neighbor("R2", 10)]
        )
        msg = TopologyService.create_topology_message(router)
        vecino = msg["neighbors"][0]
        self.assertIn("neighbor_id", vecino)
        self.assertIn("cost", vecino)
        self.assertEqual(vecino["neighbor_id"], "R2")
        self.assertEqual(vecino["cost"], 10)

    def test_mensaje_topologia_sin_vecinos(self):
        """TC-02d: Un router sin vecinos debe enviar una lista vacía."""
        router = Router(
            router_id="R1", ip="127.0.0.1", port=5001,
            status="ACTIVE", neighbors=[]
        )
        msg = TopologyService.create_topology_message(router)
        self.assertEqual(msg["neighbors"], [])


class TestLinkUpdateServiceRouter(unittest.TestCase):
    """
    TC-07 (AppRouter) — FR-08: El router debe construir correctamente
    el mensaje LINK_UPDATE con el nuevo costo del enlace.
    """

    def test_mensaje_link_update_type_correcto(self):
        """TC-07a: El mensaje debe tener type = LINK_UPDATE."""
        msg = LinkUpdateService.create_link_update_message("R1", "R3", 1)
        self.assertEqual(msg["type"], TYPE_LINK_UPDATE)

    def test_mensaje_link_update_contiene_campos(self):
        """TC-07b: El mensaje debe contener router_id, neighbor_id y new_cost."""
        msg = LinkUpdateService.create_link_update_message("R1", "R3", 1)
        self.assertEqual(msg["router_id"], "R1")
        self.assertEqual(msg["neighbor_id"], "R3")
        self.assertEqual(msg["new_cost"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)