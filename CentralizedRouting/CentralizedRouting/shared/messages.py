# shared/messages.py
# Contrato de mensajes JSON entre AppRouter (cliente) y ControlSoftwarized (servidor)
# Ambos proyectos deben importar este módulo para construir y parsear mensajes.

import json

# ──────────────────────────────────────────────
# TIPOS DE MENSAJES
# ──────────────────────────────────────────────
TYPE_REGISTER       = "REGISTER_ROUTER"
TYPE_TOPOLOGY       = "TOPOLOGY_UPDATE"
TYPE_ROUTING_TABLE  = "ROUTING_TABLE"
TYPE_LINK_UPDATE    = "LINK_UPDATE"
TYPE_ACK            = "ACK"
TYPE_ERROR          = "ERROR"


# ──────────────────────────────────────────────
# CONSTRUCTORES  (AppRouter → ControlSoftwarized)
# ──────────────────────────────────────────────

def build_register(router_id: str, ip: str, port: int, status: str = "ACTIVE") -> dict:
    """FR-01: Mensaje de registro del router."""
    return {
        "type": TYPE_REGISTER,
        "router_id": router_id,
        "ip": ip,
        "port": port,
        "status": status
    }


def build_topology(router_id: str, neighbors: list) -> dict:
    """
    FR-02: Mensaje con información de vecinos.
    neighbors: [{"neighbor_id": "R2", "cost": 5}, ...]
    """
    return {
        "type": TYPE_TOPOLOGY,
        "router_id": router_id,
        "neighbors": neighbors
    }


def build_link_update(router_id: str, neighbor_id: str, new_cost: int) -> dict:
    """FR-08: Simulación de cambio de costo de enlace."""
    return {
        "type": TYPE_LINK_UPDATE,
        "router_id": router_id,
        "neighbor_id": neighbor_id,
        "new_cost": new_cost
    }


# ──────────────────────────────────────────────
# CONSTRUCTORES  (ControlSoftwarized → AppRouter)
# ──────────────────────────────────────────────

def build_routing_table(router_id: str, table: list) -> dict:
    """
    FR-05 / FR-06: Tabla de ruteo enviada al router.
    table: [{"destination": "R3", "next_hop": "R2", "cost": 7}, ...]
    """
    return {
        "type": TYPE_ROUTING_TABLE,
        "router_id": router_id,
        "table": table
    }


def build_ack(router_id: str, info: str = "OK") -> dict:
    return {"type": TYPE_ACK, "router_id": router_id, "message": info}


def build_error(router_id: str, detail: str) -> dict:
    return {"type": TYPE_ERROR, "router_id": router_id, "message": detail}


# ──────────────────────────────────────────────
# CODIFICACIÓN / DECODIFICACIÓN
# ──────────────────────────────────────────────

def encode(msg: dict) -> bytes:
    """Serializa el dict a JSON con delimitador '\n'."""
    return (json.dumps(msg) + "\n").encode("utf-8")


def decode(raw: str) -> dict:
    """
    Parsea un string JSON a dict.
    NFR-05: lanza ValueError si el formato es inválido.
    """
    try:
        return json.loads(raw.strip())
    except json.JSONDecodeError as e:
        raise ValueError(f"Mensaje JSON inválido: {e}")
