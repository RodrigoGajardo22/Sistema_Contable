/**
 * Cliente HTTP de la aplicación.
 *
 * - Adjunta el access token en cada request.
 * - Si el token está por vencer, lo renueva antes de enviar (refresh proactivo).
 * - Ante un 401 lo intenta una vez más con un token nuevo y reintenta.
 * - Si el refresh falla, cierra la sesión y vuelve al login.
 *
 * La URL base es relativa ("/api") para funcionar igual detrás del gateway de
 * desarrollo y del nginx de producción.
 */

import axios, { AxiosError, type InternalAxiosRequestConfig } from 'axios'

const API_BASE_URL: string = import.meta.env.VITE_API_URL ?? '/api'

const CLAVE_ACCESS = 'sc.auth.access'
const CLAVE_REFRESH = 'sc.auth.refresh'
const RUTAS_SIN_REFRESH = ['/auth/login', '/auth/refresh']
const MARGEN_REFRESCO_SEGUNDOS = 30

export interface DetalleError {
  [clave: string]: unknown
}

export class ApiError extends Error {
  readonly mensaje: string
  readonly status: number
  readonly codigo: string
  readonly detalles?: DetalleError

  constructor(
    mensaje: string,
    status: number,
    codigo = 'error',
    detalles?: DetalleError,
  ) {
    super(mensaje)
    this.name = 'ApiError'
    this.mensaje = mensaje
    this.status = status
    this.codigo = codigo
    this.detalles = detalles
  }
}

/* -------------------------------------------------------------------------
   Tokens (localStorage)
   ------------------------------------------------------------------------- */

export function getAccessToken(): string | null {
  return localStorage.getItem(CLAVE_ACCESS)
}

export function getRefreshToken(): string | null {
  return localStorage.getItem(CLAVE_REFRESH)
}

export function guardarTokens(access: string, refresh?: string | null): void {
  localStorage.setItem(CLAVE_ACCESS, access)
  if (refresh) localStorage.setItem(CLAVE_REFRESH, refresh)
}

export function limpiarTokens(): void {
  localStorage.removeItem(CLAVE_ACCESS)
  localStorage.removeItem(CLAVE_REFRESH)
}

/* -------------------------------------------------------------------------
   Utilidades de JWT
   ------------------------------------------------------------------------- */

function leerPayload(token: string): { exp?: number } | null {
  const partes = token.split('.')
  const payload = partes[1]
  if (!payload) return null

  try {
    const normalizado = payload.replace(/-/g, '+').replace(/_/g, '/')
    const conRelleno = normalizado.padEnd(Math.ceil(normalizado.length / 4) * 4, '=')
    return JSON.parse(atob(conRelleno)) as { exp?: number }
  } catch {
    return null
  }
}

function estaPorVencer(token: string): boolean {
  const payload = leerPayload(token)
  if (!payload?.exp) return false
  return payload.exp - Date.now() / 1000 < MARGEN_REFRESCO_SEGUNDOS
}

/* -------------------------------------------------------------------------
   Instancia de Axios
   ------------------------------------------------------------------------- */

export const http = axios.create({
  baseURL: API_BASE_URL,
  headers: { Accept: 'application/json' },
  timeout: 20000,
})

function esRutaAuth(url: string | undefined): boolean {
  if (!url) return false
  return RUTAS_SIN_REFRESH.some((ruta) => url.includes(ruta))
}

let refrescoEnCurso: Promise<string> | null = null

/** Renueva el access token. Varias requests concurrentes comparten el mismo refresco. */
function refrescarAccessToken(): Promise<string> {
  if (refrescoEnCurso) return refrescoEnCurso

  const refresh = getRefreshToken()
  if (!refresh) return Promise.reject(new Error('No hay refresh token'))

  refrescoEnCurso = axios
    .post<{ datos: { access_token: string } }>(
      `${API_BASE_URL}/auth/refresh`,
      null,
      { headers: { Authorization: `Bearer ${refresh}` }, timeout: 20000 },
    )
    .then(({ data }) => {
      const nuevo = data.datos.access_token
      guardarTokens(nuevo)
      return nuevo
    })
    .finally(() => {
      refrescoEnCurso = null
    })

  return refrescoEnCurso
}

function cerrarSesionForzada(): void {
  limpiarTokens()
  if (!window.location.pathname.startsWith('/login')) {
    window.location.assign('/login')
  }
}

http.interceptors.request.use(async (config) => {
  if (esRutaAuth(config.url)) return config

  const token = getAccessToken()
  if (token && estaPorVencer(token) && getRefreshToken()) {
    try {
      const renovado = await refrescarAccessToken()
      config.headers.Authorization = `Bearer ${renovado}`
      return config
    } catch {
      // Si falla, la request sigue y el 401 dispara el cierre de sesión.
    }
  }

  const actual = getAccessToken()
  if (actual && !config.headers.Authorization) {
    config.headers.Authorization = `Bearer ${actual}`
  }

  return config
})

interface ConfigReintentable extends InternalAxiosRequestConfig {
  _reintentado?: boolean
}

http.interceptors.response.use(
  (respuesta) => respuesta,
  async (error: AxiosError<{ error?: { codigo?: string; mensaje?: string; detalles?: DetalleError } }>) => {
    const config = error.config as ConfigReintentable | undefined
    const status = error.response?.status

    const puedeReintentar =
      status === 401 &&
      config !== undefined &&
      !config._reintentado &&
      !esRutaAuth(config.url) &&
      Boolean(getRefreshToken())

    if (puedeReintentar && config) {
      config._reintentado = true
      try {
        const renovado = await refrescarAccessToken()
        config.headers.Authorization = `Bearer ${renovado}`
        return http(config)
      } catch {
        cerrarSesionForzada()
      }
    }

    throw aApiError(error)
  },
)

function aApiError(error: AxiosError<{ error?: { codigo?: string; mensaje?: string; detalles?: DetalleError } }>): ApiError {
  const cuerpo = error.response?.data?.error
  const status = error.response?.status ?? 0

  if (cuerpo?.mensaje) {
    return new ApiError(cuerpo.mensaje, status, cuerpo.codigo ?? 'error', cuerpo.detalles)
  }

  if (status === 0) {
    return new ApiError(
      'No pudimos contactar el servidor. Revisá tu conexión.',
      0,
      'sin_conexion',
    )
  }

  return new ApiError(`La solicitud falló (${status}).`, status)
}

/* -------------------------------------------------------------------------
   Helpers tipados para el sobre { datos, meta }
   ------------------------------------------------------------------------- */

export async function get<T>(url: string, params?: Record<string, unknown>): Promise<T> {
  const { data } = await http.get<{ datos: T }>(url, { params })
  return data.datos
}

export async function getConMeta<T>(
  url: string,
  params?: Record<string, unknown>,
): Promise<{ datos: T; total: number }> {
  const { data } = await http.get<{ datos: T; meta?: { total?: number } }>(url, { params })
  return { datos: data.datos, total: data.meta?.total ?? 0 }
}

export async function getCrudo<T>(url: string): Promise<T> {
  const { data } = await http.get<T>(url)
  return data
}

export async function post<T>(url: string, cuerpo?: unknown): Promise<T> {
  const { data } = await http.post<{ datos: T }>(url, cuerpo)
  return data.datos
}

export async function put<T>(url: string, cuerpo?: unknown): Promise<T> {
  const { data } = await http.put<{ datos: T }>(url, cuerpo)
  return data.datos
}

export async function del<T>(url: string): Promise<T> {
  const { data } = await http.delete<{ datos: T }>(url)
  return data.datos
}
