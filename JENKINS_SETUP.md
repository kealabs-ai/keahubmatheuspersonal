# Configuração Jenkins - MatheusPersonal

## Opção 1: Deploy Local (Jenkinsfile)

Pipeline simplificado que executa o deploy no próprio servidor Jenkins.

### Uso:
1. Use o arquivo `Jenkinsfile` padrão
2. O Jenkins executará `docker-compose up -d` localmente
3. Não requer configuração de credenciais

### Comando manual equivalente:
```bash
cd /var/www/matheuspersonal
docker-compose up -d --no-deps --build
```

---

## Opção 2: Deploy Remoto Hostinger (Jenkinsfile.hostinger)

Pipeline que faz deploy via SSH na Hostinger.

### Pré-requisitos:

#### 1. Criar Credencial SSH no Jenkins:
1. Acesse: Jenkins → Manage Jenkins → Credentials
2. Clique em "Add Credentials"
3. Tipo: **SSH Username with private key**
4. ID: `hostinger-ssh-credentials`
5. Username: `root` (ou seu usuário SSH)
6. Private Key: Cole sua chave privada SSH
7. Salvar

#### 2. Configurar Pipeline:
1. No Jenkins, crie um novo Pipeline
2. Em "Pipeline script from SCM":
   - SCM: Git
   - Repository URL: `https://github.com/kealabs-ai/keahubmatheuspersonal.git`
   - Branch: `*/develop`
   - Script Path: `Jenkinsfile.hostinger`

#### 3. Parâmetros do Pipeline:
- **HOSTINGER_HOST**: `srv1078.hstgr.io`
- **HOSTINGER_USER**: `root`
- **DEPLOY_PATH**: `/var/www/matheuspersonal`

---

## Opção 3: Deploy Manual via Script

Se preferir não usar Jenkins, execute diretamente:

```bash
# Na Hostinger via SSH
cd /var/www/matheuspersonal
git pull origin develop
docker-compose up -d --no-deps --build
docker-compose ps
```

---

## Troubleshooting

### Erro: "hostinger-host credential not found"
**Solução**: Use `Jenkinsfile` (deploy local) ou configure a credencial SSH conforme instruções acima.

### Erro: "Required context class hudson.FilePath is missing"
**Solução**: Removido o bloco `post always` que causava esse erro.

### Containers não atualizam
**Solução**: Use `--no-deps --build` para forçar rebuild sem afetar dependências.

### MySQL não conecta
**Solução**: Verifique as variáveis de ambiente no `.env`:
```bash
DB_HOST=srv1078.hstgr.io
DB_PORT=3306
DB_USER=u549746795_matheusmp
DB_PASSWORD=MP@2026!Passos
DB_NAME=u549746795_mp
```

---

## Estrutura de Deploy

```
/var/www/matheuspersonal/
├── docker-compose.yml
├── .env
├── services/
│   ├── users/
│   ├── subscriptions/
│   ├── orders/
│   ├── payments/
│   ├── coupons/
│   └── leads/
└── Jenkinsfile
```

---

## Comandos Úteis

```bash
# Ver logs de todos os serviços
docker-compose logs -f

# Ver logs de um serviço específico
docker-compose logs -f users-service

# Reiniciar um serviço
docker-compose restart payments-service

# Ver status dos containers
docker-compose ps

# Parar todos os serviços (NÃO RECOMENDADO se houver outras apps)
docker-compose down

# Atualizar apenas um serviço
docker-compose up -d --no-deps --build payments-service
```
