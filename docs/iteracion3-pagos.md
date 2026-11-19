# Iteración 3 – Gestión de pagos (especificación)

Nota: en el código el tipo de vehículo es `AUTOMOVIL` (sin tilde).

## Supuestos de negocio
- La mensualidad se paga por cliente; su valor depende del tipo de vehículo (automóvil, camioneta o moto) de cada vehículo del cliente.
- Cada mensualidad cubre un mes; se pueden pagar de 1 a 12 meses en un mismo pago.
- Pagos en el parqueadero (EFECTIVO, TRANSFERENCIA, TARJETA). Sin pasarelas externas.
- Sin descuentos, recargos por mora ni facturación electrónica.
- Registra el pago el operador o el administrador. Solo el administrador define tarifas, anula pagos y consulta el recaudo.

## Requerimientos funcionales
- RF-P01 (Admin): crear y actualizar la tarifa mensual por tipo de vehículo (AUTOMOVIL, CAMIONETA, MOTO), valor > 0 en COP, conservando historial.
- RF-P02 (Ambos): listar tarifas vigentes por tipo.
- RF-P03 (Ambos): registrar pago de mensualidad seleccionando cliente (por documento), meses (1 a 12) y método.
- RF-P04 (Sistema): monto = suma de la tarifa vigente de cada vehículo del cliente × meses. Queda guardado y no cambia si la tarifa se modifica después.
- RF-P05 (Ambos): métodos EFECTIVO, TRANSFERENCIA, TARJETA; en los dos últimos la referencia es obligatoria y no puede repetirse.
- RF-P06 (Sistema): nueva fecha de vencimiento = mayor entre hoy y el vencimiento vigente, más los meses pagados.
- RF-P07 (Sistema): reactivar automáticamente al cliente inactivo por mensualidad vencida al registrar su pago.
- RF-P08 (Ambos): recibo con número consecutivo único (cliente, documento, vehículos, período cubierto, monto, método, referencia, operador, fecha y hora), visualizable e imprimible.
- RF-P09 (Ambos): historial de pagos paginado con filtros por cliente, rango de fechas, método y estado.
- RF-P10 (Ambos): estado de mensualidad (AL_DIA, POR_VENCER si faltan 5 días o menos, VENCIDA, SIN_PAGO) y fecha de vencimiento.
- RF-P11 (Ambos): listar clientes con mensualidad por vencer o vencida.
- RF-P12 (Sistema): al registrar una entrada, rechazar con 409 «Mensualidad vencida» si el cliente está VENCIDA o SIN_PAGO. La salida nunca se bloquea.
- RF-P13 (Admin): anular un pago con motivo obligatorio (máx. 500 caracteres). Solo el último pago vigente del cliente; queda ANULADO y la vigencia se revierte.
- RF-P14 (Admin): reporte de recaudo por rango de fechas: total, número de pagos y desglose por método, excluyendo ANULADO.
- RF-P15 (Sistema): auditar acción, entidad, operador y fecha de cada pago registrado, pago anulado y tarifa modificada.

## Requerimientos no funcionales
- RNF-P01 Seguridad: tarifas, anulación y recaudo son solo del administrador; la API responde 403 al operador y la interfaz oculta esas opciones.
- RNF-P02 Integridad: registrar pago, vigencia, reactivación, recibo y auditoría en una sola transacción.
- RNF-P03 Integridad monetaria: NUMERIC(12,2), nunca float; monto > 0; número de recibo único por restricción en BD.
- RNF-P04 Concurrencia: sin pagos duplicados por doble clic o dos operadores; botón deshabilitado al enviar y bloqueo de la fila del cliente.
- RNF-P05 Rendimiento: registrar un pago en menos de 4 s; listados paginados con máximo 100 registros.
- RNF-P06 Usabilidad: máximo tres pasos (buscar cliente, revisar resumen, confirmar); valores en COP con separador de miles; mensajes en español.
- RNF-P07 Trazabilidad: toda escritura auditada con el operador autenticado; fechas en America/Bogota.
- RNF-P08 Confidencialidad: no se guardan datos de tarjetas, solo la referencia del comprobante.
- RNF-P09 Mantenibilidad: capas router, servicio, esquema, modelo; migración Alembic 0010.
- RNF-P10 Calidad: pruebas pytest (backend) y Vitest (frontend) para todo lo nuevo.

## Casos de uso
CU-P01 Gestionar tarifas (Admin) · CU-P02 Consultar tarifas · CU-P03 Registrar pago (requiere cliente con al menos un vehículo) · CU-P04 Calcular monto (Sistema) · CU-P05 Actualizar vigencia (Sistema) · CU-P06 Reactivar cliente por pago (Sistema, solo si estaba inactivo) · CU-P07 Generar recibo · CU-P08 Historial de pagos · CU-P09 Estado de mensualidad · CU-P10 Listar clientes por vencer o vencidos · CU-P11 Anular pago (Admin) · CU-P12 Reporte de recaudo (Admin) · CU-P13 Validar mensualidad al ingresar (Sistema).

## Criterios de aceptación clave
- HU-P01: valor > 0 en COP; historial conservado; operador recibe 403 y no ve la opción.
- HU-P03: 1 a 12 meses; referencia obligatoria y única en TRANSFERENCIA y TARJETA; todo en una transacción.
- HU-P04: monto guardado inmutable, sin decimales flotantes.
- HU-P05: vigencia = max(hoy, vencimiento) + meses; reactiva si estaba inactivo por mensualidad vencida.
- HU-P08: lista exclusiva de clientes por vencer o vencidos, con fecha exacta de vencimiento.
- HU-P09: VENCIDA o SIN_PAGO → 409 «Mensualidad vencida»; la salida nunca se bloquea.
- HU-P10: solo el último pago vigente; queda ANULADO; motivo obligatorio ≤ 500; operador recibe 403.
- HU-P11: reporte con total, número de pagos y desglose por método, sin anulados; solo admin.
- HU-P12: auditoría con acción, entidad, operador y fecha (America/Bogota).