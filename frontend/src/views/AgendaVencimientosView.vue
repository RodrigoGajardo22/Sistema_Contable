<script setup lang="ts">
import { onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'

import { ApiError } from '@/api/client'
import { clientesApi } from '@/api/clientes'
import EmptyState from '@/components/ui/EmptyState.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import TableCard from '@/components/ui/TableCard.vue'
import type { Cliente } from '@/api/tipos'
import {
  OBLIGACIONES,
  vencimientosApi,
  type EstadoVencimiento,
  type Obligacion,
  type Vencimiento,
} from '@/api/vencimientos'

const vencimientos = ref<Vencimiento[]>([])
const clientes = ref<Cliente[]>([])
const total = ref(0)
const cargando = ref(true)
const error = ref('')
const aviso = ref<{ tipo: 'ok' | 'error'; texto: string } | null>(null)

const filtros = reactive({
  cliente_id: '' as number | '',
  estado: '' as EstadoVencimiento | '',
  proximidad: '' as '' | 'proximos' | 'vencidos',
  obligacion: '' as Obligacion | '',
})

let temporizadorAviso: number | undefined

const fecha = new Intl.DateTimeFormat('es-AR', { dateStyle: 'medium' })

function fechaVisible(iso: string): string {
  const [anio, mes, dia] = iso.split('-')
  return fecha.format(new Date(Number(anio), Number(mes) - 1, Number(dia)))
}

function dias(fechaISO: string): number {
  const hoy = new Date()
  hoy.setHours(0, 0, 0, 0)
  const objetivo = new Date(`${fechaISO}T00:00:00`)
  return Math.round((objetivo.getTime() - hoy.getTime()) / 86_400_000)
}

async function cargarClientes() {
  try {
    const respuesta = await clientesApi.listar({ activo: 'activos' })
    clientes.value = respuesta.datos
  } catch {
    clientes.value = []
  }
}

async function cargar() {
  cargando.value = true
  error.value = ''
  try {
    const respuesta = await vencimientosApi.listarGlobal(filtros)
    vencimientos.value = respuesta.datos
    total.value = respuesta.total
  } catch (e) {
    error.value =
      e instanceof ApiError ? e.mensaje : 'No pudimos cargar la agenda.'
  } finally {
    cargando.value = false
  }
}

onMounted(async () => {
  await Promise.all([cargarClientes(), cargar()])
})

watch(
  [() => filtros.cliente_id, () => filtros.estado, () => filtros.proximidad, () => filtros.obligacion],
  () => cargar(),
)

onBeforeUnmount(() => window.clearTimeout(temporizadorAviso))

function avisar(tipo: 'ok' | 'error', texto: string) {
  aviso.value = { tipo, texto }
  window.clearTimeout(temporizadorAviso)
  temporizadorAviso = window.setTimeout(() => (aviso.value = null), 4500)
}

function siguienteEstado(vencimiento: Vencimiento): EstadoVencimiento | null {
  if (vencimiento.estado === 'pendiente') return 'presentado'
  if (vencimiento.estado === 'presentado') return 'pagado'
  return null
}

async function avanzar(vencimiento: Vencimiento) {
  const siguiente = siguienteEstado(vencimiento)
  if (!siguiente) return

  try {
    await vencimientosApi.cambiarEstado(vencimiento.id, siguiente)
    avisar('ok', `Vencimiento pasado a ${siguiente}.`)
    await cargar()
  } catch (e) {
    avisar(
      'error',
      e instanceof ApiError ? e.mensaje : 'No pudimos cambiar el estado.',
    )
  }
}

function limpiar() {
  filtros.cliente_id = ''
  filtros.estado = ''
  filtros.proximidad = ''
  filtros.obligacion = ''
  void cargar()
}
</script>

<template>
  <section class="agenda">
    <PageHeader
      eyebrow="Agenda"
      title="Vencimientos de mi cartera"
      subtitle="Todas las obligaciones de tus clientes asignados, ordenadas por fecha."
    >
      <template #actions>
        <button class="btn" type="button" @click="cargar">Actualizar</button>
      </template>
    </PageHeader>

    <div class="toolbar">
      <select v-model="filtros.cliente_id" class="input select" aria-label="Cliente">
        <option value="">Todos los clientes</option>
        <option v-for="cliente in clientes" :key="cliente.id" :value="cliente.id">
          {{ cliente.razon_social }}
        </option>
      </select>

      <select v-model="filtros.proximidad" class="input select" aria-label="Proximidad">
        <option value="">Todos</option>
        <option value="proximos">Próximos</option>
        <option value="vencidos">Vencidos</option>
      </select>

      <select v-model="filtros.estado" class="input select" aria-label="Estado">
        <option value="">Todos los estados</option>
        <option value="pendiente">Pendientes</option>
        <option value="presentado">Presentados</option>
        <option value="pagado">Pagados</option>
      </select>

      <select v-model="filtros.obligacion" class="input select" aria-label="Obligación">
        <option value="">Todas las obligaciones</option>
        <option v-for="obligacion in OBLIGACIONES" :key="obligacion.valor" :value="obligacion.valor">
          {{ obligacion.etiqueta }}
        </option>
      </select>

      <button class="btn btn--sm" type="button" @click="limpiar">Limpiar</button>
    </div>

    <p v-if="aviso" class="alert" :class="`alert--${aviso.tipo}`" role="status">
      {{ aviso.texto }}
    </p>

    <div v-if="error" class="alert alert--error" role="alert">
      <span>{{ error }}</span>
      <button class="btn btn--sm" type="button" @click="cargar">Reintentar</button>
    </div>

    <TableCard>
      <EmptyState v-if="cargando" loading>Cargando agenda…</EmptyState>
      <EmptyState v-else-if="vencimientos.length === 0">
        <p>No hay vencimientos para los filtros elegidos.</p>
      </EmptyState>

      <div v-else class="tabla-scroll">
        <table class="table">
          <thead>
            <tr>
              <th scope="col">Cliente</th>
              <th scope="col">Obligación</th>
              <th scope="col">Período</th>
              <th scope="col">Vencimiento</th>
              <th scope="col">Días</th>
              <th scope="col">Estado</th>
              <th scope="col"><span class="sr-only">Acciones</span></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="v in vencimientos" :key="v.id">
              <td>
                <RouterLink
                  :to="{ name: 'cliente', params: { id: v.cliente_id } }"
                  class="cliente-link"
                >
                  {{ v.cliente_nombre ?? 'Cliente' }}
                </RouterLink>
              </td>
              <td>{{ v.obligacion_etiqueta }}</td>
              <td class="tabular">{{ v.periodo }}</td>
              <td class="tabular">{{ fechaVisible(v.fecha_vencimiento) }}</td>
              <td>
                <span
                  class="badge"
                  :class="{
                    'badge--danger': v.estado !== 'pagado' && dias(v.fecha_vencimiento) < 0,
                    'badge--ok': v.estado === 'pagado',
                  }"
                >
                  {{
                    v.estado === 'pagado'
                      ? 'Pagado'
                      : `${dias(v.fecha_vencimiento)} d`
                  }}
                </span>
              </td>
              <td>
                <span class="badge" :class="v.estado === 'pendiente' ? 'badge--muted' : 'badge--ok'">
                  {{ v.estado_etiqueta }}
                </span>
              </td>
              <td>
                <div class="acciones">
                  <button
                    v-if="siguienteEstado(v)"
                    class="btn btn--sm"
                    type="button"
                    @click="avanzar(v)"
                  >
                    {{ siguienteEstado(v) === 'presentado' ? 'Presentar' : 'Pagar' }}
                  </button>
                  <RouterLink
                    :to="{ name: 'cliente-vencimientos', params: { id: v.cliente_id } }"
                    class="btn btn--sm"
                  >
                    Abrir
                  </RouterLink>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </TableCard>

    <p class="agenda__pie">
      {{ total }} {{ total === 1 ? 'vencimiento' : 'vencimientos' }} ·
      ordenados por fecha
    </p>
  </section>
</template>

<style scoped>
.agenda {
  display: grid;
  gap: var(--space-5);
}

.toolbar {
  gap: var(--space-2);
}

.toolbar .select {
  flex: 0 1 12rem;
}

.cliente-link {
  font-size: var(--text-sm);
  color: var(--color-text);
  text-decoration: none;
}

.cliente-link:hover {
  color: var(--color-accent);
}

.agenda__pie {
  font-size: var(--text-xs);
  color: var(--color-text-faint);
}
</style>
