CREATE DATABASE IF NOT EXISTS foodrescue;
USE foodrescue;

DROP TABLE IF EXISTS food_requests;
DROP TABLE IF EXISTS food_donations;
DROP TABLE IF EXISTS users;

CREATE TABLE users (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(100) NOT NULL,
  email VARCHAR(120) NOT NULL UNIQUE,
  password VARCHAR(255) NOT NULL,
  role ENUM('donor','receiver','admin') NOT NULL,
  phone VARCHAR(20),
  address TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE food_donations (
  id INT AUTO_INCREMENT PRIMARY KEY,
  donor_id INT NOT NULL,
  food_name VARCHAR(120) NOT NULL,
  food_type VARCHAR(50) NOT NULL,
  quantity VARCHAR(60) NOT NULL,
  location VARCHAR(150) NOT NULL,
  pickup_address TEXT NOT NULL,
  expiry_datetime DATETIME NOT NULL,
  description TEXT,
  status VARCHAR(30) DEFAULT 'Available',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (donor_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE food_requests (
  id INT AUTO_INCREMENT PRIMARY KEY,
  food_id INT NOT NULL,
  receiver_id INT NOT NULL,
  message TEXT,
  request_status VARCHAR(30) DEFAULT 'Pending',
  requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (food_id) REFERENCES food_donations(id) ON DELETE CASCADE,
  FOREIGN KEY (receiver_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Admin password is admin123
INSERT INTO users (name,email,password,role,phone,address) VALUES
('Admin','admin@foodrescue.com','scrypt:32768:8:1$hjQ7kbLmUl4Kv8ET$b94bbafa055d585e9b9b1ea1f54f7c48cbb1a29599ab5edbcfacb4fa5d33b131c10c9581804ae96049506daec31b741a9765a32237ceb4a9099c1c31cdd3d103','admin','9999999999','Admin Office');
