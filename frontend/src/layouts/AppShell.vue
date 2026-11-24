<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { ETIQUETA_ROL } from '@/api/tipos'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const menuAbierto = ref(false)

const nombre = computed(() => auth.usuario?.nombre ?? '')
const rol = computed(() => {
  if (!auth.usuario) return ''
  return auth.esPropietario ? 'Propietario' : ETIQUETA_ROL[auth.usuario.rol]
})
const titulo = computed(() => route.meta.titulo ?? 'Panel')

const secciones = computed(() => {
  if (auth.rol === 'cliente') {
    const id = auth.clienteId
    return [
      {
        clave: 'panel',
        nombre: 'Panel',
        ruta: '/',
        icono: 'panel',
        exacto: true,
      },
      {
        clave: 'mi-info',
        nombre: 'Mi información',
        ruta: id ? { name: 'cliente', params: { id } } : '/',
        icono: 'clientes',
        exacto: true,
      },
      {
        clave: 'comprobantes',
        nombre: 'Mis comprobantes',
        ruta: id
          ? { name: 'cliente-comprobantes', params: { id } }
          : '/',
        icono: 'comprobantes',
        exacto: true,
      },
      {
        clave: 'vencimientos',
        nombre: 'Vencimientos',
        ruta: id
          ? { name: 'cliente-vencimientos', params: { id } }
          : '/',
        icono: 'vencimientos',
        exacto: true,
      },
      {
        clave: 'reportes',
        nombre: 'Reportes',
        ruta: id ? { name: 'cliente-reportes', params: { id } } : '/',
        icono: 'reportes',
        exacto: true,
      },
    ]
  }

  return [
    {
      clave: 'panel',
      nombre: 'Panel',
      ruta: '/',
      icono: 'panel',
      exacto: true,
    },
    {
      clave: 'clientes',
      nombre: auth.esAdmin ? 'Clientes' : 'Mi cartera',
      ruta: '/clientes',
      icono: 'clientes',
      exacto: false,
    },
    {
      clave: 'bandeja',
      nombre: 'Bandeja',
      ruta: '/comprobantes',
      icono: 'comprobantes',
      exacto: true,
    },
    {
      clave: 'agenda',
      nombre: 'Agenda',
      ruta: '/vencimientos',
      icono: 'vencimientos',
      exacto: true,
    },
    ...(auth.esAdmin
      ? [
          {
            clave: 'usuarios',
            nombre: 'Usuarios',
            ruta: '/usuarios',
            icono: 'usuarios',
            exacto: false,
          },
          {
            clave: 'auditoria',
            nombre: 'Auditoría',
            ruta: '/auditoria',
            icono: 'auditoria',
            exacto: false,
          },
        ]
      : []),
  ]
})

watch(
  () => route.fullPath,
  () => {
    menuAbierto.value = false
  },
)

async function salir() {
  auth.cerrarSesion()
  await router.replace({ name: 'login' })
}
</script>

