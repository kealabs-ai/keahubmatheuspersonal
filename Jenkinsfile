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

                    DOCKER=$(which docker 2>/dev/null || find /usr /usr/local -name docker -type f 2>/dev/null | head -1)
                    DOCKER_COMPOSE=$(which docker-compose 2>/dev/null || find /usr /usr/local -name docker-compose -type f 2>/dev/null | head -1)
                    echo "Docker: $DOCKER"
                    echo "Docker Compose: $DOCKER_COMPOSE"

                    if [ -z "$DOCKER" ]; then
                        echo "ERROR: docker not found"
                        find / -name docker -type f 2>/dev/null
                        exit 1
                    fi

                    if [ -z "$DOCKER_COMPOSE" ]; then
                        echo "ERROR: docker-compose not found"
                        find / -name docker-compose -type f 2>/dev/null
                        exit 1
                    fi

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

                    $DOCKER_COMPOSE down --volumes --remove-orphans || true
                    $DOCKER ps -q | xargs -r $DOCKER stop || true
                    $DOCKER ps -aq | xargs -r $DOCKER rm -f || true

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
