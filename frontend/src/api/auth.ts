/** Endpoints de autenticación. */

import { get, post } from '@/api/client'
import type { Sesion, Usuario } from '@/api/tipos'

export const authApi = {
  login: (email: string, password: string) =>
    post<Sesion>('/auth/login', { email, password }),

  me: () => get<Usuario>('/auth/me'),
}
