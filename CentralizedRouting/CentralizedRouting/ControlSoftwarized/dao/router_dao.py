# ControlSoftwarized/dao/router_dao.py
# DAO: acceso a datos de routers y topología en MySQL (centralized_routing_db).
# FR-01 (registro), FR-03 (topología), FR-05 (tablas de ruteo), FR-09 (logs)

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from model.router import Router
from utils.database_connection import DatabaseConnection


class RouterDAO:
    """
    DAO responsable de almacenar y consultar datos de routers,
    topología, tablas de ruteo y logs en MySQL.
    """

    def __init__(self):
        self.database = DatabaseConnection()

    # ──────────────────────────────────────────
    # ROUTERS — FR-01
    # ──────────────────────────────────────────

    def save_router(self, router: Router):
        """Registra o actualiza un router en la tabla 'routers'."""
        query = """
        INSERT INTO routers (router_id, ip, port, status)
        VALUES (%s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            ip         = VALUES(ip),
            port       = VALUES(port),
            status     = VALUES(status),
            updated_at = CURRENT_TIMESTAMP;
        """
        values = (router.router_id, router.ip, router.port, router.status)
        connection = self.database.get_connection()
        try:
            cursor = connection.cursor()
            cursor.execute(query, values)
            connection.commit()
        finally:
            cursor.close()
            connection.close()

    def get_router_by_id(self, router_id: str):
        query = """
        SELECT router_id, ip, port, status
        FROM routers
        WHERE router_id = %s;
        """
        connection = self.database.get_connection()
        try:
            cursor = connection.cursor()
            cursor.execute(query, (router_id,))
            row = cursor.fetchone()
        finally:
            cursor.close()
            connection.close()
        if row is None:
            return None
        return Router(router_id=row[0], ip=row[1], port=row[2], status=row[3])

    def get_all_routers(self):
        query = """
        SELECT router_id, ip, port, status
        FROM routers
        ORDER BY router_id;
        """
        connection = self.database.get_connection()
        try:
            cursor = connection.cursor()
            cursor.execute(query)
            rows = cursor.fetchall()
        finally:
            cursor.close()
            connection.close()
        return [Router(router_id=r[0], ip=r[1], port=r[2], status=r[3]) for r in rows]

    # ──────────────────────────────────────────
    # TOPOLOGÍA — FR-03
    # ──────────────────────────────────────────

    def save_topology_link(self, source: str, target: str, cost: int):
        """Guarda o actualiza un enlace en la tabla 'topology'."""
        query = """
        INSERT INTO topology (source_router, target_router, cost)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE
            cost       = VALUES(cost),
            updated_at = CURRENT_TIMESTAMP;
        """
        connection = self.database.get_connection()
        try:
            cursor = connection.cursor()
            cursor.execute(query, (source, target, cost))
            connection.commit()
        finally:
            cursor.close()
            connection.close()

    def get_full_topology(self) -> dict:
        """
        Retorna la topología como dict de adyacencia:
        { "R1": {"R2": 1, "R3": 4}, ... }
        """
        query = "SELECT source_router, target_router, cost FROM topology;"
        connection = self.database.get_connection()
        try:
            cursor = connection.cursor()
            cursor.execute(query)
            rows = cursor.fetchall()
        finally:
            cursor.close()
            connection.close()
        adjacency = {}
        for source, target, cost in rows:
            adjacency.setdefault(source, {})[target] = cost
        return adjacency

    # ──────────────────────────────────────────
    # TABLAS DE RUTEO — FR-05
    # ──────────────────────────────────────────

    def save_routing_table(self, router_id: str, table: list):
        """
        Guarda la tabla de ruteo de un router.
        table: [{"destination": "R2", "next_hop": "R2", "cost": 1}, ...]
        """
        delete_query = "DELETE FROM routing_tables WHERE router_id = %s;"
        insert_query = """
        INSERT INTO routing_tables (router_id, destination, next_hop, cost)
        VALUES (%s, %s, %s, %s);
        """
        connection = self.database.get_connection()
        try:
            cursor = connection.cursor()
            cursor.execute(delete_query, (router_id,))
            for entry in table:
                cursor.execute(insert_query, (
                    router_id,
                    entry["destination"],
                    entry["next_hop"],
                    entry["cost"]
                ))
            connection.commit()
        finally:
            cursor.close()
            connection.close()

    # ──────────────────────────────────────────
    # LOGS DE EVENTOS — FR-09
    # ──────────────────────────────────────────

    def save_event_log(self, event_type: str, router_id: str, detail: str):
        """Registra un evento del sistema en la tabla 'event_logs'."""
        query = """
        INSERT INTO event_logs (event_type, router_id, detail)
        VALUES (%s, %s, %s);
        """
        connection = self.database.get_connection()
        try:
            cursor = connection.cursor()
            cursor.execute(query, (event_type, router_id, detail))
            connection.commit()
        finally:
            cursor.close()
            connection.close()

    def get_routing_table(self, router_id: str) -> list:
        """Retorna la tabla de ruteo de un router específico."""
        query = """
        SELECT destination, next_hop, cost
        FROM routing_tables
        WHERE router_id = %s
        ORDER BY destination;
        """
        connection = self.database.get_connection()
        try:
            cursor = connection.cursor()
            cursor.execute(query, (router_id,))
            rows = cursor.fetchall()
            return [{"destination": r[0], "next_hop": r[1], "cost": r[2]} for r in rows]
        finally:
            cursor.close()
            connection.close()

    def get_recent_logs(self, limit: int = 20) -> list:
        """Retorna los últimos eventos del log."""
        query = """
        SELECT event_type, router_id, detail, logged_at
        FROM event_logs
        ORDER BY logged_at DESC
        LIMIT %s;
        """
        connection = self.database.get_connection()
        try:
            cursor = connection.cursor()
            cursor.execute(query, (limit,))
            rows = cursor.fetchall()
            return [
                {
                    "event_type": r[0],
                    "router_id": r[1],
                    "detail": r[2],
                    "logged_at": r[3]
                }
                for r in rows
            ]
        finally:
            cursor.close()
            connection.close()