# Sistema de diseño

Documento de referencia para mantener la coherencia visual del frontend. Los
valores viven en `src/style.css` (capas `@layer`); acá se explica **por qué**
existen y cuándo usarlos.

Dirección: **Institutional Dark** — serif de alto contraste para jerarquía,
sans para interfaz, mono para cifras; superficies casi negras, hairlines de
1 px y un único acento verde "saldo".

## Orden de capas

`src/style.css` declara `@layer reset, tokens, base, components, utilities`.
Todo estilo nuevo va en la capa que le corresponde: no se usa `!important`.

| Capa         | Contenido                                              |
| ------------ | ------------------------------------------------------ |
| `reset`      | Normalización mínima (box-sizing, márgenes, medios).    |
| `tokens`     | Primitivos + semánticos. Es el único lugar con colores. |
| `base`       | Tipografía global, foco visible, selección.             |
| `components` | Primitivas reutilizables: `.btn`, `.input`, `.card`.    |
| `utilities`  | `.mono`, `.tabular`, `.sr-only`.                        |

Los estilos de layout de una vista van en su bloque `<style scoped>` y **sólo
consumen tokens**, nunca literales de color o tamaño.

## Color

Dos niveles: primitivos (`--ink-*`, `--fog-*`, `--emerald-*`) y semánticos
(`--color-*`). Las vistas usan **semánticos**; los primitivos sólo se
referencian desde `tokens`.

| Token semántico       | Valor                   | Uso                                  |
| --------------------- | ----------------------- | ------------------------------------ |
| `--color-bg`          | `#07080b`               | Fondo de la aplicación               |
| `--color-surface`     | `#101319`               | Tarjetas y paneles                   |
| `--color-text`        | `#f2f4f7`               | Texto principal                      |
| `--color-text-muted`  | `#98a2b3`               | Texto secundario (≥ 7:1)             |
| `--color-text-faint`  | `#7c8698`               | Metadatos y placeholders (≥ 5:1)     |
| `--color-accent`      | `#2bd98a`               | Saldo, foco, acción primaria         |
| `--color-on-accent`   | `#052e1f`               | Texto sobre el acento                |
| `--color-danger`      | `#f97066`               | Errores de validación                |
| `--color-line`        | `rgb(255 255 255 / 7%)` | Hairline por defecto                 |
| `--color-line-strong` | `rgb(255 255 255 / 14%)`| Bordes de campos y separadores       |

Reglas:

- El verde está reservado para **saldo, foco y acción primaria**. No se usa
  como decoración ni para texto largo.
- Todo texto sobre fondo oscuro debe superar **4.5:1** (AA). `text-faint` es
  el piso: no hay un gris más oscuro para texto.
- Profundidad por borde y sombra, no por gradientes de color.

## Tipografía

| Rol      | Familia          | Uso                                     |
| -------- | ---------------- | --------------------------------------- |
| Display  | IBM Plex Serif   | `h1`–`h3`, títulos de tarjeta           |
| UI       | IBM Plex Sans    | Cuerpo, labels, botones                 |
| Cifras   | IBM Plex Mono    | Importes, totales, códigos (`.tabular`) |

Escala: `--text-xs` (12) · `--text-sm` (14) · `--text-base` (16) ·
`--text-lg` (18) · `--text-xl` (22) · `--text-2xl` / `--text-3xl` fluidos con
`clamp()`.

Las fuentes son self-hosted vía `@fontsource` (importadas en `src/main.ts`,
sólo subset `latin`). No se agregan `<link>` a Google Fonts.

## Espaciado y forma

- Escala de 4/8: `--space-1` … `--space-12`. Sin valores sueltos.
- Radios: `--radius-sm` (controles), `--radius-md` (marca), `--radius-lg`
  (tarjetas).
- Controles con altura mínima de 44 px (`2.75rem`) para cumplir el target
  táctil.

## Movimiento

- Curvas: `--ease-out` para entradas, `--ease-in-out` para bucles.
- Duraciones: `--dur-fast` 160 ms (hover), `--dur-base` 260 ms,
  `--dur-slow` 520 ms (entradas).
- Entradas escalonadas con `animation-delay` corto (≤ 90 ms por ítem).
- **Siempre** respetar `prefers-reduced-motion`: la regla global en `base`
  anula animaciones y transiciones; el JS que anima cifras o sigue al puntero
  consulta `matchMedia` antes de arrancar.

## Accesibilidad

- Foco visible con `outline` de 2 px en `--color-accent` y offset de 3 px.
- Un `label` real por campo; `aria-invalid` cuando falla la validación.
- Mensajes de estado con `role="status"` + `aria-live="polite"`.
- Contraste AA en texto normal; AAA en texto principal.
- Nada depende sólo del color: los errores agregan texto, no sólo rojo.

