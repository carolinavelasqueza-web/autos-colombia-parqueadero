# Plan de Pruebas — Gestión de Pagos (Iteración 3)

Basado en la implementación real del repositorio: backend FastAPI (`app/schemas/pago.py`,
`app/schemas/tarifa.py`, `app/services/pago.py`, `app/services/tarifa.py`,
`app/services/mensualidad.py`, `app/services/cliente.py`, routers `pagos.py`, `tarifas.py`,
`clientes.py`) y frontend Angular (`registrar-pago`, `listado-pagos`, `services/pagos.service`,
`services/tarifas.service`, `models/mensualidad`, alertas en `control-acceso` y `clientes`,
e impresión térmica en `styles.css`).

---

## 1. Alcance y criterios de aceptación

### 1.1 Tarifas mensuales (`/tarifas`)
- **Alcance**: listar tarifas vigentes (una por tipo) y actualizar la tarifa de un tipo.
- **Criterios**:
  - `GET /tarifas` lo consume cualquier usuario autenticado; devuelve una tarifa vigente por tipo (`vigente_hasta is NULL`), ordenadas por tipo.
  - `PUT /tarifas/{tipo}` es exclusivo de **ADMINISTRADOR**; el operador recibe 403.
  - Tipos válidos: `MOTO`, `AUTOMOVIL`, `CAMIONETA`. Otro tipo → 422.
  - `valor` se valida con `validate_money` (monto monetario; `0 ≤ valor < 10.000.000.000`).
  - Al actualizar, se cierra la tarifa vigente anterior (`vigente_hasta = ahora`) y se crea una nueva fila (historial conservado). Responde **201** si se crea por primera vez, **200** si reemplaza una existente.
  - Montos serializados como texto con 2 decimales (p. ej. `"20000.00"`).

### 1.2 Registro de mensualidad (`POST /pagos`)
- **Alcance**: registrar un pago para un cliente identificado por documento, por 1–12 meses, con método y referencia, generando recibo, actualizando vigencia y reactivando al cliente si aplica.
- **Criterios** (según `PagoCrear` y `registrar_pago`):
  - Accesible para **ADMINISTRADOR** y **OPERADOR**.
  - `documento` obligatorio (se normaliza con `strip`); `meses` entero estricto `1..12`; `metodo ∈ {EFECTIVO, TRANSFERENCIA, TARJETA}`.
  - Referencia: en `EFECTIVO` debe ser nula (si llega valor → 422); en `TRANSFERENCIA`/`TARJETA` es obligatoria, se normaliza a mayúsculas, máx. 100 caracteres, y es única entre pagos vigentes.
  - Cliente inexistente → 404; cliente sin vehículos → 409.
  - Monto total = suma de la tarifa vigente de **cada vehículo cobrado** × meses (cobro por vehículo, no por tipo único). `0 < monto < 10.000.000.000`.
  - Número de recibo consecutivo `RC-NNNNNN` desde `pago_recibo_seq`.
  - Nueva vigencia = `max(hoy, vencimiento_actual) + meses` (hora America/Bogota).
  - Si el cliente estaba inactivo, el pago lo reactiva (`reactivo_cliente = true`) y audita `REACTIVAR_CLIENTE`.
  - Todo en una transacción; audita `REGISTRAR_PAGO`.

### 1.3 Selección individual por vehículo (`vehiculo_ids`)
- **Alcance**: liquidar solo uno o algunos vehículos del cliente.
- **Criterios**:
  - `vehiculo_ids` es opcional. Omitido/`null` → se cobran **todos** los vehículos del cliente (compatibilidad).
  - Si se envía: lista de enteros estrictos `≥ 1`, sin repetidos y no vacía (validación de esquema → 422).
  - Todos los ids deben pertenecer al cliente; si alguno no pertenece → 422 `"Los vehículos seleccionados deben pertenecer al cliente."`.
  - El detalle y el monto del recibo se generan solo con los vehículos seleccionados.

