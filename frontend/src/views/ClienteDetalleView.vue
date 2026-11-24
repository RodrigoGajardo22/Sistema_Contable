<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import { ApiError } from '@/api/client'
import { clientesApi } from '@/api/clientes'
import {
  formatearCuit,
  type Cliente,
  type ClienteVersion,
  type Usuario,
} from '@/api/tipos'
import { usuariosApi } from '@/api/usuarios'
import AccesoCredencialesModal from '@/components/clientes/AccesoCredencialesModal.vue'
import ClienteFormModal from '@/components/clientes/ClienteFormModal.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import Modal from '@/components/ui/Modal.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const cliente = ref<Cliente | null>(null)
const historial = ref<ClienteVersion[]>([])
const contadores = ref<Usuario[]>([])
const cargando = ref(true)
const error = ref('')

const formAbierto = ref(false)
const bajaAbierta = ref(false)
const procesandoBaja = ref(false)
const aviso = ref<{ tipo: 'ok' | 'error'; texto: string } | null>(null)

let temporizadorAviso: number | undefined

const clienteId = computed(() => Number(route.params.id))

const puedeEditar = computed(() => {
  if (!cliente.value) return false
  return auth.esAdmin || cliente.value.contador_id === auth.usuario?.id
})

const esCliente = computed(() => auth.rol === 'cliente')

/* ---------------------------------------------------------- Acceso cliente */
const accesoAccion = ref<'crear' | 'reset' | null>(null)
const guardandoAcceso = ref(false)
const revocarAbierto = ref(false)
const credencialesAbiertas = ref(false)
const credencialesEmail = ref<string | null>(null)
const credencialesPassword = ref<string | null>(null)

const puedeGestionarAcceso = computed(() => puedeEditar.value && !esCliente.value)
const accesoActivo = computed(
  () => Boolean(cliente.value?.usuario_id && cliente.value?.usuario_activo),
)
const accesoRevocado = computed(
  () => Boolean(cliente.value?.usuario_id && !cliente.value?.usuario_activo),
)

async function confirmarAcceso() {
  if (!cliente.value || !accesoAccion.value || guardandoAcceso.value) return

  const accion = accesoAccion.value
  guardandoAcceso.value = true
  try {
    const acceso =
      accion === 'crear'
        ? await clientesApi.crearAcceso(cliente.value.id)
        : await clientesApi.restablecerAcceso(cliente.value.id)

    accesoAccion.value = null
    credencialesEmail.value = acceso.email
    credencialesPassword.value = acceso.password_temporal
    credencialesAbiertas.value = true
    avisar(
      'ok',
      accion === 'crear'
        ? 'Acceso creado con una clave temporal.'
        : 'Clave temporal restablecida.',
    )
    await cargar()
  } catch (e) {
    accesoAccion.value = null
    avisar(
      'error',
      e instanceof ApiError ? e.mensaje : 'No pudimos gestionar el acceso.',
    )
  } finally {
    guardandoAcceso.value = false
  }
}

async function revocarAcceso() {
  if (!cliente.value) return
  try {
    await clientesApi.revocarAcceso(cliente.value.id)
    revocarAbierto.value = false
    avisar('ok', 'Acceso revocado.')
    await cargar()
  } catch (e) {
    revocarAbierto.value = false
    avisar('error', e instanceof ApiError ? e.mensaje : 'No pudimos revocar el acceso.')
  }
}

async function reactivarCliente() {
  if (!cliente.value) return
  try {
    cliente.value = await clientesApi.activar(cliente.value.id)
    avisar('ok', 'El cliente y su acceso volvieron a estar activos.')
  } catch (e) {
    avisar(
      'error',
      e instanceof ApiError ? e.mensaje : 'No pudimos reactivar al cliente.',
    )
  }
}

