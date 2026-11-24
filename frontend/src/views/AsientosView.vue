<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

import { ApiError } from '@/api/client'
import { asientosApi, type Asiento, type AsientoResumen, type EstadoAsiento } from '@/api/asientos'
import { clientesApi } from '@/api/clientes'
import { cuentasApi } from '@/api/cuentas'
import { formatearCuit, type Cliente, type Cuenta } from '@/api/tipos'
import EmptyState from '@/components/ui/EmptyState.vue'
import Modal from '@/components/ui/Modal.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import TableCard from '@/components/ui/TableCard.vue'

interface FilaForm {
  cuenta_id: number | null
  debe: string
  haber: string
}

const route = useRoute()
const clienteId = computed(() => Number(route.params.id))

const cliente = ref<Cliente | null>(null)
const cuentas = ref<Cuenta[]>([])
const asientos = ref<AsientoResumen[]>([])
const total = ref(0)
const pagina = ref(1)
const porPagina = 20

const cargando = ref(true)
const error = ref('')
const aviso = ref<{ tipo: 'ok' | 'error'; texto: string } | null>(null)

const filtros = reactive({
  desde: '',
  hasta: '',
  estado: '' as EstadoAsiento | '',
  cuenta: null as number | null,
  q: '',
})

function hoyISO(): string {
  const ahora = new Date()
  const desfase = ahora.getTimezoneOffset() * 60000
  return new Date(ahora.getTime() - desfase).toISOString().slice(0, 10)
}

/* --------------------------------------------------------------- Formato */
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

function normalizarMonto(valor: string): string {
  const limpio = valor.replace(',', '.').trim()
  if (limpio === '') return '0.00'
  const numero = Number(limpio)
  if (!Number.isFinite(numero)) return '0.00'
  return (Math.round(numero * 100) / 100).toFixed(2)
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
    const [datosCliente, plan, listado] = await Promise.all([
      clientesApi.obtener(clienteId.value),
      cuentasApi.listar(clienteId.value),
      asientosApi.listar(clienteId.value, {
        desde: filtros.desde,
        hasta: filtros.hasta,
        estado: filtros.estado,
        cuenta: filtros.cuenta,
        q: filtros.q,
        pagina: pagina.value,
        por_pagina: porPagina,
      }),
    ])

    cliente.value = datosCliente
    cuentas.value = plan
      .filter((cuenta) => cuenta.imputable && cuenta.activa)
      .sort((a, b) => a.codigo.localeCompare(b.codigo))
    asientos.value = listado.datos
    total.value = listado.total
  } catch (e) {
    error.value =
      e instanceof ApiError ? e.mensaje : 'No pudimos cargar el libro diario.'
  } finally {
    cargando.value = false
  }
}

onMounted(cargar)

function aplicarFiltros() {
  pagina.value = 1
  void cargar()
}

function limpiarFiltros() {
  filtros.desde = ''
  filtros.hasta = ''
  filtros.estado = ''
  filtros.cuenta = null
  filtros.q = ''
  aplicarFiltros()
}

const paginas = computed(() => Math.max(1, Math.ceil(total.value / porPagina)))

function cambiarPagina(delta: number) {
  const destino = pagina.value + delta
  if (destino < 1 || destino > paginas.value) return
  pagina.value = destino
  void cargar()
}

function avisar(tipo: 'ok' | 'error', texto: string) {
  aviso.value = { tipo, texto }
  window.setTimeout(() => (aviso.value = null), 4500)
}

/* -------------------------------------------------------------- Formulario */
const formAbierto = ref(false)
const editando = ref<Asiento | null>(null)
const form = reactive({ fecha: hoyISO(), concepto: '' })
const filas = ref<FilaForm[]>([nuevaFila(), nuevaFila()])
const formError = ref('')
const guardando = ref(false)

function nuevaFila(): FilaForm {
  return { cuenta_id: null, debe: '', haber: '' }
}

function abrirAlta() {
  editando.value = null
  form.fecha = hoyISO()
  form.concepto = ''
  filas.value = [nuevaFila(), nuevaFila()]
  formError.value = ''
  formAbierto.value = true
}

function abrirEdicion(asiento: Asiento) {
  detalleAbierto.value = false
  editando.value = asiento
  form.fecha = asiento.fecha
  form.concepto = asiento.concepto
  filas.value = asiento.renglones.map((renglon) => ({
    cuenta_id: renglon.cuenta_id,
    debe: Number(renglon.debe) ? renglon.debe : '',
    haber: Number(renglon.haber) ? renglon.haber : '',
  }))
  formError.value = ''
  formAbierto.value = true
}

