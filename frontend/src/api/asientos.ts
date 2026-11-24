/** Endpoints de asientos contables. */

import { del, get, getConMeta, post, put } from '@/api/client'

export type EstadoAsiento = 'borrador' | 'confirmado' | 'anulado'

export interface AsientoResumen {
  id: number
  cliente_id: number
  numero: number
  fecha: string
  concepto: string
  estado: EstadoAsiento
  estado_etiqueta: string
  debe: string
  haber: string
  creado_en: string
}

export interface RenglonAsiento {
  id: number
  cuenta_id: number
  cuenta_codigo: string
  cuenta_nombre: string
  debe: string
  haber: string
}

export interface Asiento {
  id: number
  cliente_id: number
  numero: number
  fecha: string
  concepto: string
  estado: EstadoAsiento
  estado_etiqueta: string
  renglones: RenglonAsiento[]
  creado_por: string | null
  creado_en: string
  anulado_por: string | null
  motivo_anulacion: string | null
  anulado_en: string | null
}

export interface RenglonInput {
  cuenta_id: number
  debe: string
  haber: string
}

export interface AsientoInput {
  fecha: string
  concepto: string
  renglones: RenglonInput[]
}

export interface FiltrosAsientos {
  desde?: string
  hasta?: string
  estado?: EstadoAsiento | ''
  cuenta?: number | null
  q?: string
  pagina?: number
  por_pagina?: number
}

function parametros(filtros: FiltrosAsientos): Record<string, unknown> {
  const params: Record<string, unknown> = {}
  if (filtros.desde) params.desde = filtros.desde
  if (filtros.hasta) params.hasta = filtros.hasta
  if (filtros.estado) params.estado = filtros.estado
  if (filtros.cuenta) params.cuenta = filtros.cuenta
  if (filtros.q) params.q = filtros.q
  if (filtros.pagina) params.pagina = filtros.pagina
  if (filtros.por_pagina) params.por_pagina = filtros.por_pagina
  return params
}

export const asientosApi = {
  listar: (clienteId: number, filtros: FiltrosAsientos = {}) =>
    getConMeta<AsientoResumen[]>(
      `/clientes/${clienteId}/asientos`,
      parametros(filtros),
    ),

  obtener: (id: number) => get<Asiento>(`/asientos/${id}`),

  crear: (clienteId: number, datos: AsientoInput) =>
    post<Asiento>(`/clientes/${clienteId}/asientos`, datos),

  actualizar: (id: number, datos: AsientoInput) =>
    put<Asiento>(`/asientos/${id}`, datos),

  confirmar: (id: number) => post<Asiento>(`/asientos/${id}/confirmar`),

  anular: (id: number, motivo: string) =>
    post<Asiento>(`/asientos/${id}/anular`, { motivo }),

  descartar: (id: number) => del<{ mensaje: string }>(`/asientos/${id}`),
}
