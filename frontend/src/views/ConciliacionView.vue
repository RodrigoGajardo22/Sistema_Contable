<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

import { ApiError } from '@/api/client'
import {
  comprobantesApi,
  type Comprobante,
} from '@/api/comprobantes'
import {
  conciliacionApi,
  type Extracto,
  type Movimiento,
} from '@/api/conciliacion'
import { cuentasApi } from '@/api/cuentas'
import type { Cuenta } from '@/api/tipos'
import EmptyState from '@/components/ui/EmptyState.vue'
import Modal from '@/components/ui/Modal.vue'
import PageHeader from '@/components/ui/PageHeader.vue'

const route = useRoute()
const clienteId = computed(() => Number(route.params.id))

const extractos = ref<Extracto[]>([])
const seleccionado = ref<Extracto | null>(null)
const movimientoSel = ref<Movimiento | null>(null)
const comprobantes = ref<Comprobante[]>([])
const cuentas = ref<Cuenta[]>([])

const cargando = ref(true)
const error = ref('')
const aviso = ref<{ tipo: 'ok' | 'error'; texto: string } | null>(null)

const importarAbierto = ref(false)
const form = reactive({
  banco: '',
  periodo: '',
  saldo_inicial: '0.00',
  saldo_final: '0.00',
  csv: '',
})
const formError = ref('')
const importando = ref(false)

const generarAbierto = ref(false)
const generarCuenta = ref<number | null>(null)
const generarConcepto = ref('')
const generarError = ref('')
const generando = ref(false)

const formato = new Intl.NumberFormat('es-AR', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})

function monto(valor: string | number | null | undefined): string {
  return formato.format(Number(valor ?? 0))
}

const fecha = new Intl.DateTimeFormat('es-AR', { dateStyle: 'medium' })

function fechaVisible(iso: string): string {
  const [anio, mes, dia] = iso.split('-')
  return fecha.format(new Date(Number(anio), Number(mes) - 1, Number(dia)))
}

function diasEntre(a: string, b: string): number {
  return Math.abs(
    (new Date(`${a}T00:00:00`).getTime() - new Date(`${b}T00:00:00`).getTime()) /
      86400000,
  )
}

const movimientos = computed(() => seleccionado.value?.movimientos ?? [])

const pendientes = computed(
  () => movimientos.value.filter((m) => m.estado === 'pendiente').length,
)

async function cargar() {
  cargando.value = true
  error.value = ''
  try {
    extractos.value = await conciliacionApi.listar(clienteId.value)
    if (extractos.value.length > 0) {
      const id = seleccionado.value?.id ?? extractos.value[0]!.id
      await abrir(id)
    } else {
      seleccionado.value = null
      movimientoSel.value = null
    }
  } catch (e) {
    error.value =
      e instanceof ApiError ? e.mensaje : 'No pudimos cargar las conciliaciones.'
  } finally {
    cargando.value = false
  }
}

async function cargarCatalogos() {
  try {
    const [plan, lista] = await Promise.all([
      cuentasApi.listar(clienteId.value),
      comprobantesApi.listar(clienteId.value, {}),
    ])
    cuentas.value = plan
      .filter((c) => c.imputable && c.activa)
      .sort((a, b) => a.codigo.localeCompare(b.codigo))
    comprobantes.value = lista.datos
  } catch {
    cuentas.value = []
    comprobantes.value = []
  }
}

onMounted(async () => {
  await Promise.all([cargar(), cargarCatalogos()])
})

async function abrir(id: number) {
  const anterior = movimientoSel.value?.id ?? null
  try {
    seleccionado.value = await conciliacionApi.obtener(id)

    const lista = seleccionado.value.movimientos ?? []
    movimientoSel.value =
      lista.find((m) => m.id === anterior) ??
      lista.find((m) => m.estado === 'pendiente') ??
      lista[0] ??
      null
  } catch (e) {
    avisar('error', e instanceof ApiError ? e.mensaje : 'No pudimos abrir el extracto.')
  }
}

