# Backend de Autos Colombia

## Autenticación y roles

La revisión `0003_autenticacion_rbac.py` amplía `operador` con `usuario`,
`contrasena_hash`, `rol` y `activo`, y crea la tabla `auditoria`. Los roles
admitidos son `ADMINISTRADOR` y `OPERADOR`. Las contraseñas se guardan con
bcrypt; nunca se devuelven en las respuestas ni se registran en auditoría.

| Método y ruta | Acceso | Resultado |
| --- | --- | --- |
| `POST /api/v1/auth/login` | Público | 200 con `access_token`, `token_type` y `expires_in`; 401 con credenciales inválidas |
| `GET /api/v1/auth/me` | Autenticado | 200 con id, nombre, usuario, rol y estado activo |

El token JWT usa HS256 e incluye `sub`, `user_id`, `rol`, `iat` y `exp`.
`get_current_user` vuelve a consultar el operador en cada solicitud, de modo que
una desactivación o un cambio de rol surten efecto de inmediato. Los errores de
autenticación devuelven 401; un rol insuficiente devuelve 403; si falta
`JWT_SECRET_KEY`, las operaciones que emiten o validan tokens devuelven 503.

Rutas administrativas (solo `ADMINISTRADOR`): crear, actualizar y desactivar
operadores; crear, actualizar, desactivar y eliminar celdas; crear, actualizar y
desactivar clientes; corregir y anular estancias. El resto de rutas requieren un
token válido. La entrada y salida de
estancias toman el `operador_id` del token, no del cuerpo de la solicitud. Tanto
`OPERADOR` como `ADMINISTRADOR` pueden registrar entradas, salidas y
reasignaciones de celda; cuando el administrador cubre el turno de un operador
ausente, la estancia, la reasignación y la auditoría conservan su propio
`operador_id`.
`DELETE /operadores/{id}` realiza una baja lógica (`activo=false`) para conservar
la trazabilidad; no borra el registro.

Cada operación relevante agrega una fila en `auditoria` con el operador
autenticado, la acción, la entidad, su id y un detalle JSON sin secretos. La
auditoría no acepta un operador indicado por el cliente. Las correcciones de
estancias registran `ACTUALIZAR` con los valores anteriores y nuevos; las
anulaciones registran `ELIMINAR` con un snapshot completo, incluido el
`operador_entrada_id` original y el `operador_id` del administrador que ejecutó
la acción.

### Configurar JWT y crear el primer administrador

Copia `.env.example` a `.env` sin sobrescribir un archivo existente y completa:

```dotenv
JWT_SECRET_KEY=una-clave-aleatoria-de-al-menos-32-caracteres
JWT_EXPIRE_MINUTES=60
```

`JWT_SECRET_KEY` es obligatoria y no puede conservar el marcador `CAMBIAR_...`.
`JWT_EXPIRE_MINUTES` debe estar entre 1 y 1440. No hay usuario ni contraseña por
defecto en la migración. Después de aplicar `0003`, crea el primer administrador
de forma interactiva o mediante variables de entorno:

```powershell
.\.venv\Scripts\python.exe .\create_admin.py
# Alternativa no interactiva:
$env:ADMIN_NOMBRE = 'Administrador'
$env:ADMIN_TELEFONO = '0000000000'
$env:ADMIN_USUARIO = 'admin'
$env:ADMIN_CONTRASENA = 'una-clave-segura'
try {
    .\.venv\Scripts\python.exe .\create_admin.py
} finally {
    Remove-Item Env:ADMIN_NOMBRE, Env:ADMIN_TELEFONO, Env:ADMIN_USUARIO, Env:ADMIN_CONTRASENA -ErrorAction SilentlyContinue
}
```

El script no imprime la contraseña ni el hash. Si el usuario ya existe, termina
con código 1 sin modificar datos.

## CRUD de operadores

Disponible bajo `/operadores` con POST, GET paginado, GET por id, PATCH parcial y
DELETE lógico. Requiere autenticación; las mutaciones exigen rol
`ADMINISTRADOR`. Los campos obligatorios al crear son `nombre`, `telefono`,
`usuario` y `contrasena`; `rol` y `activo` son opcionales y usan `OPERADOR` y
`true` por defecto. `usuario` se normaliza a minúsculas y admite entre
3 y 50 caracteres: letras, números, punto, guion y guion bajo. La contraseña debe
tener al menos 8 caracteres y no superar 72 bytes.

PATCH solo cambia los campos enviados; `contrasena` se vuelve a hashear y nunca se
devuelve. No se permite que un administrador se desactive, se quite el rol ni deje
la aplicación sin al menos otro administrador activo: esos casos devuelven 409.
El usuario duplicado devuelve 409 y los datos inválidos, 422.