### 1.4 Cálculo de tarifas y devuelta en efectivo (frontend `registrar-pago`)
- **Alcance**: wizard de 3 pasos; en el Paso 2 se listan los vehículos del cliente con checkbox (todos marcados por defecto); el total y la devuelta se calculan en pantalla.
- **Criterios**:
  - Cada vehículo muestra placa, tipo y tarifa individual; debe quedar **al menos uno** seleccionado para continuar/confirmar.
  - Total mostrado = suma de tarifas de los vehículos seleccionados × meses (coincide con el backend al enviar esos `vehiculo_ids`).
  - En `EFECTIVO` aparece "Monto recibido" y se calcula el cambio = recibido − total. No se puede confirmar si el recibido es menor al total; en otros métodos no se pide monto recibido.
  - Se mitiga el doble clic: el botón Confirmar se deshabilita mientras procesa y una segunda invocación no repite la petición.

### 1.5 Consulta y filtrado del historial (`GET /pagos`, `listado-pagos`)
- **Alcance**: listar pagos paginados con filtros.
- **Criterios**:
  - Accesible para **ADMINISTRADOR** y **OPERADOR**.
  - Filtros: `documento`, `estado` (`VIGENTE`/`ANULADO`), rango `desde`/`hasta` (interpretado en Bogotá), `offset`/`limit` (`limit` 1..100).
  - `documento` vacío → 422; rango invertido (`desde > hasta`) → 422.
  - Orden por `fecha DESC, id DESC`.
  - La vista muestra fecha, documento, recibo, meses, total, método y estado; permite "Ver Recibo" solo en pagos VIGENTES.

### 1.6 Generación e impresión de recibo térmico 80mm
- **Alcance**: recibo imprimible en `registrar-pago` (tras pagar) y en `listado-pagos` (modal "Ver Recibo").
- **Criterios**:
  - `GET /pagos/{id}/recibo` devuelve el pago completo (cliente, detalles, montos como texto) o 404 si no existe.
  - El recibo muestra cliente, documento, periodo, método, detalle por vehículo, total y, si fue en efectivo, el monto recibido y el cambio.
  - Botón "Imprimir Recibo" → `window.print()`.
  - Impresión en tirilla única: `@page { size: 80mm auto; margin: 0 }`; el contenedor `.recibo-print` queda a 76 mm, fondo blanco, sin sombras, `min-height: auto` y `break-inside: avoid`; todo lo que no es el recibo se oculta y no reserva altura (sin segunda hoja en blanco); los elementos `.no-print` nunca se imprimen.

### 1.7 Anulación de pagos (`POST /pagos/{id}/anular`)
- **Alcance**: anular un pago vigente y revertir la vigencia del cliente.
- **Criterios**:
  - Exclusivo de **ADMINISTRADOR**; el operador recibe 403. En la interfaz, el botón "Anular Pago" solo es visible para administrador.
  - `motivo` obligatorio, 1..500 caracteres (se normaliza con `strip`).
  - Solo se puede anular el **último** pago vigente del cliente; si existe uno posterior vigente → 409.
  - Pago inexistente → 404; pago ya anulado → 409.
  - La vigencia del cliente se reduce en los meses del pago; si el pago había reactivado al cliente, se vuelve a desactivar. Audita `ANULAR_PAGO` (y `DESACTIVAR_CLIENTE` cuando aplica).
  - En el frontend se pide confirmación con motivo y se mitiga el doble clic.

### 1.8 Alertas de vencimiento
- **Alcance**: estado de mensualidad por cliente y listado de alertas, más avisos visuales en el frontend.
- **Criterios** (según `estado_mensualidad`, Bogotá, `DIAS_POR_VENCER = 5`):
  - Sin fecha de vencimiento → `SIN_PAGO`; días `< 0` → `VENCIDA`; `0..5` → `POR_VENCER`; `> 5` → `AL_DIA`.
  - `GET /clientes/{id}/mensualidad` devuelve el cliente y su estado.
  - `GET /clientes/mensualidad/alertas` lista clientes **activos** con mensualidad `POR_VENCER` o `VENCIDA` (excluye `SIN_PAGO`).
  - Frontend: en `control-acceso`, al consultar un vehículo con cliente se muestra alerta amarilla si está `POR_VENCER`, con la fecha exacta; en `clientes`, badge amarillo "Vence …" en filas activas por vencer (≤ 5 días).

---

## 2. Casos de prueba funcionales (resumen)

