# ControlSoftwarized/model/router.py
# Model: representa los datos de un router en el sistema.

from dataclasses import dataclass, field
from typing import List, Dict


@dataclass
class Router:
    router_id: str
    ip: str
    port: int
    status: str


@dataclass
class TopologyLink:
    """Representa un enlace entre dos routers con su costo."""
    source: str
    target: str
    cost: int


@dataclass
class RoutingEntry:
    destination: str
    next_hop: str
    cost: int


@dataclass
class NetworkTopology:
    """
    Modelo de la topología completa de la red.
    FR-03: estructura de grafo para almacenar la topología.
    adjacency: { "R1": {"R2": 1, "R3": 4}, ... }
    """
    adjacency: Dict[str, Dict[str, int]] = field(default_factory=dict)

    def update_neighbors(self, router_id: str, neighbors: list):
        """Actualiza los vecinos de un router en el grafo."""
        self.adjacency[router_id] = {
            n["neighbor_id"]: n["cost"] for n in neighbors
        }

    def get_all_nodes(self) -> list:
        return list(self.adjacency.keys())

    def is_complete(self, registered_ids: set) -> bool:
        """Retorna True cuando todos los routers registrados enviaron su topología."""
        return registered_ids == set(self.adjacency.keys())