## Composición de la entrada (`/login`)

- Dos columnas: relato + asiento de ejemplo a la izquierda, tarjeta de acceso
  a la derecha. En ≤ 60 rem pasa a una columna con la tarjeta primero.
- Fondo en cuatro capas: aura verde, grilla técnica, spotlight que sigue al
  puntero y grano (SVG inline al 3.5 %).
- El asiento demuestra la propuesta (partida doble, debe = haber) y se cierra
  con la animación de totales; es el elemento emocional de la página.

## Patrones de aplicación (desde el slice 1)

### Shell

- Sidebar fija de 16.5 rem con marca, navegación y "próximos módulos"
  (deshabilitados, con chip `pronto`). En ≤ 56 rem pasa a off-canvas con
  backdrop y botón de menú en el topbar.
- Topbar sticky con `backdrop-filter`, título de la ruta (`meta.titulo`) y
  bloque de usuario (avatar con iniciales, nombre, rol, salir).
- El contenido se limita a 78 rem y respira con `clamp()`.

### Datos

- **Tabla:** `.table` dentro de `.card` + `.tabla-scroll` (scroll horizontal en
  mobile; la columna de fecha se oculta en ≤ 48 rem).
- **Estados obligatorios en toda vista con datos:** cargando, vacío y error con
  reintento. Nunca dejar la pantalla en blanco.
- **Filtros:** `.toolbar` con búsqueda (debounce 300 ms) y selects. La búsqueda
  se refleja en la query de la API, no se filtra en el cliente.
- **Confirmaciones destructivas:** modal con el nombre del registro y una nota
  de qué se conserva. Las bajas son lógicas: nunca se promete un borrado.

### Componentes nuevos

| Clase / componente | Uso |
| --- | --- |
| `.badge` (+ `--ok`, `--strong`, `--muted`, `--accent`) | Roles y estados. `--strong` (blanco) para admin; verde sólo para estado activo |
| `.avatar` / `--sm` | Iniciales del usuario o del cliente, mono, borde hairline |
| `.icon-btn` / `--peligro` | Acciones de fila; siempre con `aria-label` y `title` |
| `.alert` / `--ok` / `--error` | Resultado de una acción; `role="status"` o `role="alert"` |
| `.table` | Datos tabulares, header en versalitas de 10 px |
| `.select` | `<select>` con chevron propio (SVG inline) |
| `.field__error` / `.field__ayuda` | Mensaje por campo debajo del control |
| `Modal.vue` | `Teleport` a `body`, Esc para cerrar, foco al abrir, bloqueo del scroll |
| `.btn--ghost`, `.btn--danger`, `.btn--sm` | Variantes del botón base |

### Árbol y línea de tiempo (scoped)

- **Árbol de cuentas:** filas planas con `padding-left: nivel * 1.35rem`, chevron
  que rota 90° y acciones que aparecen al 40 % de opacidad (100 % en hover o
  focus). En mobile las acciones siempre visibles y los badges ocultos.
- **Historial:** línea vertical de 1 px con puntos; la versión vigente lleva el
  punto verde. Cada cambio se lee `campo  antes → después` con el valor anterior
  tachado y el nuevo en verde.
- Las filas inactivas bajan a 50 % de opacidad; el color nunca es el único
  indicador (siempre hay un badge con texto).

### Formularios de dinero

- Los importes se muestran siempre con `Intl.NumberFormat('es-AR')` y dos
  decimales; en los inputs se acepta coma o punto y se normaliza antes de enviar.
- La aritmética del formulario se hace en **centavos enteros** (`Math.round`),
  nunca con floats directos.
- En asientos, el bloque de totales (`.totales`) se pone verde y dice
  "Balanceado" cuando debe = haber; el botón de guardar queda deshabilitado
  mientras no cierre.
- En comprobantes, el resumen muestra IVA y total calculados en vivo a partir
  del neto y la alícuota; el backend los vuelve a calcular y descarta los del
  cliente.



- Toda acción con red muestra estado `…ando` en el botón y se deshabilita
  mientras corre (evita doble submit).
- El botón de baja del propio usuario se deshabilita con un `title` que explica
  por qué (regla del backend reflejada en la UI).
- El bloqueo por intentos muestra una cuenta regresiva en el botón
  (`Reintentá en 14:32`) calculada desde `reintentar_en_segundos`.



1. ¿Necesitás un color nuevo? Agregá un **semántico** que apunte a un
   primitivo; no uses hex en las vistas.
2. ¿Es un patrón que se repite en 2+ vistas? Va a `components` en
   `style.css`; si es de una sola vista, queda scoped.
3. ¿Es un dato numérico? `.tabular`.
4. Cualquier animación nueva: entrada ≤ 600 ms, sin loops infinitos salvo
   fondos, y con salida para `prefers-reduced-motion`.
