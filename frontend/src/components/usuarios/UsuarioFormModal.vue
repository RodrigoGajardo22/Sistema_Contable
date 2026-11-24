<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'

import { ApiError } from '@/api/client'
import { ETIQUETA_ROL, type Rol, type Usuario } from '@/api/tipos'
import { usuariosApi } from '@/api/usuarios'
import Modal from '@/components/ui/Modal.vue'
import { useAuthStore } from '@/stores/auth'

const props = defineProps<{
  abierto: boolean
  usuario: Usuario | null
}>()

const auth = useAuthStore()

const emit = defineEmits<{
  cerrar: []
  guardado: [usuario: Usuario, esAlta: boolean]
}>()

const ROLES = computed<Rol[]>(() =>
  auth.esPropietario ? ['admin', 'contador'] : ['contador'],
)

const formulario = reactive({
  nombre: '',
  email: '',
  password: '',
  rol: 'contador' as Rol,
})

const errores = reactive<Record<string, string>>({})
const errorGeneral = ref('')
const guardando = ref(false)

const esAlta = computed(() => props.usuario === null)
const rolBloqueado = computed(
  () => !esAlta.value && Boolean(props.usuario?.es_propietario),
)
const titulo = computed(() => (esAlta.value ? 'Nuevo usuario' : 'Editar usuario'))

watch(
  () => props.abierto,
  (abierto) => {
    if (!abierto) return

    errorGeneral.value = ''
    for (const clave of Object.keys(errores)) delete errores[clave]

    formulario.nombre = props.usuario?.nombre ?? ''
    formulario.email = props.usuario?.email ?? ''
    formulario.rol = props.usuario?.rol ?? 'contador'
    formulario.password = ''
  },
)

function validar(): boolean {
  for (const clave of Object.keys(errores)) delete errores[clave]

  if (formulario.nombre.trim().length < 2) {
    errores.nombre = 'Ingresá el nombre completo.'
  }
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formulario.email.trim())) {
    errores.email = 'El email no tiene un formato válido.'
  }
  if (esAlta.value && formulario.password.length < 8) {
    errores.password = 'La contraseña necesita al menos 8 caracteres.'
  }

  return Object.keys(errores).length === 0
}

function mapearDetalles(detalles?: Record<string, unknown>) {
  if (!detalles) return

  for (const [campo, valor] of Object.entries(detalles)) {
    const primero = Array.isArray(valor) ? valor[0] : valor
    errores[campo] = String(primero ?? 'Dato inválido.')
  }
}

async function enviar() {
  if (guardando.value || !validar()) return

  guardando.value = true
  errorGeneral.value = ''

  try {
    if (esAlta.value) {
      const creado = await usuariosApi.crear({
        nombre: formulario.nombre.trim(),
        email: formulario.email.trim(),
        password: formulario.password,
        rol: formulario.rol,
      })
      emit('guardado', creado, true)
    } else if (props.usuario) {
      const actualizado = await usuariosApi.actualizar(props.usuario.id, {
        nombre: formulario.nombre.trim(),
        email: formulario.email.trim(),
        rol: formulario.rol,
      })
      emit('guardado', actualizado, false)
    }
  } catch (error) {
    if (error instanceof ApiError) {
      errorGeneral.value = error.mensaje
      mapearDetalles(error.detalles)
    } else {
      errorGeneral.value = 'No pudimos guardar los cambios.'
    }
  } finally {
    guardando.value = false
  }
}
</script>

<template>
  <Modal :abierto="abierto" :titulo="titulo" @cerrar="emit('cerrar')">
    <form id="form-usuario" class="formulario" novalidate @submit.prevent="enviar">
      <div class="field">
        <label class="field__label" for="usuario-nombre">Nombre completo</label>
        <input
          id="usuario-nombre"
          v-model="formulario.nombre"
          class="input"
          type="text"
          autocomplete="off"
          placeholder="Ana Pérez"
          :aria-invalid="Boolean(errores.nombre)"
        />
        <p v-if="errores.nombre" class="field__error">{{ errores.nombre }}</p>
      </div>

      <div class="field">
        <label class="field__label" for="usuario-email">Email</label>
        <input
          id="usuario-email"
          v-model="formulario.email"
          class="input"
          type="email"
          autocomplete="off"
          placeholder="ana@estudio.com"
          :aria-invalid="Boolean(errores.email)"
        />
        <p v-if="errores.email" class="field__error">{{ errores.email }}</p>
      </div>

      <div class="field">
        <label class="field__label" for="usuario-rol">Rol</label>
        <select
          id="usuario-rol"
          v-model="formulario.rol"
          class="input select"
          :disabled="rolBloqueado"
        >
          <option v-for="opcion in ROLES" :key="opcion" :value="opcion">
            {{ ETIQUETA_ROL[opcion] }}
          </option>
        </select>
        <p class="field__ayuda">
          {{
            rolBloqueado
              ? 'El propietario no puede cambiar de rol. Transferí la propiedad primero.'
              : 'Los clientes se crean desde la ficha del cliente, no desde acá.'
          }}
        </p>
      </div>

      <div v-if="esAlta" class="field">
        <label class="field__label" for="usuario-password">Contraseña inicial</label>
        <input
          id="usuario-password"
          v-model="formulario.password"
          class="input"
          type="password"
          autocomplete="new-password"
          placeholder="Mínimo 8 caracteres"
          :aria-invalid="Boolean(errores.password)"
        />
        <p v-if="errores.password" class="field__error">{{ errores.password }}</p>
        <p v-else class="field__ayuda">
          Se guarda con Argon2id. El usuario puede cambiarla después.
        </p>
      </div>

      <p v-if="errorGeneral" class="alert alert--error" role="alert">
        {{ errorGeneral }}
      </p>
    </form>

    <template #pie>
      <button class="btn" type="button" @click="emit('cerrar')">Cancelar</button>
      <button
        class="btn btn--primary"
        type="submit"
        form="form-usuario"
        :disabled="guardando"
      >
        {{ guardando ? 'Guardando…' : esAlta ? 'Crear usuario' : 'Guardar cambios' }}
      </button>
    </template>
  </Modal>
</template>
