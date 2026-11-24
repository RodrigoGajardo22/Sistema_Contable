<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

import { ApiError } from '@/api/client'
import { clientesApi } from '@/api/clientes'
import { formatearCuit, type Cliente } from '@/api/tipos'
import {
  OBLIGACIONES,
  vencimientosApi,
  type EstadoVencimiento,
  type Vencimiento,
} from '@/api/vencimientos'
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

const cliente = ref<Cliente | null>(null)
const vencimientos = ref<Vencimiento[]>([])
const cargando = ref(true)
const error = ref('')
const filtroEstado = ref<EstadoVencimiento | ''>('')
const proximidad = ref<'' | 'proximos' | 'vencidos'>('')
const vista = ref<'lista' | 'calendario'>('lista')
const mes = ref(new Date().toISOString().slice(0, 7))
const aviso = ref<{ tipo: 'ok' | 'error'; texto: string } | null>(null)

const formAbierto = ref(false)
const editando = ref<Vencimiento | null>(null)
const form = reactive({
  obligacion: 'iva',
  periodo: '',
  fecha_vencimiento: '',
  observaciones: '',
})
const formError = ref('')
const guardando = ref(false)
const bajaAbierta = ref(false)
const aEliminar = ref<Vencimiento | null>(null)

const fecha = new Intl.DateTimeFormat('es-AR', { dateStyle: 'medium' })

function fechaVisible(iso: string): string {
  const [anio, mes, dia] = iso.split('-')
  return fecha.format(new Date(Number(anio), Number(mes) - 1, Number(dia)))
}

async function cargar() {
  cargando.value = true
  error.value = ''
  try {
    const [datosCliente, listado] = await Promise.all([
      clientesApi.obtener(clienteId.value),
      vencimientosApi.listar(clienteId.value, filtroEstado.value, proximidad.value),
    ])
    cliente.value = datosCliente
    vencimientos.value = listado.datos
  } catch (e) {
    error.value = e instanceof ApiError ? e.mensaje : 'No pudimos cargar los vencimientos.'
  } finally {
    cargando.value = false
  }
}

onMounted(cargar)
watch([filtroEstado, proximidad], () => cargar())

function partesMes(valor: string): [number, number] {
  const [anio, mes] = valor.split('-').map(Number)
  return [anio ?? new Date().getFullYear(), mes ?? 1]
}

const calendario = computed(() => {
  const [anio, mesNumero] = partesMes(mes.value)
  const primero = new Date(anio, mesNumero - 1, 1)
  const totalDias = new Date(anio, mesNumero, 0).getDate()
  const desplazamiento = (primero.getDay() + 6) % 7

  const celdas: { dia: number | null; fecha: string; eventos: Vencimiento[] }[] = []

  for (let i = 0; i < desplazamiento; i += 1) {
    celdas.push({ dia: null, fecha: '', eventos: [] })
  }

  for (let dia = 1; dia <= totalDias; dia += 1) {
    const fecha = `${anio}-${String(mesNumero).padStart(2, '0')}-${String(dia).padStart(2, '0')}`
    celdas.push({
      dia,
      fecha,
      eventos: vencimientos.value.filter((v) => v.fecha_vencimiento === fecha),
    })
  }

  while (celdas.length % 7 !== 0) {
    celdas.push({ dia: null, fecha: '', eventos: [] })
  }

  return celdas
})

const nombreMes = computed(() => {
  const [anio, mesNumero] = partesMes(mes.value)
  return new Intl.DateTimeFormat('es-AR', { month: 'long', year: 'numeric' }).format(
    new Date(anio, mesNumero - 1, 1),
  )
})

function moverMes(delta: number) {
  const [anio, mesNumero] = partesMes(mes.value)
  const nueva = new Date(anio, mesNumero - 1 + delta, 1)
  mes.value = `${nueva.getFullYear()}-${String(nueva.getMonth() + 1).padStart(2, '0')}`
}

function colorEvento(v: Vencimiento): string {
  if (v.estado === 'pagado') return 'is-pagado'
  if (v.vencido) return 'is-vencido'
  if (v.estado === 'presentado') return 'is-presentado'
  return ''
}

function avisar(tipo: 'ok' | 'error', texto: string) {
  aviso.value = { tipo, texto }
  window.setTimeout(() => (aviso.value = null), 4000)
}

