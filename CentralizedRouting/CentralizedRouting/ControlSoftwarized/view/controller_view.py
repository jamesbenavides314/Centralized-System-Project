# ControlSoftwarized/view/controller_view.py
# View: toda la salida por consola del controller.

class ControllerCLIView:
    """
    View responsable de mostrar información del controller
    en la línea de comandos.
    """

    @staticmethod
    def show_start_message(host: str, port: int):
        print("=" * 60)
        print("  ControllerApp iniciado")
        print(f"  Escuchando en {host}:{port}")
        print("=" * 60)

    @staticmethod
    def show_received_message(message: dict):
        print(f"\n[RX] Mensaje recibido: {message.get('type')} "
              f"| router={message.get('router_id', '?')}")

    @staticmethod
    def show_response_sent(response: dict):
        print(f"[TX] Respuesta enviada: {response.get('type')} "
              f"| {response.get('message', '')}")

    @staticmethod
    def show_topology(topology: dict):
        print("\n[TOPOLOGÍA ACTUAL]")
        for node, neighbors in topology.items():
            print(f"  {node} → {neighbors}")

    @staticmethod
    def show_routing_tables(tables: dict):
        print("\n[TABLAS DE RUTEO CALCULADAS]")
        for router_id, table in tables.items():
            print(f"\n  Router {router_id}:")
            print(f"  {'Destino':<12} {'Sig. Salto':<15} {'Costo'}")
            print(f"  {'-' * 35}")
            for entry in table:
                print(f"  {entry['destination']:<12} "
                      f"{entry['next_hop']:<15} "
                      f"{entry['cost']}")

    @staticmethod
    def show_registered_routers(routers: list):
        print(f"\n[ROUTERS REGISTRADOS] ({len(routers)} total)")
        for r in routers:
            print(f"  {r.router_id} | {r.ip}:{r.port} | {r.status}")

    @staticmethod
    def show_link_update(router_id: str, neighbor_id: str, new_cost: int):
        print(f"\n[LINK UPDATE] {router_id} → {neighbor_id}: "
              f"nuevo costo = {new_cost}")

    @staticmethod
    def show_error(msg: str):
        print(f"\n[ERROR] {msg}")

    @staticmethod
    def show_info(msg: str):
        print(f"\n[INFO] {msg}")
