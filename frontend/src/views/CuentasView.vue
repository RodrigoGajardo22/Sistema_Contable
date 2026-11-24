<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

import { ApiError } from '@/api/client'
import { clientesApi } from '@/api/clientes'
import { cuentasApi } from '@/api/cuentas'
import {
  formatearCuit,
  TIPOS_CUENTA,
  type Cliente,
  type Cuenta,
} from '@/api/tipos'
import EmptyState from '@/components/ui/EmptyState.vue'
import Modal from '@/components/ui/Modal.vue'
import PageHeader from '@/components/ui/PageHeader.vue'

interface Nodo {
  cuenta: Cuenta
  hijos: Nodo[]
  nivel: number
}

const route = useRoute()
const clienteId = computed(() => Number(route.params.id))

const cliente = ref<Cliente | null>(null)
const cuentas = ref<Cuenta[]>([])
const cargando = ref(true)
const error = ref('')
const busqueda = ref('')
const expandidos = ref<Set<number>>(new Set())

const aviso = ref<{ tipo: 'ok' | 'error'; texto: string } | null>(null)
const vista = ref<'arbol' | 'lista'>('arbol')

/* ------------------------------------------------------------------ Árbol */
function construirArbol(lista: Cuenta[]): Nodo[] {
  const porId = new Map<number, Nodo>()
  for (const cuenta of lista) {
    porId.set(cuenta.id, { cuenta, hijos: [], nivel: 0 })
  }

  const raices: Nodo[] = []

  for (const nodo of porId.values()) {
    const padre = nodo.cuenta.padre_id ? porId.get(nodo.cuenta.padre_id) : undefined
    if (padre) padre.hijos.push(nodo)
    else raices.push(nodo)
  }

  const ordenar = (nodos: Nodo[], nivel: number) => {
    nodos.sort((a, b) => a.cuenta.codigo.localeCompare(b.cuenta.codigo))
    for (const nodo of nodos) {
      nodo.nivel = nivel
      ordenar(nodo.hijos, nivel + 1)
    }
  }

  ordenar(raices, 0)
  return raices
}

const arbol = computed(() => construirArbol(cuentas.value))

interface Fila {
  cuenta: Cuenta
  nivel: number
  tieneHijos: boolean
}

const filas = computed<Fila[]>(() => {
  const termino = busqueda.value.trim().toLowerCase()

  if (termino) {
    return cuentas.value
      .filter(
        (cuenta) =>
          cuenta.codigo.toLowerCase().includes(termino) ||
          cuenta.nombre.toLowerCase().includes(termino),
      )
      .map((cuenta) => ({ cuenta, nivel: 0, tieneHijos: false }))
  }

  if (vista.value === 'lista') {
    return cuentas.value.map((cuenta) => ({
      cuenta,
      nivel: 0,
      tieneHijos: false,
    }))
  }

  const salida: Fila[] = []

  const recorrer = (nodos: Nodo[]) => {
    for (const nodo of nodos) {
      salida.push({
        cuenta: nodo.cuenta,
        nivel: nodo.nivel,
        tieneHijos: nodo.hijos.length > 0,
      })
      if (expandidos.value.has(nodo.cuenta.id)) recorrer(nodo.hijos)
    }
  }

  recorrer(arbol.value)
  return salida
})

/* ------------------------------------------------------------------ Carga */
async function cargar() {
  cargando.value = true
  error.value = ''

  try {
    const [datosCliente, lista] = await Promise.all([
      clientesApi.obtener(clienteId.value),
      cuentasApi.listar(clienteId.value),
    ])
    cliente.value = datosCliente
    cuentas.value = lista
    expandidos.value = new Set(lista.map((cuenta) => cuenta.id))
  } catch (e) {
    error.value =
      e instanceof ApiError ? e.mensaje : 'No pudimos cargar el plan de cuentas.'
  } finally {
    cargando.value = false
  }
}

onMounted(cargar)

function alternar(id: number) {
  const copia = new Set(expandidos.value)
  if (copia.has(id)) copia.delete(id)
  else copia.add(id)
  expandidos.value = copia
}

/* ------------------------------------------------------------------ Modal */
const modalAbierto = ref(false)
const cuentaEnEdicion = ref<Cuenta | null>(null)
const form = reactive({
  codigo: '',
  nombre: '',
  tipo: 'activo',
  padre_id: null as number | null,
  imputable: false,
})
const errores = reactive<Record<string, string>>({})
const errorGeneral = ref('')
const guardando = ref(false)

