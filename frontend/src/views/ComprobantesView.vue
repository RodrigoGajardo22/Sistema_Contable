<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

import { ApiError } from '@/api/client'
import { clientesApi } from '@/api/clientes'
import {
  ALICUOTAS,
  comprobantesApi,
  type Comprobante,
  type EstadoComprobante,
  type TipoComprobante,
} from '@/api/comprobantes'
import { formatearCuit, type Cliente } from '@/api/tipos'
import EmptyState from '@/components/ui/EmptyState.vue'
import Modal from '@/components/ui/Modal.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import TableCard from '@/components/ui/TableCard.vue'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const clienteId = computed(() => Number(route.params.id))

const auth = useAuthStore()
const puedeEditar = computed(() => auth.puede('admin', 'contador'))
const esCliente = computed(() => auth.rol === 'cliente')
const puedeSubir = computed(() => auth.puede('admin', 'contador', 'cliente'))

const cliente = ref<Cliente | null>(null)
const comprobantes = ref<Comprobante[]>([])
const total = ref(0)
const cargando = ref(true)
const error = ref('')
const aviso = ref<{ tipo: 'ok' | 'error'; texto: string } | null>(null)

const filtros = reactive({
  tipo: '' as TipoComprobante | '',
  estado: '' as EstadoComprobante | '',
  desde: '',
  hasta: '',
  q: '',
})

function hoyISO(): string {
  const ahora = new Date()
  const desfase = ahora.getTimezoneOffset() * 60000
  return new Date(ahora.getTime() - desfase).toISOString().slice(0, 10)
}

const formatoMoneda = new Intl.NumberFormat('es-AR', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})

function formatearMonto(valor: string | number | null | undefined): string {
  return formatoMoneda.format(Number(valor ?? 0))
}

function aCentavos(valor: string): number {
  const limpio = valor.replace(',', '.').trim()
  if (!/^\d*(\.\d{0,2})?$/.test(limpio) || limpio === '') return 0
  return Math.round(Number(limpio) * 100)
}

const fechaCorta = new Intl.DateTimeFormat('es-AR', { dateStyle: 'medium' })

function fechaVisible(iso: string): string {
  const [anio, mes, dia] = iso.split('-')
  return fechaCorta.format(new Date(Number(anio), Number(mes) - 1, Number(dia)))
}

/* ------------------------------------------------------------------ Carga */
async function cargar() {
  cargando.value = true
  error.value = ''

  try {
    const [datosCliente, listado] = await Promise.all([
      clientesApi.obtener(clienteId.value),
      comprobantesApi.listar(clienteId.value, {
        tipo: filtros.tipo,
        estado: filtros.estado,
        desde: filtros.desde,
        hasta: filtros.hasta,
        q: filtros.q,
      }),
    ])
    cliente.value = datosCliente
    comprobantes.value = listado.datos
    total.value = listado.total
  } catch (e) {
    error.value =
      e instanceof ApiError ? e.mensaje : 'No pudimos cargar los comprobantes.'
  } finally {
    cargando.value = false
  }
}

onMounted(async () => {
  await cargar()
  if (route.query.nuevo === '1' && cliente.value) abrirAlta()
})

watch([() => filtros.tipo, () => filtros.estado, () => filtros.desde, () => filtros.hasta], () => cargar())

let temporizador: number | undefined
watch(
  () => filtros.q,
  () => {
    window.clearTimeout(temporizador)
    temporizador = window.setTimeout(cargar, 300)
  },
)

function avisar(tipo: 'ok' | 'error', texto: string) {
  aviso.value = { tipo, texto }
  window.setTimeout(() => (aviso.value = null), 4500)
}

/* -------------------------------------------------------------- Formulario */
const formAbierto = ref(false)
const editando = ref<Comprobante | null>(null)
const form = reactive({
  tipo: 'venta' as TipoComprobante,
  numero: '',
  fecha: hoyISO(),
  tercero: '',
  neto: '',
  alicuota_iva: '21.00',
})
const formError = ref('')
const guardando = ref(false)

