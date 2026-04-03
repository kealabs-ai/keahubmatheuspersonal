# 📋 Área do Aluno — APIs e Banco de Dados (Microserviços)

> Documento de referência para implementação no projeto **HubMatheusPersonal**.
> Cada seção representa um microserviço independente.

---

## 🏗️ Arquitetura Geral

```
hubmatheuspersonal/
├── ms-auth/          → Autenticação e sessão
├── ms-users/         → Perfil e dados do aluno
├── ms-workouts/      → Treinos e exercícios
├── ms-progress/      → Evolução, métricas e fotos
├── ms-nutrition/     → Plano nutricional
└── ms-notifications/ → Notificações e conquistas
```

**Base URL sugerida:** `https://api.matheuspersonal.com.br/v1`

**Autenticação:** JWT Bearer Token em todos os endpoints (exceto login/register)

```
Authorization: Bearer <token>
```

---

## 1. 🔐 ms-auth — Autenticação

### Tabelas

```sql
CREATE TABLE users (
  id            INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  name          VARCHAR(100)        NOT NULL,
  email         VARCHAR(150)        NOT NULL UNIQUE,
  password_hash VARCHAR(255)        NOT NULL,
  phone         VARCHAR(20),
  birthdate     DATE,
  goal          ENUM('Hipertrofia','Emagrecimento','Condicionamento','Saúde Geral','Performance') DEFAULT 'Hipertrofia',
  plan          ENUM('BRONZE','PRATA','OURO','DIAMANTE') DEFAULT 'BRONZE',
  plan_start    DATE,
  plan_renewal  DATE,
  avatar_url    VARCHAR(500),
  role          ENUM('student','admin','nutritionist','trainer') DEFAULT 'student',
  active        TINYINT(1) DEFAULT 1,
  created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at    DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE refresh_tokens (
  id         INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  user_id    INT UNSIGNED NOT NULL,
  token      VARCHAR(500) NOT NULL,
  expires_at DATETIME     NOT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
```

### Endpoints

| Método | Rota | Descrição |
|--------|------|-----------|
| POST | `/auth/login` | Login com e-mail e senha |
| POST | `/auth/logout` | Invalidar token |
| POST | `/auth/refresh` | Renovar access token |
| POST | `/auth/forgot-password` | Solicitar reset de senha |
| POST | `/auth/reset-password` | Redefinir senha com token |

#### POST `/auth/login`
```json
// Request
{ "email": "joao@email.com", "password": "123456" }

// Response 200
{
  "access_token": "<jwt>",
  "refresh_token": "<token>",
  "expires_in": 3600,
  "user": {
    "id": 1,
    "name": "João Silva",
    "plan": "OURO",
    "role": "student"
  }
}
```

#### POST `/auth/forgot-password`
```json
// Request
{ "email": "joao@email.com" }

// Response 200
{ "message": "E-mail de recuperação enviado." }
```

---

## 2. 👤 ms-users — Perfil do Aluno

### Tabelas

```sql
-- Extensão de dados físicos (histórico)
CREATE TABLE body_metrics (
  id         INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  user_id    INT UNSIGNED NOT NULL,
  weight     DECIMAL(5,2),          -- kg
  height     DECIMAL(5,1),          -- cm
  body_fat   DECIMAL(4,1),          -- %
  waist      DECIMAL(5,1),          -- cm
  arm        DECIMAL(5,1),          -- cm
  leg        DECIMAL(5,1),          -- cm
  chest      DECIMAL(5,1),          -- cm
  recorded_at DATE NOT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Feedbacks do aluno para o personal - adaptar no já existente
CREATE TABLE student_feedbacks (
  id         INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  user_id    INT UNSIGNED NOT NULL,
  message    TEXT         NOT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
```