El listado oculta las cuentas inactivas por defecto (`activo=true`). Para verlas,
usa `?incluir_inactivos=true` o filtra con `?activo=false`. Las bajas son lógicas:
la fila se conserva para que `auditoria` mantenga su referencia.

## CRUD de clientes

La revisión `0006_clientes.py` crea la tabla `cliente` y agrega
`vehiculo.cliente_id` (clave foránea con `ON DELETE RESTRICT` e índice). Un
cliente tiene `documento`, `nombre`, `telefono`, `correo` y `activo`; solo
`documento` es único. La relación es 1:N: cada vehículo pertenece a un cliente y
un cliente puede tener varios vehículos.

Las rutas están bajo `/clientes`. La consulta requiere autenticación; crear,
editar y desactivar exigen rol `ADMINISTRADOR`.

| Método y ruta | Resultado |
| --- | --- |
| `POST /clientes` | 201 y cliente creado; `activo` es `true` por defecto |
| `GET /clientes?offset=0&limit=20` | 200 con `items`, `total`, `offset` y `limit` |
| `GET /clientes?activo=false` | 200 filtrando solo clientes inactivos |
| `GET /clientes/{id}` | 200 o 404 |
| `PATCH /clientes/{id}` | 200 con los campos enviados actualizados |
| `DELETE /clientes/{id}` | 204; baja lógica (`activo=false`), no borra el registro |

Los textos se recortan y no pueden quedar vacíos. `correo` se valida con una
comprobación pragmática de formato (`usuario@dominio.algo`) y no es único.
`activo` debe ser booleano estricto. El documento duplicado devuelve 409 con
`Ya existe un cliente con ese documento.`; los datos inválidos devuelven 422.

`DELETE` es idempotente: un cliente ya inactivo responde 204 sin cambios. La baja
lógica conserva vehículos, estancias y auditoría; para reactivar usa
`PATCH /clientes/{id}` con `{"activo": true}`. Un cliente inactivo puede seguir
asociado a vehículos en el CRUD, pero sus vehículos no podrán registrar entrada.

## Gestión de celdas

Se revisó PostgreSQL antes de implementar el CRUD: la tabla `celda` y la revisión
`0001` ya existían y no había migraciones pendientes. Se verificaron `id BIGINT
GENERATED ALWAYS AS IDENTITY`, clave primaria, `codigo` único, campos `NOT NULL`
y los CHECK de código normalizado y textos no vacíos. No se modificaron migraciones
aplicadas ni se recrearon tablas.

El CRUD sigue la organización de vehículos: `app/schemas/celda.py`,
`app/services/celda.py` y `app/routers/celdas.py`.

La estructura base tiene 80 celdas: 70 de tipo `AUTOMOVIL` con códigos `C-01` a
`C-70` y 10 de tipo `MOTO` con códigos `M-01` a `M-10`. El seed es idempotente y
se ejecuta al iniciar la API mediante `app/services/celda_seed.py`; solo inserta
las celdas que falten y no sobrescribe las existentes. Se puede desactivar con
`CELDAS_SEED_ON_STARTUP=0`. La migración `0004` contiene la misma estructura para
las bases que se actualicen mediante Alembic.

Las celdas predeterminadas conservan su código y no se pueden borrar físicamente;
el administrador sí puede cambiar su tipo y desactivarlas. Las celdas adicionales
creadas por el administrador pueden editarse; al eliminarlas se borran si no
tienen historial y se desactivan si tienen estancias relacionadas. El listado y la
consulta están disponibles para cualquier usuario autenticado; crear, editar,
desactivar y eliminar exige rol `ADMINISTRADOR`.

La revisión `0005_celda_activo.py` agrega `celda.activo` (`BOOLEAN NOT NULL
DEFAULT true`). El listado devuelve solo celdas activas por defecto. El
administrador puede usar `?incluir_inactivas=true` o `?activo=false`; un operador
que solicite inactivas recibe 403. Una celda inactiva no aparece en el listado
normal y rechaza nuevas entradas con 409.

| Operación | Resultado |
| --- | --- |
| POST `/celdas` con `codigo` y `tipo` | 201 con la celda creada y `activo=true` |
| GET `/celdas?offset=0&limit=20` | 200 con items activos, total, offset y limit |
| GET `/celdas/disponibilidad` | 200 con celdas activas, `disponible` y resumen por tipo |
| GET `/celdas/{id}` | 200 o 404; incluye celdas inactivas |
| PATCH `/celdas/{id}` | 200; admite `codigo`, `tipo` y `activo` |
| DELETE `/celdas/{id}` | 204 sin cuerpo; baja lógica o borrado físico según el caso |

