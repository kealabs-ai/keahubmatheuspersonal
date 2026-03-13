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

                    docker compose build
                    docker compose up -d --force-recreate
                    docker compose ps
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
