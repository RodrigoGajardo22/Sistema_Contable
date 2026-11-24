/** Tipos compartidos de la API. */

export type Rol = 'admin' | 'contador' | 'cliente'

export interface Usuario {
  id: number
  nombre: string
  email: string
  rol: Rol
  activo: boolean
  es_propietario: boolean
  debe_cambiar_password: boolean
  cliente_id: number | null
  creado_en: string
  actualizado_en: string
}

export interface Cliente {
  id: number
  cuit: string
  activo: boolean
  razon_social: string
  condicion_iva: string
  condicion_iva_etiqueta: string
  email: string | null
  telefono: string | null
  direccion: string | null
  contador_id: number | null
  contador_nombre: string | null
  contador_email: string | null
  usuario_id: number | null
  usuario_nombre: string | null
  usuario_email: string | null
  usuario_activo: boolean | null
  acceso_temporal?: string | null
  version_id: number
  actualizado_en: string
  actualizado_por: string | null
}

export interface ClienteVersion {
  id: number
  razon_social: string
  condicion_iva: string
  condicion_iva_etiqueta: string
  email: string | null
  telefono: string | null
  direccion: string | null
  contador_id: number | null
  contador_nombre: string | null
  creado_en: string
  creado_por: string | null
}

export const CONDICIONES_IVA = [
  { valor: 'responsable_inscripto', etiqueta: 'Responsable Inscripto' },
  { valor: 'monotributo', etiqueta: 'Monotributo' },
  { valor: 'exento', etiqueta: 'Exento' },
  { valor: 'consumidor_final', etiqueta: 'Consumidor Final' },
] as const

export interface Cuenta {
  id: number
  cliente_id: number
  codigo: string
  nombre: string
  tipo: string
  tipo_etiqueta: string
  padre_id: number | null
  imputable: boolean
  activa: boolean
  creado_en: string
}

export const TIPOS_CUENTA = [
  { valor: 'activo', etiqueta: 'Activo' },
  { valor: 'pasivo', etiqueta: 'Pasivo' },
  { valor: 'patrimonio', etiqueta: 'Patrimonio neto' },
  { valor: 'ingreso', etiqueta: 'Ingreso' },
  { valor: 'egreso', etiqueta: 'Egreso' },
] as const

export function formatearCuit(cuit: string | null | undefined): string {
  const digitos = (cuit ?? '').replace(/\D/g, '')
  if (digitos.length !== 11) return cuit ?? ''
  return `${digitos.slice(0, 2)}-${digitos.slice(2, 10)}-${digitos.slice(10)}`
}

export interface Sesion {
  usuario: Usuario
  access_token: string
  refresh_token: string
  token_type: string
}

export const ETIQUETA_ROL: Record<Rol, string> = {
  admin: 'Administrador',
  contador: 'Contador',
  cliente: 'Cliente',
}
