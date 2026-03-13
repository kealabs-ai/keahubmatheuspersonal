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
                    sh '''
                        if command -v docker-compose &> /dev/null; then
                            docker-compose build
                        else
                            docker compose build
                        fi
                    '''
                }
            }
        }
        
        stage('Deploy Services') {
            steps {
                script {
                    sh '''
                        if command -v docker-compose &> /dev/null; then
                            COMPOSE_CMD="docker-compose"
                        else
                            COMPOSE_CMD="docker compose"
                        fi
                        
                        $COMPOSE_CMD up -d --no-deps --build users-service
                        $COMPOSE_CMD up -d --no-deps --build subscriptions-service
                        $COMPOSE_CMD up -d --no-deps --build orders-service
                        $COMPOSE_CMD up -d --no-deps --build payments-service
                        $COMPOSE_CMD up -d --no-deps --build coupons-service
                        $COMPOSE_CMD up -d --no-deps --build leads-service
                    '''
                }
            }
        }
        
        stage('Verify Deployment') {
            steps {
                script {
                    sh '''
                        if command -v docker-compose &> /dev/null; then
                            docker-compose ps
                        else
                            docker compose ps
                        fi
                    '''
                }
            }
        }
    }
    
    post {
        success {
            echo '✅ Deploy realizado com sucesso!'
            script {
                sh '''
                    if command -v docker-compose &> /dev/null; then
                        docker-compose ps
                    else
                        docker compose ps
                    fi
                '''
            }
        }
        failure {
            echo '❌ Falha no deploy!'
            script {
                sh '''
                    if command -v docker-compose &> /dev/null; then
                        docker-compose logs --tail=50 || true
                    else
                        docker compose logs --tail=50 || true
                    fi
                '''
            }
        }
    }
}
