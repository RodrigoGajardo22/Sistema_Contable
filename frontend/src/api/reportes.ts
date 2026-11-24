/** Endpoints de reportes. */

import { get } from '@/api/client'

export interface RenglonDiario {
  cuenta_codigo: string
  cuenta_nombre: string
  debe: string
  haber: string
}

export interface AsientoDiario {
  numero: number
  fecha: string
  concepto: string
  renglones: RenglonDiario[]
}

export interface Balance {
  cuentas: {
    codigo: string
    nombre: string
    tipo: string
    debe: string
    haber: string
    saldo: string
  }[]
  total_debe: string
  total_haber: string
  diferencia: string
}

export interface Mayor {
  cuenta: { codigo: string; nombre: string; tipo: string }
  saldo_inicial: string
  movimientos: {
    fecha: string
    numero: number
    concepto: string
    debe: string
    haber: string
    saldo: string
  }[]
  saldo_final: string
}

export interface LibroIva {
  ventas: { items: ItemIva[]; neto: string; iva: string; total: string }
  compras: { items: ItemIva[]; neto: string; iva: string; total: string }
}

export interface ItemIva {
  numero: string
  fecha: string
  tercero: string
  neto: string
  iva: string
  total: string
}

export interface Rango {
  desde?: string
  hasta?: string
}

export const reportesApi = {
  diario: (clienteId: number, rango: Rango) =>
    get<AsientoDiario[]>(`/clientes/${clienteId}/reportes/diario`, { ...rango }),

  mayor: (clienteId: number, cuenta: number, rango: Rango) =>
    get<Mayor>(`/clientes/${clienteId}/reportes/mayor`, { ...rango, cuenta }),

  balance: (clienteId: number, rango: Rango) =>
    get<Balance>(`/clientes/${clienteId}/reportes/balance`, { ...rango }),

  libroIva: (clienteId: number, rango: Rango) =>
    get<LibroIva>(`/clientes/${clienteId}/reportes/libro-iva`, { ...rango }),
}
