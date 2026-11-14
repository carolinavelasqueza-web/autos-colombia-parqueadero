export interface CeldaCrear {
  codigo: string;
  tipo: string;
}
export interface CeldaActualizar {
  codigo?: string;
  tipo?: string;
  activo?: boolean;
}
export interface Celda extends CeldaCrear {
  id: number;
  activo: boolean;
}
export interface CeldasPagina {
  items: Celda[];
  total: number;
  offset: number;
  limit: number;
}
export interface CeldaDisponible {
  id: number;
  codigo: string;
  tipo: string;
  disponible: boolean;
}
export interface ResumenTipoCelda {
  tipo: string;
  total: number;
  disponibles: number;
  ocupadas: number;
}
export interface DisponibilidadCeldas {
  total: number;
  disponibles: number;
  ocupadas: number;
  ocupacion_porcentaje: number;
  por_tipo: ResumenTipoCelda[];
  celdas: CeldaDisponible[];
}

// Misma regla que backend/app/tipos.py: sin acentos, sin distinguir mayúsculas
// y colapsando espacios para que el selector filtre igual que la API.
export type FamiliaCelda = 'AUTOS' | 'MOTOS';

// Misma familia que backend/app/tipos.py: automóviles y camionetas comparten
// celdas; las motos usan su propio conjunto.
export function familiaTipo(tipo: string): FamiliaCelda | null {
  const clave = normalizarTipo(tipo);
  if (clave === 'AUTOMOVIL' || clave === 'CAMIONETA') return 'AUTOS';
  if (clave === 'MOTO') return 'MOTOS';
  return null;
}

export function normalizarTipo(tipo: string): string {
  return tipo
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .trim()
    .replace(/\s+/g, ' ')
    .toUpperCase();
}

export function iconoTipoCelda(tipo: string): string {
  const normalizado = normalizarTipo(tipo);
  if (normalizado === 'AUTOMOVIL') return '🚗';
  if (normalizado === 'MOTO') return '🏍️';
  return '🅿️';
}
