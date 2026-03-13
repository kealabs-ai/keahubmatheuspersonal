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
                sshagent(credentials: ['hostinger-ssh-key']) {
                    sh """
                        ssh -o StrictHostKeyChecking=no ${DEPLOY_USER}@${DEPLOY_HOST} '
                            set -e

                            mkdir -p ${DEPLOY_PATH}
                            cd ${DEPLOY_PATH}

                            if [ -d ".git" ]; then
                                git fetch origin
                                git reset --hard origin/${GIT_BRANCH}
                            else
                                git clone -b ${GIT_BRANCH} ${GIT_REPO} .
                            fi

                            docker compose build --no-cache
                            docker compose up -d --force-recreate
                            docker compose ps
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
