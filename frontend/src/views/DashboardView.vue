<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import {
  comprobantesApi,
  type Comprobante,
} from '@/api/comprobantes'
import { dashboardApi, type Dashboard } from '@/api/panel'
import { ETIQUETA_ROL } from '@/api/tipos'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()

const esCliente = computed(() => auth.rol === 'cliente')
const esContador = computed(() => auth.rol === 'contador')
const esAdmin = computed(() => auth.rol === 'admin')
const clienteId = computed(() => auth.clienteId)

const resumen = ref<Dashboard | null>(null)
const pendientes = ref<Comprobante[]>([])
const cargandoPanel = ref(true)

onMounted(async () => {
  try {
    resumen.value = await dashboardApi.resumen()
  } catch {
    resumen.value = null
  } finally {
    cargandoPanel.value = false
  }

  if (auth.rol === 'contador') {
    try {
      const bandeja = await comprobantesApi.listarGlobal({ estado: 'pendiente' })
      pendientes.value = bandeja.datos.slice(0, 5)
    } catch {
      pendientes.value = []
    }
  }
})

const nombre = computed(() =>
  esCliente.value
    ? (auth.usuario?.nombre ?? '')
    : (auth.usuario?.nombre.split(' ')[0] ?? ''),
)
const rol = computed(() =>
  auth.usuario ? ETIQUETA_ROL[auth.usuario.rol] : '',
)

const fecha = new Intl.DateTimeFormat('es-AR', {
  weekday: 'long',
  day: 'numeric',
  month: 'long',
}).format(new Date())

const fechaCorta = new Intl.DateTimeFormat('es-AR', { day: '2-digit', month: 'short' })
const moneda = new Intl.NumberFormat('es-AR', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})

function fechaVisible(iso: string): string {
  const [anio, mes, dia] = iso.split('-')
  return fechaCorta.format(new Date(Number(anio), Number(mes) - 1, Number(dia)))
}

function formatearMonto(valor: string | number | null | undefined): string {
  return moneda.format(Number(valor ?? 0))
}

const tarjetas = computed(() => {
  if (esCliente.value) {
    return [
      {
        titulo: 'Comprobantes pendientes',
        valor: cargandoPanel.value
          ? '…'
          : String(resumen.value?.comprobantes_pendientes ?? 0),
        nota: 'Esperando contabilización del estudio',
        alerta: (resumen.value?.comprobantes_pendientes ?? 0) > 0,
      },
      {
        titulo: 'Comprobantes del mes',
        valor: cargandoPanel.value
          ? '…'
          : String(resumen.value?.comprobantes_mes ?? 0),
        nota: 'Cargados en el mes en curso',
      },
      {
        titulo: 'Vencimientos próximos',
        valor: cargandoPanel.value
          ? '…'
          : String(resumen.value?.vencimientos.proximos ?? 0),
        nota: 'Próximos 30 días',
      },
      {
        titulo: 'Vencimientos vencidos',
        valor: cargandoPanel.value
          ? '…'
          : String(resumen.value?.vencimientos.vencidos ?? 0),
        nota: 'Sin presentar ni pagar',
        alerta: (resumen.value?.vencimientos.vencidos ?? 0) > 0,
      },
    ]
  }

  if (esContador.value) {
    return [
      {
        titulo: 'Clientes a cargo',
        valor: cargandoPanel.value ? '…' : String(resumen.value?.clientes ?? 0),
        nota: 'Tu cartera asignada',
      },
      {
        titulo: 'Comprobantes pendientes',
        valor: cargandoPanel.value
          ? '…'
          : String(resumen.value?.comprobantes_pendientes ?? 0),
        nota: 'Para revisar y contabilizar',
        alerta: (resumen.value?.comprobantes_pendientes ?? 0) > 0,
      },
      {
        titulo: 'Vencimientos próximos',
        valor: cargandoPanel.value
          ? '…'
          : String(resumen.value?.vencimientos.proximos ?? 0),
        nota: 'Próximos 30 días',
      },
      {
        titulo: 'Vencimientos vencidos',
        valor: cargandoPanel.value
          ? '…'
          : String(resumen.value?.vencimientos.vencidos ?? 0),
        nota: 'Sin presentar ni pagar',
        alerta: (resumen.value?.vencimientos.vencidos ?? 0) > 0,
      },
      {
        titulo: 'Conciliaciones',
        valor: cargandoPanel.value
          ? '…'
          : String(resumen.value?.conciliaciones_pendientes ?? 0),
        nota: 'Movimientos bancarios pendientes',
      },
    ]
  }

  return [
    {
      titulo: 'Clientes',
      valor: cargandoPanel.value ? '…' : String(resumen.value?.clientes ?? 0),
      nota: 'Visibles para tu rol',
    },
    {
      titulo: 'Asientos del mes',
      valor: cargandoPanel.value ? '…' : String(resumen.value?.asientos_mes ?? 0),
      nota: 'Confirmados en el mes en curso',
    },
    {
      titulo: 'Vencimientos próximos',
      valor: cargandoPanel.value ? '…' : String(resumen.value?.vencimientos.proximos ?? 0),
      nota: 'Próximos 30 días',
    },
    {
      titulo: 'Vencimientos vencidos',
      valor: cargandoPanel.value ? '…' : String(resumen.value?.vencimientos.vencidos ?? 0),
      nota: 'Sin presentar ni pagar',
      alerta: (resumen.value?.vencimientos.vencidos ?? 0) > 0,
    },
    {
      titulo: 'Conciliaciones',
      valor: cargandoPanel.value ? '…' : String(resumen.value?.conciliaciones_pendientes ?? 0),
      nota: 'Movimientos bancarios pendientes',
    },
  ]
})

