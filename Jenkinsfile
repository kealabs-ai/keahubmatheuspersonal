pipeline {
    agent any

    environment {
        DEPLOY_HOST = 'srv1078.hstgr.io'
        DEPLOY_USER = 'root'
        DEPLOY_PATH = '/var/www/matheuspersonal'
        GIT_REPO    = 'https://github.com/kealabs-ai/keahubmatheuspersonal.git'
        GIT_BRANCH  = 'develop'
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Deploy via SSH') {
            steps {
                sshagent(credentials: ['hostinger-ssh-credentials']) {
                    sh """
                        ssh -o StrictHostKeyChecking=no ${DEPLOY_USER}@${DEPLOY_HOST} '
                            set -e

                            # Criar diretório se não existir
                            mkdir -p ${DEPLOY_PATH}
                            cd ${DEPLOY_PATH}

                            # Clonar ou atualizar repositório
                            if [ -d ".git" ]; then
                                git fetch origin
                                git reset --hard origin/${GIT_BRANCH}
                            else
                                git clone -b ${GIT_BRANCH} ${GIT_REPO} .
                            fi

                            # Criar .env se não existir
                            if [ ! -f ".env" ]; then
                                cat > .env << EOF
DB_HOST=srv1078.hstgr.io
DB_PORT=3306
DB_USER=u549746795_matheusmp
DB_PASSWORD=MP@2026!Passos
DB_NAME=u549746795_mp
EOF
                            fi

                            # Build e deploy dos serviços
                            docker-compose build --no-cache
                            docker-compose up -d --no-deps --build

                            # Status final
                            docker-compose ps
                        '
                    """
                }
            }
        }
    }

    post {
        success {
            echo '✅ Deploy realizado com sucesso na Hostinger!'
        }
        failure {
            echo '❌ Falha no deploy!'
        }
    }
}
