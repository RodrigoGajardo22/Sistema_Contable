<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'

import { ApiError } from '@/api/client'
import { ETIQUETA_ROL, type Rol, type Usuario } from '@/api/tipos'
import { usuariosApi, type FiltroEstado } from '@/api/usuarios'
import EmptyState from '@/components/ui/EmptyState.vue'
import Modal from '@/components/ui/Modal.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import TableCard from '@/components/ui/TableCard.vue'
import UsuarioFormModal from '@/components/usuarios/UsuarioFormModal.vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()

const ROLES: Rol[] = ['admin', 'contador']

/* ---------------------------------------------------------------- Listado */
const usuarios = ref<Usuario[]>([])
const total = ref(0)
const cargando = ref(true)
const errorCarga = ref('')

const filtros = reactive<{ q: string; rol: Rol | ''; activo: FiltroEstado }>({
  q: '',
  rol: '',
  activo: 'todos',
})

const aviso = ref<{ tipo: 'ok' | 'error'; texto: string } | null>(null)

/* ----------------------------------------------------------------- Modales */
const formAbierto = ref(false)
const usuarioEnEdicion = ref<Usuario | null>(null)

const passwordAbierto = ref(false)
const usuarioPassword = ref<Usuario | null>(null)
const passwordActual = ref('')
const passwordNueva = ref('')
const passwordConfirmar = ref('')
const passwordError = ref('')
const guardandoPassword = ref(false)

const bajaAbierta = ref(false)
const usuarioBaja = ref<Usuario | null>(null)
const procesandoBaja = ref(false)

const detalleAbierto = ref(false)
const detalleUsuario = ref<Usuario | null>(null)

const transferirAbierto = ref(false)
const usuarioTransferir = ref<Usuario | null>(null)
const transfiriendo = ref(false)

function abrirDetalle(usuario: Usuario) {
  detalleUsuario.value = usuario
  detalleAbierto.value = true
}

function abrirTransferencia(usuario: Usuario) {
  usuarioTransferir.value = usuario
  transferirAbierto.value = true
}

async function transferirPropiedad() {
  if (!usuarioTransferir.value || transfiriendo.value) return

  transfiriendo.value = true
  try {
    await usuariosApi.transferirPropiedad(usuarioTransferir.value.id)
    transferirAbierto.value = false
    detalleAbierto.value = false
    avisar('ok', `${usuarioTransferir.value.nombre} es el nuevo propietario.`)
    await auth.cargarPerfil()
    await cargar()
  } catch (error) {
    transferirAbierto.value = false
    avisar(
      'error',
      error instanceof ApiError ? error.mensaje : 'No pudimos transferir la propiedad.',
    )
  } finally {
    transfiriendo.value = false
  }
}

const esPasswordPropia = computed(
  () => usuarioPassword.value?.id === auth.usuario?.id,
)

/* ------------------------------------------------------------------ Carga */
async function cargar() {
  cargando.value = true
  errorCarga.value = ''

  try {
    const respuesta = await usuariosApi.listar({
      q: filtros.q,
      rol: filtros.rol,
      activo: filtros.activo,
    })
    usuarios.value = respuesta.datos
    total.value = respuesta.total
  } catch (error) {
    errorCarga.value =
      error instanceof ApiError ? error.mensaje : 'No pudimos cargar los usuarios.'
  } finally {
    cargando.value = false
  }
}

let temporizadorBusqueda: number | undefined
let temporizadorAviso: number | undefined

watch(
  () => filtros.q,
  () => {
    window.clearTimeout(temporizadorBusqueda)
    temporizadorBusqueda = window.setTimeout(cargar, 300)
  },
)

watch([() => filtros.rol, () => filtros.activo], () => cargar())

onMounted(cargar)

onBeforeUnmount(() => {
  window.clearTimeout(temporizadorBusqueda)
  window.clearTimeout(temporizadorAviso)
})

function limpiarFiltros() {
  filtros.q = ''
  filtros.rol = ''
  filtros.activo = 'todos'
  void cargar()
}

function avisar(tipo: 'ok' | 'error', texto: string) {
  aviso.value = { tipo, texto }
  window.clearTimeout(temporizadorAviso)
  temporizadorAviso = window.setTimeout(() => (aviso.value = null), 4500)
}

