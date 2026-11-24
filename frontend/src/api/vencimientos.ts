/** Endpoints de vencimientos. */

import { del, getConMeta, post, put } from '@/api/client'

export type Obligacion = 'iva' | 'ingresos_brutos' | 'ganancias' | 'autonomos' | 'municipal' | 'otro'
export type EstadoVencimiento = 'pendiente' | 'presentado' | 'pagado'

export interface Vencimiento {
  id: number
  cliente_id: number
  cliente_nombre?: string
  obligacion: Obligacion
  obligacion_etiqueta: string
  periodo: string
  fecha_vencimiento: string
  estado: EstadoVencimiento
  estado_etiqueta: string
  vencido: boolean
  observaciones: string | null
}

export interface VencimientoInput {
  obligacion: Obligacion
  periodo: string
  fecha_vencimiento: string
  observaciones?: string | null
}

export const OBLIGACIONES = [
  { valor: 'iva', etiqueta: 'IVA' },
  { valor: 'ingresos_brutos', etiqueta: 'Ingresos Brutos' },
  { valor: 'ganancias', etiqueta: 'Ganancias' },
  { valor: 'autonomos', etiqueta: 'Autónomos' },
  { valor: 'municipal', etiqueta: 'Municipal' },
  { valor: 'otro', etiqueta: 'Otro' },
] as const

export interface FiltrosVencimientos {
  cliente_id?: number | ''
  estado?: EstadoVencimiento | ''
  proximidad?: '' | 'proximos' | 'vencidos'
  obligacion?: Obligacion | ''
  desde?: string
  hasta?: string
}

export const vencimientosApi = {
  listar: (
    clienteId: number,
    estado?: EstadoVencimiento | '',
    proximidad?: '' | 'proximos' | 'vencidos',
  ) =>
    getConMeta<Vencimiento[]>(`/clientes/${clienteId}/vencimientos`, {
      ...(estado ? { estado } : {}),
      ...(proximidad ? { proximidad } : {}),
    }),

  listarGlobal: (filtros: FiltrosVencimientos = {}) =>
    getConMeta<Vencimiento[]>('/vencimientos', {
      ...(filtros.cliente_id ? { cliente_id: filtros.cliente_id } : {}),
      ...(filtros.estado ? { estado: filtros.estado } : {}),
      ...(filtros.proximidad ? { proximidad: filtros.proximidad } : {}),
      ...(filtros.obligacion ? { obligacion: filtros.obligacion } : {}),
      ...(filtros.desde ? { desde: filtros.desde } : {}),
      ...(filtros.hasta ? { hasta: filtros.hasta } : {}),
    }),

  crear: (clienteId: number, datos: VencimientoInput) =>
    post<Vencimiento>(`/clientes/${clienteId}/vencimientos`, datos),

  actualizar: (id: number, datos: Partial<VencimientoInput>) =>
    put<Vencimiento>(`/vencimientos/${id}`, datos),

  cambiarEstado: (id: number, estado: EstadoVencimiento) =>
    post<Vencimiento>(`/vencimientos/${id}/estado`, { estado }),

  eliminar: (id: number) => del<{ mensaje: string }>(`/vencimientos/${id}`),
}