| ID | Módulo / Endpoint o Vista | Escenario / Datos de entrada | Resultado esperado (según el código) | Estado |
|----|---------------------------|------------------------------|--------------------------------------|--------|
| TAR-01 | `GET /tarifas` | Usuario autenticado | 200; una tarifa vigente por tipo, ordenadas por tipo; valores como texto `"n.nn"` | Aprobado |
| TAR-02 | `PUT /tarifas/{tipo}` (admin) | Primera tarifa del tipo, `valor` válido | 201; nueva tarifa vigente; audita `ACTUALIZAR_TARIFA` (CREAR) | Aprobado |
| TAR-03 | `PUT /tarifas/{tipo}` (admin) | Tipo ya con tarifa vigente | 200; cierra la anterior (`vigente_hasta`) y crea nueva (REEMPLAZAR) | Aprobado |
| TAR-04 | `PUT /tarifas/{tipo}` (operador) | Operador intenta actualizar | 403 | Aprobado |
| TAR-05 | `PUT /tarifas/{tipo}` | Tipo no válido / `valor` fuera de rango | 422 | Aprobado |
| PAG-01 | `POST /pagos` | `documento`, `meses=3`, `TRANSFERENCIA`, `referencia` | 201; `RC-000001`+, monto = Σ(tarifa×meses), estado VIGENTE, referencia en mayúsculas | Aprobado |
| PAG-02 | `POST /pagos` (esquema) | `meses=0/13/"2"/True`, método inválido, campo extra | 422 (validación de `PagoCrear`) | Aprobado |
| PAG-03 | `POST /pagos` | `EFECTIVO` con `referencia` | 422 "El pago en efectivo no admite referencia." | Aprobado |
| PAG-04 | `POST /pagos` | `TRANSFERENCIA`/`TARJETA` sin referencia | 422 "La referencia es obligatoria para transferencia o tarjeta." | Aprobado |
| PAG-05 | `POST /pagos` | `referencia` > 100 caracteres | 422 "La referencia no puede superar 100 caracteres." | Aprobado |
| PAG-06 | `POST /pagos` | Documento inexistente | 404 "Cliente no encontrado." | Aprobado |
| PAG-07 | `POST /pagos` | Cliente sin vehículos | 409 "El cliente no tiene vehículos registrados." | Aprobado |
| PAG-08 | `POST /pagos` | Cliente inactivo con vencida | Pago reactiva al cliente; `reactivo_cliente=true`; audita `REACTIVAR_CLIENTE` | Aprobado |
| PAG-09 | `registrar_pago` | Tipo sin tarifa vigente | 409 "No hay tarifa vigente para el tipo …" | Aprobado |
| PAG-10 | `registrar_pago` | Error de BD / secuencia nula / conflicto único | 503 o 409/422 según `sqlstate`; rollback; sin detalles privados | Aprobado |
| SEL-01 | `POST /pagos` | 2 autos (250) + 1 moto (100), `vehiculo_ids=[auto, moto]`, meses=2 | Detalle solo de los 2 seleccionados; monto = (250+100)×2 = 700, no los tres | Aprobado |
| SEL-02 | `POST /pagos` | `vehiculo_ids=[un_vehiculo]` | Recibo con un único detalle y su subtotal | Aprobado |
| SEL-03 | `POST /pagos` | Sin `vehiculo_ids` | Cobra todos los vehículos del cliente (compatibilidad) | Aprobado |
| SEL-04 | `POST /pagos` | `vehiculo_ids` con id de otro cliente | 422 "Los vehículos seleccionados deben pertenecer al cliente." | Aprobado |
| SEL-05 | `PagoCrear` (esquema) | `vehiculo_ids` vacío, duplicado, 0, negativo, bool, string, float | 422 (validación de `vehiculo_ids`) | Aprobado |
| FE-PAG-01 | Vista `registrar-pago` (Paso 2) | 2 autos (250) + 1 moto (100), meses=3 | Lista 3 vehículos; total 1.800 (600×3), suma por vehículo no por tipo | Aprobado |
| FE-PAG-02 | Vista `registrar-pago` | Desmarca vehículos hasta dejar 0 | Total se recalcula; con 0 seleccionados, "Continuar" deshabilitado y error "al menos un vehículo" | Aprobado |
| FE-PAG-03 | Vista `registrar-pago` (Paso 3, efectivo) | Total 100.000; recibido 80.000 | `efectivoSuficiente=false`; Confirmar deshabilitado; sin cambio mostrado | Aprobado |
| FE-PAG-04 | Vista `registrar-pago` (Paso 3, efectivo) | Total 100.000; recibido 150.000 | Cambio 50.000 visible; Confirmar habilitado | Aprobado |
| FE-PAG-05 | Vista `registrar-pago` | Método no efectivo | No se pide monto recibido; cambio nulo; puede confirmar | Aprobado |
| FE-PAG-06 | Vista `registrar-pago` | Confirmar en efectivo con cambio | POST `/pagos` con `vehiculo_ids`; recibo muestra recibido y cambio; "Imprimir Recibo" llama `window.print()` una vez | Aprobado |
| FE-PAG-07 | Vista `registrar-pago` | Doble clic en Confirmar | Botón "Procesando…" deshabilitado; segunda llamada no repite el POST | Aprobado |
| FE-PAG-08 | Servicio `registrar-pago` (búsqueda) | Cliente con 3 vehículos propios + 1 ajeno | Lista solo los 3 propios ordenados por placa, con su tarifa; total por vehículo (600) | Aprobado |
| HIS-01 | `GET /pagos` | Paginación `offset/limit` | 200; orden `fecha DESC, id DESC`; aplica límites | Aprobado |
| HIS-02 | `GET /pagos` | Filtro `documento` / `estado` | Join por documento o filtro por estado | Aprobado |
| HIS-03 | `GET /pagos` | Rango `desde/hasta` | Límites en America/Bogota (−05:00) | Aprobado |
| HIS-04 | `GET /pagos` | `documento` vacío / rango invertido | 422 | Aprobado |
| FE-HIS-01 | Vista `listado-pagos` | Carga inicial | Tabla con fecha, documento, recibo, meses, total, método, estado | Aprobado |
| FE-HIS-02 | Vista `listado-pagos` | Filtros documento+estado+fechas | GET con query exacta; actualiza el listado | Aprobado |
| FE-HIS-03 | Vista `listado-pagos` | "Ver Recibo" | Solo en pagos VIGENTES; abre modal con el recibo | Aprobado |
| REC-01 | `GET /pagos/{id}/recibo` | Pago existente | 200; pago completo con cliente, detalles y montos como texto | Aprobado |
| REC-02 | `GET /pagos/{id}/recibo` | Pago inexistente | 404 "Pago no encontrado." | Aprobado |
| FE-REC-01 | Vista `listado-pagos` (modal) | "Imprimir Recibo" | Ticket con clase `recibo-print`; botón dentro de `.no-print`; `window.print()` una vez | Aprobado |
| FE-REC-02 | Impresión (`styles.css`) | Imprimir recibo | `@page 80mm auto, margin 0`; `.recibo-print` a 76 mm, fondo blanco, sin segunda hoja; `.no-print` oculto | Aprobado |
| ANU-01 | `POST /pagos/{id}/anular` (admin) | Último pago vigente, motivo válido | 200; estado ANULADO; vigencia revertida; audita `ANULAR_PAGO` | Aprobado |
| ANU-02 | `POST /pagos/{id}/anular` | Existe un pago posterior vigente | 409 "Solo se puede anular el último pago vigente del cliente." | Aprobado |
| ANU-03 | `POST /pagos/{id}/anular` | Pago inexistente / ya anulado | 404 / 409 "El pago ya está anulado." | Aprobado |
| ANU-04 | `POST /pagos/{id}/anular` | Pago que había reactivado al cliente | Cliente se desactiva; audita `DESACTIVAR_CLIENTE` | Aprobado |
| ANU-05 | `PagoAnular` (esquema) | motivo vacío/`None`/501 caracteres/no texto | 422 | Aprobado |
| FE-ANU-01 | Vista `listado-pagos` | Rol administrador vs operador | "Anular Pago" visible solo para administrador | Aprobado |
| FE-ANU-02 | Vista `listado-pagos` | Anular con motivo + doble clic | Pide motivo; botón bloqueado; una sola petición de anulación | Aprobado |
| MEN-01 | `estado_mensualidad` | `None` / días<0 / 0..5 / >5 | `SIN_PAGO` / `VENCIDA` / `POR_VENCER` / `AL_DIA` | Aprobado |
| MEN-02 | `GET /clientes/{id}/mensualidad` | Cliente existente | 200; `{cliente, estado}` calculado en Bogotá | Aprobado |
| MEN-03 | `GET /clientes/mensualidad/alertas` | Varios clientes | Lista solo activos `POR_VENCER`/`VENCIDA`; excluye `SIN_PAGO` | Aprobado |
| FE-MEN-01 | Util `models/mensualidad` | Fechas relativas a hoy | `diasParaVencer`, `estaPorVencer` (0..5), `formatearVencimiento` sin corrimiento de día | Aprobado |
| FE-MEN-02 | Vista `control-acceso` | Consulta de vehículo, mensualidad `POR_VENCER` | Alerta amarilla con la fecha exacta; ausente si `AL_DIA` | Aprobado |
| FE-MEN-03 | Vista `clientes` | Cliente activo por vencer (≤5 días) | Badge amarillo "Vence …" solo en la fila correspondiente | Aprobado |
| SEG-01 | Interceptor + `/pagos`,`/tarifas` | Petición autenticada | Adjunta `Authorization: Bearer` a `/pagos` y `/tarifas` (y sus subrutas) | Aprobado |

