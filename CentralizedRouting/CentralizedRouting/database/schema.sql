-- database/schema.sql
-- Esquema de la base de datos centralized_routing_db
-- Ejecutar una vez antes de iniciar el sistema:
--   mysql -u root -p < schema.sql

CREATE DATABASE IF NOT EXISTS centralized_routing_db
    CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE centralized_routing_db;

-- ──────────────────────────────────────────────
-- FR-01: Tabla de routers registrados
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS routers (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    router_id  VARCHAR(20)  NOT NULL UNIQUE,
    ip         VARCHAR(45)  NOT NULL,
    port       INT          NOT NULL,
    status     VARCHAR(20)  NOT NULL DEFAULT 'ACTIVE',
    created_at DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP
);

-- ──────────────────────────────────────────────
-- FR-03: Tabla de topología (enlaces entre routers)
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS topology (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    source_router VARCHAR(20) NOT NULL,
    target_router VARCHAR(20) NOT NULL,
    cost          INT         NOT NULL,
    updated_at    DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_link (source_router, target_router)
);

-- ──────────────────────────────────────────────
-- FR-05: Tablas de ruteo calculadas
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS routing_tables (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    router_id   VARCHAR(20) NOT NULL,
    destination VARCHAR(20) NOT NULL,
    next_hop    VARCHAR(20) NOT NULL,
    cost        INT         NOT NULL,
    computed_at DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_router (router_id)
);

-- ──────────────────────────────────────────────
-- FR-09: Log de eventos del sistema
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS event_logs (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    event_type VARCHAR(50)  NOT NULL,
    router_id  VARCHAR(20)  NOT NULL,
    detail     TEXT,
    logged_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
);
