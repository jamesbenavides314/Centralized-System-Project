# AppRouter/main.py
import re
import threading
from dao.router_dao import RouterConfigDAO
from controller.router_app_controller import RouterAppController

VALID_ID_PATTERN = re.compile(r'^R\d+$')
VALID_IP_PATTERN = re.compile(r'^(\d{1,3}\.){3}\d{1,3}$')


# ──────────────────────────────────────────────
# VALIDACIONES
# ──────────────────────────────────────────────

def validate_ip(ip: str) -> bool:
    if not VALID_IP_PATTERN.match(ip):
        return False
    return all(0 <= int(p) <= 255 for p in ip.split("."))


def validate_router_id(rid: str) -> bool:
    return bool(VALID_ID_PATTERN.match(rid))


def input_int(prompt: str, min_val: int = 1, max_val: int = 65535) -> int:
    while True:
        try:
            value = int(input(prompt))
            if min_val <= value <= max_val:
                return value
            print(f"  [!] Ingresa un número entre {min_val} y {max_val}.")
        except ValueError:
            print("  [!] Ingresa un número válido.")


def input_ip(prompt: str) -> str:
    while True:
        ip = input(prompt).strip()
        if validate_ip(ip):
            return ip
        print("  [!] IP inválida. Formato esperado: 127.0.0.1")


def input_router_id(prompt: str) -> str:
    while True:
        rid = input(prompt).strip().upper()
        if validate_router_id(rid):
            return rid
        print("  [!] ID inválido. Formato esperado: R1, R2, R3...")


def input_neighbors(current_router_id: str) -> list:
    neighbors = []
    used_ids = set()
    print("  Ingresa vecinos (deja el ID vacío para terminar, mínimo 1):")
    while True:
        neighbor_id = input("    Neighbor ID: ").strip().upper()
        if not neighbor_id:
            if not neighbors:
                print("  [!] Debes agregar al menos un vecino.")
                continue
            break
        if not validate_router_id(neighbor_id):
            print("  [!] ID inválido. Formato: R1, R2...")
            continue
        if neighbor_id == current_router_id:
            print("  [!] Un router no puede ser vecino de sí mismo.")
            continue
        if neighbor_id in used_ids:
            print(f"  [!] {neighbor_id} ya fue agregado.")
            continue
        cost = input_int("    Costo del enlace: ", min_val=1, max_val=9999)
        neighbors.append({"neighbor_id": neighbor_id, "cost": cost})
        used_ids.add(neighbor_id)
    return neighbors


# ──────────────────────────────────────────────
# COMANDOS
# ──────────────────────────────────────────────

def cmd_add(dao: RouterConfigDAO, app: RouterAppController):
    print("\n[ /add_router ]")
    if app.is_connected():
        print("  [!] Ya hay una conexión activa con el controller.")
        print("  [!] Desconéctate primero con /disconnect antes de agregar un nuevo router.")
        return
    if dao.router_exists():
        r = dao.load_config()["router"]
        print(f"  [!] Ya existe el router {r['router_id']} configurado.")
        if input("  ¿Sobreescribir? (s/n): ").strip().lower() != "s":
            print("  Cancelado.")
            return

    router_id = input_router_id("  Router ID   : ")
    ip        = input_ip(       "  IP          : ")
    port      = input_int(      "  Puerto      : ", min_val=1024, max_val=65535)
    neighbors = input_neighbors(router_id)

    config = dao.load_config()
    config["router"] = {
        "router_id": router_id,
        "ip": ip,
        "port": port,
        "status": "ACTIVE",
        "neighbors": neighbors
    }
    dao.save_config(config)
    print(f"\n  ✓ Router {router_id} guardado. Usa /connect para conectarlo al controller.")


