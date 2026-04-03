pipeline {
    agent any

    environment {
        DEPLOY_PATH = '/var/jenkins_home/apps/matheuspersonal'
        GIT_REPO    = 'https://github.com/kealabs-ai/keahubmatheuspersonal.git'
        GIT_BRANCH  = 'develop'
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Deploy') {
            steps {
                sh '''
                    set -e

                    export PATH=$PATH:/usr/local/bin:/usr/bin:/bin

                    DOCKER=/var/jenkins_home/docker
                    DOCKER_COMPOSE=/var/jenkins_home/docker-compose
                    echo "Docker: $DOCKER"
                    echo "Docker Compose: $DOCKER_COMPOSE"
                    ls -la $DOCKER || true
                    $DOCKER --version || true
                    $DOCKER_COMPOSE --version || true

                    mkdir -p $DEPLOY_PATH
                    cd $DEPLOY_PATH

                    if [ -d ".git" ]; then
                        git fetch origin
                        git reset --hard origin/$GIT_BRANCH
                    else
                        git clone -b $GIT_BRANCH $GIT_REPO .
                    fi

                    cat > .env << 'ENVEOF'
DB_HOST=srv1078.hstgr.io
DB_PORT=3306
DB_NAME=u549746795_mp
DB_USER=u549746795_matheusmp
DB_PASSWORD=MP@2026!Passos
DB_ROOT_PASSWORD=rootpassword
JWT_SECRET=your-secret-key-change-in-production
ASAAS_API_KEY=$aact_hmlg_000MzkwODA2MWY2OGM3MWRlMDU2NWM3MzJlNzZmNGZhZGY6OjgxOTBhMmNhLWE4MjItNDVhZS04MTk0LTVmN2JiYjdkMTU3NDo6JGFhY2hfNzMwZDI5ODctMzExYi00ZWNlLWI2YjAtODA5MWEwYzA0OTZh
ASAAS_BASE_URL=https://sandbox.asaas.com/api/v3
ENVEOF

                    for service in services/*/; do
                        cp services/database.py "$service"
                    done

                    # Garantir buildx instalado (requerido pelo compose v5+)
                    BUILDX_PATH="/var/jenkins_home/.docker/cli-plugins/docker-buildx"
                    if [ ! -f "$BUILDX_PATH" ]; then
                        mkdir -p /var/jenkins_home/.docker/cli-plugins
                        curl -fsSL "https://github.com/docker/buildx/releases/download/v0.17.1/buildx-v0.17.1.linux-amd64" -o "$BUILDX_PATH"
                        chmod +x "$BUILDX_PATH"
                    fi

                    # Build das imagens com tags explícitas
                    $DOCKER build -t matheuspersonal/users:latest         -f services/users/Dockerfile services/
                    $DOCKER build -t matheuspersonal/subscriptions:latest  -f services/subscriptions/Dockerfile services/
                    $DOCKER build -t matheuspersonal/orders:latest         -f services/orders/Dockerfile services/
                    $DOCKER build -t matheuspersonal/payments:latest       -f services/payments/Dockerfile services/
                    $DOCKER build -t matheuspersonal/coupons:latest        -f services/coupons/Dockerfile services/
                    $DOCKER build -t matheuspersonal/leads:latest          -f services/leads/Dockerfile services/
                    $DOCKER build -t matheuspersonal/feedbacks:latest      -f services/feedbacks/Dockerfile services/
                    $DOCKER build -t matheuspersonal/asaas:latest          -f services/asaas/Dockerfile services/
                    $DOCKER build -t matheuspersonal/ms-auth:latest        -f services/ms-auth/Dockerfile services/
                    $DOCKER build -t matheuspersonal/ms-users:latest       -f services/ms-users/Dockerfile services/
                    $DOCKER build -t matheuspersonal/ms-workouts:latest    -f services/ms-workouts/Dockerfile services/
                    $DOCKER build -t matheuspersonal/ms-progress:latest    -f services/ms-progress/Dockerfile services/
                    $DOCKER build -t matheuspersonal/ms-nutrition:latest   -f services/ms-nutrition/Dockerfile services/
                    $DOCKER build -t matheuspersonal/ms-notifications:latest -f services/ms-notifications/Dockerfile services/
                    $DOCKER build -t matheuspersonal/ms-dashboard:latest   -f services/ms-dashboard/Dockerfile services/

                    $DOCKER stack rm matheuspersonal || true
                    sleep 30

                    # Aguarda rede ser removida
                    for i in $(seq 1 10); do
                        $DOCKER network rm matheuspersonal_matheuspersonal 2>/dev/null && break || true
                        sleep 5
                    done

                    $DOCKER stack deploy -c docker-compose.yml matheuspersonal --with-registry-auth
                    $DOCKER stack ps matheuspersonal
                '''
            }
        }
    }

    post {
        success {
            echo '✅ Deploy realizado com sucesso!'
        }
        failure {
            echo '❌ Falha no deploy!'
        }
    }
}