const esAlta = computed(() => cuentaEnEdicion.value === null)
const tituloModal = computed(() =>
  esAlta.value ? 'Nueva cuenta' : 'Editar cuenta',
)

/* Los padres posibles excluyen la cuenta y sus descendientes (evita ciclos). */
const padresPosibles = computed(() => {
  if (!cuentaEnEdicion.value) return cuentas.value
  const prohibidos = new Set<number>([cuentaEnEdicion.value.id])
  let cambio = true
  while (cambio) {
    cambio = false
    for (const cuenta of cuentas.value) {
      if (cuenta.padre_id && prohibidos.has(cuenta.padre_id) && !prohibidos.has(cuenta.id)) {
        prohibidos.add(cuenta.id)
        cambio = true
      }
    }
  }
  return cuentas.value.filter((cuenta) => !prohibidos.has(cuenta.id))
})

function siguienteCodigo(padre: Cuenta | null): string {
  if (!padre) return ''

  const prefijo = `${padre.codigo}.`
  const hermanos = cuentas.value.filter((cuenta) => cuenta.padre_id === padre.id)

  const numeros = hermanos
    .map((cuenta) => Number(cuenta.codigo.slice(prefijo.length)))
    .filter((numero) => Number.isFinite(numero))

  const siguiente = (numeros.length ? Math.max(...numeros) : 0) + 1
  return `${prefijo}${String(siguiente).padStart(2, '0')}`
}

function abrirAlta(padre: Cuenta | null = null) {
  cuentaEnEdicion.value = null
  form.codigo = siguienteCodigo(padre)
  form.nombre = ''
  form.tipo = padre?.tipo ?? 'activo'
  form.padre_id = padre?.id ?? null
  form.imputable = true
  errorGeneral.value = ''
  for (const clave of Object.keys(errores)) delete errores[clave]
  modalAbierto.value = true
}

function abrirEdicion(cuenta: Cuenta) {
  cuentaEnEdicion.value = cuenta
  form.codigo = cuenta.codigo
  form.nombre = cuenta.nombre
  form.tipo = cuenta.tipo
  form.padre_id = cuenta.padre_id
  form.imputable = cuenta.imputable
  errorGeneral.value = ''
  for (const clave of Object.keys(errores)) delete errores[clave]
  modalAbierto.value = true
}

function validar(): boolean {
  for (const clave of Object.keys(errores)) delete errores[clave]

  if (!form.codigo.trim()) errores.codigo = 'El código es obligatorio.'
  if (form.nombre.trim().length < 2) errores.nombre = 'Ingresá el nombre de la cuenta.'

  return Object.keys(errores).length === 0
}

function mapearDetalles(detalles?: Record<string, unknown>) {
  if (!detalles) return
  for (const [campo, valor] of Object.entries(detalles)) {
    const primero = Array.isArray(valor) ? valor[0] : valor
    errores[campo] = String(primero ?? 'Dato inválido.')
  }
}

function avisar(tipo: 'ok' | 'error', texto: string) {
  aviso.value = { tipo, texto }
  window.setTimeout(() => (aviso.value = null), 4000)
}

async function guardar() {
  if (guardando.value || !validar()) return

  guardando.value = true
  errorGeneral.value = ''

  try {
    if (esAlta.value) {
      const creada = await cuentasApi.crear(clienteId.value, {
        codigo: form.codigo.trim(),
        nombre: form.nombre.trim(),
        tipo: form.tipo,
        padre_id: form.padre_id,
        imputable: form.imputable,
      })
      avisar('ok', `Cuenta ${creada.codigo} creada.`)
    } else if (cuentaEnEdicion.value) {
      await cuentasApi.actualizar(cuentaEnEdicion.value.id, {
        nombre: form.nombre.trim(),
        padre_id: form.padre_id,
        imputable: form.imputable,
      })
      avisar('ok', 'Cuenta actualizada.')
    }

    modalAbierto.value = false
    await cargar()
  } catch (e) {
    if (e instanceof ApiError) {
      errorGeneral.value = e.mensaje
      mapearDetalles(e.detalles)
    } else {
      errorGeneral.value = 'No pudimos guardar la cuenta.'
    }
  } finally {
    guardando.value = false
  }
}

/* ------------------------------------------------------------------- Baja */
const bajaAbierta = ref(false)
const cuentaBaja = ref<Cuenta | null>(null)
const eliminando = ref(false)

