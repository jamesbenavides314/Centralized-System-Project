# AppRouter/controller/router_app_controller.py
# Controlador MVC del AppRouter: coordina model, view, service, dao y network.
# Cubre: FR-01, FR-02, FR-06, FR-07, FR-08

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

from model.router import Router, Neighbor, RoutingEntry
from dao.router_dao import RouterConfigDAO
from service.registration_service import (
    RegistrationService, TopologyService, LinkUpdateService
)
from network.tcp_client import TCPClient
from view.router_view import RouterCLIView
from shared.messages import TYPE_ROUTING_TABLE, TYPE_ACK, TYPE_ERROR


class RouterAppController:
    """
    Controlador principal del AppRouter.
    Coordina el model, view, service, DAO y capa de red.
    """

    def __init__(self, config_path: str = "config/router_config.json"):
        self.config_dao = RouterConfigDAO(config_path=config_path)
        self.view = RouterCLIView()
        self.router = None
        self.client = None

    # ──────────────────────────────────────────
    # INICIO
    # ──────────────────────────────────────────

    def is_connected(self) -> bool:
        """Retorna True si hay una conexión TCP activa con el controller."""
        return self.client is not None and self.client._socket is not None

    def check_controller_available(self) -> bool:
        """Verifica si el controller está disponible sin conectarse permanentemente."""
        import socket
        try:
            test = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            test.settimeout(2)
            config = self.config_dao.load_config()
            host = config["controller"]["host"]
            port = config["controller"]["port"]
            test.connect((host, port))
            test.close()
            return True
        except Exception:
            return False

    def disconnect(self):
        """Cierra la conexión TCP con el controller."""
        if self.client:
            self.client.close()
            self.client = None

    def start(self):
        """Flujo principal del router."""
        config = self.config_dao.load_config()

        # Construir el modelo Router con vecinos
        neighbors = [
            Neighbor(neighbor_id=n["neighbor_id"], cost=n["cost"])
            for n in config["router"].get("neighbors", [])
        ]

        self.router = Router(
            router_id=config["router"]["router_id"],
            ip=config["router"]["ip"],
            port=config["router"]["port"],
            status=config["router"].get("status", "ACTIVE"),
            neighbors=neighbors
        )

        controller_host = config["controller"]["host"]
        controller_port = config["controller"]["port"]

        self.view.show_start_message(
            self.router.router_id,
            self.router.ip,
            self.router.port
        )

        # Crear cliente TCP con callback para mensajes entrantes
        self.client = TCPClient(
            controller_host=controller_host,
            controller_port=controller_port,
            on_message_callback=self._handle_incoming
        )

        try:
            self.client.connect()
            self.client.start_listener()

            # FR-01: Registro
            self._send_registration()

            # FR-02: Topología
            self._send_topology()

            # Mantener proceso vivo esperando respuestas (FR-06)
            self.client.wait()

        except ConnectionRefusedError:
            self.view.show_error(
                "Conexión rechazada. Asegúrate de que ControlSoftwarized esté activo."
            )
        except Exception as error:
            self.view.show_error(str(error))

    # ──────────────────────────────────────────
    # FR-01 — REGISTRO
    # ──────────────────────────────────────────

    def _send_registration(self):
        msg = RegistrationService.create_registration_message(self.router)
        self.client.send_message(msg)
        self.view.show_registration_sent(msg)

    # ──────────────────────────────────────────
    # FR-02 — TOPOLOGÍA
    # ──────────────────────────────────────────

    def _send_topology(self):
        msg = TopologyService.create_topology_message(self.router)
        self.client.send_message(msg)
        self.view.show_topology_sent(msg)

    # ──────────────────────────────────────────
    # FR-06 — RECIBIR MENSAJES DEL CONTROLLER
    # ──────────────────────────────────────────

    def _handle_incoming(self, message: dict):
        """Callback invocado por TCPClient al recibir un mensaje del controller."""
        msg_type = message.get("type")

        if msg_type == TYPE_ROUTING_TABLE:
            # FR-06: almacenar tabla de ruteo
            raw_table = message.get("table", [])
            self.router.routing_table = [
                RoutingEntry(
                    destination=entry["destination"],
                    next_hop=entry["next_hop"],
                    cost=entry["cost"]
                )
                for entry in raw_table
            ]
            # FR-07: mostrar en CLI
            self.view.show_routing_table(
                self.router.router_id,
                self.router.routing_table
            )

        elif msg_type == TYPE_ACK:
            self.view.show_ack(message)

        elif msg_type == TYPE_ERROR:
            self.view.show_error(message.get("message", "Error desconocido"))

        else:
            self.view.show_info(f"Mensaje desconocido recibido: {message}")

    # ──────────────────────────────────────────
    # FR-08 — SIMULACIÓN DE CAMBIO DE ENLACE
    # ──────────────────────────────────────────

    def send_deregister(self):
        """Envía DEREGISTER_ROUTER al controller para que elimine el router de MySQL."""
        from shared.messages import build_deregister
        if self.router and self.client:
            msg = build_deregister(self.router.router_id)
            self.client.send_message(msg)

    def simulate_link_update(self, neighbor_id: str, new_cost: int):
        """
        Envía al controller una actualización de costo de enlace.
        Se puede invocar desde el main después del start.
        """
        msg = LinkUpdateService.create_link_update_message(
            router_id=self.router.router_id,
            neighbor_id=neighbor_id,
            new_cost=new_cost
        )
        self.client.send_message(msg)
        self.view.show_link_update_sent(
            self.router.router_id, neighbor_id, new_cost
        )