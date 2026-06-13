-- =====================================================
-- MIGRATION COMPLÈTE — Synchronisation schéma BDD
-- Colonnes ajoutées au modèle SQLAlchemy après init
-- À exécuter UNE SEULE FOIS sur cyber_insurance
-- =====================================================

-- 1. dossiers : lien client
ALTER TABLE dossiers
  ADD COLUMN IF NOT EXISTS id_client INTEGER REFERENCES utilisateurs(id_user);

-- 2. devis : motif de refus
ALTER TABLE devis
  ADD COLUMN IF NOT EXISTS motif TEXT;

-- 3. documents : nom du fichier + taille
ALTER TABLE documents
  ADD COLUMN IF NOT EXISTS nom VARCHAR(255);
ALTER TABLE documents
  ADD COLUMN IF NOT EXISTS taille_ko INTEGER;

-- 4. questions : options choix multiple + score inversé
ALTER TABLE questions
  ADD COLUMN IF NOT EXISTS options JSONB;
ALTER TABLE questions
  ADD COLUMN IF NOT EXISTS inverse BOOLEAN DEFAULT FALSE;

-- =====================================================
-- Vérification finale
-- =====================================================
SELECT table_name, column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'public'
  AND (
    (table_name = 'dossiers'  AND column_name = 'id_client')  OR
    (table_name = 'devis'     AND column_name = 'motif')       OR
    (table_name = 'documents' AND column_name IN ('nom','taille_ko')) OR
    (table_name = 'questions' AND column_name IN ('options','inverse'))
  )
ORDER BY table_name, column_name;
