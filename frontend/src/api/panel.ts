/** Endpoints de auditoría y dashboard. */

import { get, getConMeta } from '@/api/client'

export interface EntradaAuditoria {
  id: number
  usuario: string
  accion: string
  entidad: string
  entidad_id: number | null
  antes: Record<string, unknown> | null
  despues: Record<string, unknown> | null
  fecha: string
}

export interface Dashboard {
  clientes: number
  asientos_mes: number
  comprobantes_pendientes: number
  comprobantes_mes: number
  responsable: {
    nombre: string | null
    email: string | null
  } | null
  vencimientos: {
    proximos: number
    vencidos: number
    pendientes: number
  }
  conciliaciones_pendientes: number
  proximos_vencimientos: {
    id: number
    cliente: string
    obligacion: string
    fecha: string
    dias: number
  }[]
  ultimos_asientos: {
    id: number
    numero: number
    fecha: string
    concepto: string
    cliente: string
    total: string
  }[]
}

export const auditoriaApi = {
  listar: (
    filtros: {
      entidad?: string
      accion?: string
      usuario?: number
      desde?: string
      hasta?: string
    } = {},
  ) => getConMeta<EntradaAuditoria[]>('/auditoria', { ...filtros }),
}

export const dashboardApi = {
  resumen: () => get<Dashboard>('/dashboard'),
}