def cmd_edit(dao: RouterConfigDAO, app: RouterAppController):
    print("\n[ /edit_router ]")
    if app.is_connected():
        print("  [!] Hay una conexión activa. Desconéctate primero con /disconnect.")
        return
    if not dao.router_exists():
        print("  [!] No hay router configurado. Usa /add_router primero.")
        return

    config = dao.load_config()
    r = config["router"]
    cmd_show_config(dao)

    print("\n  (Enter para mantener el valor actual)")
    new_id = input(f"  Router ID [{r['router_id']}]: ").strip().upper()
    if new_id and not validate_router_id(new_id):
        print(f"  [!] ID inválido, se mantiene: {r['router_id']}")
        new_id = r["router_id"]
    router_id = new_id or r["router_id"]

    new_ip = input(f"  IP [{r['ip']}]: ").strip()
    if new_ip and not validate_ip(new_ip):
        print(f"  [!] IP inválida, se mantiene: {r['ip']}")
        new_ip = r["ip"]
    ip = new_ip or r["ip"]

    new_port = input(f"  Puerto [{r['port']}]: ").strip()
    if new_port:
        try:
            port = int(new_port)
            if not (1024 <= port <= 65535):
                print(f"  [!] Puerto fuera de rango, se mantiene: {r['port']}")
                port = r["port"]
        except ValueError:
            print(f"  [!] Puerto inválido, se mantiene: {r['port']}")
            port = r["port"]
    else:
        port = r["port"]

    print(f"\n  Vecinos actuales: {r.get('neighbors', [])}")
    neighbors = input_neighbors(router_id) if input(
        "  ¿Editar vecinos? (s/n): "
    ).strip().lower() == "s" else r.get("neighbors", [])

    config["router"] = {
        "router_id": router_id,
        "ip": ip,
        "port": port,
        "status": r.get("status", "ACTIVE"),
        "neighbors": neighbors
    }
    dao.save_config(config)
    print(f"\n  ✓ Router {router_id} actualizado.")


def cmd_show_config(dao: RouterConfigDAO):
    """Muestra el router del config actual (JSON)."""
    if not dao.router_exists():
        print("  [!] No hay router configurado.")
        return
    r = dao.load_config()["router"]
    print(f"\n  {'─'*38}")
    print(f"  Router ID : {r.get('router_id')}")
    print(f"  IP        : {r.get('ip')}")
    print(f"  Puerto    : {r.get('port')}")
    print(f"  Status    : {r.get('status')}")
    print(f"  Vecinos   :")
    for n in r.get("neighbors", []):
        print(f"    → {n['neighbor_id']}  (costo {n['cost']})")
    print(f"  {'─'*38}")


def cmd_show_routers(dao: RouterConfigDAO):
    """Muestra todos los routers registrados en MySQL."""
    print("\n[ /show_routers ]")
    routers = dao.get_all_routers()
    if not routers:
        print("  No hay routers registrados en la base de datos.")
        return
    print(f"\n  {'─'*55}")
    print(f"  {'Router ID':<12} {'IP':<16} {'Puerto':<8} {'Status'}")
    print(f"  {'─'*55}")
    for r in routers:
        print(f"  {r.router_id:<12} {r.ip:<16} {str(r.port):<8} {r.status}")
    print(f"  {'─'*55}")


def cmd_show_topology(dao: RouterConfigDAO):
    """Muestra la topología almacenada en MySQL."""
    print("\n[ /show_topology ]")
    topology = dao.get_topology()
    if not topology:
        print("  No hay topología registrada.")
        return
    print(f"\n  {'─'*40}")
    print(f"  {'Origen':<12} {'Destino':<12} {'Costo'}")
    print(f"  {'─'*40}")
    for link in topology:
        print(f"  {link['source']:<12} {link['target']:<12} {link['cost']}")
    print(f"  {'─'*40}")


def cmd_show_routing_table(dao: RouterConfigDAO):
    """Muestra la routing table de un router específico desde MySQL."""
    print("\n[ /show_routing_table ]")
    router_id = input_router_id("  Router ID a consultar: ")
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


def cmd_delete(dao: RouterConfigDAO, app: RouterAppController):
    print("\n[ /delete_router ]")
    if app.is_connected():
        print("  [!] Hay una conexión activa. Desconéctate primero con /disconnect.")
        return
    if not dao.router_exists():
        print("  [!] No hay router configurado.")
        return
    r = dao.load_config()["router"]
    print(f"  Router a eliminar del config: {r['router_id']}")
    if input("  ¿Confirmar? (s/n): ").strip().lower() == "s":
        config = dao.load_config()
        config["router"] = {}
        dao.save_config(config)
        print(f"  ✓ Router {r['router_id']} eliminado del config.")
    else:
        print("  Cancelado.")