function avisar(tipo: 'ok' | 'error', texto: string) {
  aviso.value = { tipo, texto }
  window.setTimeout(() => (aviso.value = null), 4000)
}

function leerArchivo(evento: Event) {
  const input = evento.target as HTMLInputElement
  const archivo = input.files?.[0]
  if (!archivo) return

  const lector = new FileReader()
  lector.onload = () => {
    form.csv = String(lector.result ?? '')
  }
  lector.readAsText(archivo)
}

async function importar() {
  if (importando.value) return
  if (!form.banco.trim() || !form.periodo.trim() || !form.csv.trim()) {
    formError.value = 'Completá banco, período y el CSV.'
    return
  }

  importando.value = true
  formError.value = ''
  try {
    const extracto = await conciliacionApi.crear(clienteId.value, {
      banco: form.banco.trim(),
      periodo: form.periodo.trim(),
      saldo_inicial: form.saldo_inicial || '0.00',
      saldo_final: form.saldo_final || '0.00',
      csv: form.csv,
    })
    importarAbierto.value = false
    avisar('ok', `Extracto importado: ${extracto.resumen.movimientos} movimientos.`)
    await cargar()
    await abrir(extracto.id)
  } catch (e) {
    formError.value = e instanceof ApiError ? e.mensaje : 'No pudimos importar el CSV.'
  } finally {
    importando.value = false
  }
}

async function refrescar() {
  if (seleccionado.value) await abrir(seleccionado.value.id)
  await cargar()
}

async function vincularAsiento(movimiento: Movimiento, asientoId: number) {
  try {
    await conciliacionApi.vincular(movimiento.id, { asiento_id: asientoId })
    avisar('ok', 'Movimiento conciliado con el asiento.')
    await refrescar()
  } catch (e) {
    avisar('error', e instanceof ApiError ? e.mensaje : 'No pudimos vincular.')
  }
}

async function vincularComprobante(movimiento: Movimiento, comprobanteId: number) {
  try {
    await conciliacionApi.vincular(movimiento.id, { comprobante_id: comprobanteId })
    avisar('ok', 'Movimiento conciliado con el comprobante.')
    await refrescar()
  } catch (e) {
    avisar('error', e instanceof ApiError ? e.mensaje : 'No pudimos vincular.')
  }
}

async function descartar(movimiento: Movimiento) {
  try {
    await conciliacionApi.descartar(movimiento.id)
    await refrescar()
  } catch (e) {
    avisar('error', e instanceof ApiError ? e.mensaje : 'No pudimos descartar.')
  }
}

async function desvincular(movimiento: Movimiento) {
  try {
    await conciliacionApi.desvincular(movimiento.id)
    avisar('ok', 'Movimiento devuelto a pendiente.')
    await refrescar()
  } catch (e) {
    avisar(
      'error',
      e instanceof ApiError ? e.mensaje : 'No pudimos deshacer la conciliación.',
    )
  }
}

function abrirGenerar(movimiento: Movimiento) {
  generarCuenta.value = cuentas.value[0]?.id ?? null
  generarConcepto.value = `Movimiento bancario: ${movimiento.descripcion}`
  generarError.value = ''
  generarAbierto.value = true
}

async function confirmarGenerar() {
  if (!movimientoSel.value || !generarCuenta.value || generando.value) return

  generando.value = true
  generarError.value = ''
  try {
    const resultado = await conciliacionApi.generarAsiento(
      movimientoSel.value.id,
      generarCuenta.value,
      generarConcepto.value.trim() || undefined,
    )
    generarAbierto.value = false
    avisar('ok', `Asiento Nº ${resultado.numero} generado y vinculado.`)
    await refrescar()
  } catch (e) {
    generarError.value =
      e instanceof ApiError ? e.mensaje : 'No pudimos generar el asiento.'
  } finally {
    generando.value = false
  }
}

