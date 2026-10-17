# Asaas Payment Flow

Review scope: backend routes, database schema, Traefik routing, and the Asaas webhook contract. No frontend source was found in this repository, so the browser checkout and its request construction still need validation in the frontend project.

## Route map

| Public route | Service route | Purpose |
|---|---|---|
| `/api/asaas/checkout` | `/asaas/checkout` | Create PIX or credit card charge for an existing order |
| `/api/asaas/checkout/cart` | `/asaas/checkout/cart` | Create a PIX charge for an existing order |
| `/api/asaas/payment/{asaas_id}/status` | `/asaas/payment/{asaas_id}/status` | Query Asaas for payment status and payment instructions |
| `/api/asaas/webhook` | `/asaas/webhook` | Authenticate notification, verify charge with Asaas, then update local payment/order state |

Traefik strips `/api` before forwarding. Configure the provider webhook URL as `https://matheuspersonal.com.br/api/asaas/webhook`.

## Validation implemented

- Checkout now verifies that the order exists, belongs to the supplied `id_user`, is not already approved, and the requested amount matches `orders.total_amount` to two decimal places.
- Checkout sends the server-side order ID as Asaas `externalReference` and uses the validated order total as the charge amount.
- The Asaas webhook requires `asaas-access-token` matching `ASAAS_WEBHOOK_TOKEN` using a constant-time comparison. It fails closed when the token is missing or incorrect.
- Before changing local state, the webhook fetches the charge from the authenticated Asaas API and checks the provider payment ID, amount, and order reference against the local record.
- Duplicate or delayed events do not move an already approved payment back to pending or rejected, and an already approved payment does not trigger onboarding a second time.
- Credit card checkout logs omit the card and cardholder payloads. The service maps `CREDIT_CARD` to the database's `credit` enum value and `PIX` to `pix`.
- Asaas API credentials and webhook authentication are separate settings. Set `ASAAS_WEBHOOK_TOKEN` to the token configured in the Asaas webhook; do not reuse `ASAAS_API_KEY`.
- Configure a random `authToken` of 32 to 255 characters in Asaas and set the same value in `ASAAS_WEBHOOK_TOKEN`. Asaas sends it in the `asaas-access-token` request header.

## Remaining gaps

- The supplied `id_user` is not tied to an authenticated caller at these checkout routes. Ownership comparison prevents cross-order mismatches only when the supplied user ID is trustworthy; add JWT validation before production use.
- The Asaas payment is created remotely before the local payment row is inserted. If local persistence fails or a webhook arrives in that interval, Asaas must retry delivery; monitor and reconcile such cases.
- Repeated or concurrent checkout requests can create multiple pending Asaas charges for the same order; add an idempotency strategy before production use.
- Rejected/refunded event handling and the `orders.payment_status` enum need a defined refund lifecycle. The current orders enum has no `refunded` state.
- Webhook retries can deliver the same event more than once. Approved-state transitions are guarded, but event IDs are not persisted in a dedicated idempotency table.
- Validate the frontend request/response fields in the frontend repository and run a sandbox transaction after configuring the webhook token and URL.

Generic legacy payment CRUD routes remain in `services/payments`; they are not Asaas checkout routes and are not covered by this flow.
