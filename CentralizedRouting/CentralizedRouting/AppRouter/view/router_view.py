# AppRouter/view/router_view.py
# View: toda la salida por consola del router.
# FR-07: muestra la tabla de ruteo en CLI.

from model.router import RoutingEntry
from typing import List


class RouterCLIView:
    """
    View responsable de mostrar información del router
    en la línea de comandos.
    FR-07: display_routing_table
    """

    @staticmethod
    def show_start_message(router_id: str, ip: str, port: int):
        print("=" * 60)
        print(f"  RouterApp iniciado: {router_id}")
        print(f"  IP: {ip}  |  Puerto: {port}")
        print("=" * 60)

    @staticmethod
    def show_registration_sent(message: dict):
        print("\n[REGISTRO] Mensaje enviado al controller:")
        print(f"  {message}")

    @staticmethod
    def show_topology_sent(message: dict):
        print("\n[TOPOLOGÍA] Información de vecinos enviada:")
        print(f"  {message}")

    @staticmethod
    def show_ack(response: dict):
        print(f"\n[ACK] Respuesta del controller: {response.get('message', 'OK')}")

    @staticmethod
    def show_routing_table(router_id: str, table: List[RoutingEntry]):
        """FR-07: Imprime la tabla de ruteo formateada en CLI."""
        print(f"\n{'=' * 60}")
        print(f"  Routing Table — Router {router_id}")
        print(f"{'=' * 60}")
        print(f"  {'Destino':<15} {'Siguiente Salto':<20} {'Costo'}")
        print(f"  {'-' * 45}")
        if table:
            for entry in table:
                print(f"  {entry.destination:<15} {entry.next_hop:<20} {entry.cost}")
        else:
            print("  (tabla vacía)")
        print(f"{'=' * 60}\n")

    @staticmethod
    def show_link_update_sent(router_id: str, neighbor_id: str, new_cost: int):
        print(f"\n[LINK UPDATE] {router_id} → {neighbor_id}: nuevo costo = {new_cost}")

    @staticmethod
    def show_error(error: str):
        print(f"\n[ERROR] {error}")

    @staticmethod
    def show_info(msg: str):
        print(f"\n[INFO] {msg}")
