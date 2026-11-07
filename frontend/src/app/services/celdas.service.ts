import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { timeout } from 'rxjs';
import { Celda, CeldaActualizar, CeldaCrear, CeldasPagina } from '../models/celda';

import { API_BASE_URL } from './api.service';

@Injectable({ providedIn: 'root' })
export class CeldasService {
  private readonly http = inject(HttpClient);
  private readonly base = inject(API_BASE_URL);
  private readonly cells = `${this.base}/celdas`;

  list(offset: number, limit: number) {
    return this.http
      .get<CeldasPagina>(this.cells, { params: { offset, limit } })
      .pipe(timeout(15000));
  }
  get(id: number) {
    return this.http.get<Celda>(`${this.cells}/${id}`).pipe(timeout(15000));
  }
  create(data: CeldaCrear) {
    return this.http.post<Celda>(this.cells, data).pipe(timeout(15000));
  }
  update(id: number, data: CeldaActualizar) {
    return this.http.patch<Celda>(`${this.cells}/${id}`, data).pipe(timeout(15000));
  }
  delete(id: number) {
    return this.http.delete<void>(`${this.cells}/${id}`).pipe(timeout(15000));
  }
}