function abrirAlta() {
  editando.value = null
  form.obligacion = 'iva'
  form.periodo = ''
  form.fecha_vencimiento = ''
  form.observaciones = ''
  formError.value = ''
  formAbierto.value = true
}

function abrirEdicion(v: Vencimiento) {
  editando.value = v
  form.obligacion = v.obligacion
  form.periodo = v.periodo
  form.fecha_vencimiento = v.fecha_vencimiento
  form.observaciones = v.observaciones ?? ''
  formError.value = ''
  formAbierto.value = true
}

async function guardar() {
  if (guardando.value) return
  if (!form.periodo.trim() || !form.fecha_vencimiento) {
    formError.value = 'Completá el período y la fecha de vencimiento.'
    return
  }

  guardando.value = true
  formError.value = ''

  const datos = {
    obligacion: form.obligacion as Vencimiento['obligacion'],
    periodo: form.periodo.trim(),
    fecha_vencimiento: form.fecha_vencimiento,
    observaciones: form.observaciones.trim() || null,
  }

  try {
    if (editando.value) {
      await vencimientosApi.actualizar(editando.value.id, datos)
      avisar('ok', 'Vencimiento actualizado.')
    } else {
      await vencimientosApi.crear(clienteId.value, datos)
      avisar('ok', 'Vencimiento registrado.')
    }
    formAbierto.value = false
    await cargar()
  } catch (e) {
    formError.value = e instanceof ApiError ? e.mensaje : 'No pudimos guardar.'
  } finally {
    guardando.value = false
  }
}

async function avanzar(v: Vencimiento) {
  const siguiente = v.estado === 'pendiente' ? 'presentado' : 'pagado'
  try {
    await vencimientosApi.cambiarEstado(v.id, siguiente)
    avisar('ok', `${v.obligacion_etiqueta}: ${siguiente}.`)
    await cargar()
  } catch (e) {
    avisar('error', e instanceof ApiError ? e.mensaje : 'No pudimos cambiar el estado.')
  }
}

function abrirBaja(v: Vencimiento) {
  aEliminar.value = v
  bajaAbierta.value = true
}

async function confirmarBaja() {
  if (!aEliminar.value) return
  try {
    await vencimientosApi.eliminar(aEliminar.value.id)
    bajaAbierta.value = false
    avisar('ok', 'Vencimiento eliminado.')
    await cargar()
  } catch (e) {
    bajaAbierta.value = false
    avisar('error', e instanceof ApiError ? e.mensaje : 'No pudimos eliminar.')
  }
}
</script>

