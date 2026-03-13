pipeline {
    agent any
    
    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }
        
        stage('Build Images') {
            steps {
                script {
                    sh 'docker-compose build'
                }
            }
        }
        
        stage('Deploy Services') {
            steps {
                script {
                    sh '''
                        docker-compose up -d --no-deps --build users-service
                        docker-compose up -d --no-deps --build subscriptions-service
                        docker-compose up -d --no-deps --build orders-service
                        docker-compose up -d --no-deps --build payments-service
                        docker-compose up -d --no-deps --build coupons-service
                        docker-compose up -d --no-deps --build leads-service
                    '''
                }
            }
        }
        
        stage('Verify Deployment') {
            steps {
                script {
                    sh 'docker-compose ps'
                }
            }
        }
    }
    
    post {
        success {
            echo '✅ Deploy realizado com sucesso!'
            script {
                sh 'docker-compose ps'
            }
        }
        failure {
            echo '❌ Falha no deploy!'
            script {
                sh 'docker-compose logs --tail=50'
            }
        }
    }
}
