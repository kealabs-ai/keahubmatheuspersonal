CREATE TABLE IF NOT EXISTS users (
    id_user INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    phone VARCHAR(15) NOT NULL,
    cpf VARCHAR(14) NOT NULL UNIQUE,
    birth_date DATE NOT NULL,
    cep VARCHAR(9) NOT NULL,
    address VARCHAR(255) NOT NULL,
    number VARCHAR(20) NOT NULL,
    neighborhood VARCHAR(100) NOT NULL,
    city VARCHAR(100) NOT NULL,
    state VARCHAR(2) NOT NULL,
    country_code VARCHAR(5) DEFAULT '+55',
    username VARCHAR(100) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS subscriptions (
    id_subscription INT PRIMARY KEY AUTO_INCREMENT,
    id_user INT NOT NULL,
    plan_name VARCHAR(100) NOT NULL,
    plan_price DECIMAL(10,2) NOT NULL,
    plan_frequency VARCHAR(50) NOT NULL,
    status ENUM('active', 'inactive', 'cancelled') DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (id_user) REFERENCES users(id_user)
);

CREATE TABLE IF NOT EXISTS credit_cards (
    id_card INT PRIMARY KEY AUTO_INCREMENT,
    id_user INT NOT NULL,
    last_four_digits CHAR(4) NOT NULL,
    card_brand VARCHAR(50) NOT NULL,
    is_recurring BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (id_user) REFERENCES users(id_user)
);

CREATE TABLE IF NOT EXISTS leads (
    id_lead INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(255),
    email VARCHAR(255),
    phone VARCHAR(15),
    source VARCHAR(100),
    message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS coupons (
    id_coupon INT PRIMARY KEY AUTO_INCREMENT,
    code VARCHAR(50) NOT NULL UNIQUE,
    description VARCHAR(255),
    discount_type ENUM('percent', 'fixed') NOT NULL,
    discount_value DECIMAL(10,2) NOT NULL,
    valid_from DATE NOT NULL,
    valid_until DATE NOT NULL,
    usage_limit INT DEFAULT NULL,
    usage_count INT DEFAULT 0,
    min_purchase_amount DECIMAL(10,2) DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS coupon_usage (
    id_usage INT PRIMARY KEY AUTO_INCREMENT,
    id_coupon INT NOT NULL,
    id_user INT NOT NULL,
    order_id VARCHAR(100),
    discount_applied DECIMAL(10,2) NOT NULL,
    used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (id_coupon) REFERENCES coupons(id_coupon),
    FOREIGN KEY (id_user) REFERENCES users(id_user)
);

CREATE TABLE IF NOT EXISTS orders (
    id_order INT PRIMARY KEY AUTO_INCREMENT,
    order_number VARCHAR(100) NOT NULL UNIQUE,
    id_user INT NOT NULL,
    subtotal DECIMAL(10,2) NOT NULL,
    discount_amount DECIMAL(10,2) DEFAULT 0,
    total_amount DECIMAL(10,2) NOT NULL,
    payment_method ENUM('credit', 'debit', 'pix') NOT NULL,
    payment_status ENUM('pending', 'approved', 'rejected', 'cancelled') DEFAULT 'pending',
    id_coupon INT DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (id_user) REFERENCES users(id_user),
    FOREIGN KEY (id_coupon) REFERENCES coupons(id_coupon)
);

CREATE TABLE IF NOT EXISTS order_items (
    id_order_item INT PRIMARY KEY AUTO_INCREMENT,
    id_order INT NOT NULL,
    plan_name VARCHAR(100) NOT NULL,
    plan_price DECIMAL(10,2) NOT NULL,
    plan_frequency VARCHAR(50) NOT NULL,
    quantity INT DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (id_order) REFERENCES orders(id_order)
);

CREATE TABLE IF NOT EXISTS payments (
    id_payment INT PRIMARY KEY AUTO_INCREMENT,
    id_order INT NOT NULL,
    payment_method ENUM('credit', 'debit', 'pix') NOT NULL,
    payment_status ENUM('pending', 'approved', 'rejected', 'refunded') DEFAULT 'pending',
    amount DECIMAL(10,2) NOT NULL,
    installments INT DEFAULT 1,
    transaction_id VARCHAR(255),
    pix_code TEXT,
    card_last_digits CHAR(4),
    card_brand VARCHAR(50),
    paid_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (id_order) REFERENCES orders(id_order)
);

CREATE TABLE IF NOT EXISTS user_addresses (
    id_address INT PRIMARY KEY AUTO_INCREMENT,
    id_user INT NOT NULL,
    cep VARCHAR(9) NOT NULL,
    address VARCHAR(255) NOT NULL,
    number VARCHAR(20) NOT NULL,
    complement VARCHAR(100),
    neighborhood VARCHAR(100) NOT NULL,
    city VARCHAR(100) NOT NULL,
    state VARCHAR(2) NOT NULL,
    is_primary BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (id_user) REFERENCES users(id_user)
);

CREATE TABLE IF NOT EXISTS feedbacks (
    id_feedback INT PRIMARY KEY AUTO_INCREMENT,
    name        VARCHAR(255) NOT NULL,
    age         TINYINT UNSIGNED NOT NULL,
    city        VARCHAR(100) NOT NULL,
    title       VARCHAR(255) NOT NULL,
    testimonial TEXT NOT NULL,
    rating      TINYINT UNSIGNED NOT NULL CHECK (rating BETWEEN 1 AND 5),
    status      ENUM('pending', 'approved', 'rejected') DEFAULT 'pending',
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =============================================
-- ÁREA DO ALUNO — Tabelas dos microserviços
-- =============================================

-- ms-auth: colunas extras na tabela users existente
ALTER TABLE users
  ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255),
  ADD COLUMN IF NOT EXISTS birthdate DATE,
  ADD COLUMN IF NOT EXISTS goal ENUM('Hipertrofia','Emagrecimento','Condicionamento','Saúde Geral','Performance') DEFAULT 'Hipertrofia',
  ADD COLUMN IF NOT EXISTS plan ENUM('BRONZE','PRATA','OURO','DIAMANTE') DEFAULT NULL,
  ADD COLUMN IF NOT EXISTS plan_start DATE,
  ADD COLUMN IF NOT EXISTS plan_renewal DATE,
  ADD COLUMN IF NOT EXISTS avatar_url VARCHAR(500),
  ADD COLUMN IF NOT EXISTS role ENUM('student','admin','nutritionist','trainer') DEFAULT 'student',
  ADD COLUMN IF NOT EXISTS active TINYINT(1) DEFAULT 1;

CREATE TABLE IF NOT EXISTS refresh_tokens (
  id         INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  user_id    INT NOT NULL,
  token      VARCHAR(500) NOT NULL,
  expires_at DATETIME     NOT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id_user) ON DELETE CASCADE
);

-- ms-users
CREATE TABLE IF NOT EXISTS body_metrics (
  id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  user_id     INT UNSIGNED NOT NULL,
  weight      DECIMAL(5,2),
  height      DECIMAL(5,1),
  body_fat    DECIMAL(4,1),
  waist       DECIMAL(5,1),
  arm         DECIMAL(5,1),
  leg         DECIMAL(5,1),
  chest       DECIMAL(5,1),
  recorded_at DATE NOT NULL,
  created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id_user) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS student_feedbacks (
  id         INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  user_id    INT UNSIGNED NOT NULL,
  message    TEXT NOT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id_user) ON DELETE CASCADE
);

-- ms-workouts
CREATE TABLE IF NOT EXISTS workout_plans (
  id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  user_id     INT UNSIGNED NOT NULL,
  trainer_id  INT UNSIGNED NOT NULL,
  name        VARCHAR(100) NOT NULL,
  week_start  DATE,
  active      TINYINT(1) DEFAULT 1,
  created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id)    REFERENCES users(id_user) ON DELETE CASCADE,
  FOREIGN KEY (trainer_id) REFERENCES users(id_user)
);

