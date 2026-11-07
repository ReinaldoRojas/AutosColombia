import { Routes } from '@angular/router';

// Las rutas de pantalla no coinciden con las de la API (/estancias, /clientes…) para no chocar con el proxy.
export const routes: Routes = [
  { path: '', pathMatch: 'full', loadComponent: () => import('./home/home').then((m) => m.Home) },
  {
    path: 'operacion/entrada',
    title: 'Registrar entrada | Autos Colombia',
    loadComponent: () => import('./entrada/entrada').then((m) => m.Entrada),
  },
  {
    path: 'operacion/salida',
    title: 'Registrar salida | Autos Colombia',
    loadComponent: () => import('./salida/salida').then((m) => m.Salida),
  },
  {
    path: 'gestion/clientes',
    title: 'Clientes y vehículos | Autos Colombia',
    loadComponent: () => import('./clientes/clientes').then((m) => m.Clientes),
  },
  {
    path: 'gestion/operadores',
    title: 'Operadores | Autos Colombia',
    loadComponent: () => import('./operadores/operadores').then((m) => m.Operadores),
  },
  {
    path: 'gestion/celdas',
    title: 'Celdas | Autos Colombia',
    loadComponent: () => import('./celdas/celdas').then((m) => m.Celdas),
  },
  { path: '**', redirectTo: '' },
];
