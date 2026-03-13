# MatheusPersonal - Microservices Architecture

Arquitetura de microserviços para o site MatheusPersonal com Python/FastAPI, MySQL, Docker e Jenkins.

## Estrutura do Projeto

```
KeaHubMatheusPersonal/
├── services/
│   ├── users/          # Serviço de usuários (porta 8001)
│   ├── subscriptions/  # Serviço de assinaturas (porta 8002)
│   ├── orders/         # Serviço de pedidos (porta 8003)
│   ├── payments/       # Serviço de pagamentos (porta 8004)
│   ├── coupons/        # Serviço de cupons (porta 8005)
│   ├── leads/          # Serviço de leads (porta 8006)
│   └── database.py     # Conexão compartilhada MySQL
├── docker-compose.yml
├── Jenkinsfile
├── init.sql
└── .env.example
```

## Microserviços

### 1. Users Service (8001)
- POST /users - Criar usuário
- GET /users/{user_id} - Buscar usuário
- POST /users/{user_id}/update - Atualizar usuário
- POST /users/{user_id}/delete - Deletar usuário

### 2. Subscriptions Service (8002)
- POST /subscriptions - Criar assinatura
- GET /subscriptions/user/{user_id} - Listar assinaturas do usuário
- POST /subscriptions/{sub_id}/update - Atualizar status
- POST /subscriptions/{sub_id}/cancel - Cancelar assinatura

### 3. Orders Service (8003)
- POST /orders - Criar pedido
- GET /orders/{order_id} - Buscar pedido
- GET /orders/user/{user_id} - Listar pedidos do usuário

### 4. Payments Service (8004)
- POST /payments - Criar pagamento
- POST /payments/{payment_id}/approve - Aprovar pagamento
- POST /payments/{payment_id}/reject - Rejeitar pagamento
- GET /payments/order/{order_id} - Listar pagamentos do pedido
- **POST /payments/infinitepay/create** - Criar pagamento InfinitePay
- **POST /payments/{payment_id}/update-transaction** - Atualizar transaction ID
- **POST /payments/webhook/infinitepay** - Webhook InfinitePay

### 5. Coupons Service (8005)
- POST /coupons - Criar cupom
- GET /coupons/{code} - Validar cupom
- POST /coupons/{coupon_id}/use - Usar cupom
- GET /coupons - Listar cupons ativos

### 6. Leads Service (8006)
- POST /leads - Criar lead
- GET /leads - Listar leads
- GET /leads/{lead_id} - Buscar lead

## Setup Local

1. Copie o arquivo de ambiente:
```bash
cp .env.example .env
```

2. Inicie os serviços:
```bash
docker-compose up -d
```

3. Acesse a documentação Swagger:
- Users: http://localhost:8001/docs
- Subscriptions: http://localhost:8002/docs
- Orders: http://localhost:8003/docs
- Payments: http://localhost:8004/docs
- Coupons: http://localhost:8005/docs
- Leads: http://localhost:8006/docs

## Deploy Jenkins (Hostinger)

### Pré-requisitos na Hostinger:
1. Docker e Docker Compose instalados
2. Acesso SSH configurado
3. Credenciais configuradas no Jenkins:
   - `hostinger-host`: Host da Hostinger
   - `hostinger-user`: Usuário SSH
   - `hostinger-ssh-key`: Chave SSH privada

### Pipeline:
O Jenkinsfile executa:
1. Checkout do código
2. Build das imagens Docker
3. Execução dos testes
4. Push das imagens
5. Deploy via SSH na Hostinger

## Banco de Dados

MySQL 8.0 com as seguintes tabelas:
- users
- subscriptions
- credit_cards
- leads
- coupons
- coupon_usage
- orders
- order_items
- payments
- user_addresses

## Tecnologias

- Python 3.11
- FastAPI
- MySQL 8.0
- Docker & Docker Compose
- Jenkins
- Uvicorn
