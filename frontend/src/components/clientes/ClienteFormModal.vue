<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'

import { ApiError } from '@/api/client'
import { clientesApi } from '@/api/clientes'
import {
  CONDICIONES_IVA,
  formatearCuit,
  type Cliente,
  type Usuario,
} from '@/api/tipos'
import Modal from '@/components/ui/Modal.vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()

const props = defineProps<{
  abierto: boolean
  cliente: Cliente | null
  contadores: Usuario[]
  esAdmin: boolean
}>()

const emit = defineEmits<{
  cerrar: []
  guardado: [cliente: Cliente, esAlta: boolean]
}>()

const formulario = reactive({
  razon_social: '',
  cuit: '',
  condicion_iva: 'responsable_inscripto',
  email: '',
  telefono: '',
  direccion: '',
  contador_id: null as number | null,
})

const errores = reactive<Record<string, string>>({})
const errorGeneral = ref('')
const guardando = ref(false)

const esAlta = computed(() => props.cliente === null)
const titulo = computed(() =>
  esAlta.value ? 'Nuevo cliente' : 'Actualizar datos del cliente',
)

watch(
  () => props.abierto,
  (abierto) => {
    if (!abierto) return

    errorGeneral.value = ''
    for (const clave of Object.keys(errores)) delete errores[clave]

    formulario.razon_social = props.cliente?.razon_social ?? ''
    formulario.cuit = props.cliente ? formatearCuit(props.cliente.cuit) : ''
    formulario.condicion_iva =
      props.cliente?.condicion_iva ?? 'responsable_inscripto'
    formulario.email = props.cliente?.email ?? ''
    formulario.telefono = props.cliente?.telefono ?? ''
    formulario.direccion = props.cliente?.direccion ?? ''
    formulario.contador_id =
      props.cliente?.contador_id ??
      (props.esAdmin ? auth.usuario?.id ?? null : null)
  },
)

function validar(): boolean {
  for (const clave of Object.keys(errores)) delete errores[clave]

  if (formulario.razon_social.trim().length < 2) {
    errores.razon_social = 'Ingresá la razón social.'
  }
  if (esAlta.value && formulario.cuit.replace(/\D/g, '').length !== 11) {
    errores.cuit = 'El CUIT debe tener 11 dígitos.'
  }
  if (!formulario.email.trim()) {
    errores.email = 'El email es obligatorio: es el usuario del portal.'
  } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formulario.email.trim())) {
    errores.email = 'El email no tiene un formato válido.'
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

  const comunes = {
    razon_social: formulario.razon_social.trim(),
    condicion_iva: formulario.condicion_iva,
    email: formulario.email.trim(),
    telefono: formulario.telefono.trim() || null,
    direccion: formulario.direccion.trim() || null,
  }

  try {
    if (esAlta.value) {
      const creado = await clientesApi.crear({
        ...comunes,
        cuit: formulario.cuit,
        ...(props.esAdmin ? { contador_id: formulario.contador_id } : {}),
      })
      emit('guardado', creado, true)
    } else if (props.cliente) {
      const actualizado = await clientesApi.actualizar(props.cliente.id, {
        ...comunes,
        ...(props.esAdmin ? { contador_id: formulario.contador_id } : {}),
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
    <form id="form-cliente" class="formulario" novalidate @submit.prevent="enviar">
      <div class="field">
        <label class="field__label" for="cliente-razon">Razón social</label>
        <input
          id="cliente-razon"
          v-model="formulario.razon_social"
          class="input"
          type="text"
          placeholder="Panadería La Espiga SRL"
          :aria-invalid="Boolean(errores.razon_social)"
        />
        <p v-if="errores.razon_social" class="field__error">
          {{ errores.razon_social }}
        </p>
      </div>

      <div class="fila">
        <div class="field">
          <label class="field__label" for="cliente-cuit">CUIT</label>
          <input
            id="cliente-cuit"
            v-model="formulario.cuit"
            class="input tabular"
            type="text"
            inputmode="numeric"
            placeholder="20-12345678-6"
            :disabled="!esAlta"
            :aria-invalid="Boolean(errores.cuit)"
          />
          <p v-if="errores.cuit" class="field__error">{{ errores.cuit }}</p>
          <p v-else-if="!esAlta" class="field__ayuda">
            El CUIT identifica al cliente y no se edita.
          </p>
        </div>

        <div class="field">
          <label class="field__label" for="cliente-iva">Condición frente al IVA</label>
          <select id="cliente-iva" v-model="formulario.condicion_iva" class="input select">
            <option v-for="opcion in CONDICIONES_IVA" :key="opcion.valor" :value="opcion.valor">
              {{ opcion.etiqueta }}
            </option>
          </select>
          <p class="field__ayuda">Cada cambio queda en el historial.</p>
        </div>
      </div>

      <div class="field">
        <label class="field__label" for="cliente-email">Email de acceso del cliente</label>
        <input
          id="cliente-email"
          v-model="formulario.email"
          class="input"
          type="email"
          autocomplete="off"
          placeholder="contacto@cliente.com"
          :aria-invalid="Boolean(errores.email)"
        />
        <p v-if="errores.email" class="field__error">{{ errores.email }}</p>
        <p v-else class="field__ayuda">
          El cliente ingresa al portal con este email. Al crear la ficha se
          genera una contraseña temporal.
        </p>
      </div>

      <div class="fila">
        <div class="field">
          <label class="field__label" for="cliente-telefono">Teléfono</label>
          <input
            id="cliente-telefono"
            v-model="formulario.telefono"
            class="input"
            type="tel"
            placeholder="2920-123456"
          />
        </div>

        <div class="field">
          <label class="field__label" for="cliente-direccion">Dirección</label>
          <input
            id="cliente-direccion"
            v-model="formulario.direccion"
            class="input"
            type="text"
            placeholder="Belgrano 123, Viedma"
          />
        </div>
      </div>

      <div v-if="esAdmin" class="field">
        <label class="field__label" for="cliente-contador">Responsable del cliente</label>
        <select id="cliente-contador" v-model="formulario.contador_id" class="input select">
          <option v-for="responsable in contadores" :key="responsable.id" :value="responsable.id">
            {{ responsable.nombre }} · {{ responsable.rol === 'admin' ? 'Administrador' : 'Contador' }}
          </option>
        </select>
        <p class="field__ayuda">
          Puede ser un contador, un administrador o el propietario. Siempre hay
          un responsable asignado.
        </p>
      </div>

      <p v-if="errorGeneral" class="alert alert--error" role="alert">
        {{ errorGeneral }}
      </p>
    </form>

    <template #pie>
      <button class="btn" type="button" @click="emit('cerrar')">Cancelar</button>
      <button class="btn btn--primary" type="submit" form="form-cliente" :disabled="guardando">
        {{ guardando ? 'Guardando…' : esAlta ? 'Crear cliente' : 'Guardar versión' }}
      </button>
    </template>
  </Modal>
</template>

<style scoped>

.fila {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(12rem, 1fr));
  gap: var(--space-4);
}
</style>
