# AppRouter/service/registration_service.py
# Service: construye mensajes de registro y topología usando el contrato compartido.

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

from shared.messages import build_register, build_topology, build_link_update
from model.router import Router


class RegistrationService:
    """
    Service responsable de crear el mensaje REGISTER_ROUTER.
    FR-01
    """

    @staticmethod
    def create_registration_message(router: Router) -> dict:
        return build_register(
            router_id=router.router_id,
            ip=router.ip,
            port=router.port,
            status=router.status
        )


class TopologyService:
    """
    Service responsable de crear el mensaje SEND_TOPOLOGY.
    FR-02
    """

    @staticmethod
    def create_topology_message(router: Router) -> dict:
        neighbors_list = [
            {"neighbor_id": n.neighbor_id, "cost": n.cost}
            for n in router.neighbors
        ]
        return build_topology(
            router_id=router.router_id,
            neighbors=neighbors_list
        )


class LinkUpdateService:
    """
    Service responsable de crear el mensaje LINK_UPDATE.
    FR-08
    """

    @staticmethod
    def create_link_update_message(router_id: str, neighbor_id: str, new_cost: int) -> dict:
        return build_link_update(
            router_id=router_id,
            neighbor_id=neighbor_id,
            new_cost=new_cost
        )
