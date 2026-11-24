/** Estado global de la sesión. */

import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { authApi } from '@/api/auth'
import {
  getAccessToken,
  guardarTokens,
  limpiarTokens,
} from '@/api/client'
import type { Rol, Usuario } from '@/api/tipos'

export const useAuthStore = defineStore('auth', () => {
  const usuario = ref<Usuario | null>(null)
  const accessToken = ref<string | null>(getAccessToken())

  const autenticado = computed(() => Boolean(accessToken.value))
  const rol = computed<Rol | null>(() => usuario.value?.rol ?? null)
  const esAdmin = computed(() => rol.value === 'admin')
  const esPropietario = computed(() => Boolean(usuario.value?.es_propietario))
  const debeCambiarPassword = computed(
    () => Boolean(usuario.value?.debe_cambiar_password),
  )
  const clienteId = computed<number | null>(
    () => usuario.value?.cliente_id ?? null,
  )
  const iniciales = computed(() => {
    const nombre = usuario.value?.nombre ?? ''
    return nombre
      .split(' ')
      .filter(Boolean)
      .slice(0, 2)
      .map((parte) => parte[0]?.toUpperCase() ?? '')
      .join('')
  })

  function puede(...roles: Rol[]): boolean {
    return rol.value !== null && roles.includes(rol.value)
  }

  async function iniciarSesion(email: string, password: string): Promise<void> {
    const sesion = await authApi.login(email, password)
    guardarTokens(sesion.access_token, sesion.refresh_token)
    accessToken.value = sesion.access_token
    usuario.value = sesion.usuario
  }

  async function cargarPerfil(): Promise<void> {
    usuario.value = await authApi.me()
    accessToken.value = getAccessToken()
  }

  function cerrarSesion(): void {
    limpiarTokens()
    accessToken.value = null
    usuario.value = null
  }

  return {
    usuario,
    accessToken,
    autenticado,
    rol,
    esAdmin,
    esPropietario,
    debeCambiarPassword,
    clienteId,
    iniciales,
    puede,
    iniciarSesion,
    cargarPerfil,
    cerrarSesion,
  }
})