/* ------------------------------------------------------------------- Altas */
function abrirAlta() {
  usuarioEnEdicion.value = null
  formAbierto.value = true
}

function abrirEdicion(usuario: Usuario) {
  usuarioEnEdicion.value = usuario
  formAbierto.value = true
}

function alGuardar(usuario: Usuario, esAlta: boolean) {
  formAbierto.value = false
  avisar('ok', esAlta ? `Usuario ${usuario.nombre} creado.` : `Usuario ${usuario.nombre} actualizado.`)
  void cargar()
}

/* --------------------------------------------------------------- Password */
function abrirPassword(usuario: Usuario) {
  usuarioPassword.value = usuario
  passwordActual.value = ''
  passwordNueva.value = ''
  passwordConfirmar.value = ''
  passwordError.value = ''
  passwordAbierto.value = true
}

async function guardarPassword() {
  if (!usuarioPassword.value || guardandoPassword.value) return

  passwordError.value = ''

  if (esPasswordPropia.value && passwordActual.value.length === 0) {
    passwordError.value = 'Ingresá tu contraseña actual.'
    return
  }
  if (passwordNueva.value.length < 8) {
    passwordError.value = 'La contraseña necesita al menos 8 caracteres.'
    return
  }
  if (passwordNueva.value !== passwordConfirmar.value) {
    passwordError.value = 'Las contraseñas no coinciden.'
    return
  }

  guardandoPassword.value = true

  try {
    await usuariosApi.cambiarPassword(usuarioPassword.value.id, {
      password_nueva: passwordNueva.value,
      ...(esPasswordPropia.value
        ? { password_actual: passwordActual.value }
        : {}),
    })
    passwordAbierto.value = false
    avisar('ok', `Contraseña de ${usuarioPassword.value.nombre} actualizada.`)
  } catch (error) {
    passwordError.value =
      error instanceof ApiError ? error.mensaje : 'No pudimos cambiar la contraseña.'
  } finally {
    guardandoPassword.value = false
  }
}

/* ------------------------------------------------------------- Baja lógica */
function abrirBaja(usuario: Usuario) {
  usuarioBaja.value = usuario
  bajaAbierta.value = true
}

async function confirmarBaja() {
  if (!usuarioBaja.value || procesandoBaja.value) return

  const objetivo = usuarioBaja.value
  procesandoBaja.value = true

  try {
    await usuariosApi.desactivar(objetivo.id)
    bajaAbierta.value = false
    avisar('ok', `${objetivo.nombre} quedó inactivo.`)
    await cargar()
  } catch (error) {
    bajaAbierta.value = false
    avisar(
      'error',
      error instanceof ApiError ? error.mensaje : 'No pudimos desactivar al usuario.',
    )
  } finally {
    procesandoBaja.value = false
  }
}

async function reactivar(usuario: Usuario) {
  try {
    await usuariosApi.activar(usuario.id)
    avisar('ok', `${usuario.nombre} volvió a estar activo.`)
    await cargar()
  } catch (error) {
    avisar(
      'error',
      error instanceof ApiError ? error.mensaje : 'No pudimos reactivar al usuario.',
    )
  }
}

/* ----------------------------------------------------------------- Helpers */
function esUnoMismo(usuario: Usuario): boolean {
  return usuario.id === auth.usuario?.id
}

function puedeGestionar(usuario: Usuario): boolean {
  if (usuario.rol === 'cliente') return false
  if (auth.esPropietario) return true
  return usuario.rol !== 'admin'
}

function puedeTransferir(usuario: Usuario): boolean {
  return (
    auth.esPropietario &&
    usuario.rol === 'admin' &&
    !usuario.es_propietario &&
    usuario.activo &&
    !esUnoMismo(usuario)
  )
}

function etiquetaRol(usuario: Usuario): string {
  return usuario.es_propietario ? 'Propietario' : ETIQUETA_ROL[usuario.rol]
}

function iniciales(nombre: string): string {
  return nombre
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((parte) => parte[0]?.toUpperCase() ?? '')
    .join('')
}

const formateadorFecha = new Intl.DateTimeFormat('es-AR', { dateStyle: 'medium' })

function fecha(iso: string): string {
  return formateadorFecha.format(new Date(iso))
}

