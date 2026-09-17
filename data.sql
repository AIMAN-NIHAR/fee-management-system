-- Your real data, copied in as-is from MySQL.
-- IDs are preserved so foreign key relationships stay correct.

INSERT INTO users (id, username, password, role) VALUES
(1, 'admin', 'admin123', 'admin'),
(7, 'sawaira@gmail.com', 'abcd', 'student'),
(11, 'insha@gmail.com', '567', 'student'),
(13, 'mehwaish@gmail.com', '12345', 'student'),
(14, 'maaz@gmail.com', '456', 'student'),
(17, 'hina@gmail.com', '123', 'student');

INSERT INTO students (id, user_id, full_name, roll_number, department, semester) VALUES
(3, 7, 'sawaira', '56', 'cs', 7),
(7, 11, 'insha', '89', 'cs', 2),
(9, 13, 'mehwaish nihar', '30', 'cs', 7),
(10, 14, 'maaz khan', '99', 'short course', 2),
(12, 17, 'hina', '90', 'english language', 1);

INSERT INTO fees (id, student_id, total_amount, due_date, status) VALUES
(4, 3, 6789.00, '2026-08-22', 'unpaid'),
(5, 3, 4000.00, '2026-08-24', 'paid'),
(6, 7, 5000.00, '2026-08-25', 'paid'),
(7, 9, 90000.00, '2026-09-06', 'partial');

INSERT INTO payments (id, fee_id, amount_paid, payment_date) VALUES
(3, 6, 3000.00, '2026-08-20'),
(4, 5, 20000.00, '2026-09-06'),
(5, 7, 1000.00, '2026-09-06'),
(6, 6, 20000.00, '2026-09-06'),
(7, 7, 2000.00, '2026-09-10');