async function cargar() {
  cargando.value = true
  error.value = ''

  try {
    const [datos, versiones] = await Promise.all([
      clientesApi.obtener(clienteId.value),
      clientesApi.historial(clienteId.value),
    ])
    cliente.value = datos
    historial.value = versiones
  } catch (e) {
    error.value =
      e instanceof ApiError ? e.mensaje : 'No pudimos cargar la ficha del cliente.'
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

onMounted(() => {
  void cargar()
  void cargarContadores()
})

onBeforeUnmount(() => window.clearTimeout(temporizadorAviso))

function avisar(tipo: 'ok' | 'error', texto: string) {
  aviso.value = { tipo, texto }
  window.clearTimeout(temporizadorAviso)
  temporizadorAviso = window.setTimeout(() => (aviso.value = null), 4500)
}

async function alGuardar(actualizado: Cliente) {
  formAbierto.value = false
  cliente.value = actualizado
  avisar('ok', 'Datos actualizados. Se agregó una versión al historial.')

  if (actualizado.acceso_temporal) {
    credencialesEmail.value = actualizado.email
    credencialesPassword.value = actualizado.acceso_temporal
    credencialesAbiertas.value = true
  }

  await cargar()
}

async function confirmarBaja() {
  if (!cliente.value || procesandoBaja.value) return

  procesandoBaja.value = true
  try {
    cliente.value = await clientesApi.desactivar(cliente.value.id)
    bajaAbierta.value = false
    avisar('ok', 'El cliente quedó inactivo.')
  } catch (e) {
    bajaAbierta.value = false
    avisar(
      'error',
      e instanceof ApiError ? e.mensaje : 'No pudimos dar de baja al cliente.',
    )
  } finally {
    procesandoBaja.value = false
  }
}

/* --------------------------------------------------------------- Historial */
const CAMPOS = [
  { clave: 'razon_social', etiqueta: 'Razón social' },
  { clave: 'condicion_iva_etiqueta', etiqueta: 'Condición IVA' },
  { clave: 'email', etiqueta: 'Email' },
  { clave: 'telefono', etiqueta: 'Teléfono' },
  { clave: 'direccion', etiqueta: 'Dirección' },
  { clave: 'contador_nombre', etiqueta: 'Responsable' },
] as const

interface Cambio {
  etiqueta: string
  antes: string
  despues: string
}

interface VersionConCambios {
  version: ClienteVersion
  esAlta: boolean
  cambios: Cambio[]
}

const historialConCambios = computed<VersionConCambios[]>(() => {
  return historial.value.map((version, indice) => {
    const anterior = historial.value[indice + 1]

    if (!anterior) {
      return { version, esAlta: true, cambios: [] }
    }

    const cambios: Cambio[] = []

    for (const campo of CAMPOS) {
      const antes = String(anterior[campo.clave] ?? '—')
      const despues = String(version[campo.clave] ?? '—')
      if (antes !== despues) {
        cambios.push({ etiqueta: campo.etiqueta, antes, despues })
      }
    }

    return { version, esAlta: false, cambios }
  })
})

const fechaHora = new Intl.DateTimeFormat('es-AR', {
  dateStyle: 'medium',
  timeStyle: 'short',
  hour12: false,
})

const fecha = new Intl.DateTimeFormat('es-AR', { dateStyle: 'medium' })

function valor(texto: string | null | undefined): string {
  return texto && texto.trim() ? texto : '—'
}
</script>

<template>
  <section class="detalle">
    <RouterLink :to="{ name: esCliente ? 'dashboard' : 'clientes' }" class="volver">
      <svg viewBox="0 0 16 16" width="14" height="14" fill="none" aria-hidden="true">
        <path d="M13 8H4M7.4 4.4 3.8 8l3.6 3.6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" />
      </svg>
      {{ esCliente ? 'Panel' : 'Clientes' }}
    </RouterLink>

    <EmptyState v-if="cargando" loading>Cargando ficha…</EmptyState>

    <div v-else-if="error" class="card estado estado--error">
      <p>{{ error }}</p>
      <button class="btn btn--sm" type="button" @click="router.replace({ name: 'clientes' })">
        Volver a clientes
      </button>
    </div>

    <template v-else-if="cliente">
      <PageHeader
        :eyebrow="esCliente ? 'Mi información' : 'Ficha del cliente'"
        :title="cliente.razon_social"
      >
        <template #sub>
          <span class="detalle__meta">
            <span class="tabular">{{ formatearCuit(cliente.cuit) }}</span>
            <span class="badge">{{ cliente.condicion_iva_etiqueta }}</span>
            <span class="badge" :class="cliente.activo ? 'badge--ok' : 'badge--muted'">
              {{ cliente.activo ? 'Activo' : 'Inactivo' }}
            </span>
          </span>
        </template>

        <template #actions>
          <div v-if="puedeEditar" class="detalle__acciones">
            <button class="btn" type="button" @click="formAbierto = true">
              Editar datos
            </button>
            <button
              v-if="cliente.activo"
              class="btn btn--danger btn--sm"
              type="button"
              @click="bajaAbierta = true"
            >
              Dar de baja
            </button>
            <button
              v-else
              class="btn btn--primary btn--sm"
              type="button"
              @click="reactivarCliente"
            >
              Reactivar cliente
            </button>
          </div>
        </template>
      </PageHeader>

      <nav class="accesos" aria-label="Módulos del cliente">
        <RouterLink
          v-if="!esCliente"
          :to="{ name: 'cliente-cuentas', params: { id: clienteId } }"
          class="acceso"
        >
          <span class="acceso__icono" aria-hidden="true">
            <svg viewBox="0 0 20 20" width="16" height="16" fill="none">
              <path d="M3 4h14M3 9h9M3 14h6" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" />
            </svg>
          </span>
          <span class="acceso__texto">
            <span class="acceso__titulo">Plan de cuentas</span>
            <span class="acceso__nota">Estructura contable del cliente</span>
          </span>
        </RouterLink>

        <RouterLink
          v-if="!esCliente"
          :to="{ name: 'cliente-asientos', params: { id: clienteId } }"
          class="acceso"
        >
          <span class="acceso__icono" aria-hidden="true">
            <svg viewBox="0 0 20 20" width="16" height="16" fill="none">
              <rect x="3" y="3" width="14" height="14" rx="2" stroke="currentColor" stroke-width="1.4" />
              <path d="M6 7h8M6 10h8M6 13h5" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" />
            </svg>
          </span>
          <span class="acceso__texto">
            <span class="acceso__titulo">Libro diario</span>
            <span class="acceso__nota">Asientos y partida doble</span>
          </span>
        </RouterLink>

        <RouterLink
          :to="{ name: 'cliente-comprobantes', params: { id: clienteId } }"
          class="acceso"
        >
          <span class="acceso__icono" aria-hidden="true">
            <svg viewBox="0 0 20 20" width="16" height="16" fill="none">
              <path d="M5 3h7l3 3v11H5V3Z" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round" />
              <path d="M7 9h6M7 12h4" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" />
            </svg>
          </span>
          <span class="acceso__texto">
            <span class="acceso__titulo">Comprobantes</span>
            <span class="acceso__nota">Facturas y contabilización</span>
          </span>
        </RouterLink>

        <RouterLink
          :to="{ name: 'cliente-vencimientos', params: { id: clienteId } }"
          class="acceso"
        >
          <span class="acceso__icono" aria-hidden="true">
            <svg viewBox="0 0 20 20" width="16" height="16" fill="none">
              <rect x="3" y="4" width="14" height="13" rx="2" stroke="currentColor" stroke-width="1.4" />
              <path d="M3 8h14M7 2.5V6M13 2.5V6" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" />
            </svg>
          </span>
          <span class="acceso__texto">
            <span class="acceso__titulo">Vencimientos</span>
            <span class="acceso__nota">Obligaciones y alertas</span>
          </span>
        </RouterLink>

        <RouterLink
          :to="{ name: 'cliente-reportes', params: { id: clienteId } }"
          class="acceso"
        >
          <span class="acceso__icono" aria-hidden="true">
            <svg viewBox="0 0 20 20" width="16" height="16" fill="none">
              <path d="M3.5 16.5V11M8 16.5V6M12.5 16.5V9M17 16.5V3.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
            </svg>
          </span>
          <span class="acceso__texto">
            <span class="acceso__titulo">Reportes</span>
            <span class="acceso__nota">Balance, mayor, diario y IVA</span>
          </span>
        </RouterLink>

        <RouterLink
          v-if="!esCliente"
          :to="{ name: 'cliente-conciliacion', params: { id: clienteId } }"
          class="acceso"
        >
          <span class="acceso__icono" aria-hidden="true">
            <svg viewBox="0 0 20 20" width="16" height="16" fill="none">
              <path d="M3 15h4l2-4 3 3 2-6h3" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" />
              <path d="M3 4v13h14" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" />
            </svg>
          </span>
          <span class="acceso__texto">
            <span class="acceso__titulo">Conciliación</span>
            <span class="acceso__nota">Extractos y matching bancario</span>
          </span>
        </RouterLink>
      </nav>

      <p v-if="aviso" class="alert" :class="`alert--${aviso.tipo}`" role="status">
        {{ aviso.texto }}
      </p>

      <div class="grid">
        <article class="card bloque">
          <h2 class="bloque__titulo">Datos vigentes</h2>

          <dl class="datos">
            <div class="dato">
              <dt>Email</dt>
              <dd>{{ valor(cliente.email) }}</dd>
            </div>
            <div class="dato">
              <dt>Teléfono</dt>
              <dd class="tabular">{{ valor(cliente.telefono) }}</dd>
            </div>
            <div class="dato">
              <dt>Dirección</dt>
              <dd>{{ valor(cliente.direccion) }}</dd>
            </div>
            <div class="dato">
              <dt>Responsable</dt>
              <dd>
                {{ cliente.contador_nombre ?? 'Sin asignar' }}
                <a
                  v-if="cliente.contador_email"
                  class="dato__email"
                  :href="`mailto:${cliente.contador_email}`"
                >
                  {{ cliente.contador_email }}
                </a>
              </dd>
            </div>
          </dl>

          <p class="bloque__pie">
            Última actualización el {{ fecha.format(new Date(cliente.actualizado_en)) }}
            por {{ cliente.actualizado_por ?? 'el sistema' }}.
          </p>
        </article>

        <article v-if="!esCliente" class="card bloque">
          <header class="bloque__cabecera">
            <h2 class="bloque__titulo">Historial de cambios</h2>
            <span class="bloque__contador">
              {{ historial.length }} {{ historial.length === 1 ? 'versión' : 'versiones' }}
            </span>
          </header>

          <ol class="timeline">
            <li
              v-for="item in historialConCambios"
              :key="item.version.id"
              class="timeline__item"
            >
              <span class="timeline__punto" aria-hidden="true"></span>

              <div class="timeline__cuerpo">
                <p class="timeline__fecha">
                  {{ fechaHora.format(new Date(item.version.creado_en)) }}
                  <span class="timeline__autor">
                    · {{ item.version.creado_por ?? 'Sistema' }}
                  </span>
                </p>

                <p v-if="item.esAlta" class="timeline__alta">
                  Alta del cliente (versión inicial)
                </p>

                <ul v-else-if="item.cambios.length" class="cambios">
                  <li v-for="cambio in item.cambios" :key="cambio.etiqueta" class="cambio">
                    <span class="cambio__campo">{{ cambio.etiqueta }}</span>
                    <span class="cambio__antes">{{ cambio.antes }}</span>
                    <span class="cambio__flecha" aria-hidden="true">→</span>
                    <span class="cambio__despues">{{ cambio.despues }}</span>
                  </li>
                </ul>

                <p v-else class="timeline__sin-cambios">
                  Sin cambios de datos.
                </p>
              </div>
            </li>
          </ol>
        </article>
      </div>

      <article v-if="puedeGestionarAcceso" class="card bloque">
        <header class="bloque__cabecera">
          <h2 class="bloque__titulo">Acceso al sistema</h2>
          <span class="badge" :class="accesoActivo ? 'badge--ok' : 'badge--muted'">
            {{ accesoActivo ? 'Activo' : accesoRevocado ? 'Revocado' : 'Sin acceso' }}
          </span>
        </header>

        <template v-if="!cliente.activo">
          <p class="texto-baja texto-baja--suave">
            El cliente está inactivo y su acceso quedó bloqueado. Reactivá el
            cliente para habilitarlo de nuevo.
          </p>
        </template>

        <template v-else-if="!cliente.usuario_id">
          <p class="texto-baja texto-baja--suave">
            El cliente no tiene un usuario vinculado. Se creará con el email de
            la ficha y una contraseña temporal.
          </p>
          <button class="btn" type="button" @click="accesoAccion = 'crear'">
            Crear acceso
          </button>
        </template>

        <template v-else>
          <p class="texto-baja">
            <strong>{{ cliente.usuario_email }}</strong>
            {{ accesoActivo ? 'puede ingresar al portal.' : 'tiene el acceso revocado.' }}
            Puede consultar su ficha, comprobantes, vencimientos y reportes.
          </p>
          <div class="acciones-acceso">
            <button class="btn btn--sm" type="button" @click="accesoAccion = 'reset'">
              {{ accesoActivo ? 'Restablecer contraseña' : 'Restablecer acceso' }}
            </button>
            <button
              v-if="accesoActivo"
              class="btn btn--danger btn--sm"
              type="button"
              @click="revocarAbierto = true"
            >
              Revocar acceso
            </button>
          </div>
        </template>
      </article>
    </template>

    <ClienteFormModal
      :abierto="formAbierto"
      :cliente="cliente"
      :contadores="contadores"
      :es-admin="auth.esAdmin"
      @cerrar="formAbierto = false"
      @guardado="alGuardar"
    />

    <Modal :abierto="bajaAbierta" titulo="Dar de baja al cliente" @cerrar="bajaAbierta = false">
      <p class="texto-baja">
        ¿Seguro que querés dar de baja a <strong>{{ cliente?.razon_social }}</strong>?
      </p>
      <p class="texto-baja texto-baja--suave">
        Queda inactivo y conserva todo su historial. Un administrador puede
        reactivarlo.
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

    <!-- Gestión del acceso -->
    <Modal
      :abierto="accesoAccion !== null"
      :titulo="accesoAccion === 'crear' ? 'Crear acceso' : 'Restablecer acceso'"
      @cerrar="accesoAccion = null"
    >
      <p class="texto-baja">
        {{
          accesoAccion === 'crear'
            ? 'Se creará el usuario cliente con el email de la ficha y una contraseña temporal.'
            : 'Se generará una contraseña temporal nueva y se cerrarán las sesiones abiertas del cliente.'
        }}
      </p>
      <p class="texto-baja texto-baja--suave">
        La contraseña se muestra una sola vez. El cliente deberá cambiarla al
        ingresar.
      </p>

      <template #pie>
        <button class="btn" type="button" @click="accesoAccion = null">Cancelar</button>
        <button
          class="btn btn--primary"
          type="button"
          :disabled="guardandoAcceso"
          @click="confirmarAcceso"
        >
          {{ guardandoAcceso ? 'Generando…' : 'Continuar' }}
        </button>
      </template>
    </Modal>

    <AccesoCredencialesModal
      :abierto="credencialesAbiertas"
      titulo="Acceso del cliente"
      :email="credencialesEmail"
      :password="credencialesPassword"
      nota="Si cerrás este aviso, podés generar una nueva clave desde esta misma ficha."
      @cerrar="credencialesAbiertas = false"
    />

    <Modal :abierto="revocarAbierto" titulo="Revocar acceso" @cerrar="revocarAbierto = false">
      <p class="texto-baja">
        El usuario de <strong>{{ cliente?.razon_social }}</strong> quedará
        inactivo y no podrá ingresar. ¿Continuar?
      </p>
      <template #pie>
        <button class="btn" type="button" @click="revocarAbierto = false">Cancelar</button>
        <button class="btn btn--danger" type="button" @click="revocarAcceso">Revocar</button>
      </template>
    </Modal>
  </section>
</template>

<style scoped>
.detalle {
  display: grid;
  gap: var(--space-5);
}

.detalle__meta {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-wrap: wrap;
  font-size: var(--text-sm);
  color: var(--color-text-muted);
}

.detalle__acciones {
  display: flex;
  gap: var(--space-2);
}

.acciones-acceso {
  display: flex;
  gap: var(--space-2);
  flex-wrap: wrap;
}

.accesos {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(14rem, 1fr));
  gap: var(--space-3);
}

.acceso {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-4);
  border: 1px solid var(--color-line);
  border-radius: var(--radius-md);
  background: rgb(255 255 255 / 1.5%);
  text-decoration: none;
  color: inherit;
  transition:
    border-color var(--dur-fast) var(--ease-out),
    background-color var(--dur-fast) var(--ease-out),
    transform var(--dur-fast) var(--ease-out);
}

