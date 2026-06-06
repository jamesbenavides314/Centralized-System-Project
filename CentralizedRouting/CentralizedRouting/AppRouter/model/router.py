# AppRouter/model/router.py
# Model: representa los datos del router (sin lógica de red ni SQL)

from dataclasses import dataclass, field
from typing import List


@dataclass
class Neighbor:
    neighbor_id: str
    cost: int


@dataclass
class RoutingEntry:
    destination: str
    next_hop: str
    cost: int


@dataclass
class Router:
    router_id: str
    ip: str
    port: int
    status: str
    neighbors: List[Neighbor] = field(default_factory=list)
    routing_table: List[RoutingEntry] = field(default_factory=list)
