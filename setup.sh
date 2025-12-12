#!/bin/bash
# Setup inicial para el bot con Chroma

set -e

echo "=== Instalando dependencias ==="
pip install -r requirements.txt

echo ""
echo "=== Construyendo índice Chroma ==="
python -m mvp_bot.chroma_index

echo ""
echo "✓ Setup completado!"
echo ""
echo "Próximos pasos:"
echo "1. Revisa que se creó la carpeta mvp_bot/chroma_db/"
echo "2. Ejecuta el bot normalmente (reflex run)"
echo ""
