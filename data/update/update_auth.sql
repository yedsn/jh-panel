ALTER TABLE sites ADD COLUMN auth_enabled TINYINT(1) DEFAULT 0;
ALTER TABLE sites ADD COLUMN auth_users TEXT;
