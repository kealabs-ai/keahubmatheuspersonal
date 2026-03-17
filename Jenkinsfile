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

                    $DOCKER_COMPOSE down --remove-orphans || true

                    $DOCKER_COMPOSE build --no-cache
                    $DOCKER_COMPOSE up -d --force-recreate
                    $DOCKER_COMPOSE ps
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