.acceso:hover {
  border-color: var(--color-line-strong);
  background: rgb(255 255 255 / 3%);
  transform: translateY(-1px);
}

.acceso__icono {
  display: grid;
  place-items: center;
  width: 2.25rem;
  height: 2.25rem;
  flex: none;
  border: 1px solid var(--color-line-strong);
  border-radius: var(--radius-sm);
  color: var(--color-accent);
}

.acceso__texto {
  display: grid;
  gap: 0.1rem;
}

.acceso__titulo {
  font-size: var(--text-sm);
  font-weight: 500;
}

.acceso__nota {
  font-size: var(--text-xs);
  color: var(--color-text-faint);
}

.grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1.1fr);
  gap: var(--space-4);
  align-items: start;
}

.bloque {
  display: grid;
  gap: var(--space-4);
  padding: clamp(1.25rem, 3vw, 1.75rem);
}

.bloque__cabecera {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--space-3);
}

.bloque__titulo {
  font-size: var(--text-lg);
}

.bloque__contador {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--color-text-faint);
}

.bloque__pie {
  padding-top: var(--space-3);
  border-top: 1px solid var(--color-line);
  font-size: var(--text-xs);
  color: var(--color-text-faint);
}

.datos {
  display: grid;
  gap: var(--space-4);
  margin: 0;
}