---

## 3. Resumen de cobertura de pruebas automatizadas ejecutadas

### 3.1 Backend (pytest)
- **Suite completa**: **486 pasadas, 21 omitidas** (las omitidas son pruebas que requieren PostgreSQL real).
- **Archivos de la Gestión de Pagos** (`test_pagos.py`, `test_tarifas.py`, `test_mensualidad.py`, `test_pagos_migracion.py`): **202 pasadas**.
  - `test_pagos.py`: esquema `PagoCrear`/`PagoAnular`, cálculo de subtotales y monto, selección por `vehiculo_ids` (subconjunto, uno, todos, id ajeno, validaciones), recibo consecutivo, vigencia/reactivación, referencia por método, conflictos de BD traducidos, listado con filtros y rango en Bogotá, recibo, y reglas de anulación.
  - `test_tarifas.py`: listado vigente, creación/reemplazo con historial, 201 vs 200, roles (403 operador), tipos y montos inválidos, conflictos de BD.
  - `test_mensualidad.py`: `estado_mensualidad`, `sumar_meses`, `nueva_vigencia`, `periodo` (incluye bordes de fin de mes y zona Bogotá).
  - `test_pagos_migracion.py`: estructura de la migración Alembic 0010 (secuencia de recibo, restricciones únicas).

