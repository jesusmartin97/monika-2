#!/bin/bash

sleep 15

cd /home/jesus62/Monika

# Modelo configurado en el .env (por defecto qwen3:4b)
MODELO="qwen3:4b"
if [ -f .env ]; then
    M="$(grep -E '^OLLAMA_MODEL=' .env | head -n1 | cut -d= -f2 | tr -d ' \r')"
    [ -n "$M" ] && MODELO="$M"
fi

# Monika es 100% local: asegurar que Ollama esté arriba antes de arrancar
if ! curl -sf http://localhost:11434/api/version >/dev/null 2>&1; then
    echo "Ollama no responde. Intentando iniciarlo..."
    systemctl start ollama 2>/dev/null
    for _ in $(seq 1 20); do
        curl -sf http://localhost:11434/api/version >/dev/null 2>&1 && break
        sleep 1
    done
fi

if ! curl -sf http://localhost:11434/api/version >/dev/null 2>&1; then
    echo "⚠ No pude conectar con Ollama."
    echo "  Ejecuta: systemctl start ollama"
    echo "  (si no está instalado: curl -fsSL https://ollama.com/install.sh | sh)"
fi

if ! ollama list 2>/dev/null | grep -q "^${MODELO}[[:space:]]"; then
    echo "⚠ El modelo ${MODELO} no está descargado."
    echo "  Ejecuta: ollama pull ${MODELO}"
fi

exec /home/jesus62/Monika/venv/bin/python /home/jesus62/Monika/main.py