</script>

<template>
  <section class="panel">
    <header class="panel__head">
      <p class="eyebrow">Panel</p>
      <h1 class="panel__titulo">Buen día, {{ nombre }}</h1>
      <p class="panel__sub">
        Sesión iniciada como <strong>{{ rol }}</strong> · {{ fecha }}
      </p>
    </header>

    <div class="tarjetas">
      <article
        v-for="tarjeta in tarjetas"
        :key="tarjeta.titulo"
        class="card tarjeta"
        :class="{ 'is-alerta': 'alerta' in tarjeta && tarjeta.alerta }"
      >
        <p class="tarjeta__rotulo">{{ tarjeta.titulo }}</p>
        <p class="tarjeta__valor">{{ tarjeta.valor }}</p>
        <p class="tarjeta__nota">{{ tarjeta.nota }}</p>
      </article>
    </div>

    <section v-if="esCliente" class="acciones-cliente">
      <div class="acciones-cliente__cabecera">
        <div>
          <p class="eyebrow">Portal del cliente</p>
          <h2 class="acciones-cliente__titulo">Accesos rápidos</h2>
        </div>
        <span class="acciones-cliente__nota">Todo tu estudio, en un lugar</span>
      </div>

      <div v-if="clienteId" class="acciones-cliente__grid">
        <RouterLink
          :to="{
            name: 'cliente-comprobantes',
            params: { id: clienteId },
            query: { nuevo: '1' },
          }"
          class="accion card"
        >
          <span class="accion__icono" aria-hidden="true">+</span>
          <span class="accion__texto">
            <span class="accion__titulo">Subir comprobante</span>
            <span class="accion__nota">Cargá una factura de compra</span>
          </span>
        </RouterLink>

        <RouterLink
          :to="{ name: 'cliente-comprobantes', params: { id: clienteId } }"
          class="accion card"
        >
          <span class="accion__icono" aria-hidden="true">▤</span>
          <span class="accion__texto">
            <span class="accion__titulo">Mis comprobantes</span>
            <span class="accion__nota">Consultá ventas y compras</span>
          </span>
        </RouterLink>

        <RouterLink
          :to="{ name: 'cliente-vencimientos', params: { id: clienteId } }"
          class="accion card"
        >
          <span class="accion__icono" aria-hidden="true">◷</span>
          <span class="accion__texto">
            <span class="accion__titulo">Vencimientos</span>
            <span class="accion__nota">Calendario impositivo</span>
          </span>
        </RouterLink>

        <RouterLink
          :to="{ name: 'cliente-reportes', params: { id: clienteId } }"
          class="accion card"
        >
          <span class="accion__icono" aria-hidden="true">▥</span>
          <span class="accion__texto">
            <span class="accion__titulo">Reportes</span>
            <span class="accion__nota">Resumen de ventas, compras e IVA</span>
          </span>
        </RouterLink>

        <RouterLink
          :to="{ name: 'cliente', params: { id: clienteId } }"
          class="accion card"
        >
          <span class="accion__icono" aria-hidden="true">◎</span>
          <span class="accion__texto">
            <span class="accion__titulo">Mi información</span>
            <span class="accion__nota">Datos, responsable y estado</span>
          </span>
        </RouterLink>
      </div>

      <p v-else class="alert alert--error" role="alert">
        Tu usuario no está vinculado a una ficha de cliente. Contactá al estudio.
      </p>

      <div v-if="resumen?.responsable" class="responsable-cliente card">
        <div>
          <p class="responsable-cliente__rotulo">Mi responsable</p>
          <p class="responsable-cliente__nombre">
            {{ resumen.responsable.nombre ?? 'Sin asignar' }}
          </p>
          <p v-if="resumen.responsable.email" class="responsable-cliente__email">
            {{ resumen.responsable.email }}
          </p>
        </div>
        <a
          v-if="resumen.responsable.email"
          class="btn btn--sm"
          :href="`mailto:${resumen.responsable.email}`"
        >
          Escribir
        </a>
      </div>
    </section>

    <section v-if="esContador" class="acciones-cliente">
      <div class="acciones-cliente__cabecera">
        <div>
          <p class="eyebrow">Escritorio del contador</p>
          <h2 class="acciones-cliente__titulo">Accesos rápidos</h2>
        </div>
        <span class="acciones-cliente__nota">Tu cartera y tus pendientes</span>
      </div>

      <div class="acciones-cliente__grid">
        <RouterLink :to="{ name: 'clientes', query: { nuevo: '1' } }" class="accion card">
          <span class="accion__icono" aria-hidden="true">+</span>
          <span class="accion__texto">
            <span class="accion__titulo">Nuevo cliente</span>
            <span class="accion__nota">Alta con acceso automático</span>
          </span>
        </RouterLink>

        <RouterLink :to="{ name: 'clientes' }" class="accion card">
          <span class="accion__icono" aria-hidden="true">◫</span>
          <span class="accion__texto">
            <span class="accion__titulo">Mi cartera</span>
            <span class="accion__nota">Clientes asignados</span>
          </span>
        </RouterLink>

        <RouterLink :to="{ name: 'comprobantes-bandeja' }" class="accion card">
          <span class="accion__icono" aria-hidden="true">▤</span>
          <span class="accion__texto">
            <span class="accion__titulo">Bandeja</span>
            <span class="accion__nota">Comprobantes por contabilizar</span>
          </span>
        </RouterLink>

        <RouterLink :to="{ name: 'vencimientos-agenda' }" class="accion card">
          <span class="accion__icono" aria-hidden="true">◷</span>
          <span class="accion__texto">
            <span class="accion__titulo">Agenda</span>
            <span class="accion__nota">Vencimientos de toda la cartera</span>
          </span>
        </RouterLink>
      </div>
    </section>

    <section v-if="esAdmin" class="acciones-cliente">
      <div class="acciones-cliente__cabecera">
        <div>
          <p class="eyebrow">Escritorio del administrador</p>
          <h2 class="acciones-cliente__titulo">Accesos rápidos</h2>
        </div>
        <span class="acciones-cliente__nota">Usuarios, cartera y control del estudio</span>
      </div>

      <div class="acciones-cliente__grid">
        <RouterLink :to="{ name: 'clientes', query: { nuevo: '1' } }" class="accion card">
          <span class="accion__icono" aria-hidden="true">+</span>
          <span class="accion__texto">
            <span class="accion__titulo">Nuevo cliente</span>
            <span class="accion__nota">Alta con acceso automático</span>
          </span>
        </RouterLink>

        <RouterLink :to="{ name: 'usuarios' }" class="accion card">
          <span class="accion__icono" aria-hidden="true">◉</span>
          <span class="accion__texto">
            <span class="accion__titulo">Usuarios</span>
            <span class="accion__nota">Roles, claves y propiedad</span>
          </span>
        </RouterLink>

        <RouterLink :to="{ name: 'comprobantes-bandeja' }" class="accion card">
          <span class="accion__icono" aria-hidden="true">▤</span>
          <span class="accion__texto">
            <span class="accion__titulo">Bandeja</span>
            <span class="accion__nota">Comprobantes por contabilizar</span>
          </span>
        </RouterLink>

        <RouterLink :to="{ name: 'auditoria' }" class="accion card">
          <span class="accion__icono" aria-hidden="true">◈</span>
          <span class="accion__texto">
            <span class="accion__titulo">Auditoría</span>
            <span class="accion__nota">Trazabilidad de cambios sensibles</span>
          </span>
        </RouterLink>
      </div>
    </section>

    <div v-if="resumen" class="listas">
      <article class="card lista">
        <header class="lista__cabecera">
          <h2 class="lista__titulo">Próximos vencimientos</h2>
          <span class="lista__nota">30 días</span>
        </header>
        <ul v-if="resumen.proximos_vencimientos.length" class="lista__items">
          <li v-for="v in resumen.proximos_vencimientos" :key="v.id" class="item">
            <span class="item__fecha tabular">{{ fechaVisible(v.fecha) }}</span>
            <span class="item__texto">
              <strong>{{ v.obligacion }}</strong>
              <span>{{ v.cliente }}</span>
            </span>
            <span class="badge" :class="v.dias <= 7 ? 'badge--danger' : ''">{{ v.dias }} d</span>
          </li>
        </ul>
        <p v-else class="vacio">Sin vencimientos próximos.</p>
      </article>

      <article v-if="esContador" class="card lista">
        <header class="lista__cabecera">
          <h2 class="lista__titulo">Pendientes de contabilizar</h2>
          <RouterLink :to="{ name: 'comprobantes-bandeja' }" class="lista__nota">
            Ver bandeja
          </RouterLink>
        </header>
        <ul v-if="pendientes.length" class="lista__items">
          <li v-for="c in pendientes" :key="c.id" class="item">
            <span class="item__fecha tabular">{{ fechaVisible(c.fecha) }}</span>
            <span class="item__texto">
              <strong>{{ c.cliente_nombre ?? 'Cliente' }}</strong>
              <span>{{ c.tipo_etiqueta }} · {{ c.numero }}</span>
            </span>
            <span class="item__monto tabular">{{ formatearMonto(c.total) }}</span>
          </li>
        </ul>
        <p v-else class="vacio">Sin comprobantes pendientes.</p>
      </article>

      <article v-if="!esCliente && !esContador" class="card lista">
        <header class="lista__cabecera">
          <h2 class="lista__titulo">Últimos asientos</h2>
          <span class="lista__nota">confirmados</span>
        </header>
        <ul v-if="resumen.ultimos_asientos.length" class="lista__items">
          <li v-for="a in resumen.ultimos_asientos" :key="a.id" class="item">
            <span class="item__fecha tabular">{{ fechaVisible(a.fecha) }}</span>
            <span class="item__texto">
              <strong>{{ a.concepto }}</strong>
              <span>{{ a.cliente }}</span>
            </span>
            <span class="item__monto tabular">{{ formatearMonto(a.total) }}</span>
          </li>
        </ul>
        <p v-else class="vacio">Todavía no hay asientos confirmados.</p>
      </article>
    </div>

    <p v-if="esCliente" class="nota-pie">
      Subí tus comprobantes de compra y el estudio se encarga de contabilizarlos.
      Ante cualquier duda, escribile a tu responsable.
    </p>
    <p v-else-if="esContador" class="nota-pie">
      Revisá la bandeja de comprobantes y la agenda de vencimientos para empezar
      el día.
    </p>
    <p v-else class="nota-pie">
      Administrá usuarios y clientes, revisá la bandeja y seguí los cambios en la auditoría.
    </p>
  </section>
