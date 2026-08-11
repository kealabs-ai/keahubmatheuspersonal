#!/bin/bash
# Script para instalar docker-compose no container Jenkins

echo "Instalando docker-compose..."

# Detectar arquitetura
ARCH=$(uname -m)
if [ "$ARCH" = "x86_64" ]; then
    ARCH="x86_64"
elif [ "$ARCH" = "aarch64" ]; then
    ARCH="aarch64"
fi

# Baixar docker-compose
DOCKER_COMPOSE_VERSION="v2.24.5"
curl -L "https://github.com/docker/compose/releases/download/${DOCKER_COMPOSE_VERSION}/docker-compose-linux-${ARCH}" -o /usr/local/bin/docker-compose

# Dar permissão de execução
chmod +x /usr/local/bin/docker-compose

# Criar link simbólico
ln -sf /usr/local/bin/docker-compose /usr/bin/docker-compose

# Verificar instalação
docker-compose --version

echo "✅ docker-compose instalado com sucesso!"