`codigo` se recorta y convierte a mayúsculas. `tipo` es texto libre obligatorio; se
compara con el tipo del vehículo al registrar entradas (ver más abajo). Blancos y
datos inválidos devuelven 422; código duplicado devuelve 409, con rollback.
Cambiar el código de una celda predeterminada devuelve 409. `DELETE` es
idempotente: una celda ya inactiva responde 204 sin cambios. Si la celda es
predeterminada o tiene estancias, se marca `activo=false` y se audita
`DESACTIVAR`; si no tiene historial, se elimina la fila y se audita `ELIMINAR`.
Una estancia creada entre la comprobación y el borrado físico también provoca baja
lógica, evitando fallos de integridad referencial. Usa `/docs`, sección **Celdas**,
con un ejemplo como `{"codigo":"A-01","tipo":"Espacio general"}`.

### Disponibilidad, familias y asignación automática

`GET /celdas/disponibilidad` está disponible para cualquier usuario autenticado y
resuelve la ocupación en una sola consulta: devuelve las celdas activas con
`disponible` en `true` o `false` según existan estancias abiertas (`salida IS
NULL`), además de `total`, `disponibles`, `ocupadas`,
`ocupacion_porcentaje` y el resumen `por_tipo`. Las celdas inactivas no cuentan en
los totales. El Control de acceso usa esta respuesta solo para los contadores; la
celda de entrada ya no se elige manualmente.

Los tipos de vehículo se agrupan en familias de celdas en `app/tipos.py`:
`AUTOMOVIL` y `CAMIONETA` comparten `AUTOS`, mientras que `MOTO` usa `MOTOS`. La
comparación normaliza acentos, mayúsculas y espacios. `PATCH /estancias/{id}`
sigue validando la familia cuando la estancia queda abierta, tanto al cambiar
`vehiculo_id` o `celda_id` como al reabrir con `salida=null`; un cruce de familia
devuelve 400 con `El tipo de vehículo no corresponde al tipo de la celda
seleccionada.`

`POST /estancias/entrada` recibe `{"placa": "...", "puerta_entrada_id": 1}`. El
backend:

1. Valida que la puerta exista y esté activa; si no, devuelve 404 con
   `Puerta no encontrada.` o 409 con `La puerta no está activa.`
2. Busca el vehículo; si no existe devuelve 404 con `Vehículo no encontrado.`
3. Exige que el vehículo tenga un cliente asociado y activo; si no, devuelve 409
   con `Vehículo no registrado o mensualidad vencida` (sin punto final).
4. Rechaza un segundo ingreso del mismo vehículo con 409.
5. Aplica el límite de ocupación simultánea de la familia: 70 vehículos
   `AUTOS` y 10 `MOTOS` (`app/capacidad.py`). El límite es de vehículos dentro,
   no del catálogo de celdas; un administrador puede crear celdas adicionales sin
   ampliar la capacidad.
6. Elige al azar una celda activa y libre de la misma familia y genera el ficho
   diario. Si otra entrada ocupa esa celda o usa el mismo consecutivo antes del
   `INSERT`, reintenta hasta cinco veces; si no queda cupo o celda libre devuelve
   409 con `Sin celdas disponibles` (sin punto final).

La respuesta 201 es `EstanciaAbiertaRespuesta`: incluye la estancia, el objeto
`celda` asignado y `puerta_entrada`, además de `ficho_codigo`. Enviar `celda_id`
en la entrada devuelve 422 porque el contrato usa `extra="forbid"`. Los índices
únicos parciales `uq_estancia_vehiculo_abierta` y `uq_estancia_celda_abierta`
siguen protegiendo la concurrencia real; los errores 409 de ocupación se traducen
a mensajes públicos sin detalles del controlador.

### Fichos y puertas

La revisión `0007_fichos.py` agrega `estancia.ficho_codigo` (`TEXT`, único y
nullable para conservar estancias heredadas) y `estancia.ficho_usado_en`. El
formato es `AC-YYYYMMDD-XXXX`, con la fecha en hora de Bogotá y un consecutivo
diario de cuatro dígitos que empieza en `0001`. La unicidad final la impone
`uq_estancia_ficho_codigo`; `app/services/ficho.py` calcula el siguiente código y
la entrada reintenta si otra transacción se adelanta. Al superar `9999` fichos en
un día responde 409 con `No se pudo generar el ficho de entrada.`

La revisión `0008_puertas_reasignacion.py` crea `puerta` (`id`, `codigo`,
`ubicacion`, `activo`), siembra `NORTE` y `SUR` con `ON CONFLICT DO NOTHING` y
agrega a `estancia` las claves foráneas `puerta_entrada_id` y
`puerta_salida_id`. Las columnas son nullable para no romper las estancias
anteriores, pero toda entrada y salida nueva exige una puerta activa.