const netoCentavos = computed(() => aCentavos(form.neto))
const ivaCentavos = computed(() =>
  Math.round((netoCentavos.value * Number(form.alicuota_iva)) / 100),
)
const totalCentavos = computed(() => netoCentavos.value + ivaCentavos.value)

function abrirAlta() {
  editando.value = null
  form.tipo = esCliente.value ? 'compra' : 'venta'
  form.numero = ''
  form.fecha = hoyISO()
  form.tercero = ''
  form.neto = ''
  form.alicuota_iva = '21.00'
  formError.value = ''
  formAbierto.value = true
}

function abrirEdicion(comprobante: Comprobante) {
  editando.value = comprobante
  form.tipo = comprobante.tipo
  form.numero = comprobante.numero
  form.fecha = comprobante.fecha
  form.tercero = comprobante.tercero
  form.neto = comprobante.neto
  form.alicuota_iva = comprobante.alicuota_iva
  formError.value = ''
  formAbierto.value = true
}

function validar(): boolean {
  formError.value = ''

  if (!form.numero.trim()) formError.value = 'Ingresá el número del comprobante.'
  else if (form.tercero.trim().length < 2) formError.value = 'Ingresá el proveedor o cliente.'
  else if (netoCentavos.value <= 0) formError.value = 'El neto tiene que ser mayor a cero.'
  else if (form.fecha > hoyISO()) formError.value = 'La fecha no puede ser futura.'

  return formError.value === ''
}

async function guardar() {
  if (guardando.value || !validar()) return

  guardando.value = true

  const datos = {
    tipo: form.tipo,
    numero: form.numero.trim(),
    fecha: form.fecha,
    tercero: form.tercero.trim(),
    neto: (netoCentavos.value / 100).toFixed(2),
    alicuota_iva: form.alicuota_iva,
  }

  try {
    if (editando.value) {
      await comprobantesApi.actualizar(editando.value.id, datos)
      avisar('ok', 'Comprobante actualizado.')
    } else {
      await comprobantesApi.crear(clienteId.value, datos)
      avisar('ok', 'Comprobante registrado como pendiente.')
    }
    formAbierto.value = false
    await cargar()
  } catch (e) {
    formError.value =
      e instanceof ApiError ? e.mensaje : 'No pudimos guardar el comprobante.'
  } finally {
    guardando.value = false
  }
}

/* ---------------------------------------------------------- Contabilizar */
const contabilizarAbierto = ref(false)
const comprobanteAccion = ref<Comprobante | null>(null)
const procesando = ref(false)

function abrirContabilizar(comprobante: Comprobante) {
  comprobanteAccion.value = comprobante
  contabilizarAbierto.value = true
}

async function confirmarContabilizacion() {
  if (!comprobanteAccion.value || procesando.value) return

  procesando.value = true
  try {
    const actualizado = await comprobantesApi.contabilizar(comprobanteAccion.value.id)
    contabilizarAbierto.value = false
    avisar('ok', `Contabilizado: asiento Nº ${actualizado.asiento_numero}.`)
    await cargar()
  } catch (e) {
    contabilizarAbierto.value = false
    avisar(
      'error',
      e instanceof ApiError ? e.mensaje : 'No pudimos contabilizar el comprobante.',
    )
  } finally {
    procesando.value = false
  }
}

/* ----------------------------------------------------------------- Anular */
const anularAbierto = ref(false)

function abrirAnulacion(comprobante: Comprobante) {
  comprobanteAccion.value = comprobante
  anularAbierto.value = true
}

async function confirmarAnulacion() {
  if (!comprobanteAccion.value || procesando.value) return

  procesando.value = true
  try {
    await comprobantesApi.anular(comprobanteAccion.value.id)
    anularAbierto.value = false
    avisar('ok', 'Comprobante anulado (y su asiento, si existía).')
    await cargar()
  } catch (e) {
    anularAbierto.value = false
    avisar('error', e instanceof ApiError ? e.mensaje : 'No pudimos anular el comprobante.')
  } finally {
    procesando.value = false
  }
}