function abrirBaja(cuenta: Cuenta) {
  cuentaBaja.value = cuenta
  bajaAbierta.value = true
}

async function confirmarBaja() {
  if (!cuentaBaja.value || eliminando.value) return

  eliminando.value = true
  try {
    await cuentasApi.eliminar(cuentaBaja.value.id)
    bajaAbierta.value = false
    avisar('ok', 'Cuenta eliminada.')
    await cargar()
  } catch (e) {
    bajaAbierta.value = false
    avisar(
      'error',
      e instanceof ApiError ? e.mensaje : 'No pudimos eliminar la cuenta.',
    )
  } finally {
    eliminando.value = false
  }
}
</script>

<template>
  <section class="plan">
    <RouterLink :to="{ name: 'cliente', params: { id: clienteId } }" class="volver">
      <svg viewBox="0 0 16 16" width="14" height="14" fill="none" aria-hidden="true">
        <path d="M13 8H4M7.4 4.4 3.8 8l3.6 3.6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" />
      </svg>
      Ficha del cliente
    </RouterLink>

    <PageHeader eyebrow="Contabilidad" title="Plan de cuentas" :show-sub="!!cliente">
      <template #sub>
        {{ cliente?.razon_social }} ·
        <span class="tabular">{{ formatearCuit(cliente?.cuit ?? '') }}</span>
      </template>

      <template #actions>
        <button class="btn btn--primary" type="button" :disabled="!cliente" @click="abrirAlta()">
          <svg viewBox="0 0 16 16" width="14" height="14" fill="none" aria-hidden="true">
            <path d="M8 3v10M3 8h10" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" />
          </svg>
          Nueva cuenta
        </button>
      </template>
    </PageHeader>

    <div class="toolbar">
      <div class="toolbar__busqueda">
        <svg viewBox="0 0 16 16" width="14" height="14" fill="none" aria-hidden="true">
          <circle cx="7" cy="7" r="4.5" stroke="currentColor" stroke-width="1.5" />
          <path d="m10.4 10.4 3 3" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
        </svg>
        <input
          v-model="busqueda"
          class="input"
          type="search"
          placeholder="Buscar por código o nombre"
          aria-label="Buscar cuentas"
        />
      </div>
      <span class="toolbar__meta">{{ cuentas.length }} cuentas</span>
      <div class="vistas" role="tablist" aria-label="Vista">
        <button class="vistas__boton" :class="{ 'is-activa': vista === 'arbol' }" type="button" @click="vista = 'arbol'">Árbol</button>
        <button class="vistas__boton" :class="{ 'is-activa': vista === 'lista' }" type="button" @click="vista = 'lista'">Lista</button>
      </div>
    </div>

    <p v-if="aviso" class="alert" :class="`alert--${aviso.tipo}`" role="status">
      {{ aviso.texto }}
    </p>

    <div v-if="error" class="alert alert--error" role="alert">
      <span>{{ error }}</span>
      <button class="btn btn--sm" type="button" @click="cargar">Reintentar</button>
    </div>

    <div class="card plan__card">
      <EmptyState v-if="cargando" loading>Cargando plan…</EmptyState>

      <ul v-else class="arbol">
        <li
          v-for="fila in filas"
          :key="fila.cuenta.id"
          class="nodo"
          :class="{ 'is-grupo': fila.tieneHijos, 'is-inactiva': !fila.cuenta.activa }"
          :style="{ '--nivel': fila.nivel }"
        >
          <button
            v-if="fila.tieneHijos && !busqueda"
            class="nodo__chevron"
            type="button"
            :aria-label="expandidos.has(fila.cuenta.id) ? 'Contraer' : 'Expandir'"
            :aria-expanded="expandidos.has(fila.cuenta.id)"
            @click="alternar(fila.cuenta.id)"
          >
            <svg
              viewBox="0 0 12 12"
              width="11"
              height="11"
              fill="none"
              :class="{ 'is-abierto': expandidos.has(fila.cuenta.id) }"
              aria-hidden="true"
            >
              <path d="m4 2.5 3.5 3.5L4 9.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
          </button>
          <span v-else class="nodo__chevron nodo__chevron--vacio" aria-hidden="true"></span>

          <span class="nodo__codigo tabular">{{ fila.cuenta.codigo }}</span>
          <span class="nodo__nombre">{{ fila.cuenta.nombre }}</span>

          <span class="nodo__badges">
            <span v-if="fila.cuenta.imputable" class="badge badge--ok">Imputable</span>
            <span v-else class="badge badge--muted">Agrupadora</span>
            <span v-if="!fila.cuenta.activa" class="badge badge--muted">Inactiva</span>
          </span>

          <span class="nodo__acciones">
            <button
              class="icon-btn"
              type="button"
              :aria-label="`Agregar subcuenta a ${fila.cuenta.nombre}`"
              title="Agregar subcuenta"
              @click="abrirAlta(fila.cuenta)"
            >
              <svg viewBox="0 0 16 16" width="14" height="14" fill="none" aria-hidden="true">
                <path d="M8 3.5v9M3.5 8h9" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
              </svg>
            </button>

            <button
              class="icon-btn"
              type="button"
              :aria-label="`Editar ${fila.cuenta.nombre}`"
              title="Editar"
              @click="abrirEdicion(fila.cuenta)"
            >
              <svg viewBox="0 0 16 16" width="14" height="14" fill="none" aria-hidden="true">
                <path
                  d="M11.2 2.6a1.6 1.6 0 0 1 2.2 2.2L5.8 12.4l-3 .8.8-3 7.6-7.6Z"
                  stroke="currentColor"
                  stroke-width="1.4"
                  stroke-linejoin="round"
                />
              </svg>
            </button>

            <button
              class="icon-btn icon-btn--peligro"
              type="button"
              :disabled="fila.tieneHijos"
              :title="fila.tieneHijos ? 'Tiene subcuentas: no se puede eliminar' : 'Eliminar'"
              :aria-label="`Eliminar ${fila.cuenta.nombre}`"
              @click="abrirBaja(fila.cuenta)"
            >
              <svg viewBox="0 0 16 16" width="14" height="14" fill="none" aria-hidden="true">
                <path d="M3.5 5h9M6.5 5V3.2h3V5M4.8 5l.5 8h5.4l.5-8" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" />
              </svg>
            </button>
          </span>
        </li>
      </ul>
    </div>

    <p class="plan__pie">
      Sólo las cuentas imputables reciben movimientos. Las agrupadoras ordenan la
      jerarquía.
    </p>

    <!-- Alta / edición -->
    <Modal :abierto="modalAbierto" :titulo="tituloModal" @cerrar="modalAbierto = false">
      <form id="form-cuenta" class="formulario" novalidate @submit.prevent="guardar">
        <div class="fila">
          <div class="field">
            <label class="field__label" for="cuenta-codigo">Código</label>
            <input
              id="cuenta-codigo"
              v-model="form.codigo"
              class="input tabular"
              type="text"
              placeholder="1.1.03"
              :disabled="!esAlta"
              :aria-invalid="Boolean(errores.codigo)"
            />
            <p v-if="errores.codigo" class="field__error">{{ errores.codigo }}</p>
          </div>

          <div class="field">
            <label class="field__label" for="cuenta-tipo">Tipo</label>
            <select id="cuenta-tipo" v-model="form.tipo" class="input select" :disabled="!esAlta">
              <option v-for="tipo in TIPOS_CUENTA" :key="tipo.valor" :value="tipo.valor">
                {{ tipo.etiqueta }}
              </option>
            </select>
          </div>
        </div>

        <div class="field">
          <label class="field__label" for="cuenta-nombre">Nombre</label>
          <input
            id="cuenta-nombre"
            v-model="form.nombre"
            class="input"
            type="text"
            placeholder="Caja chica"
            :aria-invalid="Boolean(errores.nombre)"
          />
          <p v-if="errores.nombre" class="field__error">{{ errores.nombre }}</p>
        </div>

        <div class="field">
          <label class="field__label" for="cuenta-padre">Cuenta padre</label>
          <select id="cuenta-padre" v-model="form.padre_id" class="input select">
            <option :value="null">Sin padre (raíz)</option>
            <option v-for="cuenta in padresPosibles" :key="cuenta.id" :value="cuenta.id">
              {{ cuenta.codigo }} · {{ cuenta.nombre }}
            </option>
          </select>
        </div>

        <label class="check">
          <input v-model="form.imputable" type="checkbox" />
          <span>
            Imputable
            <span class="check__ayuda">Puede recibir movimientos en asientos.</span>
          </span>
        </label>

        <p v-if="errorGeneral" class="alert alert--error" role="alert">
          {{ errorGeneral }}
        </p>
      </form>

      <template #pie>
        <button class="btn" type="button" @click="modalAbierto = false">Cancelar</button>
        <button class="btn btn--primary" type="submit" form="form-cuenta" :disabled="guardando">
          {{ guardando ? 'Guardando…' : esAlta ? 'Crear cuenta' : 'Guardar cambios' }}
        </button>
      </template>
    </Modal>

    <!-- Baja -->
    <Modal :abierto="bajaAbierta" titulo="Eliminar cuenta" @cerrar="bajaAbierta = false">
      <p class="texto-baja">
        ¿Eliminar la cuenta <strong>{{ cuentaBaja?.codigo }} · {{ cuentaBaja?.nombre }}</strong>?
      </p>
      <p class="texto-baja texto-baja--suave">
        Sólo se puede eliminar si no tiene subcuentas ni movimientos.
      </p>

      <template #pie>
        <button class="btn" type="button" @click="bajaAbierta = false">Cancelar</button>
        <button class="btn btn--danger" type="button" :disabled="eliminando" @click="confirmarBaja">
          {{ eliminando ? 'Eliminando…' : 'Eliminar' }}
        </button>
      </template>
    </Modal>
  </section>