| Método y ruta | Acceso | Resultado |
| --- | --- | --- |
| `GET /puertas` | Autenticado | 200 con las puertas activas ordenadas por código |
| `GET /puertas?incluir_inactivas=true` | `ADMINISTRADOR` | 200 con todas las puertas; un operador recibe 403 |
| `GET /estancias/{id}/ficho` | Autenticado | 200 con el comprobante y sus relaciones; 404 si la estancia no existe; 409 si no tiene ficho |

`FichoRespuesta` incluye `ficho_codigo`, `entrada`, `salida`, `ficho_usado_en`,
`vehiculo`, `celda`, `puerta_entrada`, `puerta_salida`, los operadores y el
resumen del `cliente`. Es la fuente del panel **Imprimir Ficho** del frontend.

`POST /estancias/salida` recibe `{"ficho_codigo": "AC-20261019-0001",
"puerta_salida_id": 2}`; ya no acepta `placa`. Valida, en este orden, que el
ficho exista (404 `Ficho no encontrado.`), que la estancia siga abierta (409
`La estancia ya está cerrada.`), que el ficho no se haya usado (409
`El ficho ya fue utilizado.`) y que la puerta exista y esté activa. La salida
bloquea la fila con `FOR UPDATE`, registra `salida`, `operador_salida_id`,
`ficho_usado_en` y `puerta_salida_id`, y audita `SALIDA` con el ficho y la puerta.
Dos lecturas concurrentes del mismo ficho producen una sola salida y un 409.

### Reasignación de celda

`POST /estancias/{id}/reasignar` está disponible para `OPERADOR` y
`ADMINISTRADOR` y recibe `{"celda_nueva_id": 7, "motivo": "opcional"}`. El motivo
se recorta, es opcional y admite hasta 500 caracteres. En una única transacción
`app/services/reasignacion.py`:

1. Bloquea la estancia con `FOR UPDATE` y exige que esté abierta.
2. Rechaza la misma celda actual, una celda inexistente o inactiva, un tipo de
   celda de otra familia y una celda ya ocupada por otra estancia abierta.
3. Mueve `estancia.celda_id`, deja libre la celda anterior y conserva el vehículo,
   el ficho y el historial de la estancia.
4. Inserta `estancia_reasignacion` con celda anterior, celda nueva, operador,
   fecha y motivo, y audita `REASIGNAR` con la placa y las celdas.
5. Confirma todo o revierte: si falla cualquier paso no queda un estado intermedio.

Los errores públicos son 404 `Estancia no encontrada.`/`Celda no encontrada.`,
400 `El tipo de vehículo no corresponde al tipo de la celda seleccionada.` y 409
`Solo se pueden reasignar estancias abiertas.`, `La celda nueva debe ser diferente
a la actual.`, `La celda no está disponible.` o `La celda está ocupada.`

`estancia_reasignacion` usa `ON DELETE RESTRICT` hacia estancia, celdas y
operador. Por eso una estancia con reasignaciones no se puede anular:
`DELETE /estancias/{id}` responde 409 con
`La estancia tiene reasignaciones registradas y no se puede anular.` y conserva
el registro y su auditoría.

### Corrección y anulación de estancias

`PATCH /estancias/{id}` y `DELETE /estancias/{id}` son exclusivos de
`ADMINISTRADOR`; un operador recibe 403 y una solicitud sin token, 401. Los
operadores conservan el registro normal de entrada y salida, la consulta de
vehículos, el ficho y la reasignación de celda.

`PATCH` admite `vehiculo_id`, `celda_id`, `entrada` y `salida`; los tres primeros
no aceptan `null`, las fechas requieren zona horaria y `salida=null` reabre la
estancia limpiando `operador_salida_id`. Al cerrar una estancia abierta se asigna
el administrador como `operador_salida_id`; si solo se corrige una estancia ya
cerrada, se conserva el operador de salida original. Cada cambio registra
auditoría `ACTUALIZAR` con los campos, valores anteriores y nuevos, y el
`operador_entrada_id` original.

`DELETE` elimina físicamente la estancia y registra auditoría `ELIMINAR` con un
snapshot completo (`id`, `vehiculo_id`, `celda_id`, `entrada`, `salida`,
`operador_entrada_id`, `operador_salida_id`) y el `operador_id` del administrador
autenticado. Así se conserva quién creó, quién corrigió y quién anuló el registro.
Los datos inválidos devuelven 422, una estancia inexistente 404 y los conflictos
de ocupación 409.

Las pruebas `tests/test_celdas_postgres.py` se habilitan con `RUN_POSTGRES_TESTS=1`,
igual que las de vehículos. Verifican restricciones y CRUD reales dentro de
transacciones revertidas; las secuencias pueden avanzar. No ejecutan DDL.

Desde `backend`, en PowerShell:

```powershell
.\.venv\Scripts\python.exe -m alembic -c .\alembic.ini current
.\.venv\Scripts\python.exe -m alembic -c .\alembic.ini heads
$env:RUN_POSTGRES_TESTS = '1'
try {
    .\.venv\Scripts\python.exe -m pytest -q
} finally {
    Remove-Item Env:RUN_POSTGRES_TESTS -ErrorAction SilentlyContinue
}
```

Entorno verificado: Python 3.13.16 en Windows.
Ejecuta los siguientes comandos desde la carpeta `backend` en PowerShell.

## Preparar el entorno

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

`requirements.txt` fija todas las dependencias de ejecución y pruebas, incluidas
las transitivas. No es necesario activar el entorno virtual.

## Ejecutar la API

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

`GET http://127.0.0.1:8000/health` devuelve `{"status": "ok"}` con estado HTTP 200.
La documentación interactiva está en `http://127.0.0.1:8000/docs`.

## Ejecutar las pruebas

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

## PostgreSQL local

1. Instala e inicia PostgreSQL localmente y prepara una base de datos y un usuario.
   Este proyecto no instala PostgreSQL ni crea bases de datos. Las tablas se crean
   únicamente cuando ejecutas explícitamente las migraciones descritas más abajo.
2. Si no existe `.env`, copia la plantilla sin sobrescribir un archivo existente:

   ```powershell
   if (-not (Test-Path -LiteralPath .env)) {
       Copy-Item -LiteralPath .env.example -Destination .env
   }
   ```

3. Edita `.env` localmente. Completa `DB_NAME`, `DB_USER` y `DB_PASSWORD`.
   Confirma `DB_HOST` y `DB_PORT` (ejemplos: `127.0.0.1` y `5432`).
   `DB_CONNECT_TIMEOUT` es un entero entre 1 y 60 segundos.
   Los valores `CAMBIAR_...` son marcadores: no permiten intentar una conexión.
   Si la contraseña contiene espacios o `#`, usa comillas simples en `.env`.
   No se interpolan expresiones `${...}` dentro de los valores.
4. Comprueba la conexión:

   ```powershell
   .\.venv\Scripts\python.exe .\check_db.py
   $LASTEXITCODE
   ```

El comando solo ejecuta `SELECT 1`, sin crear ni modificar tablas. Devuelve 0
únicamente tras verificar una respuesta real; 2 si faltan variables o son
inválidas; 1 si la conexión o la consulta fallan. No imprime credenciales, URL
de conexión ni detalles del controlador que pudieran contener datos privados.

Desde cualquier carpeta puedes usar rutas absolutas:

```powershell
& 'C:\Users\user\Documents\IU DIGITAL\Clase Ingeniería de Software\AutosColombia\backend\.venv\Scripts\python.exe' 'C:\Users\user\Documents\IU DIGITAL\Clase Ingeniería de Software\AutosColombia\backend\check_db.py'
```

`app/config.py` localiza `.env` respecto a su propio archivo, independientemente
de la carpeta de ejecución. Las variables de entorno tienen prioridad sobre
`.env`. Reinicia los procesos después de cambiar la configuración.

`app/database.py` proporciona `get_engine()` y la dependencia `get_session()`
para futuros endpoints. No conecta al importar ni ejecuta `create_all` o
migraciones. `/health` sigue comprobando la API, no PostgreSQL, y funciona sin
configurar la base de datos. Las pruebas usan datos ficticios y conexiones
simuladas; la verificación real se hace con `check_db.py`.

`.env` está excluido de Git. `.env.example` se conserva como plantilla pública;
nunca copies contraseñas reales a ella.

## Modelos y migraciones

Los modelos están en `app/models.py`, separados de la conexión (`app/database.py`)
y de la configuración (`app/config.py`). Las revisiones crean y amplían estas
tablas; `0001` crea las tres primeras, `0002` añade `estancia`, `0003` amplía
`operador` y crea `auditoria`, `0004` siembra las 80 celdas base, `0005` agrega
`celda.activo`, `0006` crea `cliente` y vincula `vehiculo.cliente_id`, `0007`
agrega el ficho a `estancia` y `0008` crea `puerta` y `estancia_reasignacion`:

| Clase | Tabla | Atributos |
| --- | --- | --- |
| Vehiculo | vehiculo | id, placa, color, modelo, marca, tipo, cliente_id |
| Cliente | cliente | id, documento, nombre, telefono, correo, activo |
| Celda | celda | id, codigo, tipo, activo |
| Puerta | puerta | id, codigo, ubicacion, activo |
| Operador | operador | id, nombre, telefono, usuario, contrasena_hash, rol, activo |
| Estancia | estancia | id, vehiculo_id, celda_id, entrada, salida, operador_entrada_id, operador_salida_id, ficho_codigo, ficho_usado_en, puerta_entrada_id, puerta_salida_id |
| EstanciaReasignacion | estancia_reasignacion | id, estancia_id, celda_anterior_id, celda_nueva_id, operador_id, fecha, motivo |
| Auditoria | auditoria | id, operador_id, accion, entidad, entidad_id, fecha, detalle |

