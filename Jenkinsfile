pipeline {
    agent any
    
    environment {
        DOCKER_REGISTRY = 'your-registry'
        APP_NAME = 'matheuspersonal'
        HOSTINGER_HOST = credentials('hostinger-host')
        HOSTINGER_USER = credentials('hostinger-user')
        HOSTINGER_SSH_KEY = credentials('hostinger-ssh-key')
    }
    
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
        
        stage('Run Tests') {
            steps {
                script {
                    sh 'docker-compose run --rm users-service pytest'
                    sh 'docker-compose run --rm subscriptions-service pytest'
                    sh 'docker-compose run --rm orders-service pytest'
                    sh 'docker-compose run --rm payments-service pytest'
                    sh 'docker-compose run --rm coupons-service pytest'
                    sh 'docker-compose run --rm leads-service pytest'
                }
            }
        }
        
        stage('Push Images') {
            steps {
                script {
                    sh 'docker-compose push'
                }
            }
        }
        
        stage('Deploy to Hostinger') {
            steps {
                script {
                    sh '''
                        ssh -i ${HOSTINGER_SSH_KEY} ${HOSTINGER_USER}@${HOSTINGER_HOST} << EOF
                        cd /var/www/matheuspersonal
                        docker-compose pull
                        docker-compose down
                        docker-compose up -d
                        docker-compose ps
EOF
                    '''
                }
            }
        }
    }
    
    post {
        always {
            sh 'docker-compose down'
        }
        success {
            echo 'Deploy realizado com sucesso!'
        }
        failure {
            echo 'Falha no deploy!'
        }
    }
}
