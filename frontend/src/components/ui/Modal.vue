<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'

const props = defineProps<{
  abierto: boolean
  titulo: string
}>()

const emit = defineEmits<{
  cerrar: []
}>()

const tarjeta = ref<HTMLElement | null>(null)

function alPresionarTecla(evento: KeyboardEvent) {
  if (evento.key === 'Escape' && props.abierto) emit('cerrar')
}

watch(
  () => props.abierto,
  async (abierto) => {
    if (abierto) {
      document.body.style.overflow = 'hidden'
      document.addEventListener('keydown', alPresionarTecla)
      await nextTick()
      tarjeta.value?.focus()
    } else {
      document.body.style.overflow = ''
      document.removeEventListener('keydown', alPresionarTecla)
    }
  },
)

onBeforeUnmount(() => {
  document.body.style.overflow = ''
  document.removeEventListener('keydown', alPresionarTecla)
})
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="abierto" class="modal">
        <div class="modal__fondo" @click="emit('cerrar')"></div>

        <div
          ref="tarjeta"
          class="modal__tarjeta"
          role="dialog"
          aria-modal="true"
          :aria-label="titulo"
          tabindex="-1"
        >
          <header class="modal__cabecera">
            <h2 class="modal__titulo">{{ titulo }}</h2>
            <button
              class="icon-btn"
              type="button"
              aria-label="Cerrar"
              @click="emit('cerrar')"
            >
              <svg viewBox="0 0 16 16" width="14" height="14" fill="none" aria-hidden="true">
                <path d="M4 4l8 8M12 4l-8 8" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" />
              </svg>
            </button>
          </header>

          <div class="modal__cuerpo">
            <slot />
          </div>

          <footer v-if="$slots.pie" class="modal__pie">
            <slot name="pie" />
          </footer>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.modal {
  position: fixed;
  inset: 0;
  z-index: 60;
  display: grid;
  place-items: center;
  padding: var(--space-4);
}

.modal__fondo {
  position: absolute;
  inset: 0;
  background: rgb(3 4 6 / 72%);
  backdrop-filter: blur(4px);
}

.modal__tarjeta {
  position: relative;
  display: flex;
  flex-direction: column;
  width: min(30rem, 100%);
  max-height: min(85dvh, 44rem);
  border: 1px solid var(--color-line-strong);
  border-radius: var(--radius-lg);
  background: linear-gradient(180deg, #12151c, #0a0c11);
  box-shadow: 0 40px 90px -30px rgb(0 0 0 / 90%);
  overflow: hidden;
}

.modal__cabecera {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  padding: var(--space-4) var(--space-5);
  border-bottom: 1px solid var(--color-line);
}

.modal__titulo {
  font-size: var(--text-lg);
}

.modal__cuerpo {
  padding: var(--space-5);
  overflow-y: auto;
}

.modal__pie {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
  padding: var(--space-4) var(--space-5);
  border-top: 1px solid var(--color-line);
  background: rgb(255 255 255 / 1.5%);
}

.modal-enter-active,
.modal-leave-active {
  transition: opacity var(--dur-base) var(--ease-out);
}

.modal-enter-active .modal__tarjeta,
.modal-leave-active .modal__tarjeta {
  transition:
    transform var(--dur-base) var(--ease-out),
    opacity var(--dur-base) var(--ease-out);
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-from .modal__tarjeta,
.modal-leave-to .modal__tarjeta {
  opacity: 0;
  transform: translateY(10px) scale(0.985);
}
</style>