function agregarFila() {
  filas.value.push(nuevaFila())
}

function quitarFila(indice: number) {
  if (filas.value.length <= 2) return
  filas.value.splice(indice, 1)
}

const totalDebe = computed(() =>
  filas.value.reduce((suma, fila) => suma + aCentavos(fila.debe), 0),
)
const totalHaber = computed(() =>
  filas.value.reduce((suma, fila) => suma + aCentavos(fila.haber), 0),
)
const diferencia = computed(() => totalDebe.value - totalHaber.value)
const balanceado = computed(
  () => totalDebe.value === totalHaber.value && totalDebe.value > 0,
)

function validarFormulario(): boolean {
  formError.value = ''

  if (form.concepto.trim().length < 3) {
    formError.value = 'Ingresá un concepto de al menos 3 caracteres.'
    return false
  }
  if (form.fecha > hoyISO()) {
    formError.value = 'La fecha no puede ser futura.'
    return false
  }
  if (filas.value.length < 2) {
    formError.value = 'El asiento necesita al menos dos renglones.'
    return false
  }
  if (filas.value.some((fila) => !fila.cuenta_id)) {
    formError.value = 'Elegí la cuenta en todos los renglones.'
    return false
  }
  if (
    filas.value.some(
      (fila) => aCentavos(fila.debe) === 0 && aCentavos(fila.haber) === 0,
    )
  ) {
    formError.value = 'Cada renglón necesita un importe en el debe o en el haber.'
    return false
  }
  if (
    filas.value.some(
      (fila) => aCentavos(fila.debe) > 0 && aCentavos(fila.haber) > 0,
    )
  ) {
    formError.value = 'Un renglón no puede tener debe y haber a la vez.'
    return false
  }
  if (!balanceado.value) {
    formError.value = 'El asiento tiene que balancear: debe = haber.'
    return false
  }

  return true
}

async function guardar() {
  if (guardando.value || !validarFormulario()) return

  guardando.value = true

  const datos = {
    fecha: form.fecha,
    concepto: form.concepto.trim(),
    renglones: filas.value.map((fila) => ({
      cuenta_id: fila.cuenta_id as number,
      debe: normalizarMonto(fila.debe),
      haber: normalizarMonto(fila.haber),
    })),
  }

  try {
    if (editando.value) {
      await asientosApi.actualizar(editando.value.id, datos)
      avisar('ok', 'Asiento actualizado.')
    } else {
      const creado = await asientosApi.crear(clienteId.value, datos)
      avisar('ok', `Asiento Nº ${creado.numero} guardado como borrador.`)
    }
    formAbierto.value = false
    await cargar()
  } catch (e) {
    formError.value = e instanceof ApiError ? e.mensaje : 'No pudimos guardar el asiento.'
  } finally {
    guardando.value = false
  }
}

/* ----------------------------------------------------------------- Detalle */
const detalleAbierto = ref(false)
const detalle = ref<Asiento | null>(null)
const procesando = ref(false)

async function abrirDetalle(id: number) {
  try {
    detalle.value = await asientosApi.obtener(id)
    detalleAbierto.value = true
  } catch (e) {
    avisar('error', e instanceof ApiError ? e.mensaje : 'No pudimos abrir el asiento.')
  }
}

async function confirmarAsiento() {
  if (!detalle.value || procesando.value) return
  procesando.value = true
  try {
    detalle.value = await asientosApi.confirmar(detalle.value.id)
    avisar('ok', 'Asiento confirmado: ya no se puede editar.')
    await cargar()
  } catch (e) {
    avisar('error', e instanceof ApiError ? e.mensaje : 'No pudimos confirmar el asiento.')
  } finally {
    procesando.value = false
  }
}

const anularAbierto = ref(false)
const motivo = ref('')
const motivoError = ref('')

function abrirAnulacion() {
  motivo.value = ''
  motivoError.value = ''
  anularAbierto.value = true
}

async function anularAsiento() {
  if (!detalle.value || procesando.value) return

  if (motivo.value.trim().length < 5) {
    motivoError.value = 'Escribí un motivo de al menos 5 caracteres.'
    return
  }

  procesando.value = true
  try {
    detalle.value = await asientosApi.anular(detalle.value.id, motivo.value.trim())
    anularAbierto.value = false
    avisar('ok', 'Asiento anulado.')
    await cargar()
  } catch (e) {
    motivoError.value = e instanceof ApiError ? e.mensaje : 'No pudimos anular el asiento.'
  } finally {
    procesando.value = false
  }
}