</template>

<style scoped>
.panel {
  display: grid;
  gap: clamp(1.5rem, 3vw, 2.25rem);
}

.panel__head {
  display: grid;
  gap: var(--space-2);
}

.panel__titulo {
  font-size: var(--text-2xl);
}

.panel__sub {
  font-size: var(--text-sm);
  color: var(--color-text-muted);
}

.panel__sub strong {
  font-weight: 500;
  color: var(--color-text);
}

.tarjetas {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(13rem, 1fr));
  gap: var(--space-4);
}

.tarjeta {
  display: grid;
  gap: var(--space-2);
  padding: var(--space-5);
}

.tarjeta__rotulo {
  font-size: var(--text-xs);
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--color-text-faint);
}

.tarjeta__valor {
  font-family: var(--font-display);
  font-size: var(--text-2xl);
  line-height: 1;
  color: var(--color-text-muted);
}

.tarjeta.is-alerta .tarjeta__valor {
  color: var(--color-danger);
}

.tarjeta__nota {
  font-size: var(--text-xs);
  color: var(--color-text-faint);
}

.nota-pie {
  font-size: var(--text-xs);
  color: var(--color-text-faint);
}

.listas {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(20rem, 1fr));
  gap: var(--space-4);
}

.lista {
  display: grid;
  gap: var(--space-3);
  padding: clamp(1.25rem, 3vw, 1.5rem);
}

