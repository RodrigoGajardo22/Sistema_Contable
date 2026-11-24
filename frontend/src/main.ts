import { createApp } from 'vue'
import { createPinia } from 'pinia'

// Fuentes self-hosted: sin requests a Google Fonts y sin FOUT.
import '@fontsource/ibm-plex-sans/latin-400.css'
import '@fontsource/ibm-plex-sans/latin-500.css'
import '@fontsource/ibm-plex-sans/latin-600.css'
import '@fontsource/ibm-plex-serif/latin-400.css'
import '@fontsource/ibm-plex-serif/latin-500.css'
import '@fontsource/ibm-plex-mono/latin-400.css'
import '@fontsource/ibm-plex-mono/latin-500.css'

import './style.css'

import App from './App.vue'
import router from './router'

const app = createApp(App)

app.use(createPinia())
app.use(router)

app.mount('#app')
