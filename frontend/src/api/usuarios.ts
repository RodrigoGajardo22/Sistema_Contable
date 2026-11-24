/** Endpoints de usuarios. */

import { del, getConMeta, post, put } from '@/api/client'
import type { Rol, Usuario } from '@/api/tipos'

export type FiltroEstado = 'todos' | 'activos' | 'inactivos'

export interface FiltrosUsuarios {
  q?: string
  rol?: Rol | ''
  activo?: FiltroEstado
}

export interface NuevoUsuario {
  nombre: string
  email: string
  password: string
  rol: Rol
}

export interface EdicionUsuario {
  nombre?: string
  email?: string
  rol?: Rol
}

export interface CambioPassword {
  password_nueva: string
  password_actual?: string
}

function parametros(filtros: FiltrosUsuarios): Record<string, unknown> {
  const params: Record<string, unknown> = {}
  if (filtros.q) params.q = filtros.q
  if (filtros.rol) params.rol = filtros.rol
  if (filtros.activo === 'activos') params.activo = 'true'
  if (filtros.activo === 'inactivos') params.activo = 'false'
  return params
}

export const usuariosApi = {
  listar: (filtros: FiltrosUsuarios = {}) =>
    getConMeta<Usuario[]>('/usuarios', parametros(filtros)),

  crear: (datos: NuevoUsuario) => post<Usuario>('/usuarios', datos),

  actualizar: (id: number, datos: EdicionUsuario) =>
    put<Usuario>(`/usuarios/${id}`, datos),

  desactivar: (id: number) => del<Usuario>(`/usuarios/${id}`),

  activar: (id: number) => post<Usuario>(`/usuarios/${id}/activar`),

  cambiarPassword: (id: number, datos: CambioPassword) =>
    put<{ mensaje: string }>(`/usuarios/${id}/password`, datos),

  transferirPropiedad: (id: number) =>
    post<Usuario>(`/usuarios/${id}/propietario`, {}),
}
