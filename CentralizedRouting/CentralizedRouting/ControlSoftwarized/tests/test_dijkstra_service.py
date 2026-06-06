# ControlSoftwarized/tests/test_dijkstra_service.py
# TC-03 — FR-04: Verificar que Dijkstra calcula el camino más corto correctamente.
# TC-04 — FR-05: Verificar que las tablas de ruteo generadas son correctas.
# Ejecutar desde ControlSoftwarized/: python -m pytest tests/test_dijkstra_service.py -v

import sys
import os
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from model.router import NetworkTopology
from service.registration_service import RoutingService, LinkUpdateService


def _build_topology(links: dict) -> NetworkTopology:
    """
    Helper: construye una NetworkTopology desde un dict de adyacencia.
    links: { "R1": {"R2": 2, "R3": 5}, "R2": {"R3": 1}, ... }
    """
    t = NetworkTopology()
    t.adjacency = {src: dict(dsts) for src, dsts in links.items()}
    return t


class TestDijkstraService(unittest.TestCase):
    """
    TC-03 — FR-04: Cálculo de caminos más cortos con Dijkstra (networkx).
    Topología de referencia del plan de pruebas:
        R1 ─(2)─ R2 ─(1)─ R3
        R1 ─(5)──────────  R3
    Camino más corto R1 → R3: R1 → R2 → R3, costo total 3.
    """

    def setUp(self):
        self.mock_dao = MagicMock()

    def _get_entry(self, table: list, destination: str) -> dict:
        """Helper: retorna la entrada de la tabla para un destino dado."""
        for entry in table:
            if entry["destination"] == destination:
                return entry
        return None

    # ──────────────────────────────────────────
    # TC-03: DIJKSTRA — CAMINOS CORRECTOS
    # ──────────────────────────────────────────

    def test_dijkstra_camino_R1_a_R3_via_R2(self):
        """
        TC-03a: R1→R3 debe elegir el camino R1→R2→R3 (costo 3)
        sobre el directo R1→R3 (costo 5).
        """
        topology = _build_topology({
            "R1": {"R2": 2, "R3": 5},
            "R2": {"R1": 2, "R3": 1},
            "R3": {"R1": 5, "R2": 1}
        })
        service = RoutingService(self.mock_dao, topology)
        tables = service.compute_all_tables()

        entry = self._get_entry(tables["R1"], "R3")
        self.assertIsNotNone(entry, "No hay entrada para R3 en la tabla de R1")
        self.assertEqual(entry["next_hop"], "R2",
                         "El siguiente salto de R1→R3 debe ser R2")
        self.assertEqual(entry["cost"], 3,
                         "El costo mínimo R1→R3 debe ser 3 (via R2)")

    def test_dijkstra_camino_directo_cuando_es_optimo(self):
        """
        TC-03b: Si el camino directo es el más corto, next_hop debe ser el destino.
        R1→R2 directo (costo 2) vs R1→R3→R2 (costo 5+1=6). Elige directo.
        """
        topology = _build_topology({
            "R1": {"R2": 2, "R3": 5},
            "R2": {"R1": 2, "R3": 1},
            "R3": {"R1": 5, "R2": 1}
        })
        service = RoutingService(self.mock_dao, topology)
        tables = service.compute_all_tables()

        entry = self._get_entry(tables["R1"], "R2")
        self.assertEqual(entry["next_hop"], "R2")
        self.assertEqual(entry["cost"], 2)

    def test_dijkstra_con_cuatro_routers(self):
        """
        TC-03c: NFR-06 — El algoritmo debe funcionar correctamente con 4 routers.
        Topología:
            R1─(1)─R2─(2)─R4
            R1─(4)─R3─(1)─R4
        R1→R4 debe ir por R1→R2→R4 (costo 3) en vez de R1→R3→R4 (costo 5).
        """
        topology = _build_topology({
            "R1": {"R2": 1, "R3": 4},
            "R2": {"R1": 1, "R4": 2},
            "R3": {"R1": 4, "R4": 1},
            "R4": {"R2": 2, "R3": 1}
        })
        service = RoutingService(self.mock_dao, topology)
        tables = service.compute_all_tables()

        entry = self._get_entry(tables["R1"], "R4")
        self.assertEqual(entry["next_hop"], "R2")
        self.assertEqual(entry["cost"], 3)

    def test_dijkstra_simetria_de_costos(self):
        """
        TC-03d: Si la topología es simétrica, los costos deben ser iguales
        en ambas direcciones (R1→R2 y R2→R1).
        """
        topology = _build_topology({
            "R1": {"R2": 7},
            "R2": {"R1": 7}
        })
        service = RoutingService(self.mock_dao, topology)
        tables = service.compute_all_tables()

        self.assertEqual(self._get_entry(tables["R1"], "R2")["cost"], 7)
        self.assertEqual(self._get_entry(tables["R2"], "R1")["cost"], 7)

    # ──────────────────────────────────────────
    # TC-04: GENERACIÓN DE TABLAS DE RUTEO — FR-05
    # ──────────────────────────────────────────

    def test_tabla_contiene_todos_los_destinos(self):
        """
        TC-04a: La tabla de R1 debe tener una entrada para cada router
        distinto en la topología.
        """
        topology = _build_topology({
            "R1": {"R2": 1, "R3": 4},
            "R2": {"R1": 1, "R3": 2},
            "R3": {"R1": 4, "R2": 2}
        })
        service = RoutingService(self.mock_dao, topology)
        tables = service.compute_all_tables()

        destinos_R1 = {e["destination"] for e in tables["R1"]}
        self.assertIn("R2", destinos_R1)
        self.assertIn("R3", destinos_R1)
        self.assertNotIn("R1", destinos_R1,  # No debe incluirse a sí mismo
                         "La tabla no debe contener al propio router como destino")

    def test_tabla_tiene_campos_requeridos(self):
        """
        TC-04b: Cada entrada de la tabla debe contener destination, next_hop y cost.
        """
        topology = _build_topology({
            "R1": {"R2": 3},
            "R2": {"R1": 3}
        })
        service = RoutingService(self.mock_dao, topology)
        tables = service.compute_all_tables()

        for entry in tables["R1"]:
            self.assertIn("destination", entry)
            self.assertIn("next_hop", entry)
            self.assertIn("cost", entry)

    def test_tabla_se_genera_para_todos_los_routers(self):
        """
        TC-04c: compute_all_tables debe generar tablas para R1, R2 y R3.
        """
        topology = _build_topology({
            "R1": {"R2": 1},
            "R2": {"R1": 1, "R3": 2},
            "R3": {"R2": 2}
        })
        service = RoutingService(self.mock_dao, topology)
        tables = service.compute_all_tables()
        self.assertIn("R1", tables)
        self.assertIn("R2", tables)
        self.assertIn("R3", tables)

    def test_tabla_persiste_en_dao(self):
        """
        TC-04d: save_routing_table debe ser llamado para cada router
        tras el cálculo, asegurando persistencia en MySQL.
        """
        topology = _build_topology({
            "R1": {"R2": 1},
            "R2": {"R1": 1, "R3": 2},
            "R3": {"R2": 2}
        })
        service = RoutingService(self.mock_dao, topology)
        service.compute_all_tables()
        self.assertEqual(self.mock_dao.save_routing_table.call_count, 3)

    def test_tabla_costo_nunca_negativo(self):
        """
        TC-04e: Ninguna entrada de la tabla debe tener costo negativo o cero.
        """
        topology = _build_topology({
            "R1": {"R2": 2, "R3": 5},
            "R2": {"R1": 2, "R3": 1},
            "R3": {"R1": 5, "R2": 1}
        })
        service = RoutingService(self.mock_dao, topology)
        tables = service.compute_all_tables()
        for router_id, table in tables.items():
            for entry in table:
                self.assertGreater(entry["cost"], 0,
                                   f"Costo inválido en tabla de {router_id}: {entry}")


