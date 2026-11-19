import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Observable, timeout } from 'rxjs';
import { Tarifa, TarifaActualizar, TipoTarifa } from '../models/tarifa';
import { API_BASE_URL } from './api.service';

@Injectable({ providedIn: 'root' })
export class TarifasService {
  private readonly http = inject(HttpClient);
  private readonly base = `${inject(API_BASE_URL)}/tarifas`;

  list(): Observable<Tarifa[]> {
    return this.listar();
  }

  listar(): Observable<Tarifa[]> {
    return this.http.get<Tarifa[]>(this.base).pipe(timeout(15000));
  }

  actualizar(tipo: TipoTarifa, data: TarifaActualizar): Observable<Tarifa> {
    return this.http
      .put<Tarifa>(`${this.base}/${tipo}`, data)
      .pipe(timeout(15000));
  }
}
