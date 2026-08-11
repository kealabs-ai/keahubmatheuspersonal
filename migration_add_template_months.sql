-- Migration: adiciona coluna months na tabela workout_templates
-- months = validade do treino em meses (ex: 2 = aluno com até 2 meses usa este template)

ALTER TABLE workout_templates
  ADD COLUMN IF NOT EXISTS months INT DEFAULT NULL COMMENT 'Validade do treino em meses desde o cadastro do aluno';