function candidatosComprobante(movimiento: Movimiento) {
  const importe = Math.abs(Number(movimiento.importe))

  return comprobantes.value
    .filter(
      (c) =>
        c.estado !== 'anulado' &&
        Math.abs(Number(c.total) - importe) < 0.005 &&
        diasEntre(c.fecha, movimiento.fecha) <= 3,
    )
    .map((c) => ({ comprobante: c, dias: diasEntre(c.fecha, movimiento.fecha) }))
    .sort((a, b) => a.dias - b.dias)
}

function confianza(dias: number): number {
  return [100, 90, 75, 60][dias] ?? 40
}

function colorEstado(estado: string): string {
  if (estado === 'conciliado') return 'badge--ok'
  if (estado === 'descartado') return 'badge--muted'
  return ''
}
</script>

<template>
  <section class="conciliacion">
    <RouterLink :to="{ name: 'cliente', params: { id: clienteId } }" class="volver">
      <svg viewBox="0 0 16 16" width="14" height="14" fill="none" aria-hidden="true">
        <path d="M13 8H4M7.4 4.4 3.8 8l3.6 3.6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" />
      </svg>
      Ficha del cliente
    </RouterLink>

    <PageHeader
      eyebrow="Bancos"
      title="Conciliación"
      subtitle="Extracto a la izquierda, sistema a la derecha. Importá un CSV (fecha;descripción;importe) y vinculá cada movimiento."
    >
      <template #actions>
        <button class="btn btn--primary" type="button" @click="importarAbierto = true">
          + Importar extracto
        </button>
      </template>
    </PageHeader>

    <p v-if="aviso" class="alert" :class="`alert--${aviso.tipo}`" role="status">{{ aviso.texto }}</p>
    <div v-if="error" class="alert alert--error" role="alert">{{ error }}</div>

    <EmptyState v-if="cargando" loading compact>Cargando conciliaciones…</EmptyState>

    <EmptyState v-else-if="extractos.length === 0" class="card">
      <p>No hay extractos importados.</p>
      <button class="btn btn--sm" type="button" @click="importarAbierto = true">Importar el primero</button>
    </EmptyState>

    <template v-else>
      <div class="selector">
        <button
          v-for="e in extractos"
          :key="e.id"
          class="extracto"
          :class="{ 'is-activo': seleccionado?.id === e.id }"
          type="button"
          @click="abrir(e.id)"
        >
          <span class="extracto__banco">{{ e.banco }}</span>
          <span class="extracto__detalle">{{ e.periodo }} · {{ e.resumen.movimientos }} mov.</span>
          <span class="extracto__saldo tabular">{{ monto(e.saldo_final) }}</span>
        </button>
      </div>

      <div v-if="seleccionado" class="resumen">
        <div><span>Saldo banco</span><strong class="tabular">{{ monto(seleccionado.saldo_final) }}</strong></div>
        <div><span>Saldo contable</span><strong class="tabular">{{ monto(seleccionado.resumen.saldo_contable) }}</strong></div>
        <div><span>Conciliados</span><strong class="tabular">{{ seleccionado.resumen.conciliados }}</strong></div>
        <div><span>Pendientes</span><strong class="tabular">{{ pendientes }}</strong></div>
        <div><span>Diferencia CSV</span><strong class="tabular" :class="{ 'is-ok': Number(seleccionado.resumen.diferencia) === 0 }">{{ monto(seleccionado.resumen.diferencia) }}</strong></div>
      </div>

      <div v-if="seleccionado" class="columnas">
        <aside class="card columna columna--extracto">
          <header class="columna__cabecera">
            <h2>Extracto</h2>
            <span class="columna__nota">{{ seleccionado.banco }} · {{ seleccionado.periodo }}</span>
          </header>
          <ul class="movimientos">
            <li v-for="m in movimientos" :key="m.id">
              <button
                class="movimiento"
                :class="{ 'is-activo': movimientoSel?.id === m.id }"
                type="button"
                @click="movimientoSel = m"
              >
                <span class="movimiento__fecha tabular">{{ fechaVisible(m.fecha) }}</span>
                <span class="movimiento__desc">{{ m.descripcion }}</span>
                <span class="movimiento__importe tabular" :class="{ 'is-negativo': Number(m.importe) < 0 }">
                  {{ monto(m.importe) }}
                </span>
                <span class="badge" :class="colorEstado(m.estado)">{{ m.estado_etiqueta }}</span>
              </button>
            </li>
          </ul>
        </aside>

        <section v-if="movimientoSel" class="card columna">
          <header class="columna__cabecera">
            <h2>Sistema</h2>
            <span class="columna__nota">Movimiento seleccionado</span>
          </header>

          <div class="detalle-mov">
            <p class="detalle-mov__desc">{{ movimientoSel.descripcion }}</p>
            <p class="detalle-mov__meta tabular">
              {{ fechaVisible(movimientoSel.fecha) }} · {{ monto(movimientoSel.importe) }}
            </p>
          </div>

          <template v-if="movimientoSel.estado === 'pendiente'">
            <div class="bloque-match">
              <h3 class="bloque-match__titulo">Asientos candidatos</h3>
              <div v-if="movimientoSel.sugerencias.length" class="candidatos">
                <div v-for="s in movimientoSel.sugerencias" :key="s.asiento_id" class="candidato">
                  <div class="candidato__texto">
                    <strong>Asiento Nº {{ s.numero }}</strong>
                    <span>{{ s.concepto }}</span>
                    <span class="candidato__meta tabular">{{ fechaVisible(s.fecha) }} · {{ monto(s.total) }}</span>
                  </div>
                  <span class="badge" :class="s.confianza >= 90 ? 'badge--ok' : ''">{{ s.confianza }}%</span>
                  <button class="btn btn--sm" type="button" @click="vincularAsiento(movimientoSel, s.asiento_id)">
                    Vincular
                  </button>
                </div>
              </div>
              <p v-else class="vacio">Sin asientos con importe y fecha compatibles.</p>
            </div>

            <div class="bloque-match">
              <h3 class="bloque-match__titulo">Comprobantes candidatos</h3>
              <div v-if="candidatosComprobante(movimientoSel).length" class="candidatos">
                <div
                  v-for="c in candidatosComprobante(movimientoSel)"
                  :key="c.comprobante.id"
                  class="candidato"
                >
                  <div class="candidato__texto">
                    <strong>{{ c.comprobante.tipo_etiqueta }} {{ c.comprobante.numero }}</strong>
                    <span>{{ c.comprobante.tercero }}</span>
                    <span class="candidato__meta tabular">{{ fechaVisible(c.comprobante.fecha) }} · {{ monto(c.comprobante.total) }}</span>
                  </div>
                  <span class="badge" :class="c.dias === 0 ? 'badge--ok' : ''">{{ confianza(c.dias) }}%</span>
                  <button class="btn btn--sm" type="button" @click="vincularComprobante(movimientoSel, c.comprobante.id)">
                    Vincular
                  </button>
                </div>
              </div>
              <p v-else class="vacio">Sin comprobantes compatibles.</p>
            </div>

            <div class="acciones-mov">
              <button class="btn" type="button" @click="abrirGenerar(movimientoSel)">
                Generar asiento desde el movimiento
              </button>
              <button class="btn btn--danger btn--sm" type="button" @click="descartar(movimientoSel)">
                Descartar
              </button>
            </div>
          </template>

          <div v-else-if="movimientoSel.estado === 'conciliado'" class="conciliado">
            <p>
              Conciliado con
              <strong v-if="movimientoSel.asiento_numero">el asiento Nº {{ movimientoSel.asiento_numero }}</strong>
              <strong v-else-if="movimientoSel.comprobante_numero">el comprobante {{ movimientoSel.comprobante_numero }}</strong>
              <strong v-else>un registro del sistema</strong>.
            </p>
            <button class="btn btn--sm" type="button" @click="desvincular(movimientoSel)">
              Deshacer conciliación
            </button>
          </div>

          <p v-else class="vacio">Este movimiento fue descartado.</p>
        </section>
      </div>
    </template>

    <!-- Importar -->
    <Modal :abierto="importarAbierto" titulo="Importar extracto" @cerrar="importarAbierto = false">
      <form id="form-extracto" class="formulario" novalidate @submit.prevent="importar">
        <div class="fila">
          <div class="field">
            <label class="field__label" for="e-banco">Banco</label>
            <input id="e-banco" v-model="form.banco" class="input" type="text" placeholder="Galicia" />
          </div>
          <div class="field">
            <label class="field__label" for="e-periodo">Período</label>
            <input id="e-periodo" v-model="form.periodo" class="input" type="text" placeholder="2026-11" />
          </div>
        </div>
        <div class="fila">
          <div class="field">
            <label class="field__label" for="e-inicial">Saldo inicial</label>
            <input id="e-inicial" v-model="form.saldo_inicial" class="input tabular" type="text" />
          </div>
          <div class="field">
            <label class="field__label" for="e-final">Saldo final</label>
            <input id="e-final" v-model="form.saldo_final" class="input tabular" type="text" />
          </div>
        </div>
        <div class="field">
          <label class="field__label" for="e-archivo">Archivo CSV</label>
          <input id="e-archivo" class="input" type="file" accept=".csv,text/csv" @change="leerArchivo" />
          <p class="field__ayuda">Formato: fecha;descripción;importe (una fila por movimiento).</p>
        </div>
        <div class="field">
          <label class="field__label" for="e-csv">…o pegá el contenido</label>
          <textarea id="e-csv" v-model="form.csv" class="input textarea" rows="6" placeholder="20/11/2026;Transferencia;1500,00"></textarea>
        </div>
        <p v-if="formError" class="alert alert--error" role="alert">{{ formError }}</p>
      </form>
      <template #pie>
        <button class="btn" type="button" @click="importarAbierto = false">Cancelar</button>
        <button class="btn btn--primary" type="submit" form="form-extracto" :disabled="importando">
          {{ importando ? 'Importando…' : 'Importar' }}
        </button>
      </template>
    </Modal>

    <!-- Generar asiento -->
    <Modal :abierto="generarAbierto" titulo="Generar asiento desde el movimiento" @cerrar="generarAbierto = false">
      <form id="form-generar" class="formulario" novalidate @submit.prevent="confirmarGenerar">
        <p class="texto-suave">
          Se debita/acredita Banco (1.1.02) contra la cuenta que elijas y el
          asiento queda confirmado y vinculado.
        </p>
        <div class="field">
          <label class="field__label" for="g-cuenta">Contrapartida</label>
          <select id="g-cuenta" v-model="generarCuenta" class="input select">
            <option v-for="c in cuentas" :key="c.id" :value="c.id">{{ c.codigo }} · {{ c.nombre }}</option>
          </select>
        </div>
        <div class="field">
          <label class="field__label" for="g-concepto">Concepto</label>
          <input id="g-concepto" v-model="generarConcepto" class="input" type="text" />
        </div>
        <p v-if="generarError" class="alert alert--error" role="alert">{{ generarError }}</p>
      </form>
      <template #pie>
        <button class="btn" type="button" @click="generarAbierto = false">Cancelar</button>
        <button class="btn btn--primary" type="submit" form="form-generar" :disabled="generando">
          {{ generando ? 'Generando…' : 'Generar y vincular' }}
        </button>
      </template>
    </Modal>
  </section>
