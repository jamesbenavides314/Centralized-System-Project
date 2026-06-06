# ControlSoftwarized/main.py
import json
import threading
import sys
from controller.controller_app_controller import ControllerAppController
from dao.router_dao import RouterDAO
from utils.safe_print import safe_print

# ──────────────────────────────────────────────
# UTILIDADES
# ──────────────────────────────────────────────

def load_config() -> dict:
    with open("config/controller_config.json", "r", encoding="utf-8") as file:
        return json.load(file)


def input_router_id(prompt: str) -> str:
    import re
    pattern = re.compile(r'^R\d+$')
    while True:
        rid = input(prompt).strip().upper()
        if pattern.match(rid):
            return rid
        print("  [!] ID inválido. Formato esperado: R1, R2, R3...")


def input_int(prompt: str, min_val: int = 1, max_val: int = 9999) -> int:
    while True:
        try:
            value = int(input(prompt))
            if min_val <= value <= max_val:
                return value
            print(f"  [!] Ingresa un número entre {min_val} y {max_val}.")
        except ValueError:
            print("  [!] Ingresa un número válido.")


# ──────────────────────────────────────────────
# COMANDOS
# ──────────────────────────────────────────────

def cmd_show_routers(dao: RouterDAO):
    print("\n[ /show_routers ]")
    try:
        routers = dao.get_all_routers()
        if not routers:
            print("  No hay routers registrados.")
            return
        print(f"\n  {'─'*55}")
        print(f"  {'Router ID':<12} {'IP':<16} {'Puerto':<8} {'Status'}")
        print(f"  {'─'*55}")
        for r in routers:
            print(f"  {r.router_id:<12} {r.ip:<16} {str(r.port):<8} {r.status}")
        print(f"  {'─'*55}")
    except Exception as e:
        print(f"  [!] Error: {e}")


def cmd_show_topology(dao: RouterDAO):
    print("\n[ /show_topology ]")
    try:
        topology = dao.get_full_topology()
        if not topology:
            print("  No hay topología registrada.")
            return
        print(f"\n  {'─'*40}")
        print(f"  {'Origen':<12} {'Destino':<12} {'Costo'}")
        print(f"  {'─'*40}")
        for source, neighbors in sorted(topology.items()):
            for target, cost in sorted(neighbors.items()):
                print(f"  {source:<12} {target:<12} {cost}")
        print(f"  {'─'*40}")
    except Exception as e:
        print(f"  [!] Error: {e}")


def cmd_show_routing_table(dao: RouterDAO):
    print("\n[ /show_routing_table ]")
    router_id = input_router_id("  Router ID a consultar: ")
    try:
        table = dao.get_routing_table(router_id)
        if not table:
            print(f"  [!] No hay tabla de ruteo para {router_id}.")
            return
        print(f"\n  Routing Table — {router_id}")
        print(f"  {'─'*45}")
        print(f"  {'Destino':<15} {'Siguiente Salto':<18} {'Costo'}")
        print(f"  {'─'*45}")
        for entry in table:
            print(f"  {entry['destination']:<15} {entry['next_hop']:<18} {entry['cost']}")
        print(f"  {'─'*45}")
    except Exception as e:
        print(f"  [!] Error: {e}")


def cmd_show_all_tables(dao: RouterDAO):
    print("\n[ /show_all_tables ]")
    try:
        routers = dao.get_all_routers()
        if not routers:
            print("  No hay routers registrados.")
            return
        for r in routers:
            table = dao.get_routing_table(r.router_id)
            print(f"\n  Routing Table — {r.router_id}")
            print(f"  {'─'*45}")
            print(f"  {'Destino':<15} {'Siguiente Salto':<18} {'Costo'}")
            print(f"  {'─'*45}")
            if table:
                for entry in table:
                    print(f"  {entry['destination']:<15} {entry['next_hop']:<18} {entry['cost']}")
            else:
                print("  (sin entradas)")
            print(f"  {'─'*45}")
    except Exception as e:
        print(f"  [!] Error: {e}")


def cmd_show_logs(dao: RouterDAO):
    print("\n[ /show_logs ]")
    try:
        logs = dao.get_recent_logs()
        if not logs:
            print("  No hay eventos registrados.")
            return
        print(f"\n  {'─'*70}")
        print(f"  {'Timestamp':<22} {'Evento':<20} {'Router':<8} {'Detalle'}")
        print(f"  {'─'*70}")
        for log in logs:
            print(f"  {str(log['logged_at']):<22} {log['event_type']:<20} "
                  f"{log['router_id']:<8} {log['detail'][:30]}")
        print(f"  {'─'*70}")
    except Exception as e:
        print(f"  [!] Error: {e}")


