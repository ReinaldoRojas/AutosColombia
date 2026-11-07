import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { timeout } from 'rxjs';
import { ClienteActualizar, ClienteCrear, ClienteDetalle, ClientesPagina } from '../models/cliente';
import { API_BASE_URL } from './api.service';

@Injectable({ providedIn: 'root' })
export class ClientesService {
  private readonly http = inject(HttpClient);
  private readonly base = `${inject(API_BASE_URL)}/clientes`;

  list(q: string, offset: number, limit: number) {
    const params: Record<string, string | number> = { offset, limit };
    if (q.trim()) params['q'] = q.trim();
    return this.http.get<ClientesPagina>(this.base, { params }).pipe(timeout(15000));
  }
  get(id: number) {
    return this.http.get<ClienteDetalle>(`${this.base}/${id}`).pipe(timeout(15000));
  }
  create(data: ClienteCrear) {
    return this.http.post<ClienteDetalle>(this.base, data).pipe(timeout(15000));
  }
  update(id: number, data: ClienteActualizar) {
    return this.http.patch<ClienteDetalle>(`${this.base}/${id}`, data).pipe(timeout(15000));
  }
}