const descartarAbierto = ref(false)

async function descartarAsiento() {
  if (!detalle.value || procesando.value) return
  procesando.value = true
  try {
    await asientosApi.descartar(detalle.value.id)
    descartarAbierto.value = false
    detalleAbierto.value = false
    avisar('ok', 'Borrador descartado.')
    await cargar()
  } catch (e) {
    avisar('error', e instanceof ApiError ? e.mensaje : 'No pudimos descartar el asiento.')
  } finally {
    procesando.value = false
  }
}

function claseEstado(estado: EstadoAsiento): string {
  if (estado === 'confirmado') return 'badge--ok'
  if (estado === 'anulado') return 'badge--muted'
  return ''
}
</script>

<template>
  <section class="libro">
    <RouterLink :to="{ name: 'cliente', params: { id: clienteId } }" class="volver">
      <svg viewBox="0 0 16 16" width="14" height="14" fill="none" aria-hidden="true">
        <path d="M13 8H4M7.4 4.4 3.8 8l3.6 3.6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" />
      </svg>
      Ficha del cliente
    </RouterLink>

    <PageHeader eyebrow="Contabilidad" title="Libro diario" :show-sub="!!cliente">
      <template #sub>
        {{ cliente?.razon_social }} ·
        <span class="tabular">{{ formatearCuit(cliente?.cuit ?? '') }}</span>
      </template>

      <template #actions>
        <button class="btn btn--primary" type="button" :disabled="!cliente" @click="abrirAlta">
          <svg viewBox="0 0 16 16" width="14" height="14" fill="none" aria-hidden="true">
            <path d="M8 3v10M3 8h10" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" />
          </svg>
          Nuevo asiento
        </button>
      </template>
    </PageHeader>

    <div class="filtros">
      <label class="filtro">
        <span>Desde</span>
        <input v-model="filtros.desde" class="input" type="date" @change="aplicarFiltros" />
      </label>
      <label class="filtro">
        <span>Hasta</span>
        <input v-model="filtros.hasta" class="input" type="date" @change="aplicarFiltros" />
      </label>
      <label class="filtro">
        <span>Estado</span>
        <select v-model="filtros.estado" class="input select" @change="aplicarFiltros">
          <option value="">Todos</option>
          <option value="borrador">Borrador</option>
          <option value="confirmado">Confirmado</option>
          <option value="anulado">Anulado</option>
        </select>
      </label>
      <label class="filtro">
        <span>Cuenta</span>
        <select v-model="filtros.cuenta" class="input select" @change="aplicarFiltros">
          <option :value="null">Todas</option>
          <option v-for="cuenta in cuentas" :key="cuenta.id" :value="cuenta.id">
            {{ cuenta.codigo }} · {{ cuenta.nombre }}
          </option>
        </select>
      </label>
      <label class="filtro filtro--busqueda">
        <span>Buscar</span>
        <input
          v-model="filtros.q"
          class="input"
          type="search"
          placeholder="Concepto"
          @keyup.enter="aplicarFiltros"
        />
      </label>
      <button class="btn btn--sm filtros__limpiar" type="button" @click="limpiarFiltros">
        Limpiar
      </button>
    </div>

    <p v-if="aviso" class="alert" :class="`alert--${aviso.tipo}`" role="status">
      {{ aviso.texto }}
    </p>

    <div v-if="error" class="alert alert--error" role="alert">
      <span>{{ error }}</span>
      <button class="btn btn--sm" type="button" @click="cargar">Reintentar</button>
    </div>

    <TableCard>
      <EmptyState v-if="cargando" loading>Cargando libro diario…</EmptyState>

      <EmptyState v-else-if="asientos.length === 0">
        <p>No hay asientos para los filtros elegidos.</p>
        <button class="btn btn--sm" type="button" @click="abrirAlta">
          Cargar el primero
        </button>
      </EmptyState>

      <div v-else class="tabla-scroll">
        <table class="table">
          <thead>
            <tr>
              <th scope="col">Nº</th>
              <th scope="col">Fecha</th>
              <th scope="col">Concepto</th>
              <th scope="col" class="col-monto">Debe</th>
              <th scope="col" class="col-monto">Haber</th>
              <th scope="col">Estado</th>
              <th scope="col"><span class="sr-only">Ver</span></th>
            </tr>
          </thead>

          <tbody>
            <tr
              v-for="asiento in asientos"
              :key="asiento.id"
              :class="{ 'is-anulado': asiento.estado === 'anulado' }"
              class="fila"
              @click="abrirDetalle(asiento.id)"
            >
              <td class="tabular">{{ String(asiento.numero).padStart(4, '0') }}</td>
              <td class="tabular col-fecha">{{ fechaVisible(asiento.fecha) }}</td>
              <td class="concepto">{{ asiento.concepto }}</td>
              <td class="tabular col-monto">{{ formatearMonto(asiento.debe) }}</td>
              <td class="tabular col-monto">{{ formatearMonto(asiento.haber) }}</td>
              <td>
                <span class="badge" :class="claseEstado(asiento.estado)">
                  {{ asiento.estado_etiqueta }}
                </span>
              </td>
              <td>
                <span class="icon-btn" aria-hidden="true">
                  <svg viewBox="0 0 16 16" width="15" height="15" fill="none">
                    <path d="M3 8h9M8.6 4.4 12.2 8l-3.6 3.6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" />
                  </svg>
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </TableCard>

    <div v-if="total > porPagina" class="paginacion">
      <button class="btn btn--sm" type="button" :disabled="pagina === 1" @click="cambiarPagina(-1)">
        Anterior
      </button>
      <span class="paginacion__texto">
        Página {{ pagina }} de {{ paginas }} · {{ total }} asientos
      </span>
      <button
        class="btn btn--sm"
        type="button"
        :disabled="pagina === paginas"
        @click="cambiarPagina(1)"
      >
        Siguiente
      </button>
    </div>

    <!-- ------------------------------------------------------- Alta / edición -->
    <Modal
      :abierto="formAbierto"
      :titulo="editando ? `Editar asiento Nº ${editando.numero}` : 'Nuevo asiento'"
      @cerrar="formAbierto = false"
    >
      <form id="form-asiento" class="form-asiento" novalidate @submit.prevent="guardar">
        <div class="fila-cabecera">
          <div class="field">
            <label class="field__label" for="asiento-fecha">Fecha</label>
            <input id="asiento-fecha" v-model="form.fecha" class="input" type="date" :max="hoyISO()" />
          </div>
          <div class="field">
            <label class="field__label" for="asiento-concepto">Concepto</label>
            <input
              id="asiento-concepto"
              v-model="form.concepto"
              class="input"
              type="text"
              placeholder="Venta de mercadería según factura A-0001"
            />
          </div>
        </div>

        <div class="renglones">
          <div class="renglones__cabecera">
            <span>Cuenta</span>
            <span>Debe</span>
            <span>Haber</span>
            <span></span>
          </div>

          <div v-for="(fila, indice) in filas" :key="indice" class="renglon">
            <select v-model="fila.cuenta_id" class="input select" :aria-label="`Cuenta del renglón ${indice + 1}`">
              <option :value="null" disabled>Elegir cuenta…</option>
              <option v-for="cuenta in cuentas" :key="cuenta.id" :value="cuenta.id">
                {{ cuenta.codigo }} · {{ cuenta.nombre }}
              </option>
            </select>

            <input
              v-model="fila.debe"
              class="input tabular"
              type="text"
              inputmode="decimal"
              placeholder="0,00"
              :aria-label="`Debe del renglón ${indice + 1}`"
            />
            <input
              v-model="fila.haber"
              class="input tabular"
              type="text"
              inputmode="decimal"
              placeholder="0,00"
              :aria-label="`Haber del renglón ${indice + 1}`"
            />
            <button
              class="icon-btn icon-btn--peligro"
              type="button"
              :disabled="filas.length <= 2"
              :aria-label="`Quitar renglón ${indice + 1}`"
              @click="quitarFila(indice)"
            >
              <svg viewBox="0 0 16 16" width="13" height="13" fill="none" aria-hidden="true">
                <path d="M4 4l8 8M12 4l-8 8" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
              </svg>
            </button>
          </div>

          <button class="btn btn--sm renglones__agregar" type="button" @click="agregarFila">
            + Agregar renglón
          </button>
        </div>

        <div class="totales" :class="{ 'is-ok': balanceado }">
          <div>
            <span class="totales__rotulo">Debe</span>
            <span class="totales__valor tabular">{{ formatearMonto(totalDebe / 100) }}</span>
          </div>
          <div>
            <span class="totales__rotulo">Haber</span>
            <span class="totales__valor tabular">{{ formatearMonto(totalHaber / 100) }}</span>
          </div>
          <div class="totales__diferencia">
            <span class="totales__rotulo">Diferencia</span>
            <span class="totales__valor tabular">
              {{ balanceado ? 'Balanceado' : formatearMonto(diferencia / 100) }}
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
          form="form-asiento"
          :disabled="guardando || !balanceado"
        >
          {{ guardando ? 'Guardando…' : editando ? 'Guardar cambios' : 'Guardar borrador' }}
        </button>
      </template>
    </Modal>

    <!-- ------------------------------------------------------------- Detalle -->
    <Modal
      :abierto="detalleAbierto"
      :titulo="detalle ? `Asiento Nº ${String(detalle.numero).padStart(4, '0')}` : 'Asiento'"
      @cerrar="detalleAbierto = false"
    >
      <div v-if="detalle" class="detalle">
        <div class="detalle__meta">
          <span class="tabular">{{ fechaVisible(detalle.fecha) }}</span>
          <span class="badge" :class="claseEstado(detalle.estado)">{{ detalle.estado_etiqueta }}</span>
        </div>

        <p class="detalle__concepto">{{ detalle.concepto }}</p>

        <table class="table table--compacta">
          <thead>
            <tr>
              <th scope="col">Cuenta</th>
              <th scope="col" class="col-monto">Debe</th>
              <th scope="col" class="col-monto">Haber</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="renglon in detalle.renglones" :key="renglon.id">
              <td>
                <span class="tabular cuenta-codigo">{{ renglon.cuenta_codigo }}</span>
                {{ renglon.cuenta_nombre }}
              </td>
              <td class="tabular col-monto">
                {{ Number(renglon.debe) ? formatearMonto(renglon.debe) : '—' }}
              </td>
              <td class="tabular col-monto">
                {{ Number(renglon.haber) ? formatearMonto(renglon.haber) : '—' }}
              </td>
            </tr>
          </tbody>
        </table>

        <div class="detalle__pie">
          <span>Creado por {{ detalle.creado_por ?? 'el sistema' }}</span>
          <span v-if="detalle.estado === 'anulado'" class="detalle__anulado">
            Anulado por {{ detalle.anulado_por }} · {{ detalle.motivo_anulacion }}
          </span>
        </div>
      </div>

      <template #pie>
        <template v-if="detalle">
          <button
            v-if="detalle.estado === 'borrador'"
            class="btn btn--danger btn--sm"
            type="button"
            @click="descartarAbierto = true"
          >
            Descartar
          </button>
          <button
            v-if="detalle.estado !== 'anulado'"
            class="btn btn--danger btn--sm"
            type="button"
            @click="abrirAnulacion"
          >
            Anular
          </button>
          <button
            v-if="detalle.estado === 'borrador'"
            class="btn"
            type="button"
            @click="abrirEdicion(detalle)"
          >
            Editar
          </button>
          <button
            v-if="detalle.estado === 'borrador'"
            class="btn btn--primary"
            type="button"
            :disabled="procesando"
            @click="confirmarAsiento"
          >
            Confirmar
          </button>
          <button v-else class="btn" type="button" @click="detalleAbierto = false">
            Cerrar
          </button>
        </template>
      </template>
    </Modal>

    <!-- ------------------------------------------------------------- Anular -->
    <Modal :abierto="anularAbierto" titulo="Anular asiento" @cerrar="anularAbierto = false">
      <form id="form-anular" class="form-anular" novalidate @submit.prevent="anularAsiento">
        <p class="texto-suave">
          Anular no borra: el asiento queda registrado con el motivo y el usuario.
        </p>
        <div class="field">
          <label class="field__label" for="anular-motivo">Motivo</label>
          <input
            id="anular-motivo"
            v-model="motivo"
            class="input"
            type="text"
            placeholder="Error de imputación"
          />
        </div>
        <p v-if="motivoError" class="alert alert--error" role="alert">{{ motivoError }}</p>
      </form>

      <template #pie>
        <button class="btn" type="button" @click="anularAbierto = false">Cancelar</button>
        <button
          class="btn btn--danger"
          type="submit"
          form="form-anular"
          :disabled="procesando"
        >
          {{ procesando ? 'Anulando…' : 'Anular asiento' }}
        </button>
      </template>
    </Modal>

    <!-- ----------------------------------------------------------- Descartar -->
    <Modal :abierto="descartarAbierto" titulo="Descartar borrador" @cerrar="descartarAbierto = false">
      <p class="texto-suave">
        El asiento todavía no afectó los libros, por eso se puede eliminar. Si
        querés conservarlo, confirmalo en lugar de descartarlo.
      </p>

      <template #pie>
        <button class="btn" type="button" @click="descartarAbierto = false">Cancelar</button>
        <button class="btn btn--danger" type="button" :disabled="procesando" @click="descartarAsiento">
          {{ procesando ? 'Descartando…' : 'Descartar' }}
        </button>
      </template>
    </Modal>
  </section>
