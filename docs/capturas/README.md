# Capturas del README

Las imágenes de esta carpeta se generan contra el entorno de desarrollo con
datos de demostración. Para que la documentación no vuelva a quedar vieja:

1. Levantar el entorno y cargar los datos demo:

   ```bash
   ./dev.sh up
   podman exec sistema-contable-backend flask --app run.py seed-demo
   ```

2. Abrir `http://localhost:8080` en un viewport de **1600 × 1000**, tema
   oscuro, escala 1x y locale `es-AR`. Esperar a que carguen las fuentes y las
   animaciones antes de capturar.

3. Usuarios de las capturas:

   | Captura | Usuario | Contraseña |
   | --- | --- | --- |
   | `login.png` | sin sesión | — |
   | `panel.png`, `clientes.png`, `cliente-ficha.png`, `cuentas.png`, `asiento.png`, `bandeja.png`, `agenda.png`, `conciliacion.png`, `reportes.png`, `auditoria.png` | `admin@estudio.com` | `Admin1234` |
   | `portal-cliente.png` | `cliente.espiga@estudio.com` | `Cliente1234` |
   | `api-docs.png` | sin sesión, `http://localhost:8080/api/docs` | — |

4. Detalles por captura:
   - **clientes.png**: filtrar por **Activos** para no mezclar bajas lógicas.
   - **cliente-ficha.png**: usar una ficha con acceso al portal e historial.
   - **asiento.png**: abrir el detalle del primer asiento para mostrar la
     partida doble y el estado confirmado.
   - **conciliacion.png**: elegir el extracto con movimientos conciliados
     (diferencia 0) para mostrar el matching.
   - **auditoria.png**: filtrar por entidad **Asientos** para evitar ruido de
     altas y bajas de prueba.
   - **api-docs.png**: Swagger UI con los tags colapsados (`docExpansion:
     none`).

5. Nombres y recortes: mantener exactamente los nombres de archivo que usa el
   README (`docs/capturas/<nombre>.png`) y las imágenes en formato PNG.
