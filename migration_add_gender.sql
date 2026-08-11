-- Migration: adiciona colunas gender e recurring_billing na tabela users
-- Rodar no banco de produção: u549746795_mp

ALTER TABLE users
  ADD COLUMN IF NOT EXISTS gender ENUM('masculino','feminino') DEFAULT NULL,
  ADD COLUMN IF NOT EXISTS recurring_billing TINYINT(1) DEFAULT 0;