function claseEstado(estado: EstadoComprobante): string {
  if (estado === 'contabilizado') return 'badge--ok'
  if (estado === 'anulado') return 'badge--muted'
  return ''
}

/* ------------------------------------------------------------------ Detalle */
const detalleAbierto = ref(false)
const detalle = ref<Comprobante | null>(null)

function abrirDetalle(comprobante: Comprobante) {
  detalle.value = comprobante
  detalleAbierto.value = true
}
</script>

<template>
  <section class="comprobantes">
    <RouterLink :to="{ name: 'cliente', params: { id: clienteId } }" class="volver">
      <svg viewBox="0 0 16 16" width="14" height="14" fill="none" aria-hidden="true">
        <path d="M13 8H4M7.4 4.4 3.8 8l3.6 3.6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" />
      </svg>
      {{ esCliente ? 'Mi información' : 'Ficha del cliente' }}
    </RouterLink>

    <PageHeader
      :eyebrow="esCliente ? 'Mi portal' : 'Contabilidad'"
      :title="esCliente ? 'Mis comprobantes' : 'Comprobantes'"
      :show-sub="!!cliente"
    >
      <template #sub>
        {{ cliente?.razon_social }} ·
        <span class="tabular">{{ formatearCuit(cliente?.cuit ?? '') }}</span>
      </template>

      <template #actions>
        <button v-if="puedeSubir" class="btn btn--primary" type="button" :disabled="!cliente" @click="abrirAlta">
          <svg viewBox="0 0 16 16" width="14" height="14" fill="none" aria-hidden="true">
            <path d="M8 3v10M3 8h10" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" />
          </svg>
          {{ esCliente ? 'Subir comprobante' : 'Nuevo comprobante' }}
        </button>
      </template>
    </PageHeader>

    <div class="toolbar">
      <select v-model="filtros.tipo" class="input select" aria-label="Filtrar por tipo">
        <option value="">Compra y venta</option>
        <option value="venta">Ventas</option>
        <option value="compra">Compras</option>
      </select>

      <select v-model="filtros.estado" class="input select" aria-label="Filtrar por estado">
        <option value="">Todos los estados</option>
        <option value="pendiente">Pendientes</option>
        <option value="contabilizado">Contabilizados</option>
        <option value="anulado">Anulados</option>
      </select>

      <input v-model="filtros.desde" class="input" type="date" aria-label="Desde" />
      <input v-model="filtros.hasta" class="input" type="date" aria-label="Hasta" />

      <div class="toolbar__busqueda">
        <svg viewBox="0 0 16 16" width="14" height="14" fill="none" aria-hidden="true">
          <circle cx="7" cy="7" r="4.5" stroke="currentColor" stroke-width="1.5" />
          <path d="m10.4 10.4 3 3" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
        </svg>
        <input
          v-model="filtros.q"
          class="input"
          type="search"
          placeholder="Buscar por proveedor o cliente"
          aria-label="Buscar comprobantes"
        />
      </div>
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
        <button class="btn btn--sm" type="button" @click="abrirAlta">
          Cargar el primero
        </button>
      </EmptyState>

      <div v-else class="tabla-scroll">
        <table class="table">
          <thead>
            <tr>
              <th scope="col">Tipo</th>
              <th scope="col">Número</th>
              <th scope="col" class="col-fecha">Fecha</th>
              <th scope="col">Tercero</th>
              <th scope="col" class="col-monto col-opcional">Neto</th>
              <th scope="col" class="col-monto col-opcional">IVA</th>
              <th scope="col" class="col-monto">Total</th>
              <th scope="col">Estado</th>
              <th scope="col"><span class="sr-only">Acciones</span></th>
            </tr>
          </thead>

          <tbody>
            <tr
              v-for="comprobante in comprobantes"
              :key="comprobante.id"
              :class="{ 'is-anulado': comprobante.estado === 'anulado' }"
            >
              <td>
                <span class="badge" :class="comprobante.tipo === 'venta' ? 'badge--strong' : ''">
                  {{ comprobante.tipo_etiqueta }}
                </span>
              </td>
              <td class="tabular">{{ comprobante.numero }}</td>
              <td class="tabular col-fecha">{{ fechaVisible(comprobante.fecha) }}</td>
              <td class="tercero">{{ comprobante.tercero }}</td>
              <td class="tabular col-monto col-opcional">{{ formatearMonto(comprobante.neto) }}</td>
              <td class="tabular col-monto col-opcional">{{ formatearMonto(comprobante.iva) }}</td>
              <td class="tabular col-monto">{{ formatearMonto(comprobante.total) }}</td>
              <td>
                <span class="badge" :class="claseEstado(comprobante.estado)">
                  {{ comprobante.estado_etiqueta }}
                </span>
                <span v-if="comprobante.asiento_numero" class="asiento-ref tabular">
                  Asiento {{ comprobante.asiento_numero }}
                </span>
              </td>
              <td>
                <div class="acciones">
                  <button
                    class="icon-btn"
                    type="button"
                    title="Ver detalle"
                    :aria-label="`Ver ${comprobante.numero}`"
                    @click="abrirDetalle(comprobante)"
                  >
                    <svg viewBox="0 0 16 16" width="15" height="15" fill="none" aria-hidden="true">
                      <circle cx="8" cy="8" r="5.5" stroke="currentColor" stroke-width="1.4" />
                      <path d="M8 5.2v3.3l2 1.2" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round" />
                    </svg>
                  </button>
                  <template v-if="puedeEditar">
                  <button
                    v-if="comprobante.estado === 'pendiente'"
                    class="icon-btn"
                    type="button"
                    title="Editar"
                    :aria-label="`Editar ${comprobante.numero}`"
                    @click="abrirEdicion(comprobante)"
                  >
                    <svg viewBox="0 0 16 16" width="15" height="15" fill="none" aria-hidden="true">
                      <path d="M11.2 2.6a1.6 1.6 0 0 1 2.2 2.2L5.8 12.4l-3 .8.8-3 7.6-7.6Z" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round" />
                    </svg>
                  </button>

                  <button
                    v-if="comprobante.estado === 'pendiente'"
                    class="icon-btn"
                    type="button"
                    title="Contabilizar"
                    :aria-label="`Contabilizar ${comprobante.numero}`"
                    @click="abrirContabilizar(comprobante)"
                  >
                    <svg viewBox="0 0 16 16" width="15" height="15" fill="none" aria-hidden="true">
                      <path d="M3.2 8.4 6.3 11.5 12.8 5" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" />
                    </svg>
                  </button>

                  <button
                    v-if="comprobante.estado !== 'anulado'"
                    class="icon-btn icon-btn--peligro"
                    type="button"
                    title="Anular"
                    :aria-label="`Anular ${comprobante.numero}`"
                    @click="abrirAnulacion(comprobante)"
                  >
                    <svg viewBox="0 0 16 16" width="15" height="15" fill="none" aria-hidden="true">
                      <circle cx="8" cy="8" r="5.5" stroke="currentColor" stroke-width="1.4" />
                      <path d="M4.4 4.4l7.2 7.2" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" />
                    </svg>
                  </button>
                  </template>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </TableCard>

    <p class="pie">
      {{ total }} {{ total === 1 ? 'comprobante' : 'comprobantes' }} ·
      contabilizar genera el asiento de partida doble automáticamente
    </p>

    <!-- ------------------------------------------------------- Alta / edición -->
    <Modal
      :abierto="formAbierto"
      :titulo="editando ? 'Editar comprobante' : 'Nuevo comprobante'"
      @cerrar="formAbierto = false"
    >
      <form id="form-comprobante" class="formulario" novalidate @submit.prevent="guardar">
        <div class="fila">
          <div v-if="!esCliente" class="field">
            <label class="field__label" for="comprobante-tipo">Tipo</label>
            <select id="comprobante-tipo" v-model="form.tipo" class="input select">
              <option value="venta">Venta</option>
              <option value="compra">Compra</option>
            </select>
          </div>

          <div class="field">
            <label class="field__label" for="comprobante-numero">Número</label>
            <input
              id="comprobante-numero"
              v-model="form.numero"
              class="input"
              type="text"
              placeholder="A-0001-00000001"
            />
          </div>
        </div>

        <div class="fila">
          <div class="field">
            <label class="field__label" for="comprobante-fecha">Fecha</label>
            <input id="comprobante-fecha" v-model="form.fecha" class="input" type="date" :max="hoyISO()" />
          </div>

          <div class="field">
            <label class="field__label" for="comprobante-tercero">
              {{ form.tipo === 'venta' ? 'Cliente' : 'Proveedor' }}
            </label>
            <input
              id="comprobante-tercero"
              v-model="form.tercero"
              class="input"
              type="text"
              placeholder="Razón social"
            />
          </div>
        </div>

        <div class="fila">
          <div class="field">
            <label class="field__label" for="comprobante-neto">Neto</label>
            <input
              id="comprobante-neto"
              v-model="form.neto"
              class="input tabular"
              type="text"
              inputmode="decimal"
              placeholder="0,00"
            />
          </div>

          <div class="field">
            <label class="field__label" for="comprobante-alicuota">Alícuota de IVA</label>
            <select id="comprobante-alicuota" v-model="form.alicuota_iva" class="input select">
              <option v-for="alicuota in ALICUOTAS" :key="alicuota.valor" :value="alicuota.valor">
                {{ alicuota.etiqueta }}
              </option>
            </select>
          </div>
        </div>

        <div class="resumen">
          <div>
            <span class="resumen__rotulo">IVA</span>
            <span class="resumen__valor tabular">{{ formatearMonto(ivaCentavos / 100) }}</span>
          </div>
          <div>
            <span class="resumen__rotulo">Total</span>
            <span class="resumen__valor resumen__valor--total tabular">
              {{ formatearMonto(totalCentavos / 100) }}
            </span>
          </div>
        </div>

        <p v-if="formError" class="alert alert--error" role="alert">{{ formError }}</p>
      </form>

      <template #pie>
        <button class="btn" type="button" @click="formAbierto = false">Cancelar</button>
        <button
          class="btn btn--primary"
          type="submit"
          form="form-comprobante"
          :disabled="guardando"
        >
          {{ guardando ? 'Guardando…' : editando ? 'Guardar cambios' : 'Registrar' }}
        </button>
      </template>
    </Modal>

    <!-- ----------------------------------------------------- Contabilizar -->
    <Modal
      :abierto="contabilizarAbierto"
      titulo="Contabilizar comprobante"
      @cerrar="contabilizarAbierto = false"
    >
      <p class="texto">
        Se va a generar un asiento confirmado por
        <strong class="tabular">{{ formatearMonto(comprobanteAccion?.total) }}</strong>
        y no se podrá editar después (solo anular).
      </p>
      <p class="texto texto--suave">
        Venta: Deudores / Ventas + IVA débito. Compra: Compras + IVA crédito /
        Proveedores.
      </p>

      <template #pie>
        <button class="btn" type="button" @click="contabilizarAbierto = false">Cancelar</button>
        <button
          class="btn btn--primary"
          type="button"
          :disabled="procesando"
          @click="confirmarContabilizacion"
        >
          {{ procesando ? 'Contabilizando…' : 'Contabilizar' }}
        </button>
      </template>
    </Modal>

    <!-- ---------------------------------------------------------- Detalle -->
    <Modal :abierto="detalleAbierto" titulo="Detalle del comprobante" @cerrar="detalleAbierto = false">
      <dl v-if="detalle" class="detalle-comp">
        <div><dt>Tipo</dt><dd>{{ detalle.tipo_etiqueta }}</dd></div>
        <div><dt>Número</dt><dd class="tabular">{{ detalle.numero }}</dd></div>
        <div><dt>Fecha</dt><dd>{{ fechaVisible(detalle.fecha) }}</dd></div>
        <div class="detalle-comp__ancho"><dt>Tercero</dt><dd>{{ detalle.tercero }}</dd></div>
        <div><dt>Neto</dt><dd class="tabular">{{ formatearMonto(detalle.neto) }}</dd></div>
        <div><dt>IVA ({{ Number(detalle.alicuota_iva) }} %)</dt><dd class="tabular">{{ formatearMonto(detalle.iva) }}</dd></div>
        <div><dt>Total</dt><dd class="tabular">{{ formatearMonto(detalle.total) }}</dd></div>
        <div><dt>Estado</dt><dd><span class="badge" :class="claseEstado(detalle.estado)">{{ detalle.estado_etiqueta }}</span></dd></div>
        <div><dt>Asiento</dt><dd class="tabular">{{ detalle.asiento_numero ? `Nº ${detalle.asiento_numero}` : '—' }}</dd></div>
        <div><dt>Creado por</dt><dd>{{ detalle.creado_por ?? '—' }}</dd></div>
      </dl>

      <template #pie>
        <button class="btn" type="button" @click="detalleAbierto = false">Cerrar</button>
      </template>
    </Modal>

    <!-- ---------------------------------------------------------- Anular -->
    <Modal :abierto="anularAbierto" titulo="Anular comprobante" @cerrar="anularAbierto = false">      <p class="texto">
        ¿Anular el comprobante <strong>{{ comprobanteAccion?.numero }}</strong>?
      </p>
      <p class="texto texto--suave">
        Si estaba contabilizado, su asiento también queda anulado. Nada se borra:
        el historial se conserva.
      </p>

      <template #pie>
        <button class="btn" type="button" @click="anularAbierto = false">Cancelar</button>
        <button
          class="btn btn--danger"
          type="button"
          :disabled="procesando"
          @click="confirmarAnulacion"
        >
          {{ procesando ? 'Anulando…' : 'Anular' }}
        </button>
      </template>
    </Modal>
  </section>