</template>

<style scoped>
.plan {
  display: grid;
  gap: var(--space-5);
}

.toolbar__meta {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--color-text-faint);
}

.vistas { display: flex; border: 1px solid var(--color-line-strong); border-radius: var(--radius-sm); overflow: hidden; margin-left: auto; }
.vistas__boton { padding: 0 var(--space-3); min-height: 2.5rem; border: 0; background: transparent; color: var(--color-text-muted); font-size: var(--text-xs); cursor: pointer; }
.vistas__boton.is-activa { background: rgb(43 217 138 / 12%); color: var(--color-accent); }

.plan__card {
  padding: var(--space-2) 0;
  overflow: hidden;
}

.arbol {
  display: grid;
  padding: 0;
  margin: 0;
  list-style: none;
}

.nodo {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: 0.45rem var(--space-4);
  padding-left: calc(var(--space-4) + var(--nivel) * 1.35rem);
  border-bottom: 1px solid var(--color-line);
  transition: background-color var(--dur-fast) var(--ease-out);
}

.nodo:last-child {
  border-bottom: 0;
}

.nodo:hover {
  background: rgb(255 255 255 / 2.5%);
}

.nodo.is-inactiva {
  opacity: 0.5;
}

.nodo.is-grupo .nodo__nombre {
  color: var(--color-text-muted);
}