La revisión `0003` agrega a `operador` las columnas de autenticación y estado, y
crea `auditoria` con una clave foránea `ON DELETE RESTRICT` hacia `operador`. Las
filas heredadas de `0001`/`0002` se migran con `usuario='operador-<id>'`, un hash
inutilizable, rol `OPERADOR` y `activo=false`; no se crean credenciales por
defecto. `rol` solo admite `ADMINISTRADOR` u `OPERADOR`.

- `id` usa `BIGINT GENERATED ALWAYS AS IDENTITY` y clave primaria. Se omite al insertar.
- Los campos obligatorios son `NOT NULL`; `vehiculo.cliente_id`, `estancia.salida`,
  `estancia.operador_salida_id`, `auditoria.entidad_id` y `auditoria.detalle`
  admiten `NULL`. Los textos obligatorios tienen comprobaciones contra valores
  vacíos o formados únicamente por espacios, tabulaciones o saltos de línea.
- El ORM elimina espacios exteriores y convierte `placa` y `codigo` a mayúsculas,
  tanto al construir objetos como al asignar estos atributos. PostgreSQL exige
  esa forma normalizada mediante `CHECK` y garantiza su unicidad con `UNIQUE`.
  SQL directo y operaciones masivas que omiten validadores deben normalizar antes;
  la base rechaza valores sin normalizar en lugar de transformarlos silenciosamente.
- `cliente.documento` es único y `correo` tiene un `CHECK` de formato, pero no es
  único. `vehiculo.cliente_id` usa `ON DELETE RESTRICT`: no se borra un cliente
  con vehículos asociados (la baja normal es lógica con `activo=false`).
- `estancia.ficho_codigo` es única y tiene `CHECK` de formato
  `^AC-[0-9]{8}-[0-9]{4}$`; `ficho_usado_en` exige que exista un ficho y no puede
  ser anterior a `entrada`. Las estancias heredadas pueden conservar ficho y
  puertas en `NULL`; las nuevas entradas siempre generan ambos.
- `puerta.codigo` se normaliza a mayúsculas y es único. Las claves foráneas de
  `estancia` y `estancia_reasignacion` usan `ON DELETE RESTRICT`, así que no se
  borran puertas, celdas ni operadores con historial.
- `modelo` es un año entero entre 1 y 9999, no un nombre comercial; no se impone
  un límite vinculado al año actual. `telefono` es texto y conserva prefijos y ceros.
- El tipo de vehículo admite únicamente `MOTO`, `AUTOMOVIL` y `CAMIONETA`.
  El tipo de celda es texto no vacío; la compatibilidad se resuelve por familia
  (`AUTOS` para automóvil/camioneta, `MOTOS` para moto) en `app/tipos.py`.
- No se crean tablas automáticamente al iniciar FastAPI ni al importar módulos.
  `/health` conserva su funcionamiento independiente de PostgreSQL.

La revisión **0003** supone que `0001` y `0002` ya están aplicadas. La revisión
**0004** siembra las 80 celdas base y supone que `0003` ya está aplicada. La
revisión **0005** agrega `celda.activo` y depende de `0004`; no reactiva celdas
desactivadas porque el seed usa `ON CONFLICT DO NOTHING`. La revisión **0006**
crea `cliente` y agrega `vehiculo.cliente_id` como nullable para no romper los
vehículos existentes; no asigna clientes automáticamente. La revisión **0007**
agrega `ficho_codigo` y `ficho_usado_en` a `estancia` sin generar fichos para el
historial. La revisión **0008** crea `puerta`, siembra `NORTE` y `SUR`, agrega las
puertas a `estancia` como nullable y crea `estancia_reasignacion`; no asigna
puertas a las estancias anteriores. Antes de ejecutar cada revisión revisa su SQL
con `upgrade 0002:0003 --sql`, `upgrade 0003:0004 --sql`,
`upgrade 0004:0005 --sql`, `upgrade 0005:0006 --sql`,
`upgrade 0006:0007 --sql`, `upgrade 0007:0008 --sql` o `upgrade head --sql`; no
las apliques sin autorización. Las cuentas existentes quedan desactivadas y sin
contraseña utilizable. Alembic reutiliza `backend/.env` y no almacena una URL con
credenciales en su INI.

### Instalar y revisar sin modificar PostgreSQL

