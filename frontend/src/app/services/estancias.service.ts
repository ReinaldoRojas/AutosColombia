import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { timeout } from 'rxjs';
import {
  ConsultaVehiculo,
  EntradaCrear,
  Movimiento,
  Puerta,
  SalidaCrear,
} from '../models/estancia';
import { API_BASE_URL } from './api.service';

@Injectable({ providedIn: 'root' })
export class EstanciasService {
  private readonly http = inject(HttpClient);
  private readonly root = inject(API_BASE_URL);
  private readonly base = `${this.root}/estancias`;

  consultar(placa: string) {
    return this.http
      .get<ConsultaVehiculo>(`${this.base}/vehiculo/${encodeURIComponent(placa)}`)
      .pipe(timeout(15000));
  }
  entrada(data: EntradaCrear) {
    return this.http.post<Movimiento>(`${this.base}/entrada`, data).pipe(timeout(15000));
  }
  salida(data: SalidaCrear) {
    return this.http.post<Movimiento>(`${this.base}/salida`, data).pipe(timeout(15000));
  }
  puertas() {
    return this.http.get<Puerta[]>(`${this.root}/puertas`).pipe(timeout(15000));
  }
}
