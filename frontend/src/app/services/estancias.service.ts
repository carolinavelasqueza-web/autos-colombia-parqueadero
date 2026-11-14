import { HttpClient, HttpParams } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { timeout } from 'rxjs';
import {
  EntradaCrear,
  Estancia,
  EstanciaAbierta,
  EstanciasActivasPagina,
  EstadoVehiculo,
  Ficho,
  Reasignacion,
  ReasignacionCrear,
  SalidaCrear,
} from '../models/estancia';
import { API_BASE_URL } from './api.service';

@Injectable({ providedIn: 'root' })
export class EstanciasService {
  private readonly http = inject(HttpClient);
  private readonly base = `${inject(API_BASE_URL)}/estancias`;

  entrada(data: EntradaCrear) {
    return this.http.post<EstanciaAbierta>(`${this.base}/entrada`, data).pipe(timeout(15000));
  }
  salida(data: SalidaCrear) {
    return this.http.post<Estancia>(`${this.base}/salida`, data).pipe(timeout(15000));
  }
  consultar(placa: string) {
    return this.http
      .get<EstadoVehiculo>(`${this.base}/vehiculo/${encodeURIComponent(placa)}`)
      .pipe(timeout(15000));
  }
  activas(placa: string, offset: number, limit: number) {
    const valor = placa.trim().toUpperCase();
    let params = new HttpParams();
    if (valor) params = params.set('placa', valor);
    params = params.set('offset', offset).set('limit', limit);
    return this.http
      .get<EstanciasActivasPagina>(`${this.base}/activas`, { params })
      .pipe(timeout(15000));
  }
  ficho(id: number) {
    return this.http.get<Ficho>(`${this.base}/${id}/ficho`).pipe(timeout(15000));
  }
  reasignar(id: number, data: ReasignacionCrear) {
    return this.http.post<Reasignacion>(`${this.base}/${id}/reasignar`, data).pipe(timeout(15000));
  }
}