.dato {
  display: grid;
  gap: 0.15rem;
}

.dato dt {
  font-size: var(--text-xs);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--color-text-faint);
}

.dato dd {
  margin: 0;
  font-size: var(--text-sm);
}

.dato__email {
  display: block;
  margin-top: 0.1rem;
  font-size: var(--text-xs);
  color: var(--color-text-muted);
  text-decoration: none;
}

.dato__email:hover {
  color: var(--color-accent);
}

/* ---------------------------------------------------------------- Timeline */
.timeline {
  display: grid;
  gap: var(--space-4);
  padding: 0;
  margin: 0;
  list-style: none;
}

.timeline__item {
  position: relative;
  display: grid;
  grid-template-columns: 0.75rem 1fr;
  gap: var(--space-3);
}

.timeline__item:not(:last-child)::before {
  content: '';
  position: absolute;
  top: 0.75rem;
  bottom: calc(var(--space-4) * -1);
  left: 0.3rem;
  width: 1px;
  background: var(--color-line);
}

.timeline__punto {
  width: 0.6rem;
  height: 0.6rem;
  margin-top: 0.35rem;
  border-radius: 999px;
  border: 1px solid var(--color-line-strong);
  background: var(--color-surface);
}

.timeline__item:first-child .timeline__punto {
  border-color: transparent;
  background: var(--color-accent);
  box-shadow: 0 0 0 3px rgb(43 217 138 / 12%);
}

