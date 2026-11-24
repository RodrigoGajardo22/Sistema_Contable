/** Endpoints del plan de cuentas. */

import { del, get, post, put } from '@/api/client'
import type { Cuenta } from '@/api/tipos'

export interface NuevaCuenta {
  codigo: string
  nombre: string
  tipo: string
  padre_id?: number | null
  imputable?: boolean
}

export interface EdicionCuenta {
  nombre?: string
  padre_id?: number | null
  imputable?: boolean
  activa?: boolean
}

export const cuentasApi = {
  listar: (clienteId: number) => get<Cuenta[]>(`/clientes/${clienteId}/cuentas`),

  crear: (clienteId: number, datos: NuevaCuenta) =>
    post<Cuenta>(`/clientes/${clienteId}/cuentas`, datos),

  actualizar: (id: number, datos: EdicionCuenta) =>
    put<Cuenta>(`/cuentas/${id}`, datos),

  eliminar: (id: number) => del<{ mensaje: string }>(`/cuentas/${id}`),
}
