# AppRouter/dao/router_dao.py
import json
import mysql.connector
from pathlib import Path


class RouterConfigDAO:
    def __init__(self, config_path: str = "config/router_config.json"):
        self.config_path = Path(config_path)
        self._db_config = self._load_db_config()

    def _load_db_config(self) -> dict:
        db_path = Path("config/db_config.json")
        if db_path.exists():
            with open(db_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _get_connection(self):
        return mysql.connector.connect(
            host=self._db_config.get("host", "localhost"),
            port=self._db_config.get("port", 3306),
            user=self._db_config.get("user", "root"),
            password=self._db_config.get("password", ""),
            database=self._db_config.get("database", "centralized_routing_db")
        )

    # ── JSON config ──

    def _ensure_config_exists(self):
        """Crea el archivo de config con estructura vacía si no existe."""
        if not self.config_path.exists():
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            default = {"router": {}, "controller": {"host": "127.0.0.1", "port": 9000}}
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(default, f, indent=2)

    def load_config(self) -> dict:
        self._ensure_config_exists()
        with open(self.config_path, "r", encoding="utf-8") as file:
            return json.load(file)

    def save_config(self, config: dict):
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as file:
            json.dump(config, file, indent=2)

    def router_exists(self) -> bool:
        try:
            config = self.load_config()
            return bool(config.get("router", {}).get("router_id"))
        except (FileNotFoundError, json.JSONDecodeError):
            return False

    # ── MySQL queries ──

    def delete_router_from_db(self, router_id: str):
        """Elimina el router directamente de MySQL (usado cuando no hay conexión activa)."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM routing_tables WHERE router_id = %s;", (router_id,))
            cursor.execute("DELETE FROM topology WHERE source_router = %s OR target_router = %s;", (router_id, router_id))
            cursor.execute("DELETE FROM routers WHERE router_id = %s;", (router_id,))
            conn.commit()
        except Exception as e:
            print(f"  [!] Error eliminando router de la BD: {e}")
        finally:
            cursor.close()
            conn.close()

    def get_all_routers(self) -> list:
        from model.router import Router
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT router_id, ip, port, status FROM routers ORDER BY router_id;")
            rows = cursor.fetchall()
            return [Router(router_id=r[0], ip=r[1], port=r[2], status=r[3]) for r in rows]
        except Exception as e:
            print(f"  [!] Error consultando routers: {e}")
            return []
        finally:
            cursor.close()
            conn.close()

    def get_topology(self) -> list:
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT source_router, target_router, cost FROM topology ORDER BY source_router;")
            rows = cursor.fetchall()
            return [{"source": r[0], "target": r[1], "cost": r[2]} for r in rows]
        except Exception as e:
            print(f"  [!] Error consultando topología: {e}")
            return []
        finally:
            cursor.close()
            conn.close()

    def get_routing_table(self, router_id: str) -> list:
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT destination, next_hop, cost FROM routing_tables WHERE router_id = %s ORDER BY destination;",
                (router_id,)
            )
            rows = cursor.fetchall()
            return [{"destination": r[0], "next_hop": r[1], "cost": r[2]} for r in rows]
        except Exception as e:
            print(f"  [!] Error consultando routing table: {e}")
            return []
        finally:
            cursor.close()
            conn.close()