### Endpoints

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/users/me` | Retorna dados do usuário logado |
| PUT | `/users/me` | Atualiza dados pessoais |
| PUT | `/users/me/password` | Altera senha |
| POST | `/users/me/avatar` | Upload de foto de perfil |
| GET | `/users/me/metrics` | Histórico de métricas físicas |
| POST | `/users/me/metrics` | Registrar nova medição |
| POST | `/users/me/feedback` | Enviar feedback ao personal |

#### GET `/users/me`
```json
// Response 200
{
  "id": 1,
  "name": "João Silva",
  "email": "joao@email.com",
  "phone": "(35) 99999-0000",
  "birthdate": "1995-03-22",
  "goal": "Hipertrofia",
  "plan": "OURO",
  "plan_start": "2024-01-15",
  "plan_renewal": "2025-01-15",
  "avatar_url": null,
  "latest_metrics": {
    "weight": 83,
    "height": 178,
    "body_fat": 14,
    "waist": 82,
    "arm": 38,
    "leg": 58,
    "recorded_at": "2024-07-01"
  }
}
```

#### POST `/users/me/metrics`
```json
// Request
{
  "weight": 83.0,
  "height": 178,
  "body_fat": 14.0,
  "waist": 82.0,
  "arm": 38.0,
  "leg": 58.0,
  "chest": 100.0,
  "recorded_at": "2024-07-15"
}

// Response 201
{ "id": 42, "message": "Medição registrada com sucesso." }
```

---

## 3. 🏋️ ms-workouts — Treinos

### Tabelas

```sql
-- Planos de treino (semana)
CREATE TABLE workout_plans (
  id           INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  user_id      INT UNSIGNED NOT NULL,
  trainer_id   INT UNSIGNED NOT NULL,
  name         VARCHAR(100) NOT NULL,   -- ex: "Plano Hipertrofia - Semana 1"
  week_start   DATE,
  active       TINYINT(1) DEFAULT 1,
  created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id)    REFERENCES users(id) ON DELETE CASCADE,
  FOREIGN KEY (trainer_id) REFERENCES users(id)
);

-- Dias de treino dentro de um plano
CREATE TABLE workout_days (
  id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  plan_id     INT UNSIGNED NOT NULL,
  week_day    TINYINT NOT NULL,          -- 1=Seg, 2=Ter ... 7=Dom
  name        VARCHAR(100) NOT NULL,     -- ex: "Peito + Tríceps"
  duration_min SMALLINT,
  is_rest     TINYINT(1) DEFAULT 0,
  sort_order  TINYINT DEFAULT 0,
  FOREIGN KEY (plan_id) REFERENCES workout_plans(id) ON DELETE CASCADE
);

-- Exercícios de cada dia
CREATE TABLE exercises (
  id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  day_id      INT UNSIGNED NOT NULL,
  name        VARCHAR(100) NOT NULL,
  muscle_group VARCHAR(50),             -- ex: "Peito", "Tríceps"
  sets        TINYINT,
  reps        VARCHAR(20),              -- ex: "8-12", "Falha", "45s"
  rest_seconds SMALLINT,
  video_url   VARCHAR(500),
  sort_order  TINYINT DEFAULT 0,
  FOREIGN KEY (day_id) REFERENCES workout_days(id) ON DELETE CASCADE
);

-- Registro de execução de treino (log)
CREATE TABLE workout_logs (
  id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  user_id     INT UNSIGNED NOT NULL,
  day_id      INT UNSIGNED NOT NULL,
  started_at  DATETIME,
  finished_at DATETIME,
  completed   TINYINT(1) DEFAULT 0,
  created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  FOREIGN KEY (day_id)  REFERENCES workout_days(id)
);

