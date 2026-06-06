# ControlSoftwarized/tests/test_topology.py
# TC-02 — FR-02, FR-03: Verificar que el controller recibe y almacena
#          la información de vecinos y construye la topología correctamente.
# Ejecutar desde ControlSoftwarized/: python -m pytest tests/test_topology.py -v

import sys
import os
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from model.router import NetworkTopology
from service.registration_service import TopologyService
from shared.messages import build_topology, TYPE_ACK, TYPE_ERROR


class TestTopologyUpdate(unittest.TestCase):
    """
    TC-02 — FR-02 / FR-03: Envío de información de vecinos y almacenamiento
    de la topología de red en el controller.
    Precondición: controller y routers activos (simulados con mocks).
    """

    def setUp(self):
        self.mock_dao = MagicMock()
        self.topology = NetworkTopology()
        self.service = TopologyService(
            router_dao=self.mock_dao,
            topology=self.topology
        )

    # ──────────────────────────────────────────
    # CASOS POSITIVOS
    # ──────────────────────────────────────────

    def test_topologia_actualiza_adyacencia_en_memoria(self):
        """
        TC-02a: Los vecinos de R1 deben quedar registrados en el grafo en memoria.
        Input: R1 → vecinos R2 (costo 10) y R3 (costo 5).
        Resultado esperado: topology.adjacency["R1"] = {"R2": 10, "R3": 5}.
        """
        message = build_topology("R1", [
            {"neighbor_id": "R2", "cost": 10},
            {"neighbor_id": "R3", "cost": 5}
        ])
        self.service.update_topology(message)
        self.assertIn("R1", self.topology.adjacency)
        self.assertEqual(self.topology.adjacency["R1"]["R2"], 10)
        self.assertEqual(self.topology.adjacency["R1"]["R3"], 5)

    def test_topologia_retorna_ack(self):
        """TC-02b: Un mensaje de topología válido debe retornar ACK."""
        message = build_topology("R1", [{"neighbor_id": "R2", "cost": 10}])
        response = self.service.update_topology(message)
        self.assertEqual(response["type"], TYPE_ACK)
        self.assertEqual(response["router_id"], "R1")

    def test_topologia_persiste_enlaces_en_dao(self):
        """
        TC-02c: Cada enlace debe ser guardado en MySQL vía el DAO.
        Verifica que save_topology_link se llama con source, target y cost correctos.
        """
        message = build_topology("R1", [
            {"neighbor_id": "R2", "cost": 10},
            {"neighbor_id": "R3", "cost": 5}
        ])
        self.service.update_topology(message)
        self.assertEqual(self.mock_dao.save_topology_link.call_count, 2)
        calls = self.mock_dao.save_topology_link.call_args_list
        args_1 = calls[0][1] if calls[0][1] else dict(zip(["source", "target", "cost"], calls[0][0]))
        # Verificar que se guardó el enlace R1-R2
        llamadas = [
            (c[0] if c[0] else tuple(c[1].values()))
            for c in [(c.args, c.kwargs) for c in calls]
        ]
        fuentes = [l[0] for l in llamadas]
        self.assertTrue(all(s == "R1" for s in fuentes))

    def test_topologia_multiples_routers_es_completa(self):
        """
        TC-02d: FR-03 — La topología debe marcar is_complete cuando todos
        los routers registrados hayan enviado su información.
        """
        self.service.update_topology(build_topology("R1", [{"neighbor_id": "R2", "cost": 2}]))
        self.service.update_topology(build_topology("R2", [{"neighbor_id": "R1", "cost": 2},
                                                            {"neighbor_id": "R3", "cost": 1}]))
        self.service.update_topology(build_topology("R3", [{"neighbor_id": "R2", "cost": 1}]))
        registered = {"R1", "R2", "R3"}
        self.assertTrue(self.topology.is_complete(registered))

    def test_topologia_no_completa_si_falta_un_router(self):
        """
        TC-02e: is_complete debe ser False si un router registrado no envió topología.
        """
        self.service.update_topology(build_topology("R1", [{"neighbor_id": "R2", "cost": 2}]))
        registered = {"R1", "R2", "R3"}   # R2 y R3 aún no enviaron topología
        self.assertFalse(self.topology.is_complete(registered))

    def test_topologia_actualiza_costo_al_reenviar(self):
        """
        TC-02f: Si R1 reenvía su topología con costos distintos, el grafo debe actualizarse.
        """
        self.service.update_topology(build_topology("R1", [{"neighbor_id": "R2", "cost": 10}]))
        self.service.update_topology(build_topology("R1", [{"neighbor_id": "R2", "cost": 3}]))
        self.assertEqual(self.topology.adjacency["R1"]["R2"], 3)

    # ──────────────────────────────────────────
    # CASOS NEGATIVOS
    # ──────────────────────────────────────────

    def test_topologia_sin_router_id_retorna_error(self):
        """
        TC-02g: NFR-05 — Mensaje sin router_id debe retornar ERROR sin crashear.
        """
        message = {"type": "TOPOLOGY_UPDATE", "neighbors": []}
        response = self.service.update_topology(message)
        self.assertEqual(response["type"], TYPE_ERROR)

    def test_topologia_sin_vecinos_retorna_ack_y_no_guarda_enlaces(self):
        """
        TC-02h: Un router sin vecinos debe retornar ACK pero no guardar enlaces.
        """
        message = build_topology("R1", [])
        response = self.service.update_topology(message)
        self.assertEqual(response["type"], TYPE_ACK)
        self.mock_dao.save_topology_link.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)