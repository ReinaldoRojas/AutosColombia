import { Component, input } from '@angular/core';
import { Movimiento } from '../models/estancia';
import { NOMBRE_TIPO } from '../models/vehiculo';
import { fechaHora } from './formato';

/** Comprobante de ingreso que el conductor presenta para retirar el vehículo (RN-11). */
@Component({
  selector: 'app-recibo',
  template: `
    @let m = movimiento();
    <article class="recibo" aria-label="Recibo de ingreso">
      <header>
        <span class="marca">AC</span>
        <div>
          <strong>Autos Colombia</strong>
          <small>Parqueadero por mensualidad · 24 horas</small>
        </div>
      </header>
      <p class="titulo">Recibo de ingreso</p>
      <p class="numero">{{ m.numero_recibo }}</p>
      <dl>
        <dt>Placa</dt>
        <dd class="placa">{{ m.placa }}</dd>
        <dt>Vehículo</dt>
        <dd>{{ tipo(m.tipo_vehiculo) }} · {{ m.marca }} {{ m.linea ?? '' }} · {{ m.color }}</dd>
        <dt>Celda</dt>
        <dd class="celda">{{ m.celda.codigo }}</dd>
        <dt>Ingreso</dt>
        <dd>{{ fecha(m.entrada) }} · {{ m.puerta_entrada.nombre }}</dd>
        <dt>Operador</dt>
        <dd>{{ m.operador_entrada.nombre }}</dd>
        @if (m.cliente) {
          <dt>Cliente</dt>
          <dd>{{ m.cliente }}</dd>
        }
      </dl>
      <p class="pie">Presente este recibo para retirar el vehículo.</p>
    </article>
  `,
  styles: `
    .recibo {
      max-width: 360px;
      margin: 18px 0 0;
      padding: 20px 22px;
      background: #fff;
      border: 1px dashed #9fb3a7;
      border-radius: 12px;
      font-size: 14px;
    }
    header {
      display: flex;
      gap: 10px;
      align-items: center;
    }
    header small {
      display: block;
      color: #627168;
      font-size: 11px;
    }
    .marca {
      display: grid;
      place-items: center;
      width: 34px;
      height: 34px;
      border-radius: 9px;
      background: #214c43;
      color: #fff;
      font-size: 12px;
      font-weight: 700;
    }
    .titulo {
      margin: 16px 0 0;
      font-size: 11px;
      letter-spacing: 2px;
      text-transform: uppercase;
      color: #526c60;
    }
    .numero {
      margin: 2px 0 10px;
      font-size: 24px;
      font-weight: 700;
      letter-spacing: 1px;
      color: #203a33;
    }
    dl {
      display: grid;
      grid-template-columns: 82px 1fr;
      gap: 6px 10px;
      margin: 0;
    }
    dt {
      color: #627168;
    }
    dd {
      margin: 0;
      font-weight: 600;
    }
    .placa,
    .celda {
      font-size: 18px;
      letter-spacing: 1px;
    }
    .pie {
      margin: 14px 0 0;
      font-size: 12px;
      color: #627168;
      border-top: 1px solid #e6ebe5;
      padding-top: 10px;
    }
    @media print {
      .recibo {
        border: 1px solid #000;
      }
    }
  `,
})
export class ReciboComponent {
  readonly movimiento = input.required<Movimiento>();
  readonly fecha = fechaHora;
  tipo(value: string): string {
    return NOMBRE_TIPO[value] ?? value;
  }
}
