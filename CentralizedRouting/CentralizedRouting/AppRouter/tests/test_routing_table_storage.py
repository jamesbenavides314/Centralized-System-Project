# AppRouter/tests/test_routing_table_storage.py
# TC-05 (lado router) — FR-06: Verificar que el router recibe y almacena
#                               su tabla de ruteo correctamente.
# TC-06           — FR-07: Verificar que la tabla se muestra en CLI.
# Ejecutar desde AppRouter/: python -m pytest tests/test_routing_table_storage.py -v

import sys
import os
import io
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from model.router import Router, Neighbor, RoutingEntry
from controller.router_app_controller import RouterAppController
from view.router_view import RouterCLIView
from shared.messages import build_routing_table, TYPE_ACK, TYPE_ERROR


class TestRoutingTableStorage(unittest.TestCase):
    """
    TC-05 (AppRouter) — FR-06: El router debe recibir el mensaje ROUTING_TABLE
    del controller y almacenarlo en su modelo local.
    """

    def _make_controller_with_router(self):
        """Helper: crea un RouterAppController con un router preconfigurado."""
        ctrl = RouterAppController()
        ctrl.router = Router(
            router_id="R1",
            ip="127.0.0.1",
            port=5001,
            status="ACTIVE",
            neighbors=[Neighbor("R2", 2)]
        )
        return ctrl

    def test_tabla_recibida_se_almacena_en_modelo(self):
        """
        TC-05a: Al recibir ROUTING_TABLE, el router debe guardar las
        entradas en router.routing_table.
        """
        ctrl = self._make_controller_with_router()
        message = build_routing_table("R1", [
            {"destination": "R2", "next_hop": "R2", "cost": 2},
            {"destination": "R3", "next_hop": "R2", "cost": 3}
        ])
        ctrl._handle_incoming(message)
        self.assertEqual(len(ctrl.router.routing_table), 2)

    def test_tabla_entradas_son_routing_entry(self):
        """
        TC-05b: Cada elemento de routing_table debe ser un RoutingEntry
        con destination, next_hop y cost.
        """
        ctrl = self._make_controller_with_router()
        message = build_routing_table("R1", [
            {"destination": "R3", "next_hop": "R2", "cost": 3}
        ])
        ctrl._handle_incoming(message)
        entry = ctrl.router.routing_table[0]
        self.assertIsInstance(entry, RoutingEntry)
        self.assertEqual(entry.destination, "R3")
        self.assertEqual(entry.next_hop, "R2")
        self.assertEqual(entry.cost, 3)

    def test_tabla_se_sobreescribe_al_recibir_nueva(self):
        """
        TC-05c: Si el router recibe una segunda tabla, debe reemplazar
        la anterior (no acumular entradas duplicadas).
        """
        ctrl = self._make_controller_with_router()
        # Primera tabla
        ctrl._handle_incoming(build_routing_table("R1", [
            {"destination": "R2", "next_hop": "R2", "cost": 2}
        ]))
        self.assertEqual(len(ctrl.router.routing_table), 1)

        # Segunda tabla (actualización)
        ctrl._handle_incoming(build_routing_table("R1", [
            {"destination": "R2", "next_hop": "R2", "cost": 1},
            {"destination": "R3", "next_hop": "R2", "cost": 4}
        ]))
        self.assertEqual(len(ctrl.router.routing_table), 2)

    def test_ack_no_modifica_routing_table(self):
        """
        TC-05d: Un mensaje ACK no debe modificar la routing_table del router.
        """
        ctrl = self._make_controller_with_router()
        ack_msg = {"type": TYPE_ACK, "router_id": "R1", "message": "OK"}
        ctrl._handle_incoming(ack_msg)
        self.assertEqual(ctrl.router.routing_table, [])

    def test_mensaje_desconocido_no_crashea(self):
        """
        TC-05e: NFR-05 — Un mensaje de tipo desconocido no debe crashear el router.
        """
        ctrl = self._make_controller_with_router()
        try:
            ctrl._handle_incoming({"type": "UNKNOWN_MSG", "router_id": "R1"})
        except Exception as e:
            self.fail(f"_handle_incoming lanzó excepción inesperada: {e}")

    def test_tabla_vacia_se_almacena_correctamente(self):
        """
        TC-05f: Una tabla vacía enviada por el controller debe
        limpiar la tabla local del router sin error.
        """
        ctrl = self._make_controller_with_router()
        # Primero llenar la tabla
        ctrl._handle_incoming(build_routing_table("R1", [
            {"destination": "R2", "next_hop": "R2", "cost": 2}
        ]))
        # Luego recibir tabla vacía
        ctrl._handle_incoming(build_routing_table("R1", []))
        self.assertEqual(ctrl.router.routing_table, [])