.nodo__chevron {
  display: grid;
  place-items: center;
  width: 1.25rem;
  height: 1.25rem;
  flex: none;
  border: 0;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--color-text-faint);
  cursor: pointer;
}

.nodo__chevron:hover {
  color: var(--color-text);
}

.nodo__chevron svg {
  transition: transform var(--dur-fast) var(--ease-out);
}

.nodo__chevron svg.is-abierto {
  transform: rotate(90deg);
}

.nodo__chevron--vacio {
  visibility: hidden;
}

.nodo__codigo {
  width: 4.5rem;
  flex: none;
  font-size: var(--text-xs);
  color: var(--color-text-faint);
}

.nodo__nombre {
  flex: 1;
  min-width: 0;
  font-size: var(--text-sm);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.nodo__badges {
  display: flex;
  gap: var(--space-2);
  flex: none;
}

.nodo__acciones {
  display: flex;
  gap: 2px;
  flex: none;
  opacity: 0.4;
  transition: opacity var(--dur-fast) var(--ease-out);
}

.nodo:hover .nodo__acciones,
.nodo:focus-within .nodo__acciones {
  opacity: 1;
}

.plan__pie {
  font-size: var(--text-xs);
  color: var(--color-text-faint);
}

.fila {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-4);
}

.check {
  display: flex;
  align-items: flex-start;
  gap: var(--space-3);
  font-size: var(--text-sm);
  cursor: pointer;
}

.check input {
  margin-top: 0.2rem;
  accent-color: var(--color-accent);
}

.check__ayuda {
  display: block;
  font-size: var(--text-xs);
  color: var(--color-text-faint);
}

.texto-baja {
  font-size: var(--text-sm);
}

.texto-baja--suave {
  margin-top: var(--space-2);
  color: var(--color-text-muted);
}

@media (max-width: 48rem) {
  .nodo__badges {
    display: none;
  }

  .nodo__acciones {
    opacity: 1;
  }

  .fila {
    grid-template-columns: 1fr;
  }
}
</style>
