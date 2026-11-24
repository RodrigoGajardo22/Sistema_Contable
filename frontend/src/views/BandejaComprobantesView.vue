<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'

import { ApiError } from '@/api/client'
import { clientesApi } from '@/api/clientes'
import {
  comprobantesApi,
  type Comprobante,
  type EstadoComprobante,
  type TipoComprobante,
} from '@/api/comprobantes'
import type { Cliente } from '@/api/tipos'
import EmptyState from '@/components/ui/EmptyState.vue'
import Modal from '@/components/ui/Modal.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import TableCard from '@/components/ui/TableCard.vue'

const comprobantes = ref<Comprobante[]>([])
const clientes = ref<Cliente[]>([])
const total = ref(0)
const cargando = ref(true)
const error = ref('')
const aviso = ref<{ tipo: 'ok' | 'error'; texto: string } | null>(null)

const filtros = reactive({
  cliente_id: '' as number | '',
  tipo: '' as TipoComprobante | '',
  estado: 'pendiente' as EstadoComprobante | '',
  desde: '',
  hasta: '',
  q: '',
})

const comprobanteAccion = ref<Comprobante | null>(null)
const procesando = ref(false)

let temporizadorBusqueda: number | undefined
let temporizadorAviso: number | undefined

const formatoMoneda = new Intl.NumberFormat('es-AR', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})

const fecha = new Intl.DateTimeFormat('es-AR', { dateStyle: 'medium' })

function fechaVisible(iso: string): string {
  const [anio, mes, dia] = iso.split('-')
  return fecha.format(new Date(Number(anio), Number(mes) - 1, Number(dia)))
}

function monto(valor: string | number | null | undefined): string {
  return formatoMoneda.format(Number(valor ?? 0))
}

function claseEstado(estado: EstadoComprobante): string {
  if (estado === 'pendiente') return 'badge--muted'
  if (estado === 'anulado') return 'badge--danger'
  return 'badge--ok'
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
    const respuesta = await comprobantesApi.listarGlobal(filtros)
    comprobantes.value = respuesta.datos
    total.value = respuesta.total
  } catch (e) {
    error.value =
      e instanceof ApiError ? e.mensaje : 'No pudimos cargar la bandeja.'
  } finally {
    cargando.value = false
  }
}

onMounted(async () => {
  await Promise.all([cargarClientes(), cargar()])
})

watch(
  [() => filtros.cliente_id, () => filtros.tipo, () => filtros.estado, () => filtros.desde, () => filtros.hasta],
  () => cargar(),
)

watch(
  () => filtros.q,
  () => {
    window.clearTimeout(temporizadorBusqueda)
    temporizadorBusqueda = window.setTimeout(cargar, 300)
  },
)

onBeforeUnmount(() => {
  window.clearTimeout(temporizadorBusqueda)
  window.clearTimeout(temporizadorAviso)
})

function avisar(tipo: 'ok' | 'error', texto: string) {
  aviso.value = { tipo, texto }
  window.clearTimeout(temporizadorAviso)
  temporizadorAviso = window.setTimeout(() => (aviso.value = null), 4500)
}

function limpiar() {
  filtros.cliente_id = ''
  filtros.tipo = ''
  filtros.estado = 'pendiente'
  filtros.desde = ''
  filtros.hasta = ''
  filtros.q = ''
  void cargar()
}

function abrirContabilizar(comprobante: Comprobante) {
  comprobanteAccion.value = comprobante
}

async function contabilizar() {
  if (!comprobanteAccion.value || procesando.value) return

  procesando.value = true
  try {
    await comprobantesApi.contabilizar(comprobanteAccion.value.id)
    comprobanteAccion.value = null
    avisar('ok', 'Comprobante contabilizado.')
    await cargar()
  } catch (e) {
    comprobanteAccion.value = null
    avisar(
      'error',
      e instanceof ApiError ? e.mensaje : 'No pudimos contabilizar el comprobante.',
    )
  } finally {
    procesando.value = false
  }
}

const tituloAccion = computed(() =>
  comprobanteAccion.value
    ? `Contabilizar ${comprobanteAccion.value.numero}`
    : 'Contabilizar comprobante',
)
</script>