class TestRoutingTableDisplay(unittest.TestCase):
    """
    TC-06 — FR-07: La vista del router debe mostrar la tabla de ruteo
    en la CLI con destination, next_hop y cost.
    """

    def _capture_output(self, router_id, table_entries):
        """Helper: captura el stdout de show_routing_table."""
        output = io.StringIO()
        with patch("sys.stdout", output):
            RouterCLIView.show_routing_table(router_id, table_entries)
        return output.getvalue()

    def test_tabla_muestra_encabezado_con_router_id(self):
        """TC-06a: La salida debe incluir el ID del router."""
        entries = [RoutingEntry("R2", "R2", 2)]
        output = self._capture_output("R1", entries)
        self.assertIn("R1", output)

    def test_tabla_muestra_destino(self):
        """TC-06b: La salida debe incluir el destino."""
        entries = [RoutingEntry("R3", "R2", 3)]
        output = self._capture_output("R1", entries)
        self.assertIn("R3", output)

    def test_tabla_muestra_siguiente_salto(self):
        """TC-06c: La salida debe incluir el siguiente salto."""
        entries = [RoutingEntry("R3", "R2", 3)]
        output = self._capture_output("R1", entries)
        self.assertIn("R2", output)

    def test_tabla_muestra_costo(self):
        """TC-06d: La salida debe incluir el costo."""
        entries = [RoutingEntry("R3", "R2", 7)]
        output = self._capture_output("R1", entries)
        self.assertIn("7", output)

    def test_tabla_vacia_no_crashea(self):
        """TC-06e: Una tabla vacía debe mostrar mensaje indicativo sin error."""
        try:
            output = self._capture_output("R1", [])
            self.assertIn("R1", output)
        except Exception as e:
            self.fail(f"show_routing_table con tabla vacía lanzó excepción: {e}")

    def test_tabla_multiples_entradas_todas_visibles(self):
        """TC-06f: Con múltiples entradas, todas deben aparecer en la salida."""
        entries = [
            RoutingEntry("R2", "R2", 2),
            RoutingEntry("R3", "R2", 3),
            RoutingEntry("R4", "R3", 5)
        ]
        output = self._capture_output("R1", entries)
        for entry in entries:
            self.assertIn(entry.destination, output,
                          f"El destino {entry.destination} no aparece en la salida")

    def test_tabla_se_muestra_al_recibir_routing_table(self):
        """
        TC-06g: Al recibir el mensaje ROUTING_TABLE desde el controller,
        show_routing_table debe ser invocado automáticamente.
        """
        ctrl = RouterAppController()
        ctrl.router = Router(
            router_id="R1", ip="127.0.0.1", port=5001,
            status="ACTIVE", neighbors=[]
        )
        message = build_routing_table("R1", [
            {"destination": "R2", "next_hop": "R2", "cost": 2}
        ])
        with patch.object(RouterCLIView, "show_routing_table") as mock_show:
            ctrl._handle_incoming(message)
            mock_show.assert_called_once()
            args = mock_show.call_args[0]
            self.assertEqual(args[0], "R1")


if __name__ == "__main__":
    unittest.main(verbosity=2)