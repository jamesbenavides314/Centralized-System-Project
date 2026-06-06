# ControlSoftwarized/tests/test_routing_table_service.py
# TC-04 / TC-05 - FR-05, FR-06: Tablas de ruteo generadas y enviadas correctamente.
# Ejecutar desde ControlSoftwarized/: python -m pytest tests/test_routing_table_service.py -v

import sys
import os
import json
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from model.router import NetworkTopology
from service.registration_service import RoutingService
from shared.messages import build_routing_table, TYPE_ROUTING_TABLE


def _build_topology(links: dict) -> NetworkTopology:
    t = NetworkTopology()
    t.adjacency = {src: dict(dsts) for src, dsts in links.items()}
    return t


class TestRoutingTableGeneration(unittest.TestCase):
    """TC-04 - FR-05: Tablas generadas con destination, next_hop y cost validos."""

    def setUp(self):
        self.mock_dao = MagicMock()
        self.topology = _build_topology({
            "R1": {"R2": 1, "R3": 4},
            "R2": {"R1": 1, "R3": 2, "R4": 5},
            "R3": {"R1": 4, "R2": 2, "R4": 1},
            "R4": {"R2": 5, "R3": 1}
        })
        self.service = RoutingService(self.mock_dao, self.topology)

    def test_tabla_R1_tiene_tres_destinos(self):
        """TC-04a: La tabla de R1 debe tener entradas para R2, R3 y R4."""
        tables = self.service.compute_all_tables()
        destinos = {e["destination"] for e in tables["R1"]}
        self.assertEqual(destinos, {"R2", "R3", "R4"})

    def test_tabla_R1_hacia_R4_costo_correcto(self):
        """
        TC-04b: R1->R4 por R1->R2(1)->R3(2)->R4(1) = costo 4
        vs R1->R3(4)->R4(1) = costo 5. Elige costo 4.
        """
        tables = self.service.compute_all_tables()
        entry = next(e for e in tables["R1"] if e["destination"] == "R4")
        self.assertEqual(entry["cost"], 4)
        self.assertEqual(entry["next_hop"], "R2")

    def test_tabla_generada_para_todos_los_routers(self):
        """TC-04c: compute_all_tables debe retornar tablas para los 4 routers."""
        tables = self.service.compute_all_tables()
        self.assertSetEqual(set(tables.keys()), {"R1", "R2", "R3", "R4"})

    def test_tabla_no_incluye_router_propio(self):
        """TC-04d: Ningun router debe aparecer en su propia tabla como destino."""
        tables = self.service.compute_all_tables()
        for router_id, table in tables.items():
            destinos = [e["destination"] for e in table]
            self.assertNotIn(router_id, destinos,
                             f"{router_id} no debe aparecer en su propia tabla")


class TestRoutingTableDelivery(unittest.TestCase):
    """TC-05 - FR-06: El controller envia la tabla correcta a cada socket TCP."""

    def setUp(self):
        self.mock_dao = MagicMock()
        self.topology = _build_topology({
            "R1": {"R2": 2, "R3": 5},
            "R2": {"R1": 2, "R3": 1},
            "R3": {"R1": 5, "R2": 1}
        })

    def _make_ctrl(self, topology=None):
        from controller.controller_app_controller import ControllerAppController
        with patch("controller.controller_app_controller.TCPServer"):
            ctrl = ControllerAppController(host="127.0.0.1", port=9000)
        ctrl.router_dao = self.mock_dao
        ctrl.topology = topology or self.topology
        ctrl.routing_service = RoutingService(self.mock_dao, ctrl.topology)
        return ctrl

    def test_mensaje_routing_table_tiene_tipo_correcto(self):
        """TC-05a: build_routing_table debe generar type=ROUTING_TABLE."""
        table = [
            {"destination": "R2", "next_hop": "R2", "cost": 2},
            {"destination": "R3", "next_hop": "R2", "cost": 3}
        ]
        msg = build_routing_table("R1", table)
        self.assertEqual(msg["type"], TYPE_ROUTING_TABLE)
        self.assertEqual(msg["router_id"], "R1")
        self.assertEqual(len(msg["table"]), 2)

    def test_tabla_enviada_por_socket(self):
        """
        TC-05b: Cada socket registrado debe recibir sendall con la tabla.
        """
        ctrl = self._make_ctrl()
        ctrl._registered_ids = {"R1", "R2", "R3"}
        mock_R1, mock_R2, mock_R3 = MagicMock(), MagicMock(), MagicMock()
        ctrl._connections = {"R1": mock_R1, "R2": mock_R2, "R3": mock_R3}

        with patch("builtins.print"):
            ctrl._compute_and_distribute()

        self.assertTrue(mock_R1.sendall.called, "R1 no recibio su tabla")
        self.assertTrue(mock_R2.sendall.called, "R2 no recibio su tabla")
        self.assertTrue(mock_R3.sendall.called, "R3 no recibio su tabla")

    def test_tabla_enviada_es_json_valido(self):
        """TC-05c: Los bytes enviados por sendall deben ser JSON decodificable."""
        ctrl = self._make_ctrl(topology=_build_topology({
            "R1": {"R2": 3}, "R2": {"R1": 3}
        }))
        ctrl._registered_ids = {"R1", "R2"}
        mock_conn = MagicMock()
        ctrl._connections = {"R1": mock_conn, "R2": mock_conn}

        with patch("builtins.print"):
            ctrl._compute_and_distribute()

        self.assertTrue(mock_conn.sendall.called)
        sent_bytes = mock_conn.sendall.call_args_list[0][0][0]
        parsed = json.loads(sent_bytes.decode("utf-8").strip())
        self.assertEqual(parsed["type"], TYPE_ROUTING_TABLE)
        self.assertIn("table", parsed)

    def test_router_sin_conexion_no_crashea_controller(self):
        """
        TC-05d: NFR-05 - Si un router no tiene socket activo,
        el controller no debe lanzar excepcion.
        """
        ctrl = self._make_ctrl(topology=_build_topology({
            "R1": {"R2": 3}, "R2": {"R1": 3}
        }))
        ctrl._registered_ids = {"R1", "R2"}
        ctrl._connections = {"R1": MagicMock()}   # R2 sin socket

        try:
            with patch("builtins.print"):
                ctrl._compute_and_distribute()
        except Exception as e:
            self.fail(f"_compute_and_distribute lanzo excepcion inesperada: {e}")


if __name__ == "__main__":
    unittest.main(verbosity=2)