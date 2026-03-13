pipeline {
    agent any

    environment {
        DB_HOST     = 'srv1078.hstgr.io'
        DB_PORT     = '3306'
        DB_USER     = 'u549746795_matheusmp'
        DB_PASSWORD = 'MP@2026!Passos'
        DB_NAME     = 'u549746795_mp'
        DB_ROOT_PASSWORD = 'rootpassword'
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Build Images') {
            steps {
                sh 'docker compose build'
            }
        }

        stage('Deploy Services') {
            steps {
                sh '''
                    docker compose up -d --no-deps --build users-service
                    docker compose up -d --no-deps --build subscriptions-service
                    docker compose up -d --no-deps --build orders-service
                    docker compose up -d --no-deps --build payments-service
                    docker compose up -d --no-deps --build coupons-service
                    docker compose up -d --no-deps --build leads-service
                '''
            }
        }

        stage('Verify Deployment') {
            steps {
                sh 'docker compose ps'
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