<template>
  <div class="shell">
    <!-- Sidebar -->
    <aside class="sidebar" :class="{ 'is-open': menuAbierto }">
      <RouterLink to="/" class="sidebar__brand">
        <span class="sidebar__mark" aria-hidden="true">
          <svg viewBox="0 0 24 24" width="17" height="17" fill="none">
            <path
              d="M4 7h16M4 12h11M4 17h7"
              stroke="currentColor"
              stroke-width="1.5"
              stroke-linecap="round"
            />
            <circle cx="18" cy="17" r="2.2" fill="currentColor" />
          </svg>
        </span>
        <span class="sidebar__texto">
          <span class="sidebar__nombre">Sistema Contable</span>
          <span class="sidebar__tag">Estudio · Viedma</span>
        </span>
      </RouterLink>

      <nav class="sidebar__nav" aria-label="Principal">
        <RouterLink
          v-for="seccion in secciones"
          :key="seccion.clave"
          :to="seccion.ruta"
          class="nav-item"
          :active-class="seccion.exacto ? '' : 'is-active'"
          :exact-active-class="seccion.exacto ? 'is-active' : undefined"
        >
          <svg
            v-if="seccion.icono === 'panel'"
            viewBox="0 0 20 20"
            width="16"
            height="16"
            fill="none"
            aria-hidden="true"
          >
            <rect x="2.5" y="2.5" width="6" height="6" rx="1.5" stroke="currentColor" stroke-width="1.4" />
            <rect x="11.5" y="2.5" width="6" height="6" rx="1.5" stroke="currentColor" stroke-width="1.4" />
            <rect x="2.5" y="11.5" width="6" height="6" rx="1.5" stroke="currentColor" stroke-width="1.4" />
            <rect x="11.5" y="11.5" width="6" height="6" rx="1.5" stroke="currentColor" stroke-width="1.4" />
          </svg>

          <svg
            v-else-if="seccion.icono === 'clientes'"
            viewBox="0 0 20 20"
            width="16"
            height="16"
            fill="none"
            aria-hidden="true"
          >
            <path
              d="M3 17V4.5c0-.8.7-1.5 1.5-1.5h7c.8 0 1.5.7 1.5 1.5V17"
              stroke="currentColor"
              stroke-width="1.4"
              stroke-linejoin="round"
            />
            <path d="M13 8h2.5c.8 0 1.5.7 1.5 1.5V17M2 17h16" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" />
            <path d="M6 6.5h4M6 9.5h4M6 12.5h4" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" />
          </svg>

          <svg
            v-else-if="seccion.icono === 'auditoria'"
            viewBox="0 0 20 20"
            width="16"
            height="16"
            fill="none"
            aria-hidden="true"
          >
            <path d="M10 2.5 16 5v5c0 3.6-2.5 6.3-6 7.5-3.5-1.2-6-3.9-6-7.5V5l6-2.5Z" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round" />
            <path d="M7.4 9.8 9.3 11.7l3.4-3.4" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" />
          </svg>

          <svg
            v-else-if="seccion.icono === 'comprobantes'"
            viewBox="0 0 20 20"
            width="16"
            height="16"
            fill="none"
            aria-hidden="true"
          >
            <path d="M5 3h7l3 3v11H5V3Z" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round" />
            <path d="M7 9h6M7 12h4" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" />
          </svg>

          <svg
            v-else-if="seccion.icono === 'vencimientos'"
            viewBox="0 0 20 20"
            width="16"
            height="16"
            fill="none"
            aria-hidden="true"
          >
            <rect x="3" y="4" width="14" height="13" rx="2" stroke="currentColor" stroke-width="1.4" />
            <path d="M3 8h14M7 2.5V6M13 2.5V6" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" />
          </svg>

          <svg
            v-else-if="seccion.icono === 'reportes'"
            viewBox="0 0 20 20"
            width="16"
            height="16"
            fill="none"
            aria-hidden="true"
          >
            <path d="M3.5 16.5V11M8 16.5V6M12.5 16.5V9M17 16.5V3.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
          </svg>

          <svg
            v-else
            viewBox="0 0 20 20"
            width="16"
            height="16"
            fill="none"
            aria-hidden="true"
          >
            <circle cx="7.5" cy="6.5" r="2.75" stroke="currentColor" stroke-width="1.4" />
            <path
              d="M2.75 16c0-2.6 2.13-4.5 4.75-4.5s4.75 1.9 4.75 4.5"
              stroke="currentColor"
              stroke-width="1.4"
              stroke-linecap="round"
            />
            <path
              d="M13.5 4.5a2.5 2.5 0 0 1 0 5M15 11.8c1.4.6 2.3 1.9 2.3 3.5"
              stroke="currentColor"
              stroke-width="1.4"
              stroke-linecap="round"
            />
          </svg>

          {{ seccion.nombre }}
        </RouterLink>
      </nav>

      <div class="sidebar__pie">
        <span class="sidebar__version">v1.0 · TP final</span>
        <a
          class="sidebar__legal"
          href="/api/docs"
          target="_blank"
          rel="noopener"
        >
          Documentación API ↗
        </a>
        <span class="sidebar__legal">UNComa · PWD</span>
      </div>
    </aside>

    <button
      v-if="menuAbierto"
      class="sidebar__backdrop"
      aria-label="Cerrar menú"
      @click="menuAbierto = false"
    ></button>

    <!-- Contenido -->
    <div class="shell__main">
      <header class="topbar">
        <button
          class="icon-btn topbar__menu"
          type="button"
          aria-label="Abrir menú"
          @click="menuAbierto = true"
        >
          <svg viewBox="0 0 20 20" width="18" height="18" fill="none" aria-hidden="true">
            <path d="M3 6h14M3 10h14M3 14h14" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
          </svg>
        </button>

        <p class="topbar__titulo">{{ titulo }}</p>

        <div class="topbar__usuario">
          <span class="avatar" aria-hidden="true">{{ auth.iniciales }}</span>
          <span class="topbar__datos">
            <span class="topbar__nombre">{{ nombre }}</span>
            <span class="topbar__rol">{{ rol }}</span>
          </span>
          <RouterLink
            v-if="!auth.debeCambiarPassword"
            :to="{ name: 'cambiar-password' }"
            class="btn btn--ghost btn--sm"
          >
            Mi cuenta
          </RouterLink>
          <button class="btn btn--ghost btn--sm" type="button" @click="salir">
            Salir
          </button>
        </div>
      </header>

      <main class="contenido">
        <RouterView />
      </main>
    </div>
  </div>
