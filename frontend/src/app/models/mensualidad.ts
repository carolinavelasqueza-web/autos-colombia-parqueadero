/**
 * Utilidades de vencimiento de mensualidad, alineadas con el backend
 * (app/services/mensualidad.py): zona horaria America/Bogota y la regla
 * POR_VENCER cuando faltan 5 días o menos (y aún no ha vencido).
 */

export const DIAS_POR_VENCER = 5;

/** Fecha de hoy (solo día) en la zona horaria de Bogotá, como objeto Date en UTC medianoche. */
function hoyBogota(ahora: Date = new Date()): Date {
  // en-CA produce "AAAA-MM-DD", que podemos tratar como fecha ISO sin hora.
  const texto = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'America/Bogota',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(ahora);
  return new Date(`${texto}T00:00:00Z`);
}

/** Convierte una fecha ISO (AAAA-MM-DD) a un Date en UTC medianoche, o null si no es válida. */
function fechaSolo(valor: string | null | undefined): Date | null {
  if (!valor) return null;
  const soloDia = valor.slice(0, 10);
  const fecha = new Date(`${soloDia}T00:00:00Z`);
  return Number.isNaN(fecha.getTime()) ? null : fecha;
}

/**
 * Días que faltan para el vencimiento (negativo si ya venció), o null si no hay fecha.
 * Usa el día actual en Bogotá para que coincida con el cálculo del backend.
 */
export function diasParaVencer(
  fechaVencimiento: string | null | undefined,
  ahora: Date = new Date(),
): number | null {
  const vencimiento = fechaSolo(fechaVencimiento);
  if (vencimiento === null) return null;
  const hoy = hoyBogota(ahora);
  const MS_POR_DIA = 24 * 60 * 60 * 1000;
  return Math.round((vencimiento.getTime() - hoy.getTime()) / MS_POR_DIA);
}

/** true cuando la mensualidad está vigente pero vence en 5 días o menos. */
export function estaPorVencer(
  fechaVencimiento: string | null | undefined,
  ahora: Date = new Date(),
): boolean {
  const dias = diasParaVencer(fechaVencimiento, ahora);
  return dias !== null && dias >= 0 && dias <= DIAS_POR_VENCER;
}

/** Formatea una fecha de vencimiento (AAAA-MM-DD) como fecha larga en español. */
export function formatearVencimiento(valor: string | null | undefined): string {
  const fecha = fechaSolo(valor);
  if (fecha === null) return '';
  return new Intl.DateTimeFormat('es-CO', {
    timeZone: 'UTC',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  }).format(fecha);
}
