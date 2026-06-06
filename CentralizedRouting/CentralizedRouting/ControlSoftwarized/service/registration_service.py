# ControlSoftwarized/service/registration_service.py
# Services del controller: registro, topología, Dijkstra con networkx, logs.

import sys
import os
import logging
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

import networkx as nx

from model.router import Router, NetworkTopology
from dao.router_dao import RouterDAO
from shared.messages import build_routing_table, build_ack, build_error
from utils.safe_print import safe_print

# ──────────────────────────────────────────────
# FR-09 — LOGGING
# ──────────────────────────────────────────────
logging.basicConfig(
    filename="controller.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)


def log(event_type: str, router_id: str, detail: str, dao: RouterDAO = None):
    from main import safe_print
    msg = f"[{event_type}] router={router_id} | {detail}"
    safe_print(f"\n[CONTROLLER] {msg}")
    logging.info(msg)
    if dao:
        try:
            dao.save_event_log(event_type, router_id, detail)
        except Exception:
            pass


# ──────────────────────────────────────────────
# FR-01 — REGISTRO
# ──────────────────────────────────────────────

class RouterRegistrationService:
    """
    Valida el mensaje REGISTER_ROUTER y persiste el router en MySQL.
    """

    def __init__(self, router_dao: RouterDAO):
        self.router_dao = router_dao

    def register_router(self, message: dict) -> dict:
        required = ["type", "router_id", "ip", "port", "status"]
        for field in required:
            if field not in message:
                return build_error("unknown", f"Campo faltante: {field}")

        if message["type"] != "REGISTER_ROUTER":
            return build_error("unknown", "Tipo de mensaje inválido")

        router = Router(
            router_id=message["router_id"],
            ip=message["ip"],
            port=int(message["port"]),
            status="ACTIVE"
        )

        self.router_dao.save_router(router)
        log("REGISTER", router.router_id,
            f"ip={router.ip} port={router.port}", self.router_dao)

        return build_ack(router.router_id, "Router registrado exitosamente")


# ──────────────────────────────────────────────
# FR-02 / FR-03 — TOPOLOGÍA
# ──────────────────────────────────────────────

class TopologyService:
    """
    Recibe y almacena la información de vecinos de cada router.
    """

    def __init__(self, router_dao: RouterDAO, topology: NetworkTopology):
        self.router_dao = router_dao
        self.topology = topology

    def update_topology(self, message: dict) -> dict:
        router_id = message.get("router_id")
        neighbors = message.get("neighbors", [])

        if not router_id:
            return build_error("unknown", "router_id faltante en topología")

        # Actualizar modelo en memoria
        self.topology.update_neighbors(router_id, neighbors)

        # Persistir enlaces en MySQL
        for n in neighbors:
            self.router_dao.save_topology_link(
                source=router_id,
                target=n["neighbor_id"],
                cost=n["cost"]
            )

        log("TOPOLOGY", router_id,
            f"vecinos={neighbors}", self.router_dao)

        return build_ack(router_id, "Topología recibida")


# ──────────────────────────────────────────────
# FR-04 — DIJKSTRA con networkx
# FR-05 — GENERAR TABLAS
# ──────────────────────────────────────────────

class RoutingService:
    """
    Calcula las tablas de ruteo usando Dijkstra (networkx) y las distribuye.
    FR-04: shortest paths.
    FR-05: generar routing table por router.
    """

    def __init__(self, router_dao: RouterDAO, topology: NetworkTopology):
        self.router_dao = router_dao
        self.topology = topology

    def compute_all_tables(self) -> dict:
        """
        Ejecuta Dijkstra desde cada nodo y retorna las tablas.
        Retorna: { "R1": [{"destination": ..., "next_hop": ..., "cost": ...}], ... }
        """
        adjacency = self.topology.adjacency

        # Construir grafo dirigido con networkx
        G = nx.DiGraph()
        for source, neighbors in adjacency.items():
            for target, cost in neighbors.items():
                G.add_edge(source, target, weight=cost)

        tables = {}

        for router_id in adjacency:
            table = []

            # Dijkstra desde router_id a todos los demás nodos
            try:
                lengths = nx.single_source_dijkstra_path_length(
                    G, router_id, weight="weight"
                )
                paths = nx.single_source_dijkstra_path(
                    G, router_id, weight="weight"
                )
            except nx.NetworkXError as e:
                log("ERROR", router_id, f"Dijkstra falló: {e}", self.router_dao)
                continue

            for dest, cost in lengths.items():
                if dest == router_id:
                    continue
                path = paths.get(dest, [])
                # El siguiente salto es el segundo nodo del camino
                next_hop = path[1] if len(path) > 1 else dest

                table.append({
                    "destination": dest,
                    "next_hop": next_hop,
                    "cost": cost
                })

            tables[router_id] = table

            # Persistir en MySQL
            self.router_dao.save_routing_table(router_id, table)
            log("ROUTE_COMPUTED", router_id,
                f"entradas={len(table)}", self.router_dao)

        return tables


# ──────────────────────────────────────────────
# FR-08 — ACTUALIZACIÓN DE ENLACE
# ──────────────────────────────────────────────

class LinkUpdateService:
    """
    Procesa el mensaje LINK_UPDATE y recalcula las rutas afectadas.
    """

    def __init__(self, router_dao: RouterDAO, topology: NetworkTopology,
                 routing_service: RoutingService):
        self.router_dao = router_dao
        self.topology = topology
        self.routing_service = routing_service

    def update_link(self, message: dict) -> dict:
        router_id   = message.get("router_id")
        neighbor_id = message.get("neighbor_id")
        new_cost    = message.get("new_cost")

        if not all([router_id, neighbor_id, new_cost is not None]):
            return build_error(router_id or "unknown", "Campos faltantes en LINK_UPDATE")

        # Actualizar costo en memoria
        if router_id in self.topology.adjacency:
            self.topology.adjacency[router_id][neighbor_id] = new_cost

        # Persistir en MySQL
        self.router_dao.save_topology_link(router_id, neighbor_id, new_cost)

        log("LINK_UPDATE", router_id,
            f"neighbor={neighbor_id} new_cost={new_cost}", self.router_dao)

        return build_ack(router_id, f"Enlace actualizado: {neighbor_id} → costo {new_cost}")
