import { HttpClient, HttpParams } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { timeout } from 'rxjs';
import { ReporteOcupacion } from '../models/reporte';
import { API_BASE_URL } from './api.service';

@Injectable({ providedIn: 'root' })
export class ReportesService {
  private readonly http = inject(HttpClient);
  private readonly base = `${inject(API_BASE_URL)}/reportes`;

  ocupacion(desde?: string, hasta?: string) {
    let params = new HttpParams();
    if (desde) params = params.set('desde', desde);
    if (hasta) params = params.set('hasta', hasta);
    return this.http
      .get<ReporteOcupacion>(`${this.base}/ocupacion`, { params })
      .pipe(timeout(20000));
  }
}
