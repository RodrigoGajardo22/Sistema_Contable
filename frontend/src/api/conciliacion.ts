/** Endpoints de conciliación bancaria. */

import { del, get, post, put } from '@/api/client'

export interface Sugerencia {
  asiento_id: number
  numero: number
  fecha: string
  concepto: string
  total: string
  confianza: number
}

export interface Movimiento {
  id: number
  fecha: string
  descripcion: string
  importe: string
  estado: 'pendiente' | 'conciliado' | 'descartado'
  estado_etiqueta: string
  asiento_id: number | null
  asiento_numero: number | null
  comprobante_id: number | null
  comprobante_numero: string | null
  sugerencias: Sugerencia[]
}

export interface ResumenConciliacion {
  movimientos: number
  conciliados: number
  pendientes: number
  suma_movimientos: string
  saldo_contable: string
  diferencia: string
}

export interface Extracto {
  id: number
  cliente_id: number
  banco: string
  periodo: string
  saldo_inicial: string
  saldo_final: string
  resumen: ResumenConciliacion
  movimientos?: Movimiento[]
}

export interface ExtractoInput {
  banco: string
  periodo: string
  saldo_inicial: string
  saldo_final: string
  csv: string
}

export const conciliacionApi = {
  listar: (clienteId: number) =>
    get<Extracto[]>(`/clientes/${clienteId}/extractos`),

  crear: (clienteId: number, datos: ExtractoInput) =>
    post<Extracto>(`/clientes/${clienteId}/extractos`, datos),

  obtener: (id: number) => get<Extracto>(`/extractos/${id}`),

  eliminar: (id: number) => del<{ mensaje: string }>(`/extractos/${id}`),

  vincular: (movimientoId: number, objetivo: { asiento_id?: number; comprobante_id?: number }) =>
    put<{ id: number; estado: string }>(`/movimientos/${movimientoId}/vincular`, objetivo),

  generarAsiento: (movimientoId: number, cuentaId: number, concepto?: string) =>
    post<{ movimiento_id: number; asiento_id: number; numero: number; estado: string }>(
      `/movimientos/${movimientoId}/asiento`,
      { cuenta_id: cuentaId, concepto },
    ),

  descartar: (movimientoId: number) =>
    put<{ id: number; estado: string }>(`/movimientos/${movimientoId}/descartar`),

  desvincular: (movimientoId: number) =>
    put<{ id: number; estado: string }>(`/movimientos/${movimientoId}/desvincular`),
}