<template>
  <section class="vencimientos">
    <RouterLink :to="{ name: 'cliente', params: { id: clienteId } }" class="volver">
      <svg viewBox="0 0 16 16" width="14" height="14" fill="none" aria-hidden="true">
        <path d="M13 8H4M7.4 4.4 3.8 8l3.6 3.6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" />
      </svg>
      {{ esCliente ? 'Mi información' : 'Ficha del cliente' }}
    </RouterLink>

    <PageHeader eyebrow="Obligaciones" title="Vencimientos" :show-sub="!!cliente">
      <template #sub>
        {{ cliente?.razon_social }} ·
        <span class="tabular">{{ formatearCuit(cliente?.cuit ?? '') }}</span>
      </template>

      <template #actions>
        <button v-if="puedeEditar" class="btn btn--primary" type="button" :disabled="!cliente" @click="abrirAlta">
          + Nuevo vencimiento
        </button>
      </template>
    </PageHeader>

    <div class="toolbar">
      <select v-model="filtroEstado" class="input select" aria-label="Filtrar por estado">
        <option value="">Todos los estados</option>
        <option value="pendiente">Pendientes</option>
        <option value="presentado">Presentados</option>
        <option value="pagado">Pagados</option>
      </select>
      <select v-model="proximidad" class="input select" aria-label="Filtrar por proximidad">
        <option value="">Cualquier fecha</option>
        <option value="proximos">Próximos 30 días</option>
        <option value="vencidos">Vencidos</option>
      </select>
      <div class="vistas" role="tablist" aria-label="Vista">
        <button class="vistas__boton" :class="{ 'is-activa': vista === 'lista' }" type="button" @click="vista = 'lista'">Lista</button>
        <button class="vistas__boton" :class="{ 'is-activa': vista === 'calendario' }" type="button" @click="vista = 'calendario'">Calendario</button>
      </div>
    </div>

    <p v-if="aviso" class="alert" :class="`alert--${aviso.tipo}`" role="status">{{ aviso.texto }}</p>
    <div v-if="error" class="alert alert--error" role="alert">
      <span>{{ error }}</span>
      <button class="btn btn--sm" type="button" @click="cargar">Reintentar</button>
    </div>

    <TableCard v-if="vista === 'lista'">
      <EmptyState v-if="cargando" loading compact>Cargando vencimientos…</EmptyState>
      <EmptyState v-else-if="vencimientos.length === 0" compact>
        <p>No hay vencimientos cargados.</p>
        <button v-if="puedeEditar" class="btn btn--sm" type="button" @click="abrirAlta">Cargar el primero</button>
      </EmptyState>
      <div v-else class="tabla-scroll">
        <table class="table">
          <thead>
            <tr>
              <th scope="col">Obligación</th>
              <th scope="col">Período</th>
              <th scope="col">Vence</th>
              <th scope="col">Estado</th>
              <th scope="col"><span class="sr-only">Acciones</span></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="v in vencimientos" :key="v.id" :class="{ 'is-vencido': v.vencido }">
              <td>
                {{ v.obligacion_etiqueta }}
                <span v-if="v.observaciones" class="obs">{{ v.observaciones }}</span>
              </td>
              <td class="tabular">{{ v.periodo }}</td>
              <td class="tabular">
                {{ fechaVisible(v.fecha_vencimiento) }}
                <span v-if="v.vencido" class="badge badge--danger">Vencido</span>
              </td>
              <td>
                <span class="badge" :class="v.estado === 'pagado' ? 'badge--ok' : v.estado === 'presentado' ? 'badge--strong' : ''">
                  {{ v.estado_etiqueta }}
                </span>
              </td>
              <td>
                <div v-if="puedeEditar" class="acciones">
                  <button
                    v-if="v.estado !== 'pagado'"
                    class="btn btn--sm"
                    type="button"
                    @click="avanzar(v)"
                  >
                    {{ v.estado === 'pendiente' ? 'Presentar' : 'Pagar' }}
                  </button>
                  <button
                    v-if="v.estado !== 'pagado'"
                    class="icon-btn"
                    type="button"
                    title="Editar"
                    :aria-label="`Editar ${v.obligacion_etiqueta}`"
                    @click="abrirEdicion(v)"
                  >
                    ✎
                  </button>
                  <button
                    class="icon-btn icon-btn--peligro"
                    type="button"
                    title="Eliminar"
                    :aria-label="`Eliminar ${v.obligacion_etiqueta}`"
                    @click="abrirBaja(v)"
                  >
                    ×
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </TableCard>

    <div v-else class="card calendario">
      <header class="calendario__head">
        <button class="icon-btn" type="button" aria-label="Mes anterior" @click="moverMes(-1)">‹</button>
        <span class="calendario__mes">{{ nombreMes }}</span>
        <button class="icon-btn" type="button" aria-label="Mes siguiente" @click="moverMes(1)">›</button>
      </header>

      <div class="calendario__grilla">
        <span v-for="dia in ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']" :key="dia" class="calendario__semana">
          {{ dia }}
        </span>

        <div
          v-for="(celda, indice) in calendario"
          :key="indice"
          class="calendario__celda"
          :class="{ 'is-vacia': !celda.dia }"
        >
          <span v-if="celda.dia" class="calendario__numero">{{ celda.dia }}</span>
          <span
            v-for="evento in celda.eventos"
            :key="evento.id"
            class="calendario__evento"
            :class="colorEvento(evento)"
            :title="`${evento.obligacion_etiqueta} · ${evento.estado_etiqueta}`"
          >
            {{ evento.obligacion_etiqueta }}
          </span>
        </div>
      </div>
    </div>

    <Modal :abierto="formAbierto" :titulo="editando ? 'Editar vencimiento' : 'Nuevo vencimiento'" @cerrar="formAbierto = false">
      <form id="form-vencimiento" class="formulario" novalidate @submit.prevent="guardar">
        <div class="fila">
          <div class="field">
            <label class="field__label" for="v-obligacion">Obligación</label>
            <select id="v-obligacion" v-model="form.obligacion" class="input select">
              <option v-for="o in OBLIGACIONES" :key="o.valor" :value="o.valor">{{ o.etiqueta }}</option>
            </select>
          </div>
          <div class="field">
            <label class="field__label" for="v-periodo">Período</label>
            <input id="v-periodo" v-model="form.periodo" class="input" type="text" placeholder="2026-11" />
          </div>
        </div>
        <div class="field">
          <label class="field__label" for="v-fecha">Fecha de vencimiento</label>
          <input id="v-fecha" v-model="form.fecha_vencimiento" class="input" type="date" />
        </div>
        <div class="field">
          <label class="field__label" for="v-obs">Observaciones</label>
          <input id="v-obs" v-model="form.observaciones" class="input" type="text" placeholder="Opcional" />
        </div>
        <p v-if="formError" class="alert alert--error" role="alert">{{ formError }}</p>
      </form>
      <template #pie>
        <button class="btn" type="button" @click="formAbierto = false">Cancelar</button>
        <button class="btn btn--primary" type="submit" form="form-vencimiento" :disabled="guardando">
          {{ guardando ? 'Guardando…' : 'Guardar' }}
        </button>
      </template>
    </Modal>

    <Modal :abierto="bajaAbierta" titulo="Eliminar vencimiento" @cerrar="bajaAbierta = false">
      <p class="texto">¿Eliminar el vencimiento de <strong>{{ aEliminar?.obligacion_etiqueta }}</strong> ({{ aEliminar?.periodo }})?</p>
      <template #pie>
        <button class="btn" type="button" @click="bajaAbierta = false">Cancelar</button>
        <button class="btn btn--danger" type="button" @click="confirmarBaja">Eliminar</button>
      </template>
    </Modal>
  </section>
