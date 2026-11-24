<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

import { ApiError } from '@/api/client'
import { clientesApi } from '@/api/clientes'
import { formatearCuit, type Cliente, type Usuario } from '@/api/tipos'
import { usuariosApi } from '@/api/usuarios'
import AccesoCredencialesModal from '@/components/clientes/AccesoCredencialesModal.vue'
import ClienteFormModal from '@/components/clientes/ClienteFormModal.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import Modal from '@/components/ui/Modal.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import TableCard from '@/components/ui/TableCard.vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const route = useRoute()

const esContador = computed(() => auth.rol === 'contador')
const puedeCrear = computed(() => auth.puede('admin', 'contador'))
const titulo = computed(() => (esContador.value ? 'Mi cartera' : 'Clientes'))

const clientes = ref<Cliente[]>([])
const contadores = ref<Usuario[]>([])
const total = ref(0)
const cargando = ref(true)
const errorCarga = ref('')

const filtros = reactive<{ q: string; activo: 'todos' | 'activos' | 'inactivos' }>({
  q: '',
  activo: 'todos',
})

const aviso = ref<{ tipo: 'ok' | 'error'; texto: string } | null>(null)

const formAbierto = ref(false)
const clienteEnEdicion = ref<Cliente | null>(null)

const credencialesAbiertas = ref(false)
const credencialesEmail = ref<string | null>(null)
const credencialesPassword = ref<string | null>(null)

const bajaAbierta = ref(false)
const clienteBaja = ref<Cliente | null>(null)
const procesandoBaja = ref(false)

let temporizadorBusqueda: number | undefined
let temporizadorAviso: number | undefined

async function cargar() {
  cargando.value = true
  errorCarga.value = ''

  try {
    const respuesta = await clientesApi.listar({
      q: filtros.q,
      activo: filtros.activo,
    })
    clientes.value = respuesta.datos
    total.value = respuesta.total
  } catch (error) {
    errorCarga.value =
      error instanceof ApiError ? error.mensaje : 'No pudimos cargar los clientes.'
  } finally {
    cargando.value = false
  }
}

async function cargarContadores() {
  if (!auth.esAdmin) return
  try {
    const respuesta = await usuariosApi.listar({ activo: 'activos' })
    contadores.value = respuesta.datos.filter(
      (usuario) => usuario.rol === 'admin' || usuario.rol === 'contador',
    )
  } catch {
    contadores.value = []
  }
}

watch(
  () => filtros.q,
  () => {
    window.clearTimeout(temporizadorBusqueda)
    temporizadorBusqueda = window.setTimeout(cargar, 300)
  },
)

watch(
  () => filtros.activo,
  () => cargar(),
)

onMounted(async () => {
  await Promise.all([cargar(), cargarContadores()])
  if (route.query.nuevo === '1') abrirAlta()
})

onBeforeUnmount(() => {
  window.clearTimeout(temporizadorBusqueda)
  window.clearTimeout(temporizadorAviso)
})

function avisar(tipo: 'ok' | 'error', texto: string) {
  aviso.value = { tipo, texto }
  window.clearTimeout(temporizadorAviso)
  temporizadorAviso = window.setTimeout(() => (aviso.value = null), 4500)
}

function abrirAlta() {
  clienteEnEdicion.value = null
  formAbierto.value = true
}

function abrirEdicion(cliente: Cliente) {
  clienteEnEdicion.value = cliente
  formAbierto.value = true
}

function alGuardar(cliente: Cliente, esAlta: boolean) {
  formAbierto.value = false
  avisar(
    'ok',
    esAlta
      ? `Cliente ${cliente.razon_social} creado con su acceso al portal.`
      : `Datos de ${cliente.razon_social} actualizados (nueva versión).`,
  )

  if (cliente.acceso_temporal) {
    credencialesEmail.value = cliente.email
    credencialesPassword.value = cliente.acceso_temporal
    credencialesAbiertas.value = true
  }

  void cargar()
}

function abrirBaja(cliente: Cliente) {
  clienteBaja.value = cliente
  bajaAbierta.value = true
}

async function confirmarBaja() {
  if (!clienteBaja.value || procesandoBaja.value) return

  const objetivo = clienteBaja.value
  procesandoBaja.value = true

  try {
    await clientesApi.desactivar(objetivo.id)
    bajaAbierta.value = false
    avisar('ok', `${objetivo.razon_social} quedó inactivo.`)
    await cargar()
  } catch (error) {
    bajaAbierta.value = false
    avisar(
      'error',
      error instanceof ApiError ? error.mensaje : 'No pudimos dar de baja al cliente.',
    )
  } finally {
    procesandoBaja.value = false
  }
}

