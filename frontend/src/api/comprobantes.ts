/** Endpoints de comprobantes. */

import { del, getConMeta, post, put } from '@/api/client'

export type TipoComprobante = 'compra' | 'venta'
export type EstadoComprobante = 'pendiente' | 'contabilizado' | 'anulado'

export interface Comprobante {
  id: number
  cliente_id: number
  cliente_nombre?: string
  tipo: TipoComprobante
  tipo_etiqueta: string
  numero: string
  fecha: string
  tercero: string
  neto: string
  alicuota_iva: string
  iva: string
  total: string
  estado: EstadoComprobante
  estado_etiqueta: string
  asiento_id: number | null
  asiento_numero: number | null
  motivo_anulacion: string | null
  creado_por: string | null
  creado_en: string
}

export interface ComprobanteInput {
  tipo: TipoComprobante
  numero: string
  fecha: string
  tercero: string
  neto: string
  alicuota_iva: string
}

export interface FiltrosComprobantes {
  cliente_id?: number | ''
  tipo?: TipoComprobante | ''
  estado?: EstadoComprobante | ''
  desde?: string
  hasta?: string
  q?: string
}

export const ALICUOTAS = [
  { valor: '0.00', etiqueta: '0 %' },
  { valor: '10.50', etiqueta: '10,5 %' },
  { valor: '21.00', etiqueta: '21 %' },
  { valor: '27.00', etiqueta: '27 %' },
] as const

function parametros(filtros: FiltrosComprobantes): Record<string, unknown> {
  const params: Record<string, unknown> = {}
  if (filtros.cliente_id) params.cliente_id = filtros.cliente_id
  if (filtros.tipo) params.tipo = filtros.tipo
  if (filtros.estado) params.estado = filtros.estado
  if (filtros.desde) params.desde = filtros.desde
  if (filtros.hasta) params.hasta = filtros.hasta
  if (filtros.q) params.q = filtros.q
  return params
}

export const comprobantesApi = {
  listar: (clienteId: number, filtros: FiltrosComprobantes = {}) =>
    getConMeta<Comprobante[]>(
      `/clientes/${clienteId}/comprobantes`,
      parametros(filtros),
    ),

  listarGlobal: (filtros: FiltrosComprobantes = {}) =>
    getConMeta<Comprobante[]>('/comprobantes', parametros(filtros)),

  crear: (clienteId: number, datos: ComprobanteInput) =>
    post<Comprobante>(`/clientes/${clienteId}/comprobantes`, datos),

  actualizar: (id: number, datos: ComprobanteInput) =>
    put<Comprobante>(`/comprobantes/${id}`, datos),

  contabilizar: (id: number) =>
    post<Comprobante>(`/comprobantes/${id}/contabilizar`),

  anular: (id: number) => del<Comprobante>(`/comprobantes/${id}`),
}
