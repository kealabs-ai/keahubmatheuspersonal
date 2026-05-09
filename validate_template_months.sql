-- ============================================================
-- VALIDAÇÃO: Regra de seleção de template por gender + goal + months
-- Lógica de intervalos:
--   meses <= 2   → template com months = 2
--   meses <= 4   → template com months = 4
--   meses <= 6   → template com months = 6
--   meses <= 8   → template com months = 8
--   meses <= 10  → template com months = 10
--   meses <= 12  → template com months = 12
--   meses > 12   → template com months IS NULL (sem limite)
-- ============================================================


-- 1. Templates cadastrados com suas regras (ordenados por months ASC)
SELECT
    id,
    name,
    goal,
    level,
    gender,
    months,
    active,
    CASE
        WHEN months IS NULL THEN '> 12 meses (sem limite)'
        ELSE CONCAT('<= ', months, ' meses')
    END AS intervalo_aplicavel
FROM workout_templates
WHERE active = 1
ORDER BY goal, gender, months ASC;


-- 2. Simulação da regra para todos os alunos ativos
-- Prioridade: goal + gender + months → goal + months → gender + months → só months
SELECT
    u.id_user,
    u.name                                                              AS aluno,
    u.goal                                                              AS objetivo,
    u.gender                                                            AS genero,
    FLOOR(DATEDIFF(CURDATE(), u.created_at) / 30)                      AS meses_cadastrado,
    -- Template selecionado (goal + gender + months)
    COALESCE(
        (SELECT wt.name FROM workout_templates wt
         WHERE wt.active = 1
           AND wt.goal = u.goal
           AND (wt.gender = u.gender OR wt.gender IS NULL)
           AND (wt.months IS NULL OR wt.months >= FLOOR(DATEDIFF(CURDATE(), u.created_at) / 30))
         ORDER BY CASE WHEN wt.months IS NULL THEN 1 ELSE 0 END, wt.months ASC, wt.id ASC
         LIMIT 1),
        -- Fallback: goal + months (sem gender)
        (SELECT wt.name FROM workout_templates wt
         WHERE wt.active = 1
           AND wt.goal = u.goal
           AND (wt.months IS NULL OR wt.months >= FLOOR(DATEDIFF(CURDATE(), u.created_at) / 30))
         ORDER BY CASE WHEN wt.months IS NULL THEN 1 ELSE 0 END, wt.months ASC, wt.id ASC
         LIMIT 1),
        -- Fallback: gender + months (sem goal)
        (SELECT wt.name FROM workout_templates wt
         WHERE wt.active = 1
           AND (wt.gender = u.gender OR wt.gender IS NULL)
           AND (wt.months IS NULL OR wt.months >= FLOOR(DATEDIFF(CURDATE(), u.created_at) / 30))
         ORDER BY CASE WHEN wt.months IS NULL THEN 1 ELSE 0 END, wt.months ASC, wt.id ASC
         LIMIT 1),
        -- Fallback final: qualquer template compatível com months
        (SELECT wt.name FROM workout_templates wt
         WHERE wt.active = 1
           AND (wt.months IS NULL OR wt.months >= FLOOR(DATEDIFF(CURDATE(), u.created_at) / 30))
         ORDER BY CASE WHEN wt.months IS NULL THEN 1 ELSE 0 END, wt.months ASC, wt.id ASC
         LIMIT 1)
    )                                                                   AS template_selecionado,
    COALESCE(
        (SELECT wt.months FROM workout_templates wt
         WHERE wt.active = 1
           AND wt.goal = u.goal
           AND (wt.gender = u.gender OR wt.gender IS NULL)
           AND (wt.months IS NULL OR wt.months >= FLOOR(DATEDIFF(CURDATE(), u.created_at) / 30))
         ORDER BY CASE WHEN wt.months IS NULL THEN 1 ELSE 0 END, wt.months ASC, wt.id ASC
         LIMIT 1),
        -1
    )                                                                   AS validade_meses
FROM users u
WHERE u.active = 1
  AND u.role = 'student'
ORDER BY u.goal, u.gender, meses_cadastrado ASC;


-- 3. Teste dos intervalos com dados fictícios (sem depender de alunos reais)
-- Simula alunos com 1, 3, 5, 7, 9, 11, 13 meses para um goal e gender específicos
-- Substitua 'Hipertrofia' e 'masculino' conforme necessário
SELECT
    meses_teste,
    CASE
        WHEN meses_teste <= 2  THEN '<= 2 meses'
        WHEN meses_teste <= 4  THEN '> 2 e <= 4 meses'
        WHEN meses_teste <= 6  THEN '> 4 e <= 6 meses'
        WHEN meses_teste <= 8  THEN '> 6 e <= 8 meses'
        WHEN meses_teste <= 10 THEN '> 8 e <= 10 meses'
        WHEN meses_teste <= 12 THEN '> 10 e <= 12 meses'
        ELSE                        '> 12 meses'
    END AS intervalo,
    (
        SELECT wt.name FROM workout_templates wt
        WHERE wt.active = 1
          AND wt.goal = 'Hipertrofia'
          AND (wt.gender = 'masculino' OR wt.gender IS NULL)
          AND (wt.months IS NULL OR wt.months >= meses_teste)
        ORDER BY CASE WHEN wt.months IS NULL THEN 1 ELSE 0 END, wt.months ASC, wt.id ASC
        LIMIT 1
    ) AS template_selecionado
FROM (
    SELECT 1  AS meses_teste UNION ALL
    SELECT 2  UNION ALL
    SELECT 3  UNION ALL
    SELECT 4  UNION ALL
    SELECT 5  UNION ALL
    SELECT 6  UNION ALL
    SELECT 7  UNION ALL
    SELECT 8  UNION ALL
    SELECT 9  UNION ALL
    SELECT 10 UNION ALL
    SELECT 11 UNION ALL
    SELECT 12 UNION ALL
    SELECT 13 UNION ALL
    SELECT 18 UNION ALL
    SELECT 24
) AS simulacao
ORDER BY meses_teste;


-- 4. Verificar se há gaps (meses sem template coberto) para um goal+gender
SELECT
    n.meses,
    CASE
        WHEN EXISTS (
            SELECT 1 FROM workout_templates wt
            WHERE wt.active = 1
              AND wt.goal = 'Hipertrofia'
              AND (wt.gender = 'masculino' OR wt.gender IS NULL)
              AND (wt.months IS NULL OR wt.months >= n.meses)
        ) THEN '✓ Coberto'
        ELSE '✗ SEM TEMPLATE — gap na configuração!'
    END AS cobertura
FROM (
    SELECT 1 AS meses UNION ALL SELECT 2 UNION ALL SELECT 3 UNION ALL SELECT 4  UNION ALL
    SELECT 5 UNION ALL SELECT 6 UNION ALL SELECT 7 UNION ALL SELECT 8  UNION ALL
    SELECT 9 UNION ALL SELECT 10 UNION ALL SELECT 11 UNION ALL SELECT 12 UNION ALL
    SELECT 13 UNION ALL SELECT 18 UNION ALL SELECT 24
) n
ORDER BY n.meses;