CREATE TABLE IF NOT EXISTS workout_days (
  id           INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  plan_id      INT UNSIGNED NOT NULL,
  week_day     TINYINT NOT NULL,
  name         VARCHAR(100) NOT NULL,
  duration_min SMALLINT,
  is_rest      TINYINT(1) DEFAULT 0,
  sort_order   TINYINT DEFAULT 0,
  FOREIGN KEY (plan_id) REFERENCES workout_plans(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS exercises (
  id           INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  day_id       INT UNSIGNED NOT NULL,
  name         VARCHAR(100) NOT NULL,
  muscle_group VARCHAR(50),
  sets         TINYINT,
  reps         VARCHAR(20),
  rest_seconds SMALLINT,
  video_url    VARCHAR(500),
  sort_order   TINYINT DEFAULT 0,
  FOREIGN KEY (day_id) REFERENCES workout_days(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS workout_logs (
  id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  user_id     INT UNSIGNED NOT NULL,
  day_id      INT UNSIGNED NOT NULL,
  started_at  DATETIME,
  finished_at DATETIME,
  completed   TINYINT(1) DEFAULT 0,
  created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id_user) ON DELETE CASCADE,
  FOREIGN KEY (day_id)  REFERENCES workout_days(id)
);

CREATE TABLE IF NOT EXISTS exercise_logs (
  id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  log_id      INT UNSIGNED NOT NULL,
  exercise_id INT UNSIGNED NOT NULL,
  weight_kg   DECIMAL(6,2),
  reps_done   TINYINT,
  sets_done   TINYINT,
  completed   TINYINT(1) DEFAULT 0,
  FOREIGN KEY (log_id)      REFERENCES workout_logs(id) ON DELETE CASCADE,
  FOREIGN KEY (exercise_id) REFERENCES exercises(id)
);

-- ms-progress
CREATE TABLE IF NOT EXISTS weight_history (
  id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  user_id     INT UNSIGNED NOT NULL,
  weight_kg   DECIMAL(5,2) NOT NULL,
  recorded_at DATE NOT NULL,
  created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id_user) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS personal_records (
  id            INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  user_id       INT UNSIGNED NOT NULL,
  exercise_name VARCHAR(100) NOT NULL,
  weight_kg     DECIMAL(6,2) NOT NULL,
  recorded_at   DATE NOT NULL,
  created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id_user) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS progress_photos (
  id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  user_id     INT UNSIGNED NOT NULL,
  photo_url   VARCHAR(500) NOT NULL,
  label       VARCHAR(100),
  recorded_at DATE NOT NULL,
  created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id_user) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS badges (
  id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  slug            VARCHAR(50)  NOT NULL UNIQUE,
  name            VARCHAR(100) NOT NULL,
  description     VARCHAR(255),
  icon            VARCHAR(10),
  condition_type  ENUM('streak','weight_loss','total_workouts','pr','manual') NOT NULL,
  condition_value INT
);

CREATE TABLE IF NOT EXISTS user_badges (
  id        INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  user_id   INT UNSIGNED NOT NULL,
  badge_id  INT UNSIGNED NOT NULL,
  earned_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_user_badge (user_id, badge_id),
  FOREIGN KEY (user_id)  REFERENCES users(id_user) ON DELETE CASCADE,
  FOREIGN KEY (badge_id) REFERENCES badges(id)
);

-- ms-nutrition
CREATE TABLE IF NOT EXISTS nutritionists (
  id      INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  user_id INT UNSIGNED NOT NULL,
  crn     VARCHAR(30)  NOT NULL,
  bio     TEXT,
  active  TINYINT(1) DEFAULT 1,
  FOREIGN KEY (user_id) REFERENCES users(id_user) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS nutrition_plans (
  id               INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  user_id          INT UNSIGNED NOT NULL,
  nutritionist_id  INT UNSIGNED NOT NULL,
  name             VARCHAR(100) NOT NULL,
  goal_calories    SMALLINT,
  goal_protein_g   SMALLINT,
  goal_carbs_g     SMALLINT,
  goal_fat_g       SMALLINT,
  water_goal_ml    SMALLINT DEFAULT 3000,
  active           TINYINT(1) DEFAULT 1,
  valid_from       DATE,
  valid_until      DATE,
  created_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id)         REFERENCES users(id_user) ON DELETE CASCADE,
  FOREIGN KEY (nutritionist_id) REFERENCES nutritionists(id)
);

CREATE TABLE IF NOT EXISTS meals (
  id           INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  plan_id      INT UNSIGNED NOT NULL,
  meal_type    VARCHAR(50)  NOT NULL,
  meal_time    TIME,
  icon         VARCHAR(10),
  is_highlight TINYINT(1) DEFAULT 0,
  sort_order   TINYINT DEFAULT 0,
  FOREIGN KEY (plan_id) REFERENCES nutrition_plans(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS meal_items (
  id         INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  meal_id    INT UNSIGNED NOT NULL,
  food_name  VARCHAR(150) NOT NULL,
  quantity   VARCHAR(50)  NOT NULL,
  calories   SMALLINT,
  protein_g  DECIMAL(5,1),
  carbs_g    DECIMAL(5,1),
  fat_g      DECIMAL(5,1),
  sort_order TINYINT DEFAULT 0,
  FOREIGN KEY (meal_id) REFERENCES meals(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS meal_logs (
  id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  user_id     INT UNSIGNED NOT NULL,
  meal_id     INT UNSIGNED NOT NULL,
  consumed_at DATE NOT NULL,
  created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_meal_log (user_id, meal_id, consumed_at),
  FOREIGN KEY (user_id) REFERENCES users(id_user) ON DELETE CASCADE,
  FOREIGN KEY (meal_id) REFERENCES meals(id)
);

CREATE TABLE IF NOT EXISTS nutritionist_notes (
  id               INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  user_id          INT UNSIGNED NOT NULL,
  nutritionist_id  INT UNSIGNED NOT NULL,
  message          TEXT NOT NULL,
  created_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at       DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id)         REFERENCES users(id_user) ON DELETE CASCADE,
  FOREIGN KEY (nutritionist_id) REFERENCES nutritionists(id)
);

-- ms-notifications
CREATE TABLE IF NOT EXISTS notifications (
  id         INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  user_id    INT UNSIGNED NOT NULL,
  type       ENUM('badge','plan_renewal','nutritionist_note','trainer_message','system') NOT NULL,
  title      VARCHAR(150) NOT NULL,
  body       TEXT,
  read_at    DATETIME,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id_user) ON DELETE CASCADE
);

-- ms-videos
CREATE TABLE IF NOT EXISTS videos (
  id            INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  title         VARCHAR(255) NOT NULL,
  description   TEXT,
  url           VARCHAR(500) NOT NULL,
  thumbnail_url VARCHAR(500),
  category      VARCHAR(50) DEFAULT 'Geral',
  duration_min  SMALLINT,
  created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Seeds: badges padrão
INSERT IGNORE INTO badges (slug, name, icon, condition_type, condition_value) VALUES
('first_workout',  'Primeiro treino',       '💪', 'total_workouts', 1),
('streak_7',       'Sequência de 7 dias',   '🔥', 'streak',         7),
('streak_12',      'Sequência de 12 dias',  '🔥', 'streak',         12),
('streak_30',      '30 dias seguidos',      '🏆', 'streak',         30),
('workouts_50',    '50 treinos realizados', '⚡', 'total_workouts', 50),
('weight_loss_5',  'Perdeu 5kg',            '⚖️', 'weight_loss',    5),
('pr_bench',       'Supino 70kg',           '🏋️', 'pr',             70),
('goal_weight',    'Meta de peso atingida', '🎯', 'manual',         0);