</template>

<style scoped>
.conciliacion { display: grid; gap: var(--space-5); }

.selector { display: flex; gap: var(--space-2); overflow-x: auto; padding-bottom: var(--space-1); }
.extracto { display: grid; gap: 0.1rem; min-width: 12rem; padding: var(--space-3); border: 1px solid var(--color-line); border-radius: var(--radius-md); background: rgb(255 255 255 / 1.5%); text-align: left; cursor: pointer; color: inherit; }
.extracto:hover { border-color: var(--color-line-strong); }
.extracto.is-activo { border-color: var(--color-accent); background: rgb(43 217 138 / 6%); }
.extracto__banco { font-size: var(--text-sm); font-weight: 500; }
.extracto__detalle { font-size: var(--text-xs); color: var(--color-text-faint); }
.extracto__saldo { font-size: var(--text-xs); }

.resumen { display: grid; grid-template-columns: repeat(auto-fit, minmax(9rem, 1fr)); gap: var(--space-3); }
.resumen > div { display: grid; gap: 0.15rem; padding: var(--space-3) var(--space-4); border: 1px solid var(--color-line); border-radius: var(--radius-md); background: rgb(255 255 255 / 1.5%); }
.resumen span { font-size: 0.625rem; letter-spacing: 0.1em; text-transform: uppercase; color: var(--color-text-faint); }
.resumen strong { font-size: var(--text-lg); font-weight: 500; }
.resumen strong.is-ok { color: var(--color-accent); }

