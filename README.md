#  Sistema de Información - Parqueadero Autos Colombia

##  Descripción
Sistema web para la gestión integral del parqueadero "Autos Colombia", 
desarrollado como evidencia de aprendizaje para la asignatura de 
Ingeniería de Software - Universidad IU Digital.

**Iteración 1:** Gestión de la entrada y salida de vehículos.

**Iteración 2:** Autenticación por roles, CRUD de vehículos, celdas y operadores.

**Iteración 3:** Gestión de clientes, vínculo vehículo-cliente, asignación
automática de celda y control de capacidad del parqueadero. Incluye fichos de
entrada, control por puertas y reasignación transaccional de celdas.

## 👥 Autor
**Carolina Velasquez avila**

**Johnatan Dario Velez**  

**Elisabeth Martinez**  
  
Estudiantes de Ingeniería de Software  
Octubre 2026

## 🛠️ Tecnologías Utilizadas
- **Backend:** Python 3.13 + FastAPI
- **Frontend:** Angular 22 + TypeScript
- **Base de Datos:** PostgreSQL 13+
- **Migraciones:** Alembic
- **Control de versiones:** Git + GitHub

## 🚗 Iteración 3: clientes, capacidad y control de acceso

**Parte 1: clientes y capacidad**

- Un cliente tiene documento único, nombre, teléfono, correo y estado activo.
  La baja es lógica (`DELETE /clientes/{id}` deja `activo=false`) y conserva su
  historial y sus vehículos.
- Cada vehículo nuevo debe indicar un `cliente_id`. El listado y las respuestas
  incluyen el resumen del cliente; los vehículos heredados pueden no tenerlo.
- El Control de acceso solo pide la placa: el backend elige al azar una celda
  activa y libre compatible con el vehículo y devuelve la celda asignada.
- `AUTOMOVIL` y `CAMIONETA` comparten las 70 celdas de la familia `AUTOS`; `MOTO`
  usa las 10 de `MOTOS`. El límite es de ocupación simultánea, no del catálogo.
- Si el vehículo no tiene un cliente activo, la entrada responde 409 con
  `Vehículo no registrado o mensualidad vencida`. Si la familia está llena o no
  quedan celdas libres, responde 409 con `Sin celdas disponibles`.

**Parte 2: fichos, puertas y reasignación**

- Cada entrada genera un ficho único con formato `AC-YYYYMMDD-XXXX`, consecutivo
  por día en hora de Bogotá. El comprobante se consulta en
  `GET /estancias/{id}/ficho` y se puede previsualizar e **Imprimir Ficho**.
- La entrada y la salida exigen una puerta activa. Las puertas base `NORTE` y
  `SUR` se siembran con la migración `0008` y se listan en `GET /puertas`.
- La salida se registra con el código del ficho y la puerta de salida:
  `{"ficho_codigo": "AC-YYYYMMDD-XXXX", "puerta_salida_id": 2}`. Un ficho
  inexistente, usado o de una estancia cerrada se rechaza con 409/404.
- `POST /estancias/{id}/reasignar` mueve una estancia abierta a otra celda libre
  de la misma familia en una sola transacción. Deja libre la celda anterior,
  mueve el vehículo, guarda el motivo opcional en `estancia_reasignacion` y
  registra la auditoría `REASIGNAR`. Está disponible para `OPERADOR` y
  `ADMINISTRADOR`.
- Una estancia con reasignaciones no se puede anular: `DELETE` responde 409 para
  conservar el historial.

Rutas principales:

| Método y ruta | Uso |
| --- | --- |
| `POST/GET/PATCH/DELETE /clientes` | CRUD de clientes; escritura solo `ADMINISTRADOR` |
| `POST /vehiculos` | Registro de vehículo con `cliente_id` obligatorio |
| `GET /puertas` | Puertas activas para entrada y salida |
| `POST /estancias/entrada` | Entrada con `placa` y `puerta_entrada_id`; celda y ficho automáticos |
| `GET /estancias/{id}/ficho` | Comprobante para consulta e impresión |
| `POST /estancias/salida` | Salida con `ficho_codigo` y `puerta_salida_id` |
| `POST /estancias/{id}/reasignar` | Cambio transaccional de celda con auditoría |
| `GET /estancias/vehiculo/{placa}` | Consulta del estado del vehículo y su estancia |
| `GET /celdas/disponibilidad` | Contadores y celdas libres por tipo |

En la interfaz, el administrador encuentra **Clientes** dentro de la gestión y
**Vehículos** exige seleccionar el propietario. El formulario de registro rápido
del Control de acceso también solicita el cliente. Allí mismo se elige la puerta
de entrada, se muestra el ficho asignado con su botón de impresión, se registra
la salida con ficho y puerta, y se abre el modal **Reasignar celda** con las
celdas libres compatibles.

Las migraciones `0006_clientes.py`, `0007_fichos.py` y
`0008_puertas_reasignacion.py` deben revisarse con
`alembic upgrade 0006:0008 --sql` antes de aplicarlas; no se ejecutan
automáticamente. La base debe quedar en la revisión `0008` para usar fichos,
puertas y reasignaciones.

## ⚙️ Configuración Local

### Requisitos previos
- Python 3.13+
- Node.js 24+
- PostgreSQL 13+
- Git

### Instalación

1. **Clonar el repositorio:**
   ```bash
   git clone https:https://github.com/carolinavelasqueza-web/AutosColombia.git
   cd AutosColombia
