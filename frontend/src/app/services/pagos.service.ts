import { HttpClient, HttpParams } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Observable, timeout } from 'rxjs';
import {
  ClientesMensualidadPagina,
  FiltrosPagos,
  Mensualidad,
  Pago,
  PagoAnular,
  PagoCrear,
  PagosPagina,
  ReporteRecaudo,
} from '../models/pago';
import { API_BASE_URL } from './api.service';

@Injectable({ providedIn: 'root' })
export class PagosService {
  private readonly http = inject(HttpClient);
  private readonly base = inject(API_BASE_URL);
  private readonly pagos = `${this.base}/pagos`;
  private readonly clientes = `${this.base}/clientes`;
  private readonly reportes = `${this.base}/reportes`;

  registrar(data: PagoCrear): Observable<Pago> {
    return this.http.post<Pago>(this.pagos, data).pipe(timeout(15000));
  }

  listar(filtros: FiltrosPagos = {}): Observable<PagosPagina> {
    let params = new HttpParams()
      .set('offset', filtros.offset ?? 0)
      .set('limit', filtros.limit ?? 20);
    if (filtros.documento) params = params.set('documento', filtros.documento);
    if (filtros.estado) params = params.set('estado', filtros.estado);
    if (filtros.desde) params = params.set('desde', filtros.desde);
    if (filtros.hasta) params = params.set('hasta', filtros.hasta);
    return this.http
      .get<PagosPagina>(this.pagos, { params })
      .pipe(timeout(15000));
  }

  recibo(id: number): Observable<Pago> {
    return this.http
      .get<Pago>(`${this.pagos}/${id}/recibo`)
      .pipe(timeout(15000));
  }

  anular(id: number, data: PagoAnular): Observable<Pago> {
    return this.http
      .post<Pago>(`${this.pagos}/${id}/anular`, data)
      .pipe(timeout(15000));
  }

  mensualidad(clienteId: number): Observable<Mensualidad> {
    return this.http
      .get<Mensualidad>(`${this.clientes}/${clienteId}/mensualidad`)
      .pipe(timeout(15000));
  }

  alertas(offset: number, limit: number): Observable<ClientesMensualidadPagina> {
    const params = new HttpParams().set('offset', offset).set('limit', limit);
    return this.http
      .get<ClientesMensualidadPagina>(`${this.clientes}/mensualidad/alertas`, {
        params,
      })
      .pipe(timeout(15000));
  }

  recaudo(desde?: string, hasta?: string): Observable<ReporteRecaudo> {
    let params = new HttpParams();
    if (desde) params = params.set('desde', desde);
    if (hasta) params = params.set('hasta', hasta);
    return this.http
      .get<ReporteRecaudo>(`${this.reportes}/recaudo`, { params })
      .pipe(timeout(20000));
  }
}
