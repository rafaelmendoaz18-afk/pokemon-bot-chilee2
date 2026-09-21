name: Monitor Pokemon Chile

on:
  schedule:
    # Se ejecuta automáticamente cada 15 minutos en la nube
    - cron: '*/15 * * * *'
  workflow_dispatch: # Permite ejecutarlo manualmente con un clic

jobs:
  check-stores:
    runs-on: ubuntu-latest
    permissions:
      contents: write

    steps:
      - name: Descargar repositorio
        uses: actions/checkout@v4

      - name: Configurar Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Instalar dependencias
        run: pip install requests

      - name: Ejecutar monitor
        run: python monitor_pokemon.py

      - name: Guardar historial de productos
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add vistos.json || exit 0
          git commit -m "Actualizar productos vistos" || exit 0
          git push
