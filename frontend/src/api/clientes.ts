/** Endpoints de clientes. */

import { del, get, getConMeta, post, put } from '@/api/client'
import type { Cliente, ClienteVersion } from '@/api/tipos'
import type { FiltroEstado } from '@/api/usuarios'

export interface FiltrosClientes {
  q?: string
  activo?: FiltroEstado
  contador?: number | null
}

export interface NuevoCliente {
  razon_social: string
  cuit: string
  condicion_iva: string
  email: string
  telefono?: string | null
  direccion?: string | null
  contador_id?: number | null
}

export type EdicionCliente = Partial<Omit<NuevoCliente, 'cuit'>>

export interface AccesoCreado {
  usuario_id: number
  nombre: string
  email: string
  password_temporal: string
}

function parametros(filtros: FiltrosClientes): Record<string, unknown> {
  const params: Record<string, unknown> = {}
  if (filtros.q) params.q = filtros.q
  if (filtros.activo === 'activos') params.activo = 'true'
  if (filtros.activo === 'inactivos') params.activo = 'false'
  if (filtros.contador) params.contador = filtros.contador
  return params
}

export const clientesApi = {
  listar: (filtros: FiltrosClientes = {}) =>
    getConMeta<Cliente[]>('/clientes', parametros(filtros)),

  obtener: (id: number) => get<Cliente>(`/clientes/${id}`),

  crear: (datos: NuevoCliente) => post<Cliente>('/clientes', datos),

  actualizar: (id: number, datos: EdicionCliente) =>
    put<Cliente>(`/clientes/${id}`, datos),

  desactivar: (id: number) => del<Cliente>(`/clientes/${id}`),

  activar: (id: number) => post<Cliente>(`/clientes/${id}/activar`, {}),

  historial: (id: number) => get<ClienteVersion[]>(`/clientes/${id}/historial`),

  crearAcceso: (id: number) =>
    post<AccesoCreado>(`/clientes/${id}/acceso`, {}),

  restablecerAcceso: (id: number) =>
    post<AccesoCreado>(`/clientes/${id}/acceso/reset`, {}),

  revocarAcceso: (id: number) =>
    del<{ mensaje: string }>(`/clientes/${id}/acceso`),
}
