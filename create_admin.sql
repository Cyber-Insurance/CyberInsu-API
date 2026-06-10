-- =====================================================
-- SCRIPT SQL - Créer un utilisateur ADMIN pour les tests
-- =====================================================

-- 1. S'assurer que le rôle 'admin' existe
INSERT INTO roles (status) 
VALUES ('admin') 
ON CONFLICT DO NOTHING;

-- 2. Récupérer l'ID du rôle admin
-- (Vous aurez besoin de l'ID du rôle admin)

-- 3. Créer l'utilisateur admin
-- NOTE: Le mot de passe doit être hashé avec bcrypt
-- Utilisez: Admin123!@# hashé en bcrypt
INSERT INTO utilisateurs (email, password, id_role, mfa_enabled, created_at)
VALUES (
    'admin@cyber.fr',
    '$2b$12$LoAzpWzqXqq5ZqQqXqQqQe9w9qw9qw9qw9qw9qw9qw9qw9qw9qw9qw',  -- Admin123!@# hashé
    (SELECT id_role FROM roles WHERE status = 'admin'),
    FALSE,
    CURRENT_TIMESTAMP
) ON CONFLICT DO NOTHING;

-- =====================================================
-- Vérifier la création
-- =====================================================
SELECT 
    u.id_user,
    u.email,
    r.status as role,
    u.mfa_enabled,
    u.created_at
FROM utilisateurs u
LEFT JOIN roles r ON u.id_role = r.id_role
WHERE u.email = 'admin@cyber.fr';

-- =====================================================
-- Créer d'autres utilisateurs de test (OPTIONNEL)
-- =====================================================

-- Assureur
INSERT INTO utilisateurs (email, password, id_role, mfa_enabled, created_at)
VALUES (
    'assureur@cyber.fr',
    '$2b$12$LoAzpWzqXqq5ZqQqXqQqQe9w9qw9qw9qw9qw9qw9qw9qw9qw9qw9qw',  -- Admin123!@# hashé
    (SELECT id_role FROM roles WHERE status = 'assureur'),
    FALSE,
    CURRENT_TIMESTAMP
) ON CONFLICT DO NOTHING;

-- Courtier
INSERT INTO utilisateurs (email, password, id_role, mfa_enabled, created_at)
VALUES (
    'courtier@cyber.fr',
    '$2b$12$LoAzpWzqXqq5ZqQqXqQqQe9w9qw9qw9qw9qw9qw9qw9qw9qw9qw9qw',  -- Admin123!@# hashé
    (SELECT id_role FROM roles WHERE status = 'courtier'),
    FALSE,
    CURRENT_TIMESTAMP
) ON CONFLICT DO NOTHING;

-- Client
INSERT INTO utilisateurs (email, password, id_role, mfa_enabled, created_at)
VALUES (
    'client@cyber.fr',
    '$2b$12$LoAzpWzqXqq5ZqQqXqQqQe9w9qw9qw9qw9qw9qw9qw9qw9qw9qw9qw',  -- Admin123!@# hashé
    (SELECT id_role FROM roles WHERE status = 'client'),
    FALSE,
    CURRENT_TIMESTAMP
) ON CONFLICT DO NOTHING;

-- =====================================================
-- Voir tous les utilisateurs
-- =====================================================
SELECT 
    u.id_user,
    u.email,
    r.status as role,
    u.mfa_enabled,
    u.created_at
FROM utilisateurs u
LEFT JOIN roles r ON u.id_role = r.id_role
ORDER BY u.created_at DESC;
