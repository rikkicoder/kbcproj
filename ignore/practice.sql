CREATE DATABASE kbc_game;
USE kbc_game;
CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    uid VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    dob DATE NOT NULL,
    qualification VARCHAR(100) NOT NULL,
    status ENUM('waiting', 'accepted', 'rejected') DEFAULT 'waiting'
);
CREATE TABLE questions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    question TEXT NOT NULL,
    difficulty VARCHAR(10) NOT NULL,
    category VARCHAR(50),
    correct_answer VARCHAR(255) NOT NULL,
    incorrect_answers JSON NOT NULL
);
TRUNCATE TABLE users;
SELECT * FROM users;
TRUNCATE TABLE questions;
SELECT * FROM questions;