.columnas { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1.15fr); gap: var(--space-4); align-items: start; }
.columna { display: grid; gap: var(--space-3); padding: var(--space-4); align-content: start; }
.columna__cabecera { display: flex; align-items: baseline; justify-content: space-between; gap: var(--space-3); }
.columna__cabecera h2 { font-size: var(--text-lg); }
.columna__nota { font-size: var(--text-xs); color: var(--color-text-faint); }

.movimientos { display: grid; gap: 2px; padding: 0; margin: 0; list-style: none; }
.movimiento { display: grid; grid-template-columns: 5.5rem minmax(0, 1fr) auto auto; align-items: center; gap: var(--space-2); width: 100%; padding: var(--space-2); border: 1px solid transparent; border-radius: var(--radius-sm); background: transparent; color: inherit; text-align: left; cursor: pointer; font-size: var(--text-sm); }
.movimiento:hover { background: rgb(255 255 255 / 3%); }
.movimiento.is-activo { border-color: var(--color-line-strong); background: rgb(43 217 138 / 5%); }
.movimiento__fecha { font-size: var(--text-xs); color: var(--color-text-faint); }
.movimiento__desc { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.movimiento__importe { font-size: var(--text-xs); }
.movimiento__importe.is-negativo { color: var(--color-danger); }

.detalle-mov { display: grid; gap: 0.2rem; padding-bottom: var(--space-3); border-bottom: 1px solid var(--color-line); }
.detalle-mov__desc { font-size: var(--text-base); }
.detalle-mov__meta { font-size: var(--text-xs); color: var(--color-text-faint); }

.bloque-match { display: grid; gap: var(--space-2); }
.bloque-match__titulo { font-size: var(--text-xs); letter-spacing: 0.1em; text-transform: uppercase; color: var(--color-text-faint); }
.candidatos { display: grid; gap: var(--space-2); }
.candidato { display: flex; align-items: center; gap: var(--space-3); padding: var(--space-2) var(--space-3); border: 1px solid var(--color-line); border-radius: var(--radius-sm); background: rgb(255 255 255 / 1.5%); }
.candidato__texto { flex: 1; min-width: 0; display: grid; gap: 0.05rem; font-size: var(--text-sm); }
.candidato__texto span { font-size: var(--text-xs); color: var(--color-text-faint); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.candidato__meta { font-family: var(--font-mono); }

.acciones-mov { display: flex; gap: var(--space-2); flex-wrap: wrap; padding-top: var(--space-2); border-top: 1px solid var(--color-line); }
.conciliado { display: grid; gap: var(--space-3); font-size: var(--text-sm); justify-items: start; }
.vacio { font-size: var(--text-xs); color: var(--color-text-faint); }

.fila { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-4); }
.textarea { min-height: 7rem; padding: var(--space-2); resize: vertical; font-family: var(--font-mono); font-size: var(--text-xs); }
.texto-suave { font-size: var(--text-sm); color: var(--color-text-muted); }

@media (max-width: 68rem) { .columnas { grid-template-columns: 1fr; } }
@media (max-width: 48rem) { .fila { grid-template-columns: 1fr; } .movimiento { grid-template-columns: 1fr auto; } .movimiento__fecha { display: none; } }
</style>