</template>

<style scoped>
.vencimientos { display: grid; gap: var(--space-5); }
.toolbar { flex-wrap: nowrap; }
.toolbar .select { max-width: 14rem; }
.acciones { align-items: center; }
.obs { display: block; font-size: var(--text-xs); color: var(--color-text-faint); }
.is-vencido td:first-child { color: var(--color-danger); }
.fila { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-4); }
.texto { font-size: var(--text-sm); }
@media (max-width: 48rem) { .fila { grid-template-columns: 1fr; } }

.vistas { display: flex; border: 1px solid var(--color-line-strong); border-radius: var(--radius-sm); overflow: hidden; }
.vistas__boton { padding: 0 var(--space-3); min-height: 2.5rem; border: 0; background: transparent; color: var(--color-text-muted); font-size: var(--text-xs); cursor: pointer; }
.vistas__boton.is-activa { background: rgb(43 217 138 / 12%); color: var(--color-accent); }

.calendario { padding: var(--space-4); }
.calendario__head { display: flex; align-items: center; justify-content: center; gap: var(--space-4); margin-bottom: var(--space-4); }
.calendario__mes { font-family: var(--font-display); font-size: var(--text-lg); text-transform: capitalize; }
.calendario__grilla { display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); gap: 1px; background: var(--color-line); border: 1px solid var(--color-line); border-radius: var(--radius-sm); overflow: hidden; }
.calendario__semana { padding: var(--space-2); background: var(--color-surface); font-size: 0.625rem; letter-spacing: 0.1em; text-transform: uppercase; color: var(--color-text-faint); text-align: center; }
.calendario__celda { min-height: 5rem; padding: var(--space-2); background: var(--color-surface); display: grid; align-content: start; gap: 0.25rem; }
.calendario__celda.is-vacia { background: rgb(7 8 11 / 60%); }
.calendario__numero { font-family: var(--font-mono); font-size: var(--text-xs); color: var(--color-text-muted); }
.calendario__evento { display: block; padding: 0.1rem 0.3rem; border-radius: 3px; font-size: 0.625rem; line-height: 1.3; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; background: rgb(255 255 255 / 6%); color: var(--color-text-muted); }
.calendario__evento.is-vencido { background: rgb(249 112 102 / 14%); color: var(--color-danger); }
.calendario__evento.is-presentado { background: rgb(43 217 138 / 10%); color: var(--color-accent); }
.calendario__evento.is-pagado { opacity: 0.45; }
@media (max-width: 40rem) { .calendario__celda { min-height: 3.5rem; } .calendario__evento { display: none; } }
</style>
