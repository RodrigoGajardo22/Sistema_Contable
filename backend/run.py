"""Punto de entrada de la aplicación.

- Desarrollo: `flask --app run.py run --debug`
- Producción:  `gunicorn run:app`
- Migraciones: `flask --app run.py db upgrade`
- Seed:        `flask --app run.py seed`
"""

from app import create_app

app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