### 3.2 Frontend (Vitest / `ng test`)
- **Suite completa**: **158 pasadas** en 23 archivos (aislamiento por archivo activado).
- **Specs de la Gestión de Pagos** (67 casos `it`):
  - `registrar-pago.component.spec.ts` (9): referencia por método, total por vehículo (bug corregido), selección/deselección, cambio en efectivo y bloqueo de confirmación, recibo imprimible, doble clic, armado de la lista de vehículos.
  - `listado-pagos.component.spec.ts` (6): tabla, filtros, "Ver Recibo" solo vigentes, "Anular Pago" solo admin, anulación con motivo sin duplicar, botón "Imprimir Recibo".
  - `pagos.service.spec.ts` (9) y `tarifas.service.spec.ts` (2): construcción de URLs/params de listar, recibo, anular, mensualidad, alertas, recaudo y tarifas.
  - `models/mensualidad.spec.ts` (3): cálculo de días, estado por vencer y formato de fecha.
  - `control-acceso.spec.ts` (18) y `clientes.spec.ts` (10): incluyen las alertas de vencimiento (amarilla con fecha / badge por vencer).
  - `gestion-tarifas.spec.ts` (5): gestión de tarifas en la interfaz.
  - `auth.interceptor.spec.ts` (5): token adjuntado a `/pagos` y `/tarifas`.

### 3.3 Build
- `ng build` (producción) compila **sin errores ni advertencias** de presupuesto (budget `anyComponentStyle` elevado a 8 kB).

> **Estado global: todas las pruebas automatizadas en verde.** La columna "Estado: Aprobado" de la tabla refleja el comportamiento verificado por estas suites sobre la implementación actual.
