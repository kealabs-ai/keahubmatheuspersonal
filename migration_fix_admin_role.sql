-- Corrige role NULL para 'student' em todos os usuários
UPDATE users SET role = 'student' WHERE role IS NULL;

-- Promove o usuário admin pelo e-mail (ajuste o e-mail conforme necessário)
UPDATE users SET role = 'admin' WHERE email = 'admin@matheuspersonal.com.br';

-- Verificar resultado:
-- SELECT id_user, name, email, role FROM users ORDER BY role;