-- Registro de carga por exercício
CREATE TABLE exercise_logs (
  id           INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  log_id       INT UNSIGNED NOT NULL,
  exercise_id  INT UNSIGNED NOT NULL,
  weight_kg    DECIMAL(6,2),
  reps_done    TINYINT,
  sets_done    TINYINT,
  completed    TINYINT(1) DEFAULT 0,
  FOREIGN KEY (log_id)      REFERENCES workout_logs(id) ON DELETE CASCADE,
  FOREIGN KEY (exercise_id) REFERENCES exercises(id)
);
```

### Endpoints

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/workouts/plan` | Plano ativo da semana do aluno |
| GET | `/workouts/plan/:planId/days` | Dias de treino do plano |
| GET | `/workouts/days/:dayId/exercises` | Exercícios de um dia |
| POST | `/workouts/logs` | Iniciar sessão de treino |
| PUT | `/workouts/logs/:logId` | Finalizar/atualizar sessão |
| POST | `/workouts/logs/:logId/exercises` | Registrar carga de exercício |
| GET | `/workouts/logs/history` | Histórico de treinos realizados |
| GET | `/workouts/streak` | Sequência atual de dias |

#### GET `/workouts/plan`
```json
// Response 200
{
  "plan": {
    "id": 5,
    "name": "Plano Hipertrofia",
    "week_start": "2024-07-15",
    "days": [
      {
        "id": 1,
        "week_day": 1,
        "name": "Peito + Tríceps",
        "duration_min": 55,
        "is_rest": false,
        "status": "done",
        "exercises_count": 6
      },
      {
        "id": 3,
        "week_day": 3,
        "name": "Pernas",
        "duration_min": 65,
        "is_rest": false,
        "status": "today",
        "exercises_count": 6
      }
    ]
  }
}
```

#### POST `/workouts/logs`
```json
// Request
{ "day_id": 3 }

// Response 201
{ "log_id": 88, "started_at": "2024-07-17T16:00:00Z" }
```

#### POST `/workouts/logs/:logId/exercises`
```json
// Request
{
  "exercises": [
    { "exercise_id": 1, "weight_kg": 80, "sets_done": 4, "reps_done": 10, "completed": true },
    { "exercise_id": 2, "weight_kg": 70, "sets_done": 4, "reps_done": 12, "completed": true }
  ]
}

// Response 200
{ "message": "Exercícios registrados com sucesso." }
```

#### GET `/workouts/streak`
```json
// Response 200
{
  "current_streak": 12,
  "longest_streak": 18,
  "trainings_this_week": 3,
  "total_trainings": 87,
  "days_active": 183
}
```

---

## 4. 📈 ms-progress — Evolução

### Tabelas

```sql
-- Histórico de peso (separado para consultas rápidas de gráfico)
CREATE TABLE weight_history (
  id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  user_id     INT UNSIGNED NOT NULL,
  weight_kg   DECIMAL(5,2) NOT NULL,
  recorded_at DATE         NOT NULL,
  created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Recordes pessoais por exercício
CREATE TABLE personal_records (
  id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  user_id     INT UNSIGNED NOT NULL,
  exercise_name VARCHAR(100) NOT NULL,
  weight_kg   DECIMAL(6,2) NOT NULL,
  recorded_at DATE         NOT NULL,
  created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Fotos de progresso
CREATE TABLE progress_photos (
  id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  user_id     INT UNSIGNED NOT NULL,
  photo_url   VARCHAR(500) NOT NULL,
  label       VARCHAR(100),            -- ex: "Início", "3 meses"
  recorded_at DATE         NOT NULL,
  created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Conquistas/badges
CREATE TABLE badges (
  id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  slug        VARCHAR(50)  NOT NULL UNIQUE,  -- ex: "first_workout", "streak_30"
  name        VARCHAR(100) NOT NULL,
  description VARCHAR(255),
  icon        VARCHAR(10),                   -- emoji
  condition_type ENUM('streak','weight_loss','total_workouts','pr','manual') NOT NULL,
  condition_value INT
);

CREATE TABLE user_badges (
  id         INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  user_id    INT UNSIGNED NOT NULL,
  badge_id   INT UNSIGNED NOT NULL,
  earned_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_user_badge (user_id, badge_id),
  FOREIGN KEY (user_id)  REFERENCES users(id)  ON DELETE CASCADE,
  FOREIGN KEY (badge_id) REFERENCES badges(id)
);
```