def cmd_connect(dao: RouterConfigDAO, app: RouterAppController):
    print("\n[ /connect ]")
    if app.is_connected():
        print("  [!] Ya hay una conexión activa con el controller.")
        return
    if not dao.router_exists():
        print("  [!] No hay router configurado. Usa /add_router primero.")
        return
    cmd_show_config(dao)
    if input("\n  ¿Conectar al controller? (s/n): ").strip().lower() == "s":
        thread = threading.Thread(target=app.start, daemon=True)
        thread.start()
        print("  ✓ Conectando en segundo plano... El menú sigue disponible.")


def cmd_disconnect(app: RouterAppController):
    print("\n[ /disconnect ]")
    if not app.is_connected():
        print("  [!] No hay conexión activa.")
        return
    app.disconnect()
    print("  ✓ Desconectado del controller.")


def cmd_status(app: RouterAppController):
    print("\n[ /status ]")
    if app.is_connected():
        print(f"  ✓ Conectado al controller.")
        print(f"  Router activo: {app.router.router_id if app.router else '?'}")
    else:
        print("  ✗ Sin conexión activa.")


def cmd_update_link(app: RouterAppController):
    """FR-08: Simula un cambio de costo de enlace desde el router."""
    print("\n[ /update_link ]")
    if not app.is_connected():
        print("  [!] No hay conexión activa. Usa /connect primero.")
        return
    if not app.router:
        print("  [!] El router no está inicializado.")
        return

    neighbor_id = input_router_id("  Neighbor ID  : ")
    new_cost    = input_int("  Nuevo costo  : ", min_val=1, max_val=9999)

    app.simulate_link_update(neighbor_id, new_cost)
    print(f"\n  ✓ Solicitud de cambio enviada: {app.router.router_id} → {neighbor_id}, costo {new_cost}.")
    print("  ✓ El controller recalculará las rutas y redistribuirá las tablas.")


def cmd_help():
    print("""
  Comandos disponibles:
  ─────────────────────────────────────────────────
  /add_router           Agregar/configurar un router
  /edit_router          Editar el router del config
  /delete_router        Eliminar router del config
  /connect              Conectar al controller (persistente)
  /disconnect           Desconectar del controller
  /status               Ver estado de la conexión
  /show_routers         Listar todos los routers en BD
  /show_topology        Ver topología de la red en BD
  /show_routing_table   Ver tabla de ruteo de un router
  /update_link          Simular cambio de costo de enlace (FR-08)
  /help                 Mostrar esta ayuda
  /exit                 Salir
  ─────────────────────────────────────────────────""")


# ──────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────

def main():
    dao = RouterConfigDAO()
    app = RouterAppController()

    print("\n" + "=" * 48)
    print("         AppRouter — CLI")
    print("=" * 48)

    # Verificación inicial de conexión con el controller
    print("\n  Verificando conexión con el controller...")
    if app.check_controller_available():
        print("  ✓ Controller disponible en 127.0.0.1:9000")
    else:
        print("  [!] Controller no disponible. Inicia ControlSoftwarized primero.")
        print("  [!] Puedes configurar routers pero no conectarte hasta que esté activo.")

    print("\n  Escribe /help para ver los comandos.")
    print("=" * 48)

    while True:
        try:
            command = input("\nAppRouter> ").strip().lower()
            if not command:
                continue
            if command == "/exit":
                if app.is_connected():
                    app.disconnect()
                print("\n  Saliendo...\n")
                break
            elif command == "/add_router":
                cmd_add(dao, app)
            elif command == "/edit_router":
                cmd_edit(dao, app)
            elif command == "/delete_router":
                cmd_delete(dao, app)
            elif command == "/connect":
                cmd_connect(dao, app)
            elif command == "/disconnect":
                cmd_disconnect(app)
            elif command == "/status":
                cmd_status(app)
            elif command == "/show_routers":
                cmd_show_routers(dao)
            elif command == "/show_topology":
                cmd_show_topology(dao)
            elif command == "/show_routing_table":
                cmd_show_routing_table(dao)
            elif command == "/update_link":
                cmd_update_link(app)
            elif command == "/help":
                cmd_help()
            else:
                print(f"  [!] Comando no reconocido: '{command}'. Escribe /help.")
        except KeyboardInterrupt:
            if app.is_connected():
                app.disconnect()
            print("\n\n  Saliendo...\n")
            break


if __name__ == "__main__":
    main()