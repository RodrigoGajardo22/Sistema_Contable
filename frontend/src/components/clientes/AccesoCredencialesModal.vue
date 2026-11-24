<script setup lang="ts">
import { ref, watch } from 'vue'

import Modal from '@/components/ui/Modal.vue'

const props = defineProps<{
  abierto: boolean
  titulo?: string
  email: string | null
  password: string | null
  nota?: string
}>()

const emit = defineEmits<{ cerrar: [] }>()

const copiado = ref(false)

watch(
  () => props.abierto,
  (abierto) => {
    if (abierto) copiado.value = false
  },
)

async function copiar() {
  if (!props.password) return
  try {
    await navigator.clipboard.writeText(props.password)
    copiado.value = true
  } catch {
    copiado.value = false
  }
}
</script>

<template>
  <Modal
    :abierto="abierto"
    :titulo="titulo ?? 'Acceso del cliente'"
    @cerrar="emit('cerrar')"
  >
    <div class="credenciales">
      <p class="credenciales__intro">
        Entregá estos datos al cliente. La contraseña temporal se muestra una
        sola vez y el sistema pedirá cambiarla al ingresar.
      </p>

      <dl class="credenciales__datos">
        <div>
          <dt>Email</dt>
          <dd>{{ email ?? '—' }}</dd>
        </div>
        <div>
          <dt>Contraseña temporal</dt>
          <dd class="credenciales__clave tabular">{{ password ?? '—' }}</dd>
        </div>
      </dl>

      <button
        class="btn"
        type="button"
        :disabled="!password"
        @click="copiar"
      >
        {{ copiado ? 'Copiada' : 'Copiar contraseña' }}
      </button>

      <p v-if="nota" class="credenciales__nota">{{ nota }}</p>
    </div>

    <template #pie>
      <button class="btn btn--primary" type="button" @click="emit('cerrar')">
        Entendido
      </button>
    </template>
  </Modal>
</template>

<style scoped>
.credenciales {
  display: grid;
  gap: var(--space-4);
}

.credenciales__intro,
.credenciales__nota {
  font-size: var(--text-sm);
  color: var(--color-text-muted);
}

.credenciales__datos {
  display: grid;
  gap: var(--space-3);
  margin: 0;
  padding: var(--space-4);
  border: 1px solid var(--color-line-strong);
  border-radius: var(--radius-md);
  background: rgb(255 255 255 / 2%);
}

.credenciales__datos > div {
  display: grid;
  gap: 0.15rem;
}

.credenciales__datos dt {
  font-size: var(--text-xs);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--color-text-faint);
}

.credenciales__datos dd {
  margin: 0;
  font-size: var(--text-sm);
}

.credenciales__clave {
  font-family: var(--font-mono);
  font-size: var(--text-lg);
  letter-spacing: 0.04em;
  color: var(--color-accent);
  overflow-wrap: anywhere;
}
</style>
