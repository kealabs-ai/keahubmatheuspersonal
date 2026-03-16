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

                    mkdir -p nginx
                    if [ ! -f nginx/nginx.conf ]; then
                        cat > nginx/nginx.conf << 'NGINXEOF'
events {}

http {
    server {
        listen 80;
        server_name srv1023256.hstgr.cloud;
        return 301 https://\$host\$request_uri;
    }

    server {
        listen 443 ssl;
        server_name srv1023256.hstgr.cloud;

        ssl_certificate     /etc/nginx/certs/fullchain.pem;
        ssl_certificate_key /etc/nginx/certs/privkey.pem;

        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers   HIGH:!aNULL:!MD5;

        add_header Access-Control-Allow-Origin  "*";
        add_header Access-Control-Allow-Methods "GET, POST, PUT, DELETE, OPTIONS";
        add_header Access-Control-Allow-Headers "Content-Type, Authorization";

        location /api/users/ {
            proxy_pass http://users-service:8000/;
            proxy_set_header Host \$host;
            proxy_set_header X-Real-IP \$remote_addr;
        }
        location /api/subscriptions/ {
            proxy_pass http://subscriptions-service:8000/;
            proxy_set_header Host \$host;
            proxy_set_header X-Real-IP \$remote_addr;
        }
        location /api/orders/ {
            proxy_pass http://orders-service:8000/;
            proxy_set_header Host \$host;
            proxy_set_header X-Real-IP \$remote_addr;
        }
        location /api/payments/ {
            proxy_pass http://payments-service:8000/;
            proxy_set_header Host \$host;
            proxy_set_header X-Real-IP \$remote_addr;
        }
        location /api/coupons/ {
            proxy_pass http://coupons-service:8000/;
            proxy_set_header Host \$host;
            proxy_set_header X-Real-IP \$remote_addr;
        }
        location /api/leads/ {
            proxy_pass http://leads-service:8000/;
            proxy_set_header Host \$host;
            proxy_set_header X-Real-IP \$remote_addr;
        }
    }
}
NGINXEOF
                    fi

                    docker-compose build
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