.timeline__cuerpo {
  display: grid;
  gap: var(--space-2);
  padding-bottom: var(--space-1);
}

.timeline__fecha {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--color-text-faint);
}

.timeline__autor {
  color: var(--color-text-muted);
}

.timeline__alta {
  font-size: var(--text-sm);
  color: var(--color-text);
}

.timeline__sin-cambios {
  font-size: var(--text-xs);
  color: var(--color-text-faint);
}

.cambios {
  display: grid;
  gap: var(--space-2);
  padding: 0;
  margin: 0;
  list-style: none;
}

.cambio {
  display: flex;
  align-items: baseline;
  gap: var(--space-2);
  flex-wrap: wrap;
  font-size: var(--text-sm);
}

.cambio__campo {
  min-width: 6.5rem;
  font-size: var(--text-xs);
  color: var(--color-text-faint);
}

.cambio__antes {
  color: var(--color-text-faint);
  text-decoration: line-through;
}

.cambio__flecha {
  color: var(--color-text-faint);
}

.cambio__despues {
  color: var(--color-accent);
}

.estado--error {
  padding: var(--space-8);
}

.texto-baja {
  font-size: var(--text-sm);
}

.texto-baja--suave {
  margin-top: var(--space-2);
  color: var(--color-text-muted);
}

@media (max-width: 62rem) {
  .grid {
    grid-template-columns: 1fr;
  }
}
</style>