.lista__cabecera {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--space-3);
}

.lista__titulo {
  font-size: var(--text-base);
}

.lista__nota {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--color-text-faint);
}

.lista__items {
  display: grid;
  gap: var(--space-1);
  padding: 0;
  margin: 0;
  list-style: none;
}

.item {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-2) 0;
  border-bottom: 1px solid var(--color-line);
  font-size: var(--text-sm);
}

.item:last-child {
  border-bottom: 0;
}

.item__fecha {
  width: 4.5rem;
  flex: none;
  font-size: var(--text-xs);
  color: var(--color-text-faint);
}

.item__texto {
  flex: 1;
  min-width: 0;
  display: grid;
  gap: 0.05rem;
}

.item__texto strong {
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.item__texto span {
  font-size: var(--text-xs);
  color: var(--color-text-faint);
}

.item__monto {
  font-size: var(--text-xs);
  white-space: nowrap;
}

.vacio {
  font-size: var(--text-xs);
  color: var(--color-text-faint);
}

/* ------------------------------------------------------- Portal del cliente */
.acciones-cliente {
  display: grid;
  gap: var(--space-4);
}

.acciones-cliente__cabecera {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: var(--space-3);
  flex-wrap: wrap;
}

.acciones-cliente__titulo {
  font-size: var(--text-lg);
}

.acciones-cliente__nota {
  font-size: var(--text-xs);
  color: var(--color-text-faint);
}

.acciones-cliente__grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(13rem, 1fr));
  gap: var(--space-3);
}