</template>

<style scoped>
.comprobantes {
  display: grid;
  gap: var(--space-5);
}

.toolbar__busqueda {
  flex: 1 1 16rem;
}

.toolbar .select {
  flex: 0 1 11rem;
}

tbody tr.is-anulado {
  opacity: 0.55;
}

.tercero {
  max-width: 16rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.col-monto {
  text-align: right;
  white-space: nowrap;
}

.asiento-ref {
  display: block;
  margin-top: 0.15rem;
  font-size: 0.625rem;
  color: var(--color-text-faint);
}

.pie {
  font-size: var(--text-xs);
  color: var(--color-text-faint);
}

.fila {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-4);
}

.resumen {
  display: flex;
  gap: var(--space-6);
  padding: var(--space-3) var(--space-4);
  border: 1px solid var(--color-line);
  border-radius: var(--radius-sm);
  background: rgb(255 255 255 / 2%);
}

.resumen__rotulo {
  display: block;
  font-size: 0.625rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--color-text-faint);
}

.resumen__valor {
  font-size: var(--text-sm);
}

.resumen__valor--total {
  color: var(--color-accent);
}

.texto {
  font-size: var(--text-sm);
}

.detalle-comp {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-3) var(--space-4);
  margin: 0;
}

.detalle-comp > div {
  display: grid;
  gap: 0.1rem;
}

.detalle-comp__ancho {
  grid-column: 1 / -1;
}

.detalle-comp dt {
  font-size: 0.625rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--color-text-faint);
}

.detalle-comp dd {
  margin: 0;
  font-size: var(--text-sm);
}

.texto--suave {
  margin-top: var(--space-2);
  color: var(--color-text-muted);
}

@media (max-width: 56rem) {
  .col-opcional,
  .col-fecha {
    display: none;
  }

  .fila {
    grid-template-columns: 1fr;
  }
}
</style>