<template>
  <section class="bandeja">
    <PageHeader
      eyebrow="Contabilidad"
      title="Bandeja de comprobantes"
      subtitle="Comprobantes pendientes de todos tus clientes, en un solo lugar."
    >
      <template #actions>
        <button class="btn" type="button" @click="cargar">Actualizar</button>
      </template>
    </PageHeader>

    <div class="toolbar">
      <div class="toolbar__busqueda">
        <input
          v-model="filtros.q"
          class="input"
          type="search"
          placeholder="Buscar por número o tercero"
          aria-label="Buscar comprobantes"
        />
      </div>

      <select v-model="filtros.cliente_id" class="input select" aria-label="Cliente">
        <option value="">Todos los clientes</option>
        <option v-for="cliente in clientes" :key="cliente.id" :value="cliente.id">
          {{ cliente.razon_social }}
        </option>
      </select>

      <select v-model="filtros.tipo" class="input select" aria-label="Tipo">
        <option value="">Todos los tipos</option>
        <option value="compra">Compras</option>
        <option value="venta">Ventas</option>
      </select>

      <select v-model="filtros.estado" class="input select" aria-label="Estado">
        <option value="">Todos los estados</option>
        <option value="pendiente">Pendientes</option>
        <option value="contabilizado">Contabilizados</option>
        <option value="anulado">Anulados</option>
      </select>

      <input v-model="filtros.desde" class="input" type="date" aria-label="Desde" />
      <input v-model="filtros.hasta" class="input" type="date" aria-label="Hasta" />

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
      <EmptyState v-if="cargando" loading>Cargando comprobantes…</EmptyState>
      <EmptyState v-else-if="comprobantes.length === 0">
        <p>No hay comprobantes para los filtros elegidos.</p>
      </EmptyState>

      <div v-else class="tabla-scroll">
        <table class="table">
          <thead>
            <tr>
              <th scope="col">Cliente</th>
              <th scope="col">Tipo</th>
              <th scope="col">Número</th>
              <th scope="col">Fecha</th>
              <th scope="col">Tercero</th>
              <th scope="col" class="num">Total</th>
              <th scope="col">Estado</th>
              <th scope="col"><span class="sr-only">Acciones</span></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="c in comprobantes" :key="c.id">
              <td>
                <RouterLink
                  :to="{ name: 'cliente', params: { id: c.cliente_id } }"
                  class="cliente-link"
                >
                  {{ c.cliente_nombre ?? 'Cliente' }}
                </RouterLink>
              </td>
              <td>
                <span class="badge" :class="c.tipo === 'venta' ? 'badge--strong' : ''">
                  {{ c.tipo_etiqueta }}
                </span>
              </td>
              <td class="tabular">{{ c.numero }}</td>
              <td class="tabular">{{ fechaVisible(c.fecha) }}</td>
              <td>{{ c.tercero }}</td>
              <td class="num tabular">{{ monto(c.total) }}</td>
              <td>
                <span class="badge" :class="claseEstado(c.estado)">
                  {{ c.estado_etiqueta }}
                </span>
              </td>
              <td>
                <div class="acciones">
                  <button
                    v-if="c.estado === 'pendiente'"
                    class="btn btn--primary btn--sm"
                    type="button"
                    @click="abrirContabilizar(c)"
                  >
                    Contabilizar
                  </button>
                  <RouterLink
                    :to="{ name: 'cliente-comprobantes', params: { id: c.cliente_id } }"
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

    <p class="bandeja__pie">
      {{ total }} {{ total === 1 ? 'comprobante' : 'comprobantes' }} ·
      sólo clientes visibles para tu rol
    </p>

    <Modal
      :abierto="comprobanteAccion !== null"
      :titulo="tituloAccion"
      @cerrar="comprobanteAccion = null"
    >
      <p class="texto">
        ¿Confirmás la contabilización del comprobante
        <strong>{{ comprobanteAccion?.numero }}</strong> de
        <strong>{{ comprobanteAccion?.cliente_nombre ?? 'el cliente' }}</strong>?
      </p>
      <p class="texto texto--suave">
        Se generará el asiento contable y el comprobante quedará contabilizado.
      </p>

      <template #pie>
        <button class="btn" type="button" @click="comprobanteAccion = null">
          Cancelar
        </button>
        <button
          class="btn btn--primary"
          type="button"
          :disabled="procesando"
          @click="contabilizar"
        >
          {{ procesando ? 'Contabilizando…' : 'Contabilizar' }}
        </button>
      </template>
    </Modal>
  </section>
</template>

<style scoped>
.bandeja {
  display: grid;
  gap: var(--space-5);
}

.toolbar {
  gap: var(--space-2);
}

.toolbar__busqueda {
  flex: 1 1 16rem;
}

.toolbar__busqueda .input {
  padding-left: var(--space-3);
}

.toolbar .select {
  flex: 0 1 12rem;
}

.toolbar .input[type='date'] {
  flex: 0 1 9rem;
}

.cliente-link {
  font-size: var(--text-sm);
  color: var(--color-text);
  text-decoration: none;
}

.cliente-link:hover {
  color: var(--color-accent);
}

.num {
  text-align: right;
  white-space: nowrap;
}

.bandeja__pie {
  font-size: var(--text-xs);
  color: var(--color-text-faint);
}

.texto {
  font-size: var(--text-sm);
}

.texto--suave {
  margin-top: var(--space-2);
  color: var(--color-text-muted);
}
</style>
