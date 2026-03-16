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
                sh """
                    set -e
                    mkdir -p ${DEPLOY_PATH}
                    cd ${DEPLOY_PATH}

                    if [ -d ".git" ]; then
                        git fetch origin
                        git reset --hard origin/${GIT_BRANCH}
                    else
                        git clone -b ${GIT_BRANCH} ${GIT_REPO} .
                    fi

                    # Create .env file with database credentials
                    cat > .env << EOF
DB_HOST=srv1078.hstgr.io
DB_PORT=3306
DB_NAME=u549746795_mp
DB_USER=u549746795_matheusmp
DB_PASSWORD=MP@2026!Passos
DB_ROOT_PASSWORD=rootpassword
JWT_SECRET=your-secret-key-change-in-production
EOF

                    # Copy database.py to each service directory
                    for service in services/*/; do
                        cp services/database.py "\$service"
                    done

                    docker-compose down --volumes --remove-orphans || true
                    docker volume prune -f || true

                    docker-compose build --no-cache
                    docker-compose up -d --force-recreate
                    docker-compose ps
                """
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