```powershell
Set-Location -LiteralPath 'C:\Users\user\Documents\IU DIGITAL\Clase Ingeniería de Software\AutosColombia\backend'
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe .\check_db.py
.\.venv\Scripts\python.exe -m alembic -c .\alembic.ini history
.\.venv\Scripts\python.exe -m alembic -c .\alembic.ini heads
Get-Content -LiteralPath .\migrations\versions\0003_autenticacion_rbac.py
Get-Content -LiteralPath .\migrations\versions\0004_celdas_predeterminadas.py
Get-Content -LiteralPath .\migrations\versions\0005_celda_activo.py
Get-Content -LiteralPath .\migrations\versions\0006_clientes.py
Get-Content -LiteralPath .\migrations\versions\0007_fichos.py
Get-Content -LiteralPath .\migrations\versions\0008_puertas_reasignacion.py
.\.venv\Scripts\python.exe -m alembic -c .\alembic.ini upgrade 0002:0003 --sql
.\.venv\Scripts\python.exe -m alembic -c .\alembic.ini upgrade 0003:0004 --sql
.\.venv\Scripts\python.exe -m alembic -c .\alembic.ini upgrade 0004:0005 --sql
.\.venv\Scripts\python.exe -m alembic -c .\alembic.ini upgrade 0005:0006 --sql
.\.venv\Scripts\python.exe -m alembic -c .\alembic.ini upgrade 0006:0007 --sql
.\.venv\Scripts\python.exe -m alembic -c .\alembic.ini upgrade 0007:0008 --sql
.\.venv\Scripts\python.exe -m alembic -c .\alembic.ini upgrade head --sql
```

El último comando **solo imprime SQL**: no conecta a PostgreSQL ni aplica cambios.
Incluye las tablas, columnas, restricciones, índices y datos iniciales de las
ocho revisiones y `alembic_version`, que Alembic utiliza para registrar las
revisiones aplicadas. Las pruebas comparan modelos y migraciones y compilan DDL
PostgreSQL, pero no crean tablas ni prueban inserciones reales en la base local.

### Aplicar después de revisar (estos comandos sí modifican el esquema)

Ejecuta este bloque únicamente cuando decidas aplicar la migración:

```powershell
Set-Location -LiteralPath 'C:\Users\user\Documents\IU DIGITAL\Clase Ingeniería de Software\AutosColombia\backend'
.\.venv\Scripts\python.exe .\check_db.py
if ($LASTEXITCODE -ne 0) { throw 'La conexión no está disponible; no aplicar migraciones.' }
.\.venv\Scripts\python.exe -m alembic -c .\alembic.ini upgrade head
if ($LASTEXITCODE -ne 0) { throw 'La migración no se completó; revisar el esquema antes de continuar.' }
.\.venv\Scripts\python.exe -m alembic -c .\alembic.ini current
```

El resultado esperado de `current` después de aplicar es `0008 (head)`.
No uses `stamp` para dar por aplicada una migración que no se ejecutó. Si ya hay
tablas con los mismos nombres, detente y revisa su estructura: la migración no
las borra ni las recrea y fallará ante un conflicto. El `downgrade` de `0003`
elimina la auditoría y las columnas de autenticación, pero conserva las tablas de
`0001`/`0002`; no lo ejecutes como parte de la instalación. Después de aplicar
`0003`, crea el primer administrador con `create_admin.py`.

Los paths de Alembic se resuelven respecto a `alembic.ini`. Desde otra carpeta,
utiliza rutas absolutas para el intérprete y `-c`, igual que con `check_db.py`.

## CRUD de vehículos

La implementación se divide en `app/schemas/vehiculo.py` (validación y respuestas),
`app/routers/vehiculos.py` (APIRouter) y `app/services/vehiculo.py` (operaciones y
transacciones). Reutiliza el modelo `Vehiculo`, `get_session()` y las tablas existentes.

| Método y ruta | Resultado |
| --- | --- |
| `POST /vehiculos` | 201 y vehículo registrado, incluido su id |
| `GET /vehiculos?offset=0&limit=20` | 200 con `items`, `total`, `offset` y `limit` |
| `GET /vehiculos/{id}` | 200 y vehículo, o 404 |
| `PATCH /vehiculos/{id}` | 200 y vehículo actualizado, o 404 |
| `DELETE /vehiculos/{id}` | 204 sin cuerpo, o 404 |

La lista se ordena por id ascendente; `offset` empieza en 0 y `limit` admite de
1 a 100 (20 por defecto). `total` es el número total de vehículos, no solo el de
la página. Los ids deben ser enteros positivos dentro del rango de BIGINT.

