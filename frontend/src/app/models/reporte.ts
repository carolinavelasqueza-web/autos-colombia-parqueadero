export interface OcupacionFamilia {
  familia: string;
  capacidad: number;
  ocupadas: number;
  disponibles: number;
  porcentaje: number;
}

export interface DiaOcupacion {
  fecha: string;
  entradas: number;
  salidas: number;
  ocupadas: number;
  porcentaje: number;
}

export interface ReporteOcupacion {
  generado_en: string;
  desde: string;
  hasta: string;
  capacidad_total: number;
  ocupadas: number;
  disponibles: number;
  porcentaje: number;
  entradas: number;
  salidas: number;
  permanencia_promedio_minutos: number;
  por_tipo: OcupacionFamilia[];
  historico: DiaOcupacion[];
}