.accion {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-4);
  color: inherit;
  text-decoration: none;
  transition:
    border-color var(--dur-fast) var(--ease-out),
    background-color var(--dur-fast) var(--ease-out),
    transform var(--dur-fast) var(--ease-out);
}

.accion:hover {
  border-color: var(--color-line-strong);
  background: rgb(255 255 255 / 3%);
  transform: translateY(-1px);
}

.accion__icono {
  display: grid;
  place-items: center;
  width: 2.25rem;
  height: 2.25rem;
  flex: none;
  border: 1px solid var(--color-line-strong);
  border-radius: var(--radius-sm);
  color: var(--color-accent);
  font-family: var(--font-mono);
  font-size: var(--text-sm);
}

.accion__texto {
  display: grid;
  gap: 0.1rem;
}

.accion__titulo {
  font-size: var(--text-sm);
  font-weight: 500;
}

.accion__nota {
  font-size: var(--text-xs);
  color: var(--color-text-faint);
}

.responsable-cliente {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  padding: var(--space-4) var(--space-5);
  flex-wrap: wrap;
}

.responsable-cliente__rotulo {
  font-size: var(--text-xs);
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--color-text-faint);
}

.responsable-cliente__nombre {
  font-size: var(--text-base);
  font-weight: 500;
}

.responsable-cliente__email {
  font-size: var(--text-xs);
  color: var(--color-text-muted);
}
</style>
