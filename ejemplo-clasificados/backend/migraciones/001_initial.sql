-- Migración inicial para el sitio de clasificados
-- Tablas: usuarios, categorias, anuncios, favoritos, mensajes, sesiones

-- Tabla de usuarios
CREATE TABLE usuarios (
    id INT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    clave_hash VARCHAR(255) NOT NULL,
    clave_salt VARCHAR(255) NOT NULL,
    creado_en DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Tabla de categorías
CREATE TABLE categorias (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(255) UNIQUE NOT NULL,
    orden INT NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Tabla de anuncios
CREATE TABLE anuncios (
    id INT AUTO_INCREMENT PRIMARY KEY,
    usuario_id INT NOT NULL,
    categoria_id INT NOT NULL,
    titulo VARCHAR(255) NOT NULL,
    descripcion TEXT NOT NULL,
    precio_centavos INT NOT NULL,
    foto_url VARCHAR(500),
    creado_en DATETIME DEFAULT CURRENT_TIMESTAMP,
    actualizado_en DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (categoria_id) REFERENCES categorias(id) ON DELETE CASCADE,
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Tabla de favoritos
CREATE TABLE favoritos (
    usuario_id INT NOT NULL,
    anuncio_id INT NOT NULL,
    creado_en DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (usuario_id, anuncio_id),
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE,
    FOREIGN KEY (anuncio_id) REFERENCES anuncios(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Tabla de mensajes
CREATE TABLE mensajes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    anuncio_id INT NOT NULL,
    de_usuario_id INT NOT NULL,
    a_usuario_id INT NOT NULL,
    cuerpo TEXT NOT NULL,
    creado_en DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (anuncio_id) REFERENCES anuncios(id) ON DELETE CASCADE,
    FOREIGN KEY (de_usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE,
    FOREIGN KEY (a_usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Tabla de sesiones
CREATE TABLE sesiones (
    token VARCHAR(255) PRIMARY KEY,
    usuario_id INT NOT NULL,
    creado_en DATETIME DEFAULT CURRENT_TIMESTAMP,
    expira_en DATETIME NOT NULL,
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;