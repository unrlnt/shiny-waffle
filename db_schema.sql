CREATE TABLE tasks (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    start_time DATETIME NOT NULL,
    deadline DATETIME NOT NULL,
    duration INT NOT NULL, -- in minutes
    priority FLOAT NOT NULL, -- percentage range 0.0 to 1.0
    category VARCHAR(50),
    status ENUM('pending', 'completed', 'failed') DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    task_id INT,
    message TEXT,
    log_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
);

-- Table for defining schedules for categories
CREATE TABLE schedules (
    id INT AUTO_INCREMENT PRIMARY KEY,
    category VARCHAR(50) NOT NULL, -- e.g., 'work', 'private', 'exercise', etc.
    day_of_week ENUM('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday') NOT NULL,
    start_hour TIME NOT NULL, -- e.g., '09:00:00'
    end_hour TIME NOT NULL -- e.g., '13:00:00'
);

-- Table for storing recurring patterns or additional settings
CREATE TABLE recurring_settings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    task_id INT,
    recurring_pattern VARCHAR(255), -- e.g., 'weekly, Monday'
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
);