def cmd_update_link(controller: ControllerAppController):
    print("\n[ /update_link ] — FR-08: Cambio de costo de enlace")
    router_id   = input_router_id("  Router origen  : ")
    neighbor_id = input_router_id("  Router destino : ")
    new_cost    = input_int("  Nuevo costo    : ", min_val=1, max_val=9999)

    message = {
        "type": "LINK_UPDATE",
        "router_id": router_id,
        "neighbor_id": neighbor_id,
        "new_cost": new_cost
    }
    # Invoca directamente el handler del controller (sin necesidad de socket)
    controller.handle_message(message, conn=None)
    print(f"\n  ✓ Enlace {router_id} → {neighbor_id} actualizado a costo {new_cost}.")
    print("  ✓ Dijkstra recalculado y tablas redistribuidas.")


def cmd_status(controller: ControllerAppController):
    print("\n[ /status ]")
    try:
        routers = controller.router_dao.get_all_routers()
        connected = list(controller._connections.keys())
        print(f"\n  Servidor TCP    : activo en {controller.host}:{controller.port}")
        print(f"  Routers en BD   : {len(routers)}")
        print(f"  Conectados ahora: {len(connected)} → {connected if connected else 'ninguno'}")
        print(f"  Topología actual: {list(controller.topology.adjacency.keys())}")
    except Exception as e:
        print(f"  [!] Error: {e}")


def cmd_help():
    print("""
  Comandos disponibles:
  ─────────────────────────────────────────────────────
  /show_routers         Listar todos los routers en BD
  /show_topology        Ver topología completa de la red
  /show_routing_table   Ver tabla de ruteo de un router
  /show_all_tables      Ver tablas de ruteo de todos
  /show_logs            Ver log de eventos del sistema
  /update_link          Cambiar costo de un enlace (FR-08)
  /status               Estado del servidor y conexiones
  /help                 Mostrar esta ayuda
  /exit                 Detener el controller y salir
  ─────────────────────────────────────────────────────""")


# ──────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────

def main():
    config = load_config()
    dao = RouterDAO()

    # ──────────────────────────────────────────
    # VALIDACIÓN INICIAL — CONEXIÓN A MYSQL
    # ──────────────────────────────────────────
    print("\n" + "=" * 50)
    print("       ControlSoftwarized — CLI")
    print("=" * 50)
    print("  Verificando conexión con la base de datos...")

    try:
        conn = dao.database.get_connection()
        conn.close()
        print("  ✓ Conexión con MySQL establecida correctamente.")
    except Exception as e:
        print(f"\n  [!] No se pudo conectar a la base de datos.")
        print(f"  [!] Detalle: {e}")
        print(f"\n  Verifica que:")
        print(f"    1. MySQL esté corriendo.")
        print(f"    2. Las credenciales en config/database_config.json sean correctas.")
        print(f"    3. La base de datos 'centralized_routing_db' exista.")
        print(f"\n  El sistema no puede continuar sin la base de datos. Saliendo...\n")
        return

    controller = ControllerAppController(
        host=config["host"],
        port=config["port"]
    )

    # El servidor TCP corre en un hilo separado — no bloquea el menú
    server_thread = threading.Thread(target=controller.start, daemon=True)
    server_thread.start()

    # Esperar brevemente a que el servidor arranque antes de imprimir el menú
    import time
    time.sleep(0.5)

    # Limpiar consola y mostrar encabezado limpio
    print("\n" + "=" * 50)
    print(f"  ✓ Servidor TCP activo en {config['host']}:{config['port']}")
    print("  ✓ Esperando conexiones de routers...")
    print("  Escribe /help para ver los comandos.")
    print("=" * 50)

    while True:
        try:
            command = input("\nController> ").strip().lower()
            if not command:
                continue
            if command == "/exit":
                print("\n  Deteniendo controller...\n")
                break
            elif command == "/show_routers":
                cmd_show_routers(dao)
            elif command == "/show_topology":
                cmd_show_topology(dao)
            elif command == "/show_routing_table":
                cmd_show_routing_table(dao)
            elif command == "/show_all_tables":
                cmd_show_all_tables(dao)
            elif command == "/show_logs":
                cmd_show_logs(dao)
            elif command == "/update_link":
                cmd_update_link(controller)
            elif command == "/status":
                cmd_status(controller)
            elif command == "/help":
                cmd_help()
            else:
                print(f"  [!] Comando no reconocido: '{command}'. Escribe /help.")
        except KeyboardInterrupt:
            print("\n\n  Deteniendo controller...\n")
            break


if __name__ == "__main__":
    main()