### Endpoints

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/progress/weight` | Histórico de peso para gráfico |
| POST | `/progress/weight` | Registrar novo peso |
| GET | `/progress/strength/:exercise` | Evolução de carga por exercício |
| GET | `/progress/strength` | Todos os recordes pessoais |
| GET | `/progress/measurements` | Histórico de medidas corporais |
| GET | `/progress/photos` | Fotos de progresso |
| POST | `/progress/photos` | Upload de foto de progresso |
| DELETE | `/progress/photos/:id` | Remover foto |
| GET | `/progress/badges` | Conquistas do aluno (earned + locked) |

#### GET `/progress/weight?period=6m`
```json
// Response 200
{
  "data": [
    { "date": "2024-01", "weight": 92.0 },
    { "date": "2024-02", "weight": 90.5 },
    { "date": "2024-07", "weight": 83.0 }
  ],
  "summary": {
    "start": 92.0,
    "current": 83.0,
    "diff": -9.0
  }
}
```

#### GET `/progress/strength/Supino Reto`
```json
// Response 200
{
  "exercise": "Supino Reto",
  "data": [
    { "date": "2024-01", "weight": 50 },
    { "date": "2024-07", "weight": 72.5 }
  ],
  "record": 72.5,
  "gain": 22.5
}
```

#### GET `/progress/badges`
```json
// Response 200
{
  "earned": [
    { "slug": "first_workout", "name": "Primeiro treino", "icon": "💪", "earned_at": "2024-01-15" },
    { "slug": "streak_12", "name": "Sequência de 12 dias", "icon": "🔥", "earned_at": "2024-07-10" }
  ],
  "locked": [
    { "slug": "streak_30", "name": "30 dias seguidos", "icon": "🏆" },
    { "slug": "goal_weight", "name": "Meta de peso", "icon": "🎯" }
  ]
}
```

---

## 5. 🥗 ms-nutrition — Nutrição

### Tabelas

```sql
-- Nutricionistas
CREATE TABLE nutritionists (
  id         INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  user_id    INT UNSIGNED NOT NULL,   -- referência à tabela users (role=nutritionist)
  crn        VARCHAR(30)  NOT NULL,
  bio        TEXT,
  active     TINYINT(1) DEFAULT 1,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Planos nutricionais
CREATE TABLE nutrition_plans (
  id               INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  user_id          INT UNSIGNED NOT NULL,
  nutritionist_id  INT UNSIGNED NOT NULL,
  name             VARCHAR(100) NOT NULL,   -- ex: "Plano Hipertrofia - Julho"
  goal_calories    SMALLINT,
  goal_protein_g   SMALLINT,
  goal_carbs_g     SMALLINT,
  goal_fat_g       SMALLINT,
  water_goal_ml    SMALLINT DEFAULT 3000,
  active           TINYINT(1) DEFAULT 1,
  valid_from       DATE,
  valid_until      DATE,
  created_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id)         REFERENCES users(id) ON DELETE CASCADE,
  FOREIGN KEY (nutritionist_id) REFERENCES nutritionists(id)
);

-- Refeições do plano
CREATE TABLE meals (
  id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  plan_id     INT UNSIGNED NOT NULL,
  meal_type   VARCHAR(50)  NOT NULL,   -- ex: "Café da Manhã", "Pré-Treino"
  meal_time   TIME,
  icon        VARCHAR(10),             -- emoji
  is_highlight TINYINT(1) DEFAULT 0,  -- destaque pré/pós treino
  sort_order  TINYINT DEFAULT 0,
  FOREIGN KEY (plan_id) REFERENCES nutrition_plans(id) ON DELETE CASCADE
);

