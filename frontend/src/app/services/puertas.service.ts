import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { timeout } from 'rxjs';
import { Puerta } from '../models/puerta';
import { API_BASE_URL } from './api.service';

@Injectable({ providedIn: 'root' })
export class PuertasService {
  private readonly http = inject(HttpClient);
  private readonly base = `${inject(API_BASE_URL)}/puertas`;

  listar(incluirInactivas = false) {
    return this.http
      .get<Puerta[]>(this.base, {
        params: incluirInactivas ? { incluir_inactivas: 'true' } : {},
      })
      .pipe(timeout(15000));
  }
}