class TestLinkUpdateService(unittest.TestCase):
    """
    TC-07 — FR-08: Verificar que un cambio de costo de enlace actualiza
    la topología y recalcula las rutas correctamente.
    """

    def setUp(self):
        self.mock_dao = MagicMock()

    def test_link_update_cambia_costo_en_topologia(self):
        """
        TC-07a: Tras LINK_UPDATE, el costo del enlace debe reflejarse
        en topology.adjacency.
        """
        topology = _build_topology({
            "R1": {"R3": 5},
            "R3": {"R1": 5}
        })
        routing_service = RoutingService(self.mock_dao, topology)
        service = LinkUpdateService(self.mock_dao, topology, routing_service)

        message = {"type": "LINK_UPDATE", "router_id": "R1",
                   "neighbor_id": "R3", "new_cost": 1}
        service.update_link(message)

        self.assertEqual(topology.adjacency["R1"]["R3"], 1)

    def test_link_update_recalcula_ruta_optima(self):
        """
        TC-07b: Después de cambiar el costo R1-R3 de 5 a 1, R1→R3 debe
        ir directo (next_hop=R3, costo=1) en lugar de pasar por R2.
        """
        topology = _build_topology({
            "R1": {"R2": 2, "R3": 5},
            "R2": {"R1": 2, "R3": 1},
            "R3": {"R1": 5, "R2": 1}
        })
        routing_service = RoutingService(self.mock_dao, topology)
        link_service = LinkUpdateService(self.mock_dao, topology, routing_service)

        # Antes del cambio: R1→R3 vía R2 (costo 3)
        tables_antes = routing_service.compute_all_tables()
        entry_antes = next(e for e in tables_antes["R1"] if e["destination"] == "R3")
        self.assertEqual(entry_antes["next_hop"], "R2")
        self.assertEqual(entry_antes["cost"], 3)

        # Actualizar costo R1-R3 a 1
        link_service.update_link({
            "type": "LINK_UPDATE",
            "router_id": "R1",
            "neighbor_id": "R3",
            "new_cost": 1
        })
        # Recalcular tras el cambio
        tables_despues = routing_service.compute_all_tables()
        entry_despues = next(e for e in tables_despues["R1"] if e["destination"] == "R3")
        self.assertEqual(entry_despues["next_hop"], "R3",
                         "Tras el cambio, R1→R3 debe ir directo")
        self.assertEqual(entry_despues["cost"], 1)

    def test_link_update_sin_campos_retorna_error(self):
        """
        TC-07c: NFR-05 — LINK_UPDATE incompleto debe retornar ERROR.
        """
        topology = _build_topology({"R1": {"R2": 5}})
        routing_service = RoutingService(self.mock_dao, topology)
        service = LinkUpdateService(self.mock_dao, topology, routing_service)

        response = service.update_link({"type": "LINK_UPDATE"})
        from shared.messages import TYPE_ERROR
        self.assertEqual(response["type"], TYPE_ERROR)

    def test_link_update_persiste_en_dao(self):
        """
        TC-07d: El nuevo costo debe guardarse en MySQL vía save_topology_link.
        """
        topology = _build_topology({"R1": {"R3": 5}, "R3": {"R1": 5}})
        routing_service = RoutingService(self.mock_dao, topology)
        service = LinkUpdateService(self.mock_dao, topology, routing_service)

        service.update_link({
            "type": "LINK_UPDATE",
            "router_id": "R1",
            "neighbor_id": "R3",
            "new_cost": 2
        })
        self.mock_dao.save_topology_link.assert_called_with("R1", "R3", 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)