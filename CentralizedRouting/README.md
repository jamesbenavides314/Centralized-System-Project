# Centralized Routing System

Sistema de enrutamiento centralizado desarrollado en Python como simulación educativa de una arquitectura SDN (Software-Defined Networking) simplificada. El sistema está compuesto por dos aplicaciones independientes: **ControlSoftwarized** (el controller) y **AppRouter** (el router cliente), que se comunican mediante sockets TCP y mensajes JSON.

---

## Contexto y motivación

En el enrutamiento tradicional, cada router computa sus propias rutas de forma distribuida (como en OSPF o RIP). Este proyecto invierte ese modelo: los routers son entidades pasivas que reportan su información local a un controller central, y es el controller quien tiene la visión global de la red, ejecuta el algoritmo de caminos más cortos y distribuye las tablas de ruteo calculadas.

Este paradigma es la base conceptual de SDN, donde el plano de control (decisiones de ruteo) está separado del plano de datos (reenvío de paquetes).

---

## Arquitectura general

```
┌──────────────────────────────────────┐
│          ControlSoftwarized          │
│                                      │
│  RouterRegistry   TopologyManager    │
│  RoutingService   LinkUpdateService  │
│  TCPServer        RouterDAO          │
│  MySQL            Logging            │
└────────────┬─────────────────────────┘
             │  TCP + JSON (port 9000)
     ┌───────┴────────┐
     │                │
┌────┴─────┐    ┌─────┴────┐    ┌──────────┐
│ AppRouter│    │ AppRouter│    │ AppRouter│
│   R1     │    │   R2     │    │   R3...  │
│ TCPClient│    │ TCPClient│    │ TCPClient│
└──────────┘    └──────────┘    └──────────┘
```

La comunicación es siempre cliente → servidor para el envío de información de red (registro, topología, cambios de enlace), y servidor → cliente para la distribución de tablas de ruteo.

---

## Estructura del proyecto

```
CentralizedRouting/
├── shared/
│   └── messages.py              # Contrato de mensajes compartido
│
├── ControlSoftwarized/
│   ├── main.py                  # Punto de entrada del controller
│   ├── controller/
│   │   └── controller_app_controller.py   # Coordinador MVC principal
│   ├── model/
│   │   └── router.py            # Router, NetworkTopology, RoutingEntry
│   ├── service/
│   │   └── registration_service.py        # Lógica de negocio (registro, Dijkstra, etc.)
│   ├── dao/
│   │   └── router_dao.py        # Acceso a MySQL
│   ├── network/
│   │   └── tcp_server.py        # Servidor TCP multihilo
│   ├── view/
│   │   └── controller_view.py   # Salidas por CLI
│   ├── utils/
│   │   ├── safe_print.py        # Print thread-safe
│   │   └── database_connection.py
│   └── tests/
│       ├── test_router_registry.py
│       ├── test_topology.py
│       ├── test_dijkstra_service.py
│       ├── test_routing_table_service.py
│       └── test_controller_communication.py
│
└── AppRouter/
    ├── main.py                  # Punto de entrada y CLI del router
    ├── controller/
    │   └── router_app_controller.py       # Coordinador MVC del router
    ├── model/
    │   └── router.py            # Router, Neighbor, RoutingEntry
    ├── service/
    │   └── registration_service.py        # Constructores de mensajes
    ├── dao/
    │   └── router_dao.py        # Lectura/escritura de config JSON
    ├── network/
    │   └── tcp_client.py        # Cliente TCP con listener en hilo
    ├── view/
    │   └── router_view.py       # Salidas por CLI
    └── tests/
        ├── test_registration.py
        ├── test_routing_table_storage.py
        └── test_router_communication.py
```

---

## Patrón arquitectónico: MVC por capas

Ambas aplicaciones siguen el patrón **Model-View-Controller** aplicado por capas:

| Capa | Responsabilidad |
|------|----------------|
| **Model** | Estructuras de datos puras (`Router`, `NetworkTopology`, `RoutingEntry`, `Neighbor`). Sin lógica de negocio ni dependencias externas. Implementadas con `@dataclass`. |
| **DAO** | Acceso a persistencia. En el controller: MySQL. En el router: archivo JSON de configuración. Aíslan al resto del sistema de los detalles de almacenamiento. |
| **Service** | Lógica de negocio. Valida mensajes, ejecuta Dijkstra, construye tablas de ruteo, gestiona el logging. No conocen la red ni la vista. |
| **Network** | Comunicación TCP. `TCPServer` (controller) y `TCPClient` (router) manejan sockets, hilos y el protocolo de mensajes. |
| **View** | Salidas por terminal. Sin lógica, solo formateo y print. |
| **Controller** | Coordinador central de cada aplicación. Recibe eventos (mensajes entrantes, comandos CLI) y delega a services, DAOs y vistas según corresponda. |

