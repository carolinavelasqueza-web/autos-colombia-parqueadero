# Frontend de Autos Colombia

Angular 22 con componentes standalone, TypeScript estricto, formularios reactivos y CSS.
Las dependencias son locales; conserva `package-lock.json` y usa `npm.cmd ci` al reinstalar.

## Iniciar en Windows (PowerShell)

Mantén el backend activo en otra terminal, como se explica en el [README principal](../README.md).

```powershell
Set-Location -LiteralPath 'C:\Users\user\Documents\IU DIGITAL\Clase Ingeniería de Software\AutosColombia\frontend'
npm.cmd ci
npm.cmd start -- --host 127.0.0.1 --port 4200
```

Abre <http://127.0.0.1:4200/login>. Si todavía no existe una cuenta
`ADMINISTRADOR`, créala desde `backend` con `create_admin.py` antes de iniciar sesión.

El proxy `proxy.conf.json` conecta `/api/**`, `/health`, `/estancias/**`, `/puertas/**`,
`/clientes/**`, `/operadores/**`, `/celdas/**` y `/vehiculos/**` con FastAPI en
`127.0.0.1:8000`. Reinicia el servidor de Angular si cambias ese archivo. En
producción, configura estas rutas de API en el servidor web; `ng build` no incluye
un proxy.

## Acceso y roles

- `ADMINISTRADOR`: ve Inicio, Control de acceso, Vehículos, Operadores y Celdas.
- `OPERADOR`: solo accede a Control de acceso. Puede registrar un vehículo nuevo,
  registrar entradas, confirmar salidas, imprimir fichos y reasignar celdas de
  estancias abiertas; las rutas de gestión quedan bloqueadas.
- El token JWT y el perfil se guardan en `sessionStorage` (`autos-colombia.sesion`).
  La sesión se limpia al cerrar la pestaña, al usar **Cerrar sesión** o cuando el
  backend responde 401.
- El interceptor agrega `Authorization: Bearer <token>` a las peticiones del backend.
  `AuthGuard` y `RoleGuard` protegen las rutas; el backend sigue siendo la fuente de
  verdad de los permisos.
- La entrada y la salida usan el usuario autenticado. No se envía `operador_id`
  desde el formulario.
- En **Operadores**, el administrador crea cuentas con nombre, teléfono, usuario y
  contraseña inicial. Al editar, la contraseña es opcional: si se deja vacía se
  conserva la actual.

## Disponibilidad y contadores

La pantalla **Control de acceso** consulta `GET /celdas/disponibilidad` y muestra
tres tarjetas: autos disponibles, motos disponibles y ocupación total. La celda de
entrada ya no se elige a mano: el backend asigna una celda activa y libre de la
familia del vehículo. Los contadores se actualizan al registrar una entrada, una
salida o una reasignación, y con el botón **Actualizar disponibilidad**. La
comparación de tipos ignora acentos, mayúsculas y espacios, igual que el backend.

## Fichos, puertas y reasignación

- La entrada exige `puerta_entrada_id`. Las opciones salen de `GET /puertas`, que
  solo devuelve puertas activas; al registrar la entrada se muestra la celda
  asignada, la puerta y el ficho generado.
- El panel del ficho incluye el botón **Imprimir Ficho**, que usa `window.print()`.
  Los estilos de `styles.css` ocultan el resto de la aplicación al imprimir y
  conservan solo el comprobante.
- La salida exige el código impreso y la puerta de salida. El formulario valida el
  formato `AC-YYYYMMDD-XXXX` y comprueba localmente que coincida con el ficho de la
  estancia abierta antes de llamar a la API.
- **Reasignar celda** abre un modal con las celdas libres compatibles. El motivo es
  opcional y los errores del backend se muestran sin cerrar el modal. Al terminar,
  la consulta y el ficho visible se actualizan con la celda nueva.

## Verificar

```powershell
npm.cmd run build
npm.cmd test -- --watch=false
```

La compilación se guarda en `dist/frontend`. Las pruebas usan respuestas simuladas y
no modifican PostgreSQL.