-- Alimentos de cada refeição
CREATE TABLE meal_items (
  id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  meal_id     INT UNSIGNED NOT NULL,
  food_name   VARCHAR(150) NOT NULL,
  quantity    VARCHAR(50)  NOT NULL,   -- ex: "200g", "1 unidade"
  calories    SMALLINT,
  protein_g   DECIMAL(5,1),
  carbs_g     DECIMAL(5,1),
  fat_g       DECIMAL(5,1),
  sort_order  TINYINT DEFAULT 0,
  FOREIGN KEY (meal_id) REFERENCES meals(id) ON DELETE CASCADE
);

-- Registro de refeições consumidas no dia
CREATE TABLE meal_logs (
  id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  user_id     INT UNSIGNED NOT NULL,
  meal_id     INT UNSIGNED NOT NULL,
  consumed_at DATE         NOT NULL,
  created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_meal_log (user_id, meal_id, consumed_at),
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  FOREIGN KEY (meal_id) REFERENCES meals(id)
);

-- Recados da nutricionista para o aluno
CREATE TABLE nutritionist_notes (
  id               INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  user_id          INT UNSIGNED NOT NULL,
  nutritionist_id  INT UNSIGNED NOT NULL,
  message          TEXT         NOT NULL,
  created_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at       DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id)         REFERENCES users(id) ON DELETE CASCADE,
  FOREIGN KEY (nutritionist_id) REFERENCES nutritionists(id)
);
```

### Endpoints

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/nutrition/plan` | Plano nutricional ativo do aluno |
| GET | `/nutrition/plan/:planId/meals` | Refeições do plano com itens |
| GET | `/nutrition/today` | Refeições do dia + macros consumidos |
| POST | `/nutrition/logs` | Marcar refeição como consumida |
| DELETE | `/nutrition/logs/:mealId` | Desmarcar refeição |
| GET | `/nutrition/note` | Último recado da nutricionista |
| GET | `/nutrition/history` | Histórico de planos anteriores |

#### GET `/nutrition/plan`
```json
// Response 200
{
  "plan": {
    "id": 3,
    "name": "Plano Hipertrofia - Julho",
    "goal_calories": 2800,
    "goal_protein_g": 180,
    "goal_carbs_g": 300,
    "goal_fat_g": 70,
    "water_goal_ml": 3000,
    "nutritionist": {
      "name": "Dra. Ana Paula",
      "crn": "CRN-3 12345"
    }
  }
}
```

#### GET `/nutrition/today`
```json
// Response 200
{
  "date": "2024-07-17",
  "meals": [
    {
      "id": 1,
      "meal_type": "Café da Manhã",
      "meal_time": "07:00",
      "icon": "🌅",
      "is_highlight": false,
      "consumed": true,
      "calories": 480,
      "items": [
        { "food_name": "Ovos mexidos", "quantity": "3 unidades", "calories": 210, "protein_g": 18, "carbs_g": 2, "fat_g": 15 }
      ]
    }
  ],
  "totals": {
    "calories_consumed": 480,
    "calories_goal": 2800,
    "protein_g": 18,
    "carbs_g": 2,
    "fat_g": 15
  }
}
```

#### GET `/nutrition/note`
```json
// Response 200
{
  "id": 12,
  "nutritionist": "Dra. Ana Paula",
  "crn": "CRN-3 12345",
  "message": "Lembre-se de beber pelo menos 3L de água hoje...",
  "updated_at": "2024-07-17T08:30:00Z"
}
```

---

## 6. 🔔 ms-notifications — Notificações e Conquistas

### Tabelas

```sql
CREATE TABLE notifications (
  id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  user_id     INT UNSIGNED NOT NULL,
  type        ENUM('badge','plan_renewal','nutritionist_note','trainer_message','system') NOT NULL,
  title       VARCHAR(150) NOT NULL,
  body        TEXT,
  read_at     DATETIME,
  created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
```