function claseRol(rol: Rol): string {
  if (rol === 'admin') return 'badge--strong'
  if (rol === 'cliente') return 'badge--muted'
  return ''
}
</script>

<template>
  <section class="usuarios">
    <PageHeader
      eyebrow="Administración"
      title="Usuarios"
      subtitle="Las cuentas del estudio y el rol de cada una. Los accesos de clientes se crean y gestionan desde la ficha del cliente, no desde acá."
    >
      <template #actions>
        <button class="btn btn--primary" type="button" @click="abrirAlta">
          <svg viewBox="0 0 16 16" width="14" height="14" fill="none" aria-hidden="true">
            <path d="M8 3v10M3 8h10" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" />
          </svg>
          Nuevo usuario
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
          placeholder="Buscar por nombre o email"
          aria-label="Buscar usuarios"
        />
      </div>

      <select v-model="filtros.rol" class="input select" aria-label="Filtrar por rol">
        <option value="">Todos los roles</option>
        <option v-for="rol in ROLES" :key="rol" :value="rol">
          {{ ETIQUETA_ROL[rol] }}
        </option>
      </select>

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
      <EmptyState v-if="cargando" loading>Cargando usuarios…</EmptyState>

      <EmptyState v-else-if="usuarios.length === 0">
        <p>No hay usuarios que coincidan con el filtro.</p>
        <button class="btn btn--sm" type="button" @click="limpiarFiltros">
          Limpiar filtros
        </button>
      </EmptyState>

      <div v-else class="tabla-scroll">
        <table class="table">
          <thead>
            <tr>
              <th scope="col">Usuario</th>
              <th scope="col">Rol</th>
              <th scope="col">Estado</th>
              <th scope="col" class="col-fecha">Alta</th>
              <th scope="col"><span class="sr-only">Acciones</span></th>
            </tr>
          </thead>

          <tbody>
            <tr v-for="usuario in usuarios" :key="usuario.id">
              <td>
                <div class="celda-usuario">
                  <span class="avatar avatar--sm" aria-hidden="true">
                    {{ iniciales(usuario.nombre) }}
                  </span>
                  <div class="celda-usuario__texto">
                    <p class="celda-usuario__nombre">
                      {{ usuario.nombre }}
                      <span v-if="esUnoMismo(usuario)" class="chip">vos</span>
                    </p>
                    <p class="celda-usuario__email">{{ usuario.email }}</p>
                  </div>
                </div>
              </td>

              <td>
                <span
                  class="badge"
                  :class="usuario.es_propietario ? 'badge--strong' : claseRol(usuario.rol)"
                >
                  {{ etiquetaRol(usuario) }}
                </span>
                <span v-if="usuario.debe_cambiar_password" class="chip">
                  clave temporal
                </span>
              </td>

              <td>
                <span class="badge" :class="usuario.activo ? 'badge--ok' : 'badge--muted'">
                  {{ usuario.activo ? 'Activo' : 'Inactivo' }}
                </span>
              </td>

              <td class="col-fecha tabular">{{ fecha(usuario.creado_en) }}</td>

              <td>
                <div class="acciones">
                  <button
                    class="icon-btn"
                    type="button"
                    :aria-label="`Ver ${usuario.nombre}`"
                    title="Ver detalle"
                    @click="abrirDetalle(usuario)"
                  >
                    <svg viewBox="0 0 16 16" width="15" height="15" fill="none" aria-hidden="true">
                      <circle cx="8" cy="8" r="5.5" stroke="currentColor" stroke-width="1.4" />
                      <path d="M8 5.2v3.3l2 1.2" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round" />
                    </svg>
                  </button>
                  <button
                    v-if="puedeGestionar(usuario)"
                    class="icon-btn"
                    type="button"
                    :aria-label="`Editar a ${usuario.nombre}`"
                    title="Editar"
                    @click="abrirEdicion(usuario)"
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
                    v-if="puedeGestionar(usuario) && !esUnoMismo(usuario)"
                    class="icon-btn"
                    type="button"
                    :aria-label="`Cambiar contraseña de ${usuario.nombre}`"
                    title="Cambiar contraseña"
                    @click="abrirPassword(usuario)"
                  >
                    <svg viewBox="0 0 16 16" width="15" height="15" fill="none" aria-hidden="true">
                      <circle cx="5.5" cy="8" r="2.5" stroke="currentColor" stroke-width="1.4" />
                      <path
                        d="M8 8h5.5M11.5 8v2M13.2 8v1.6"
                        stroke="currentColor"
                        stroke-width="1.4"
                        stroke-linecap="round"
                      />
                    </svg>
                  </button>

                  <button
                    v-if="usuario.activo && puedeGestionar(usuario)"
                    class="icon-btn icon-btn--peligro"
                    type="button"
                    :disabled="esUnoMismo(usuario)"
                    :title="
                      esUnoMismo(usuario)
                        ? 'No podés desactivar tu propio usuario'
                        : 'Desactivar'
                    "
                    :aria-label="`Desactivar a ${usuario.nombre}`"
                    @click="abrirBaja(usuario)"
                  >
                    <svg viewBox="0 0 16 16" width="15" height="15" fill="none" aria-hidden="true">
                      <circle cx="8" cy="8" r="5.5" stroke="currentColor" stroke-width="1.4" />
                      <path d="M4.4 4.4l7.2 7.2" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" />
                    </svg>
                  </button>

                  <button
                    v-else-if="puedeGestionar(usuario)"
                    class="icon-btn"
                    type="button"
                    :aria-label="`Reactivar a ${usuario.nombre}`"
                    title="Reactivar"
                    @click="reactivar(usuario)"
                  >
                    <svg viewBox="0 0 16 16" width="15" height="15" fill="none" aria-hidden="true">
                      <path
                        d="M13 8a5 5 0 1 1-1.5-3.5"
                        stroke="currentColor"
                        stroke-width="1.4"
                        stroke-linecap="round"
                      />
                      <path d="M13 2.5V5h-2.5" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" />
                    </svg>
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </TableCard>

    <p class="usuarios__pie">
      {{ total }} {{ total === 1 ? 'usuario' : 'usuarios' }} ·
      los inactivos conservan su historial
    </p>

    <!-- Alta / edición -->
    <UsuarioFormModal
      :abierto="formAbierto"
      :usuario="usuarioEnEdicion"
      @cerrar="formAbierto = false"
      @guardado="alGuardar"
    />

    <!-- Cambio de contraseña -->
    <Modal
      :abierto="passwordAbierto"
      :titulo="`Contraseña de ${usuarioPassword?.nombre ?? ''}`"
      @cerrar="passwordAbierto = false"
    >
      <form id="form-password" class="form-password" novalidate @submit.prevent="guardarPassword">
        <p class="form-password__intro">
          El cambio se aplica de inmediato. Se guarda con Argon2id.
        </p>

        <div v-if="esPasswordPropia" class="field">
          <label class="field__label" for="password-actual">Contraseña actual</label>
          <input
            id="password-actual"
            v-model="passwordActual"
            class="input"
            type="password"
            autocomplete="current-password"
          />
        </div>

        <div class="field">
          <label class="field__label" for="password-nueva">Nueva contraseña</label>
          <input
            id="password-nueva"
            v-model="passwordNueva"
            class="input"
            type="password"
            autocomplete="new-password"
            placeholder="Mínimo 8 caracteres"
          />
        </div>

        <div class="field">
          <label class="field__label" for="password-confirmar">Repetir contraseña</label>
          <input
            id="password-confirmar"
            v-model="passwordConfirmar"
            class="input"
            type="password"
            autocomplete="new-password"
          />
        </div>

        <p v-if="passwordError" class="alert alert--error" role="alert">
          {{ passwordError }}
        </p>
      </form>

      <template #pie>
        <button class="btn" type="button" @click="passwordAbierto = false">Cancelar</button>
        <button
          class="btn btn--primary"
          type="submit"
          form="form-password"
          :disabled="guardandoPassword"
        >
          {{ guardandoPassword ? 'Guardando…' : 'Cambiar contraseña' }}
        </button>
      </template>
    </Modal>

    <!-- Detalle -->
    <Modal :abierto="detalleAbierto" titulo="Detalle del usuario" @cerrar="detalleAbierto = false">
      <dl v-if="detalleUsuario" class="detalle-usuario">
        <div><dt>Nombre</dt><dd>{{ detalleUsuario.nombre }}</dd></div>
        <div><dt>Email</dt><dd>{{ detalleUsuario.email }}</dd></div>
        <div><dt>Rol</dt><dd>{{ etiquetaRol(detalleUsuario) }}</dd></div>
        <div><dt>Estado</dt><dd>{{ detalleUsuario.activo ? 'Activo' : 'Inactivo' }}</dd></div>
        <div><dt>Alta</dt><dd class="tabular">{{ fecha(detalleUsuario.creado_en) }}</dd></div>
        <div><dt>Última actualización</dt><dd class="tabular">{{ fecha(detalleUsuario.actualizado_en) }}</dd></div>
        <div v-if="detalleUsuario.debe_cambiar_password">
          <dt>Clave</dt><dd>Cambio pendiente</dd>
        </div>
      </dl>

      <template #pie>
        <button
          v-if="detalleUsuario && puedeTransferir(detalleUsuario)"
          class="btn btn--danger"
          type="button"
          @click="abrirTransferencia(detalleUsuario)"
        >
          Transferir propiedad
        </button>
        <button class="btn" type="button" @click="detalleAbierto = false">Cerrar</button>
      </template>
    </Modal>

    <!-- Transferencia de propiedad -->
    <Modal
      :abierto="transferirAbierto"
      titulo="Transferir la propiedad"
      @cerrar="transferirAbierto = false"
    >
      <p class="texto-baja">
        ¿Querés que <strong>{{ usuarioTransferir?.nombre }}</strong> sea el nuevo
        propietario del sistema?
      </p>
      <p class="texto-baja texto-baja--suave">
        Vos quedarás como administrador y ya no podrás gestionar otros
        administradores. Esta acción se registra en auditoría.
      </p>

      <template #pie>
        <button class="btn" type="button" @click="transferirAbierto = false">
          Cancelar
        </button>
        <button
          class="btn btn--danger"
          type="button"
          :disabled="transfiriendo"
          @click="transferirPropiedad"
        >
          {{ transfiriendo ? 'Transfiriendo…' : 'Transferir' }}
        </button>
      </template>
    </Modal>

    <!-- Baja -->
    <Modal
      :abierto="bajaAbierta"
      titulo="Desactivar usuario"
      @cerrar="bajaAbierta = false"
    >
      <p class="texto-baja">
        ¿Seguro que querés desactivar a
        <strong>{{ usuarioBaja?.nombre }}</strong>?
      </p>
      <p class="texto-baja texto-baja--suave">
        No se borra: queda inactivo, no puede iniciar sesión y conserva todo su
        historial. Podés reactivarlo cuando quieras.
      </p>

      <template #pie>
        <button class="btn" type="button" @click="bajaAbierta = false">Cancelar</button>
        <button
          class="btn btn--danger"
          type="button"
          :disabled="procesandoBaja"
          @click="confirmarBaja"
        >
          {{ procesandoBaja ? 'Desactivando…' : 'Desactivar' }}
        </button>
      </template>
    </Modal>
  </section>
