import { createRouter, createWebHistory } from 'vue-router'

import type { Rol } from '@/api/tipos'
import { useAuthStore } from '@/stores/auth'

declare module 'vue-router' {
  interface RouteMeta {
    publica?: boolean
    requiereAuth?: boolean
    roles?: Rol[]
    titulo?: string
  }
}

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),

  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginView.vue'),
      meta: { publica: true },
    },
    {
      path: '/',
      component: () => import('@/layouts/AppShell.vue'),
      meta: { requiereAuth: true },
      children: [
        {
          path: '',
          name: 'dashboard',
          component: () => import('@/views/DashboardView.vue'),
          meta: { titulo: 'Panel' },
        },
        {
          path: 'comprobantes',
          name: 'comprobantes-bandeja',
          component: () => import('@/views/BandejaComprobantesView.vue'),
          meta: { titulo: 'Bandeja de comprobantes', roles: ['admin', 'contador'] },
        },
        {
          path: 'vencimientos',
          name: 'vencimientos-agenda',
          component: () => import('@/views/AgendaVencimientosView.vue'),
          meta: { titulo: 'Agenda de vencimientos', roles: ['admin', 'contador'] },
        },
        {
          path: 'clientes',
          name: 'clientes',
          component: () => import('@/views/ClientesView.vue'),
          meta: { titulo: 'Clientes', roles: ['admin', 'contador'] },
        },
        {
          path: 'clientes/:id',
          name: 'cliente',
          component: () => import('@/views/ClienteDetalleView.vue'),
          meta: { titulo: 'Ficha del cliente', roles: ['admin', 'contador', 'cliente'] },
        },
        {
          path: 'clientes/:id/cuentas',
          name: 'cliente-cuentas',
          component: () => import('@/views/CuentasView.vue'),
          meta: { titulo: 'Plan de cuentas', roles: ['admin', 'contador'] },
        },
        {
          path: 'clientes/:id/asientos',
          name: 'cliente-asientos',
          component: () => import('@/views/AsientosView.vue'),
          meta: { titulo: 'Libro diario', roles: ['admin', 'contador'] },
        },
        {
          path: 'clientes/:id/comprobantes',
          name: 'cliente-comprobantes',
          component: () => import('@/views/ComprobantesView.vue'),
          meta: { titulo: 'Comprobantes', roles: ['admin', 'contador', 'cliente'] },
        },
        {
          path: 'clientes/:id/vencimientos',
          name: 'cliente-vencimientos',
          component: () => import('@/views/VencimientosView.vue'),
          meta: { titulo: 'Vencimientos', roles: ['admin', 'contador', 'cliente'] },
        },
        {
          path: 'clientes/:id/reportes',
          name: 'cliente-reportes',
          component: () => import('@/views/ReportesView.vue'),
          meta: { titulo: 'Reportes', roles: ['admin', 'contador', 'cliente'] },
        },
        {
          path: 'clientes/:id/conciliacion',
          name: 'cliente-conciliacion',
          component: () => import('@/views/ConciliacionView.vue'),
          meta: { titulo: 'Conciliación', roles: ['admin', 'contador'] },
        },
        {
          path: 'auditoria',
          name: 'auditoria',
          component: () => import('@/views/AuditoriaView.vue'),
          meta: { titulo: 'Auditoría', roles: ['admin'] },
        },
        {
          path: 'usuarios',
          name: 'usuarios',
          component: () => import('@/views/UsuariosView.vue'),
          meta: { titulo: 'Usuarios', roles: ['admin'] },
        },
        {
          path: 'cambiar-password',
          name: 'cambiar-password',
          component: () => import('@/views/CambiarPasswordView.vue'),
          meta: { titulo: 'Cambiar contraseña' },
        },
        {
          path: 'denegado',
          name: 'denegado',
          component: () => import('@/views/AccesoDenegadoView.vue'),
          meta: { titulo: 'Acceso denegado' },
        },
      ],
    },
    {
      path: '/:pathMatch(.*)*',
      redirect: { name: 'dashboard' },
    },
  ],

  scrollBehavior: () => ({ top: 0 }),
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  const requiereAuth = to.matched.some((registro) => registro.meta.requiereAuth)

  if (!requiereAuth) {
    // Ya logueado: el login no tiene sentido.
    if (to.name === 'login' && auth.autenticado) {
      return auth.usuario?.debe_cambiar_password
        ? { name: 'cambiar-password' }
        : { name: 'dashboard' }
    }
    return true
  }

  if (!auth.autenticado) {
    return {
      name: 'login',
      query: to.fullPath === '/' ? undefined : { redirect: to.fullPath },
    }
  }

  if (!auth.usuario) {
    try {
      await auth.cargarPerfil()
    } catch {
      auth.cerrarSesion()
      return { name: 'login' }
    }
  }

  if (auth.debeCambiarPassword && to.name !== 'cambiar-password') {
    return { name: 'cambiar-password' }
  }

  if (auth.rol === 'cliente' && to.name === 'clientes') {
    return auth.clienteId
      ? { name: 'cliente', params: { id: auth.clienteId } }
      : { name: 'dashboard' }
  }

  const rolesPermitidos = to.matched.flatMap(
    (registro) => registro.meta.roles ?? [],
  )

  if (
    rolesPermitidos.length > 0 &&
    auth.usuario &&
    !rolesPermitidos.includes(auth.usuario.rol)
  ) {
    return { name: 'denegado' }
  }

  return true
})

export default router
