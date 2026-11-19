import { diasParaVencer, estaPorVencer, formatearVencimiento } from './mensualidad';

describe('Utilidades de mensualidad', () => {
  // Punto fijo de referencia: 10 de enero de 2026, mañana en Bogotá.
  const ahora = new Date('2026-01-10T15:00:00Z');

  it('calcula los días que faltan para el vencimiento', () => {
    expect(diasParaVencer('2026-01-15', ahora)).toBe(5);
    expect(diasParaVencer('2026-01-10', ahora)).toBe(0);
    expect(diasParaVencer('2026-01-08', ahora)).toBe(-2);
    expect(diasParaVencer(null, ahora)).toBeNull();
    expect(diasParaVencer(undefined, ahora)).toBeNull();
  });

  it('marca por vencer solo entre 0 y 5 días', () => {
    expect(estaPorVencer('2026-01-15', ahora)).toBe(true); // 5 días
    expect(estaPorVencer('2026-01-11', ahora)).toBe(true); // 1 día
    expect(estaPorVencer('2026-01-10', ahora)).toBe(true); // hoy
    expect(estaPorVencer('2026-01-16', ahora)).toBe(false); // 6 días
    expect(estaPorVencer('2026-01-09', ahora)).toBe(false); // ya venció
    expect(estaPorVencer(null, ahora)).toBe(false);
  });

  it('formatea la fecha de vencimiento en español sin corrimiento de día', () => {
    expect(formatearVencimiento('2026-01-15')).toBe('15 de enero de 2026');
    expect(formatearVencimiento(null)).toBe('');
  });
});