</template>

<style scoped>
.usuarios {
  display: grid;
  gap: var(--space-5);
}

.toolbar .select {
  flex: 0 1 12rem;
}

.celda-usuario {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.celda-usuario__texto {
  display: grid;
  gap: 0.05rem;
}

.celda-usuario__nombre {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-sm);
  font-weight: 500;
  color: var(--color-text);
}

.celda-usuario__email {
  font-size: var(--text-xs);
  color: var(--color-text-faint);
}

.usuarios__pie {
  font-size: var(--text-xs);
  color: var(--color-text-faint);
}

.form-password {
  display: grid;
  gap: var(--space-4);
}

.form-password__intro {
  font-size: var(--text-sm);
  color: var(--color-text-muted);
}

.texto-baja {
  font-size: var(--text-sm);
}

.detalle-usuario {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-3) var(--space-4);
  margin: 0;
}

.detalle-usuario > div {
  display: grid;
  gap: 0.1rem;
}

.detalle-usuario dt {
  font-size: 0.625rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--color-text-faint);
}

.detalle-usuario dd {
  margin: 0;
  font-size: var(--text-sm);
}

.texto-baja--suave {
  margin-top: var(--space-2);
  color: var(--color-text-muted);
}

@media (max-width: 48rem) {
  .col-fecha {
    display: none;
  }

  .toolbar .select {
    flex: 1 1 auto;
  }
}
</style>
