<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import { ApiError } from '@/api/client'
import { usuariosApi } from '@/api/usuarios'
import PageHeader from '@/components/ui/PageHeader.vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()

const formulario = reactive({
  actual: '',
  nueva: '',
  confirmar: '',
})

const error = ref('')
const guardando = ref(false)

const forzado = computed(() => auth.debeCambiarPassword)
const titulo = computed(() =>
  forzado.value ? 'Cambiá tu clave inicial' : 'Cambiar contraseña',
)

async function guardar() {
  if (guardando.value || !auth.usuario) return

  error.value = ''

  if (!formulario.actual) {
    error.value = 'Ingresá tu contraseña actual.'
    return
  }
  if (formulario.nueva.length < 8) {
    error.value = 'La nueva contraseña necesita al menos 8 caracteres.'
    return
  }
  if (formulario.nueva !== formulario.confirmar) {
    error.value = 'Las contraseñas no coinciden.'
    return
  }

  guardando.value = true
  try {
    await usuariosApi.cambiarPassword(auth.usuario.id, {
      password_actual: formulario.actual,
      password_nueva: formulario.nueva,
    })

    // El backend invalida los tokens viejos: hay que volver a ingresar.
    auth.cerrarSesion()
    await router.replace({ name: 'login', query: { password: 'cambiada' } })
  } catch (e) {
    error.value =
      e instanceof ApiError ? e.mensaje : 'No pudimos cambiar la contraseña.'
  } finally {
    guardando.value = false
  }
}
</script>

<template>
  <section class="cuenta">
    <PageHeader
      eyebrow="Seguridad"
      :title="titulo"
      subtitle="Usá una clave propia, de al menos 8 caracteres. Al guardar se cierran todas las sesiones abiertas con la clave anterior."
    />

    <p v-if="forzado" class="alert" role="status">
      Estás ingresando con una clave temporal. Cambiala para poder usar el
      sistema.
    </p>

    <article class="card cuenta__card">
      <form class="formulario" novalidate @submit.prevent="guardar">
        <div class="field">
          <label class="field__label" for="cuenta-actual">Contraseña actual</label>
          <input
            id="cuenta-actual"
            v-model="formulario.actual"
            class="input"
            type="password"
            autocomplete="current-password"
          />
        </div>

        <div class="field">
          <label class="field__label" for="cuenta-nueva">Nueva contraseña</label>
          <input
            id="cuenta-nueva"
            v-model="formulario.nueva"
            class="input"
            type="password"
            autocomplete="new-password"
            placeholder="Mínimo 8 caracteres"
          />
        </div>

        <div class="field">
          <label class="field__label" for="cuenta-confirmar">Repetir contraseña</label>
          <input
            id="cuenta-confirmar"
            v-model="formulario.confirmar"
            class="input"
            type="password"
            autocomplete="new-password"
          />
        </div>

        <p v-if="error" class="alert alert--error" role="alert">{{ error }}</p>

        <div class="acciones">
          <RouterLink
            v-if="!forzado"
            :to="{ name: 'dashboard' }"
            class="btn"
          >
            Cancelar
          </RouterLink>
          <button class="btn btn--primary" type="submit" :disabled="guardando">
            {{ guardando ? 'Guardando…' : 'Cambiar contraseña' }}
          </button>
        </div>
      </form>
    </article>
  </section>
</template>

<style scoped>
.cuenta {
  display: grid;
  gap: var(--space-5);
  max-width: 34rem;
}

.cuenta__card {
  padding: clamp(1.25rem, 3vw, 1.75rem);
}

.acciones {
  gap: var(--space-2);
}
</style>
