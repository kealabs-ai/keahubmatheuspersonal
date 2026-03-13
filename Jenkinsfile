pipeline {
    agent any

    environment {
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
                withCredentials([
                    sshUserPrivateKey(credentialsId: 'hostinger-ssh-key', keyFileVariable: 'SSH_KEY', usernameVariable: 'DEPLOY_USER'),
                    string(credentialsId: 'hostinger-host', variable: 'DEPLOY_HOST'),
                    string(credentialsId: 'hostinger-db-user', variable: 'DB_USER'),
                    string(credentialsId: 'hostinger-db-password', variable: 'DB_PASSWORD'),
                    string(credentialsId: 'hostinger-db-name', variable: 'DB_NAME'),
                    string(credentialsId: 'hostinger-db-host', variable: 'DB_HOST')
                ]) {
                    sh """
                        ssh -i \$SSH_KEY -o StrictHostKeyChecking=no \$DEPLOY_USER@\$DEPLOY_HOST '
                            set -e
                            mkdir -p ${DEPLOY_PATH}
                            cd ${DEPLOY_PATH}

                            if [ -d ".git" ]; then
                                git fetch origin
                                git reset --hard origin/${GIT_BRANCH}
                            else
                                git clone -b ${GIT_BRANCH} ${GIT_REPO} .
                            fi

                            if [ ! -f ".env" ]; then
                                cat > .env << EOF
DB_HOST=\$DB_HOST
DB_PORT=3306
DB_USER=\$DB_USER
DB_PASSWORD=\$DB_PASSWORD
DB_NAME=\$DB_NAME
EOF
                            fi

                            docker-compose build --no-cache
                            docker-compose up -d --no-deps --build
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
