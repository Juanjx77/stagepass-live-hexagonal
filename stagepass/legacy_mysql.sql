-- Esquema ilustrativo del MySQL legacy (solo consulta). Compatible con MySQL 8.
CREATE TABLE recintos (
  id VARCHAR(20) PRIMARY KEY,
  nombre VARCHAR(120) NOT NULL,
  aforo INT NOT NULL
);
CREATE TABLE asientos (
  id VARCHAR(40) PRIMARY KEY,
  recinto_id VARCHAR(20) NOT NULL,
  codigo_ubicacion VARCHAR(30) NOT NULL,
  precio_base DECIMAL(12,2) NOT NULL,
  FOREIGN KEY (recinto_id) REFERENCES recintos(id)
);
CREATE TABLE eventos (
  id VARCHAR(20) PRIMARY KEY,
  nombre VARCHAR(160) NOT NULL,
  tipo VARCHAR(20) NOT NULL,          -- CONCIERTO | TEATRO | FESTIVAL
  recinto_id VARCHAR(20) NOT NULL,
  fecha_hora DATETIME NOT NULL,
  estado VARCHAR(20) NOT NULL,        -- PROGRAMADO | AGOTADO | CANCELADO
  FOREIGN KEY (recinto_id) REFERENCES recintos(id)
);
INSERT INTO recintos VALUES ('R1', 'Arena Central', 40), ('R2', 'Teatro Municipal', 20);
INSERT INTO asientos VALUES
  ('R1-VIP-A1','R1','VIP-A1',300000.00), ('R1-VIP-A2','R1','VIP-A2',300000.00),
  ('R1-GEN-01','R1','General-01',80000.00), ('R2-PLA-01','R2','Platea-01',120000.00);
INSERT INTO eventos VALUES
  ('E1','Festival Andino de Rock','FESTIVAL','R1','2027-03-20 19:00:00','PROGRAMADO'),
  ('E2','Obra: La Casa de Bernarda Alba','TEATRO','R2','2027-04-02 20:00:00','PROGRAMADO');
