# Integração InfinitePay - Payment Service

## Endpoints para InfinitePay

### 1. Criar Pagamento InfinitePay
```
POST /payments/infinitepay/create
```

**Body:**
```json
{
  "id_order": 1,
  "payment_method": "credit",
  "amount": 100.00,
  "installments": 1,
  "card_last_digits": "1234",
  "card_brand": "Visa"
}
```

**Response:**
```json
{
  "payment_id": 1,
  "transaction_id": "TEMP_abc123...",
  "status": "pending",
  "message": "Payment created, waiting for InfinitePay confirmation"
}
```

### 2. Atualizar Transaction ID
```
POST /payments/{payment_id}/update-transaction
```

**Query Params:**
- `transaction_id`: ID real retornado pelo InfinitePay

**Response:**
```json
{
  "updated": true,
  "payment_id": 1,
  "transaction_id": "infinitepay_real_id"
}
```

### 3. Webhook InfinitePay
```
POST /payments/webhook/infinitepay
```

**Configurar no painel InfinitePay:**
- URL: `https://seu-dominio.com/payments/webhook/infinitepay`

**Payload esperado:**
```json
{
  "event": "payment.approved",
  "id": "infinitepay_transaction_id",
  "transaction_id": "infinitepay_transaction_id",
  "status": "approved",
  "amount": 100.00,
  "payment_method": "credit_card"
}
```

**Response:**
```json
{
  "success": true,
  "payment_id": 1,
  "status": "approved",
  "event": "payment.approved"
}
```

## Mapeamento de Status

| Status InfinitePay | Status Interno |
|-------------------|----------------|
| approved          | approved       |
| paid              | approved       |
| authorized        | approved       |
| pending           | pending        |
| processing        | pending        |
| rejected          | rejected       |
| failed            | rejected       |
| cancelled         | rejected       |
| refunded          | refunded       |

## Fluxo de Integração

1. **Frontend cria pagamento:**
   - POST `/payments/infinitepay/create`
   - Recebe `payment_id` e `transaction_id` temporário

2. **Frontend envia para InfinitePay:**
   - Usa SDK/API do InfinitePay
   - Recebe `transaction_id` real

3. **Frontend atualiza transaction_id:**
   - POST `/payments/{payment_id}/update-transaction`

4. **InfinitePay envia webhook:**
   - POST `/payments/webhook/infinitepay`
   - Sistema atualiza status automaticamente
   - Atualiza tabela `payments` e `orders`

## Dados Gravados na Tabela Payments

```sql
- id_payment (auto)
- id_order
- payment_method (credit/debit/pix)
- payment_status (pending/approved/rejected/refunded)
- amount
- installments
- transaction_id (InfinitePay)
- card_last_digits
- card_brand
- paid_at (timestamp quando aprovado)
- created_at
- updated_at
```

## Segurança

- Validar assinatura do webhook (implementar conforme documentação InfinitePay)
- Usar HTTPS em produção
- Verificar IP de origem do webhook
- Implementar rate limiting
