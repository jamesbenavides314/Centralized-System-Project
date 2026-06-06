# ControlSoftwarized/controller/controller_app_controller.py
# Controlador MVC del ControlSoftwarized: coordina todas las capas.
# FR-01, FR-02, FR-03, FR-04, FR-05, FR-06, FR-08, FR-09

import sys
import os
import json
import threading
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

from model.router import NetworkTopology
from dao.router_dao import RouterDAO
from service.registration_service import (
    RouterRegistrationService,
    TopologyService,
    RoutingService,
    LinkUpdateService,
    log
)
from network.tcp_server import TCPServer
from view.controller_view import ControllerCLIView
from shared.messages import (
    TYPE_REGISTER, TYPE_TOPOLOGY, TYPE_LINK_UPDATE,
    build_error
)


class ControllerAppController:
    """
    Controlador principal del ControllerApp.
    Coordina view, services, DAO y capa de red.
    """

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port

        self.view = ControllerCLIView()
        self.router_dao = RouterDAO()
        self.topology = NetworkTopology()
        self._lock = threading.Lock()

        # Mapa: router_id → socket de conexión activa
        self._connections = {}

        # Registro de routers registrados (para saber cuándo la topología es completa)
        self._registered_ids = set()

        # Services
        self.registration_service = RouterRegistrationService(self.router_dao)
        self.topology_service = TopologyService(self.router_dao, self.topology)
        self.routing_service = RoutingService(self.router_dao, self.topology)
        self.link_update_service = LinkUpdateService(
            self.router_dao, self.topology, self.routing_service
        )

    # ──────────────────────────────────────────
    # HANDLER DE MENSAJES
    # ──────────────────────────────────────────

    def handle_message(self, message: dict, conn) -> dict:
        """
        Callback invocado por TCPServer por cada mensaje recibido.
        Retorna la respuesta inmediata al router.
        """
        self.view.show_received_message(message)
        msg_type = message.get("type")

        if msg_type == TYPE_REGISTER:
            return self._handle_register(message, conn)

        elif msg_type == TYPE_TOPOLOGY:
            return self._handle_topology(message)

        elif msg_type == TYPE_LINK_UPDATE:
            return self._handle_link_update(message)

        else:
            response = build_error(
                message.get("router_id", "unknown"),
                f"Tipo de mensaje no soportado: {msg_type}"
            )
            self.view.show_response_sent(response)
            return response

    # ──────────────────────────────────────────
    # FR-01 — REGISTRO
    # ──────────────────────────────────────────

    def _handle_register(self, message: dict, conn) -> dict:
        response = self.registration_service.register_router(message)

        router_id = message.get("router_id")
        if router_id and response.get("type") == "ACK":
            with self._lock:
                self._connections[router_id] = conn
                self._registered_ids.add(router_id)

            routers = self.router_dao.get_all_routers()
            self.view.show_registered_routers(routers)

        self.view.show_response_sent(response)
        return response

    # ──────────────────────────────────────────
    # FR-02 / FR-03 — TOPOLOGÍA
    # ──────────────────────────────────────────

    def _handle_topology(self, message: dict) -> dict:
        response = self.topology_service.update_topology(message)
        self.view.show_topology(self.topology.adjacency)
        self.view.show_response_sent(response)

        # FR-04 / FR-05: calcular y distribuir tablas cuando todos los
        # routers registrados hayan enviado su topología
        with self._lock:
            registered = set(self._registered_ids)
            topology_ready = self.topology.is_complete(registered)

        if topology_ready and len(registered) >= 2:
            self._compute_and_distribute()

        return response

    # ──────────────────────────────────────────
    # FR-04 / FR-05 / FR-06 — DIJKSTRA + DISTRIBUCIÓN
    # ──────────────────────────────────────────

    def _compute_and_distribute(self):
        """Calcula Dijkstra y envía las tablas a cada router."""
        log("ROUTE_COMPUTATION", "ALL",
            "Iniciando cálculo de tablas de ruteo", self.router_dao)

        tables = self.routing_service.compute_all_tables()
        self.view.show_routing_tables(tables)

        with self._lock:
            connections = dict(self._connections)

        for router_id, table in tables.items():
            conn = connections.get(router_id)
            if conn is None:
                self.view.show_error(
                    f"No hay conexión activa para {router_id}"
                )
                continue
            try:
                from shared.messages import build_routing_table
                msg = build_routing_table(router_id, table)
                raw = (json.dumps(msg) + "\n").encode("utf-8")
                conn.sendall(raw)
                log("TABLE_SENT", router_id,
                    f"entradas={len(table)}", self.router_dao)
            except Exception as e:
                self.view.show_error(
                    f"Error enviando tabla a {router_id}: {e}"
                )

    # ──────────────────────────────────────────
    # FR-08 — LINK UPDATE
    # ──────────────────────────────────────────

    def _handle_link_update(self, message: dict) -> dict:
        router_id   = message.get("router_id", "?")
        neighbor_id = message.get("neighbor_id", "?")
        new_cost    = message.get("new_cost", 0)

        self.view.show_link_update(router_id, neighbor_id, new_cost)

        response = self.link_update_service.update_link(message)
        self.view.show_response_sent(response)

        # Recalcular y redistribuir tras el cambio
        self._compute_and_distribute()

        return response

    # ──────────────────────────────────────────
    # INICIO
    # ──────────────────────────────────────────

    def start(self):
        self.view.show_start_message(self.host, self.port)

        server = TCPServer(
            host=self.host,
            port=self.port,
            message_handler=self.handle_message
        )
        server.start()