---

## Flujo de comunicación completo

### 1. Arranque y registro (FR-01)

Cuando un AppRouter se conecta al controller, envía inmediatamente un mensaje `REGISTER_ROUTER`:

```json
{
  "type": "REGISTER_ROUTER",
  "router_id": "R1",
  "ip": "127.0.0.1",
  "port": 5001,
  "status": "ACTIVE"
}
```

El controller almacena el router en MySQL, guarda el socket activo en `_connections[router_id]` y responde con `ACK`.

### 2. Envío de topología (FR-02, FR-03)

Tras el registro, el router envía su información de vecinos con `TOPOLOGY_UPDATE`:

```json
{
  "type": "TOPOLOGY_UPDATE",
  "router_id": "R1",
  "neighbors": [
    {"neighbor_id": "R2", "cost": 2},
    {"neighbor_id": "R3", "cost": 5}
  ]
}
```

El controller actualiza el grafo en memoria (`NetworkTopology.adjacency`) y persiste los enlaces en MySQL. Cuando todos los routers registrados han enviado su topología (`is_complete()` retorna `True`), se dispara automáticamente el cálculo de rutas.

### 3. Cálculo de rutas y distribución (FR-04, FR-05, FR-06)

El controller construye un grafo dirigido con networkx y ejecuta Dijkstra desde cada nodo:

```python
G = nx.DiGraph()
# Se agregan los enlaces con sus costos como peso
lengths = nx.single_source_dijkstra_path_length(G, router_id, weight="weight")
paths   = nx.single_source_dijkstra_path(G, router_id, weight="weight")
```

Para cada destino, el siguiente salto se extrae como el segundo nodo del camino más corto (`path[1]`). Las tablas resultantes se envían a cada router mediante su socket activo:

```json
{
  "type": "ROUTING_TABLE",
  "router_id": "R1",
  "table": [
    {"destination": "R2", "next_hop": "R2", "cost": 2},
    {"destination": "R3", "next_hop": "R2", "cost": 3}
  ]
}
```

### 4. Visualización en el router (FR-07)

Al recibir `ROUTING_TABLE`, el router almacena las entradas como objetos `RoutingEntry` y las muestra en terminal automáticamente. También se puede consultar manualmente con `/show_routing_table`.

### 5. Cambio de costo de enlace (FR-08)

Desde el controller (`/update_link`) o desde el router (`/update_link`), se envía un mensaje `LINK_UPDATE`:

```json
{
  "type": "LINK_UPDATE",
  "router_id": "R1",
  "neighbor_id": "R3",
  "new_cost": 1
}
```

El controller actualiza el costo en `topology.adjacency`, lo persiste en MySQL y ejecuta nuevamente `_compute_and_distribute()`, redistribuyendo las tablas actualizadas a todos los routers.

---

## Protocolo de mensajes — shared/messages.py

El módulo `shared/` es compartido por ambas aplicaciones y actúa como contrato formal del protocolo. Define:

- **Tipos de mensaje**: `REGISTER_ROUTER`, `TOPOLOGY_UPDATE`, `ROUTING_TABLE`, `LINK_UPDATE`, `ACK`, `ERROR`.
- **Constructores**: funciones `build_*` que garantizan que todos los mensajes tengan la estructura correcta.
- **Codificación**: `encode(msg)` serializa a JSON UTF-8 con `\n` como delimitador de mensaje. `decode(raw)` parsea y lanza `ValueError` ante JSON inválido.

El delimitador `\n` es fundamental para TCP, que es un protocolo de flujo de bytes sin fronteras de mensaje. El servidor acumula los bytes recibidos en un buffer y los procesa línea por línea.

---

## Manejo de concurrencia

El controller atiende cada router en un hilo independiente:

```python
thread = threading.Thread(target=self._handle_client, args=(client_socket,), daemon=True)
thread.start()
```

El acceso a estructuras compartidas (`_connections`, `_registered_ids`) está protegido con `threading.Lock()` para evitar condiciones de carrera. Los prints en terminal usan `safe_print()` de `utils/safe_print.py`, que también aplica un lock para evitar mezcla de salidas entre hilos.

El AppRouter ejecuta el listener TCP en un hilo separado (`start_listener()`), lo que permite que el menú CLI siga respondiendo mientras el router espera mensajes del controller.

---

## Persistencia — MySQL

El controller persiste todo en MySQL con cuatro tablas:

| Tabla | Contenido |
|-------|-----------|
| `routers` | Routers registrados con ID, IP, puerto y status |
| `topology` | Enlaces entre routers con su costo |
| `routing_tables` | Tablas de ruteo calculadas por router |
| `event_logs` | Log de eventos del sistema |

El AppRouter no usa MySQL. Su configuración (ID, IP, puerto, vecinos, dirección del controller) se lee y escribe en un archivo `router_config.json` local gestionado por `RouterConfigDAO`.

---

## Logging (FR-09)

El controller registra eventos en dos destinos simultáneamente:

- **Archivo** `controller.log`: mediante el módulo `logging` de Python estándar, con timestamp y nivel.
- **MySQL** tabla `event_logs`: para consulta histórica desde cualquier cliente de base de datos.

Los eventos registrados son: `REGISTER`, `TOPOLOGY`, `ROUTE_COMPUTED`, `TABLE_SENT`, `LINK_UPDATE`, `ERROR`.

---

## Algoritmo de enrutamiento — Dijkstra

Se usa la implementación de Dijkstra de la librería **networkx** (`nx.single_source_dijkstra_path` y `nx.single_source_dijkstra_path_length`). El algoritmo opera sobre un grafo dirigido construido desde `NetworkTopology.adjacency`. Se ejecuta desde cada router como nodo origen, obteniendo los caminos más cortos a todos los destinos alcanzables.

**Ejemplo con la topología de referencia del plan de pruebas:**

```
R1 ─(2)─ R2 ─(1)─ R3
R1 ─(5)──────────  R3
```

Dijkstra desde R1:
- R1 → R2: camino directo, costo 2, next_hop = R2
- R1 → R3: camino vía R2 (2+1=3) < directo (5), next_hop = R2, costo = 3

Este resultado es verificado por el test `test_dijkstra_camino_R1_a_R3_via_R2`.

---

## Tests

Los tests están organizados en `tests/` dentro de cada aplicación y cubren los 8 casos de prueba definidos en el plan de pruebas del proyecto (TC-01 a TC-08). Se ejecutan con pytest:

```bash
# Controller
cd ControlSoftwarized
python -m pytest tests/ -v

# Router
cd AppRouter
python -m pytest tests/ -v
```

Todos los tests usan `unittest.mock` para aislar MySQL y los sockets TCP, por lo que no requieren base de datos ni red activa para correr.

| Archivo | Casos | Cubre |
|---------|-------|-------|
| `test_router_registry.py` | 8 | TC-01 / FR-01 |
| `test_topology.py` | 8 | TC-02 / FR-02, FR-03 |
| `test_dijkstra_service.py` | 14 | TC-03 / FR-04 + TC-07 / FR-08 |
| `test_routing_table_service.py` | 8 | TC-04, TC-05 / FR-05, FR-06 |
| `test_controller_communication.py` | 11 | TC-08 / NFR-05 |
| `test_registration.py` | 13 | TC-01, TC-02 lado router |
| `test_routing_table_storage.py` | 13 | TC-05, TC-06 / FR-06, FR-07 |
| `test_router_communication.py` | 13 | NFR-04 + TC-05 red |

---

## Comandos disponibles

### ControlSoftwarized

| Comando | Descripción |
|---------|-------------|
| `/show_routers` | Lista todos los routers registrados |
| `/show_topology` | Muestra la topología almacenada |
| `/show_routing_table` | Consulta la tabla de ruteo de un router |
| `/update_link` | Simula cambio de costo de enlace y recalcula rutas |
| `/help` | Lista de comandos |

### AppRouter

| Comando | Descripción |
|---------|-------------|
| `/add_router` | Configura el router (ID, IP, puerto, vecinos) |
| `/edit_router` | Edita la configuración existente |
| `/connect` | Conecta al controller y ejecuta el flujo completo |
| `/disconnect` | Cierra la conexión TCP |
| `/status` | Estado actual de la conexión |
| `/show_routing_table` | Muestra la tabla de ruteo recibida |
| `/update_link` | Envía cambio de costo de enlace al controller |
| `/help` | Lista de comandos |

---

## Dependencias principales

| Librería | Uso |
|----------|-----|
| `socket` | Comunicación TCP entre controller y routers |
| `threading` | Concurrencia en el servidor y listener del router |
| `networkx` | Implementación de Dijkstra |
| `mysql-connector-python` | Persistencia en MySQL |
| `json` | Serialización de mensajes del protocolo |
| `logging` | Registro de eventos a archivo |
| `dataclasses` | Modelos de datos limpios sin boilerplate |
| `unittest.mock` | Aislamiento en tests |