Al crear se requieren placa, color, modelo, marca, tipo y `cliente_id`. El año
debe ser un entero JSON entre 1 y 9999; no se aceptan cadenas, booleanos ni
decimales. Los textos no pueden estar vacíos. La placa se recorta y se convierte
a mayúsculas. Los tipos admitidos son `MOTO`, `AUTOMOVIL` y `CAMIONETA`.
`cliente_id` debe existir; si no, devuelve 404. La respuesta incluye el resumen
del cliente en `cliente`. Por compatibilidad con vehículos anteriores a `0006`,
la columna es nullable en la base y las lecturas pueden devolver
`cliente_id`/`cliente` en `null`, pero los vehículos nuevos creados por la API o
la interfaz exigen cliente. Un cliente inactivo puede asignarse en el CRUD; la
restricción de mensualidad se aplica únicamente al registrar la entrada.

PATCH aplica solo los campos enviados, rechaza valores nulos y campos desconocidos,
incluido `id`. Un objeto vacío conserva el vehículo. También permite reasignar
`cliente_id`, comprobando que el cliente exista. Los errores de validación
devuelven 422, una placa duplicada devuelve 409 y un vehículo inexistente, 404.
La unicidad se comprueba en PostgreSQL, también ante peticiones concurrentes;
las transacciones fallidas se revierten. Una clave foránea que impida borrar
devuelve 409 sin eliminar registros relacionados. No hay borrado en cascada en
el servicio. Los fallos generales de base de datos devuelven 503 sin detalles privados.

### Probar desde /docs

Inicia o reinicia el servidor para cargar las nuevas rutas:

```powershell
Set-Location -LiteralPath 'C:\Users\user\Documents\IU DIGITAL\Clase Ingeniería de Software\AutosColombia\backend'
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Abre <http://127.0.0.1:8000/docs>, despliega **Vehículos** y usa **Try it out**.
Crea un vehículo con POST, copia el id devuelto y úsalo para GET, PATCH y DELETE.
Repite el POST con la misma placa para comprobar 409; prueba PATCH con
`{"color": null}` para comprobar 422. Después de borrar el registro, GET devuelve
404. Estas acciones desde `/docs` sí guardan cambios en tu base.

### Probar desde otra terminal de PowerShell

Este ejemplo crea una placa de prueba aleatoria y elimina solo el vehículo que
acaba de crear. Mantén el backend en ejecución en la primera terminal.

```powershell
$apiUrl = 'http://127.0.0.1:8000'
$testPlate = 'TEST-' + [guid]::NewGuid().ToString('N').Substring(0, 12).ToUpperInvariant()
$payload = @{
    placa = $testPlate
    color = 'Azul'
    modelo = 2025
    marca = 'Prueba'
    tipo = 'AUTOMOVIL'
} | ConvertTo-Json
$vehicle = Invoke-RestMethod -Method Post -Uri "$apiUrl/vehiculos" -ContentType 'application/json; charset=utf-8' -Body ([Text.Encoding]::UTF8.GetBytes($payload))
try {
    $vehicle
    Invoke-RestMethod -Uri "$apiUrl/vehiculos?offset=0&limit=20"
    Invoke-RestMethod -Uri "$apiUrl/vehiculos/$($vehicle.id)"
    Invoke-RestMethod -Method Patch -Uri "$apiUrl/vehiculos/$($vehicle.id)" -ContentType 'application/json' -Body '{"color":"Rojo"}'
} finally {
    $response = Invoke-WebRequest -Method Delete -Uri "$apiUrl/vehiculos/$($vehicle.id)" -UseBasicParsing
    $response.StatusCode # 204
}
```

### Pruebas automatizadas

Las pruebas habituales no requieren PostgreSQL; la integración se omite por defecto:

```powershell
Set-Location -LiteralPath 'C:\Users\user\Documents\IU DIGITAL\Clase Ingeniería de Software\AutosColombia\backend'
.\.venv\Scripts\python.exe -m pytest -q
```

Para comprobar el CRUD real, usando la base `autos_colombia` de `.env` y las
migraciones hasta `0008` ya aplicadas:

```powershell
$env:RUN_POSTGRES_TESTS = '1'
try {
    .\.venv\Scripts\python.exe -m pytest -q
    if ($LASTEXITCODE -ne 0) { throw 'Fallaron las pruebas.' }
} finally {
    Remove-Item Env:RUN_POSTGRES_TESTS -ErrorAction SilentlyContinue
}
```

No necesita un servidor HTTP iniciado: TestClient llama a la aplicación y esta
usa PostgreSQL real. Las pruebas de vehículos y celdas usan una transacción
exterior con savepoints que se revierte al terminar. Las de estancias confirman
datos propios con identificadores únicos y los eliminan en su limpieza, sin tocar
registros ajenos. No se crean tablas ni se modifica el esquema; las secuencias de
ids pueden avanzar porque PostgreSQL no revierte sus valores.
