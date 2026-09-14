-- Migration 017: Drop macro_ideas_theme_check constraint to allow dynamic emerging themes.
ALTER TABLE macro_ideas DROP CONSTRAINT IF EXISTS macro_ideas_theme_check;
