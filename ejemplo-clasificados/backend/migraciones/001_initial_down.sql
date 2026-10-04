-- Script de reversa para la migración inicial
-- Elimina las tablas en orden inverso a su creación para respetar las claves foráneas

DROP TABLE IF EXISTS sesiones;
DROP TABLE IF EXISTS mensajes;
DROP TABLE IF EXISTS favoritos;
DROP TABLE IF EXISTS anuncios;
DROP TABLE IF EXISTS usuarios;
DROP TABLE IF EXISTS categorias;