### Endpoints

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/notifications` | Listar notificações do aluno |
| PUT | `/notifications/:id/read` | Marcar como lida |
| PUT | `/notifications/read-all` | Marcar todas como lidas |
| GET | `/notifications/unread-count` | Contagem de não lidas |

#### GET `/notifications`
```json
// Response 200
{
  "unread_count": 2,
  "notifications": [
    {
      "id": 5,
      "type": "nutritionist_note",
      "title": "Novo recado da nutricionista",
      "body": "Dra. Ana Paula atualizou seu plano alimentar.",
      "read_at": null,
      "created_at": "2024-07-17T08:30:00Z"
    },
    {
      "id": 4,
      "type": "badge",
      "title": "Conquista desbloqueada! 🔥",
      "body": "Você completou 12 dias seguidos de treino.",
      "read_at": null,
      "created_at": "2024-07-16T19:00:00Z"
    }
  ]
}
```

---

## 7. 📊 Dashboard — Endpoint Agregado

> Endpoint único que o Dashboard consome para montar todos os cards de uma vez, evitando múltiplas requisições.

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/dashboard/summary` | Resumo completo do aluno |

#### GET `/dashboard/summary`
```json
// Response 200
{
  "user": {
    "name": "João Silva",
    "plan": "OURO",
    "plan_renewal": "2025-01-15"
  },
  "stats": {
    "streak": 12,
    "trainings_this_week": 3,
    "days_active": 183
  },
  "week": [
    { "week_day": 1, "name": "Peito + Tríceps", "status": "done" },
    { "week_day": 3, "name": "Pernas",           "status": "today" },
    { "week_day": 7, "name": "Descanso",          "status": "rest" }
  ],
  "today_workout": {
    "day_id": 3,
    "name": "Pernas",
    "duration_min": 65,
    "exercises_count": 6
  },
  "unread_notifications": 2,
  "badges_earned": 4,
  "badges_total": 6
}
```

---

## 8. 🔒 Regras de Acesso por Role

| Role | Permissões |
|------|-----------|
| `student` | Lê/escreve apenas seus próprios dados |
| `trainer` | Lê dados de seus alunos, cria/edita planos de treino |
| `nutritionist` | Lê dados de seus alunos, cria/edita planos nutricionais e recados |
| `admin` | Acesso total |

---

## 9. 📦 Seeds Iniciais Necessários

```sql
-- Badges padrão
INSERT INTO badges (slug, name, icon, condition_type, condition_value) VALUES
('first_workout',  'Primeiro treino',       '💪', 'total_workouts', 1),
('streak_7',       'Sequência de 7 dias',   '🔥', 'streak',         7),
('streak_12',      'Sequência de 12 dias',  '🔥', 'streak',         12),
('streak_30',      '30 dias seguidos',      '🏆', 'streak',         30),
('workouts_50',    '50 treinos realizados', '⚡', 'total_workouts', 50),
('weight_loss_5',  'Perdeu 5kg',            '⚖️', 'weight_loss',    5),
('pr_bench',       'Supino 70kg',           '🏋️', 'pr',             70),
('goal_weight',    'Meta de peso atingida', '🎯', 'manual',         0);
```

---

## 10. 🗂️ Resumo de Tabelas por Microserviço

| Microserviço | Tabelas |
|---|---|
| ms-auth | `users`, `refresh_tokens` |
| ms-users | `body_metrics`, `student_feedbacks` |
| ms-workouts | `workout_plans`, `workout_days`, `exercises`, `workout_logs`, `exercise_logs` |
| ms-progress | `weight_history`, `personal_records`, `progress_photos`, `badges`, `user_badges` |
| ms-nutrition | `nutritionists`, `nutrition_plans`, `meals`, `meal_items`, `meal_logs`, `nutritionist_notes` |
| ms-notifications | `notifications` |

**Total: 19 tabelas**

---

*Documento gerado em: Janeiro 2025*
*Projeto: MatheusPersonal — Área do Aluno*
*Desenvolvido por: Kealabs*