</template>

<style scoped>
.libro {
  display: grid;
  gap: var(--space-5);
}

.filtros {
  display: flex;
  align-items: flex-end;
  gap: var(--space-3);
  flex-wrap: wrap;
}

.filtro {
  display: grid;
  gap: var(--space-1);
}

.filtro > span {
  font-size: 0.625rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--color-text-faint);
}

.filtro .input {
  min-height: 2.5rem;
}

.filtro--busqueda {
  flex: 1 1 14rem;
}

.filtros__limpiar {
  margin-bottom: 0.1rem;
}

.fila {
  cursor: pointer;
}

.fila.is-anulado {
  opacity: 0.55;
}

.concepto {
  max-width: 26rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.col-monto {
  text-align: right;
  white-space: nowrap;
}

.paginacion {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: var(--space-3);
}

.paginacion__texto {
  font-size: var(--text-xs);
  color: var(--color-text-faint);
}

/* ------------------------------------------------------------- Formulario */
.form-asiento {
  display: grid;
  gap: var(--space-4);
}

.fila-cabecera {
  display: grid;
  grid-template-columns: 10rem 1fr;
  gap: var(--space-3);
}

.renglones {
  display: grid;
  gap: var(--space-2);
}

.renglones__cabecera,
.renglon {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 7rem 7rem 2rem;
  gap: var(--space-2);
  align-items: center;
}

.renglones__cabecera {
  padding: 0 var(--space-1);
  font-size: 0.625rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--color-text-faint);
}