function puedeEditar(cliente: Cliente): boolean {
  return auth.esAdmin || cliente.contador_id === auth.usuario?.id
}

function accesoEtiqueta(cliente: Cliente): string {
  if (!cliente.activo) return 'Cliente inactivo'
  if (!cliente.usuario_id) return 'Sin acceso'
  return cliente.usuario_activo ? 'Activo' : 'Revocado'
}

function accesoClase(cliente: Cliente): string {
  if (!cliente.activo) return 'badge--muted'
  if (!cliente.usuario_id) return 'badge--muted'
  return cliente.usuario_activo ? 'badge--ok' : 'badge--danger'
}

function inicial(nombre: string): string {
  return nombre.trim().charAt(0).toUpperCase()
}

const fecha = new Intl.DateTimeFormat('es-AR', { dateStyle: 'medium' })
</script>

<template>
  <section class="clientes">
    <PageHeader
      :eyebrow="esContador ? 'Mi cartera' : 'Cartera'"
      :title="titulo"
      :subtitle="
        esContador
          ? 'Los clientes que tenés asignados y el estado de su acceso.'
          : 'Cada cambio de datos crea una versión nueva: nada se sobrescribe.'
      "
    >
      <template #actions>
        <button v-if="puedeCrear" class="btn btn--primary" type="button" @click="abrirAlta">
          <svg viewBox="0 0 16 16" width="14" height="14" fill="none" aria-hidden="true">
            <path d="M8 3v10M3 8h10" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" />
          </svg>
          Nuevo cliente
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
          v-model="filtros.q"
          class="input"
          type="search"
          placeholder="Buscar por razón social o CUIT"
          aria-label="Buscar clientes"
        />
      </div>

      <select v-model="filtros.activo" class="input select" aria-label="Filtrar por estado">
        <option value="todos">Todos</option>
        <option value="activos">Activos</option>
        <option value="inactivos">Inactivos</option>
      </select>
    </div>

    <p v-if="aviso" class="alert" :class="`alert--${aviso.tipo}`" role="status">
      {{ aviso.texto }}
    </p>

    <div v-if="errorCarga" class="alert alert--error" role="alert">
      <span>{{ errorCarga }}</span>
      <button class="btn btn--sm" type="button" @click="cargar">Reintentar</button>
    </div>

    <TableCard>
      <EmptyState v-if="cargando" loading>Cargando clientes…</EmptyState>

      <EmptyState v-else-if="clientes.length === 0">
        <p>No hay clientes que coincidan con el filtro.</p>
        <button v-if="puedeCrear" class="btn btn--sm" type="button" @click="abrirAlta">
          Cargar el primero
        </button>
      </EmptyState>

      <div v-else class="tabla-scroll">
        <table class="table">
          <thead>
            <tr>
              <th scope="col">Cliente</th>
              <th scope="col">IVA</th>
              <th scope="col">Acceso</th>
              <th scope="col" class="col-contador">Responsable</th>
              <th scope="col" class="col-fecha">Actualizado</th>
              <th scope="col"><span class="sr-only">Acciones</span></th>
            </tr>
          </thead>

          <tbody>
            <tr v-for="cliente in clientes" :key="cliente.id">
              <td>
                <RouterLink :to="`/clientes/${cliente.id}`" class="celda-cliente">
                  <span class="avatar avatar--sm" aria-hidden="true">
                    {{ inicial(cliente.razon_social) }}
                  </span>
                  <span class="celda-cliente__texto">
                    <span class="celda-cliente__nombre">{{ cliente.razon_social }}</span>
                    <span class="celda-cliente__cuit tabular">
                      {{ formatearCuit(cliente.cuit) }}
                    </span>
                  </span>
                </RouterLink>
              </td>

              <td>
                <span class="badge">{{ cliente.condicion_iva_etiqueta }}</span>
              </td>

              <td>
                <span class="badge" :class="accesoClase(cliente)">
                  {{ accesoEtiqueta(cliente) }}
                </span>
              </td>

              <td class="col-contador">
                <span :class="{ 'texto-suave': !cliente.contador_nombre }">
                  {{ cliente.contador_nombre ?? 'Sin asignar' }}
                </span>
              </td>

              <td class="col-fecha">
                <span class="texto-suave">{{ fecha.format(new Date(cliente.actualizado_en)) }}</span>
              </td>

              <td>
                <div class="acciones">
                  <button
                    v-if="puedeEditar(cliente)"
                    class="icon-btn"
                    type="button"
                    :aria-label="`Editar a ${cliente.razon_social}`"
                    title="Editar datos"
                    @click="abrirEdicion(cliente)"
                  >
                    <svg viewBox="0 0 16 16" width="15" height="15" fill="none" aria-hidden="true">
                      <path
                        d="M11.2 2.6a1.6 1.6 0 0 1 2.2 2.2L5.8 12.4l-3 .8.8-3 7.6-7.6Z"
                        stroke="currentColor"
                        stroke-width="1.4"
                        stroke-linejoin="round"
                      />
                    </svg>
                  </button>

                  <button
                    v-if="cliente.activo && puedeEditar(cliente)"
                    class="icon-btn icon-btn--peligro"
                    type="button"
                    title="Dar de baja"
                    :aria-label="`Dar de baja a ${cliente.razon_social}`"
                    @click="abrirBaja(cliente)"
                  >
                    <svg viewBox="0 0 16 16" width="15" height="15" fill="none" aria-hidden="true">
                      <circle cx="8" cy="8" r="5.5" stroke="currentColor" stroke-width="1.4" />
                      <path d="M4.4 4.4l7.2 7.2" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" />
                    </svg>
                  </button>

                  <RouterLink
                    :to="`/clientes/${cliente.id}`"
                    class="icon-btn"
                    title="Ver ficha"
                    :aria-label="`Ver ficha de ${cliente.razon_social}`"
                  >
                    <svg viewBox="0 0 16 16" width="15" height="15" fill="none" aria-hidden="true">
                      <path d="M3 8h9M8.6 4.4 12.2 8l-3.6 3.6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" />
                    </svg>
                  </RouterLink>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </TableCard>

    <p class="clientes__pie">
      {{ total }} {{ total === 1 ? 'cliente' : 'clientes' }} ·
      las bajas son lógicas y conservan todo el historial
    </p>

    <ClienteFormModal
      :abierto="formAbierto"
      :cliente="clienteEnEdicion"
      :contadores="contadores"
      :es-admin="auth.esAdmin"
      @cerrar="formAbierto = false"
      @guardado="alGuardar"
    />

    <AccesoCredencialesModal
      :abierto="credencialesAbiertas"
      titulo="Acceso creado"
      :email="credencialesEmail"
      :password="credencialesPassword"
      nota="Si cerrás este aviso, podés generar una nueva clave desde la ficha del cliente."
      @cerrar="credencialesAbiertas = false"
    />

    <Modal :abierto="bajaAbierta" titulo="Dar de baja al cliente" @cerrar="bajaAbierta = false">
      <p class="texto-baja">
        ¿Seguro que querés dar de baja a
        <strong>{{ clienteBaja?.razon_social }}</strong>?
      </p>
      <p class="texto-baja texto-baja--suave">
        Queda inactivo y conserva sus datos y versiones. No se puede deshacer
        desde acá, pero un administrador puede reactivarlo.
      </p>

      <template #pie>
        <button class="btn" type="button" @click="bajaAbierta = false">Cancelar</button>
        <button
          class="btn btn--danger"
          type="button"
          :disabled="procesandoBaja"
          @click="confirmarBaja"
        >
          {{ procesandoBaja ? 'Dando de baja…' : 'Dar de baja' }}
        </button>
      </template>
    </Modal>
  </section>
</template>

<style scoped>
.clientes {
  display: grid;
  gap: var(--space-5);
}

.toolbar .select {
  flex: 0 1 10rem;
}

.celda-cliente {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  text-decoration: none;
  color: inherit;
}

.celda-cliente__texto {
  display: grid;
  gap: 0.05rem;
}

.celda-cliente__nombre {
  font-size: var(--text-sm);
  font-weight: 500;
}

.celda-cliente__cuit {
  font-size: var(--text-xs);
  color: var(--color-text-faint);
}

.texto-suave {
  font-size: var(--text-xs);
  color: var(--color-text-faint);
}

.clientes__pie {
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
  .col-fecha,
  .col-contador {
    display: none;
  }

  .toolbar .select {
    flex: 1 1 auto;
  }
}
</style>
