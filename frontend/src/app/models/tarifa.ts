export const TIPOS_TARIFA = ['MOTO', 'AUTOMOVIL', 'CAMIONETA'] as const;
export type TipoTarifa = (typeof TIPOS_TARIFA)[number];

export interface Tarifa {
  id: number;
  tipo: TipoTarifa;
  valor: string;
  vigente_desde: string;
  vigente_hasta: string | null;
}

export interface TarifaActualizar {
  valor: string;
}
