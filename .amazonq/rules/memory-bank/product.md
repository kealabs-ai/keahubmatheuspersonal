# MatheusPersonal - Product Overview

## Purpose
Backend platform for **MatheusPersonal** (matheuspersonal.com.br), a personal trainer subscription service. Provides the full API layer for managing students (alunos), workout plans, nutrition, payments, and administrative operations.

## Value Proposition
- Complete student lifecycle management: from lead capture → purchase → onboarding → active training
- Payment processing via **Asaas** (Brazilian payment gateway)
- Structured training programs with workouts, nutrition plans, and progress tracking
- Admin panel support for managing content, students, and subscriptions

## Key Features & Capabilities

### Student Area (`/api/aluno/*`)
- Authentication with JWT (login, password reset via email)
- Profile management with avatar upload
- Workout plan access and exercise tracking
- Nutrition plan viewing
- Progress photo uploads and body measurement tracking
- Dashboard with summary stats
- Notifications
- Video library access

### Admin Area (`/api/admin/*`)
- Workout template creation and management
- Onboarding flow configuration
- Video content management
- Student management

### Commerce & Payments
- Lead capture for marketing funnel
- Coupon/discount system
- Order creation and management
- Subscription lifecycle (create, cancel, update)
- Asaas checkout and webhook status updates

### Supporting Services
- Feedback collection
- Email notifications via SMTP (Hostinger)

## Target Users
- **Students (Alunos)**: Access training, nutrition, progress tracking via frontend app
- **Admin (Matheus)**: Manage content, students, plans, and business operations
- **External Systems**: Asaas webhook callbacks for payment status updates

## Production URLs
- Domain: `https://matheuspersonal.com.br`
- Server: `https://srv1023256.hstgr.cloud`
- API prefix: `/api/{service-name}/`

## Payment Flow Status
- This repository contains backend APIs and deployment configuration; no frontend source was found during the payment flow review.
- Asaas checkout validates the supplied user ID against the order and compares the requested amount to the stored total, but it does not authenticate that user ID with a JWT. Add caller authentication before production use.
- The Asaas webhook validates `asaas-access-token` against `ASAAS_WEBHOOK_TOKEN` and checks payment details against the Asaas API.
- The public Asaas API prefix is `/api/asaas`; Traefik strips `/api` before forwarding to the service.
- See `.amazonq/rules/memory-bank/payments.md` for the route map and known gaps.