</template>

<style scoped>
.shell {
  display: grid;
  grid-template-columns: 16.5rem minmax(0, 1fr);
  min-height: 100dvh;
  background: var(--color-bg);
}

/* ------------------------------------------------------------------ Sidebar */
.sidebar {
  position: sticky;
  top: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-6);
  height: 100dvh;
  padding: var(--space-5) var(--space-4);
  border-right: 1px solid var(--color-line);
  background:
    radial-gradient(120% 60% at 0% 0%, rgb(43 217 138 / 7%), transparent 60%),
    linear-gradient(180deg, rgb(11 13 18 / 98%), rgb(7 8 11 / 98%));
  overflow-y: auto;
}

.sidebar__brand {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-1) var(--space-2);
  text-decoration: none;
}

.sidebar__mark {
  display: grid;
  place-items: center;
  width: 2.25rem;
  height: 2.25rem;
  border: 1px solid var(--color-line-strong);
  border-radius: var(--radius-md);
  background: linear-gradient(150deg, rgb(43 217 138 / 14%), transparent 65%);
  color: var(--color-accent);
  flex: none;
}

.sidebar__texto {
  display: grid;
  line-height: 1.25;
}

.sidebar__nombre {
  font-size: var(--text-sm);
  font-weight: 600;
}

.sidebar__tag {
  font-size: var(--text-xs);
  color: var(--color-text-faint);
}

.sidebar__nav {
  display: grid;
  gap: 2px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: 0.55rem var(--space-3);
  border-radius: var(--radius-sm);
  color: var(--color-text-muted);
  font-size: var(--text-sm);
  text-decoration: none;
  transition:
    background-color var(--dur-fast) var(--ease-out),
    color var(--dur-fast) var(--ease-out);
}

.nav-item:hover {
  background: rgb(255 255 255 / 4%);
  color: var(--color-text);
}

.nav-item.is-active {
  background: rgb(43 217 138 / 10%);
  color: var(--color-accent);
}

.sidebar__pie {
  display: grid;
  gap: var(--space-1);
  margin-top: auto;
  padding: var(--space-3) var(--space-2) 0;
  border-top: 1px solid var(--color-line);
}

.sidebar__version {
  font-family: var(--font-mono);
  font-size: 0.625rem;
  color: var(--color-text-faint);
}

.sidebar__legal {
  font-size: var(--text-xs);
  color: var(--color-text-faint);
  text-decoration: none;
}

.sidebar__legal:hover {
  color: var(--color-text-muted);
}

.sidebar__backdrop {
  display: none;
}

/* ------------------------------------------------------------------- Topbar */
.shell__main {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.topbar {
  position: sticky;
  top: 0;
  z-index: var(--z-content);
  display: flex;
  align-items: center;
  gap: var(--space-4);
  min-height: 4rem;
  padding: var(--space-3) clamp(1rem, 3vw, 2.5rem);
  border-bottom: 1px solid var(--color-line);
  background: rgb(7 8 11 / 78%);
  backdrop-filter: blur(14px);
}

.topbar__menu {
  display: none;
}

.topbar__titulo {
  font-family: var(--font-display);
  font-size: var(--text-lg);
  letter-spacing: -0.01em;
}

.topbar__usuario {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-left: auto;
}

.topbar__datos {
  display: grid;
  line-height: 1.2;
  text-align: right;
}

.topbar__nombre {
  font-size: var(--text-sm);
  font-weight: 500;
}

.topbar__rol {
  font-size: var(--text-xs);
  color: var(--color-text-faint);
}

.contenido {
  width: 100%;
  max-width: 78rem;
  margin-inline: auto;
  padding: clamp(1.25rem, 3vw, 2.5rem);
}

/* ------------------------------------------------------------------ Mobile */
@media (max-width: 56rem) {
  .shell {
    grid-template-columns: 1fr;
  }

  .sidebar {
    position: fixed;
    inset: 0 auto 0 0;
    z-index: var(--z-overlay);
    width: 17rem;
    transform: translateX(-100%);
    transition: transform var(--dur-base) var(--ease-out);
    box-shadow: 0 0 60px rgb(0 0 0 / 60%);
  }

  .sidebar.is-open {
    transform: none;
  }

  .sidebar__backdrop {
    position: fixed;
    inset: 0;
    z-index: calc(var(--z-overlay) - 1);
    display: block;
    border: 0;
    background: rgb(0 0 0 / 55%);
    backdrop-filter: blur(2px);
  }

  .topbar__menu {
    display: grid;
  }

  .topbar__datos {
    display: none;
  }
}
</style>