.renglones__cabecera span:nth-child(2),
.renglones__cabecera span:nth-child(3) {
  text-align: right;
}

.renglon .input {
  min-height: 2.5rem;
}

.renglones__agregar {
  justify-self: start;
  margin-top: var(--space-1);
}

.totales {
  display: flex;
  gap: var(--space-6);
  padding: var(--space-3) var(--space-4);
  border: 1px solid var(--color-line);
  border-radius: var(--radius-sm);
  background: rgb(255 255 255 / 2%);
}

.totales.is-ok {
  border-color: rgb(43 217 138 / 25%);
  background: rgb(43 217 138 / 5%);
}

.totales__rotulo {
  display: block;
  font-size: 0.625rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--color-text-faint);
}

.totales__valor {
  font-size: var(--text-sm);
}

.totales.is-ok .totales__valor {
  color: var(--color-accent);
}

.totales__diferencia {
  margin-left: auto;
  text-align: right;
}

/* ---------------------------------------------------------------- Detalle */
.detalle {
  display: grid;
  gap: var(--space-3);
}

.detalle__meta {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  font-size: var(--text-xs);
  color: var(--color-text-muted);
}

.detalle__concepto {
  font-size: var(--text-sm);
}

.table--compacta th,
.table--compacta td {
  padding: 0.5rem var(--space-2);
}

.cuenta-codigo {
  margin-right: var(--space-2);
  font-size: var(--text-xs);
  color: var(--color-text-faint);
}

.detalle__pie {
  display: grid;
  gap: var(--space-1);
  font-size: var(--text-xs);
  color: var(--color-text-faint);
}

.detalle__anulado {
  color: var(--color-danger);
}

.texto-suave {
  font-size: var(--text-sm);
  color: var(--color-text-muted);
}

.form-anular {
  display: grid;
  gap: var(--space-3);
}

@media (max-width: 52rem) {
  .col-fecha {
    display: none;
  }

  .fila-cabecera,
  .renglon,
  .renglones__cabecera {
    grid-template-columns: minmax(0, 1fr) 6rem 6rem 1.5rem;
  }

  .fila-cabecera .field:nth-child(2) {
    grid-column: 1 / -1;
  }

  .fila-cabecera {
    grid-template-columns: 1fr;
  }
}
</style>
