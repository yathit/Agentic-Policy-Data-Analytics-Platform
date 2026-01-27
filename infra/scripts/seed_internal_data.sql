-- Seed script for mock IMDA internal datasets
-- Creates policy-plausible synthetic data for demonstration purposes

-- Drop tables if they exist
DROP TABLE IF EXISTS ai_workforce_programmes CASCADE;
DROP TABLE IF EXISTS digital_sector_employment CASCADE;
DROP TABLE IF EXISTS online_safety_incidents_summary CASCADE;
DROP TABLE IF EXISTS emerging_tech_adoption_index CASCADE;

-- 1. Digital Sector Employment
-- Tracks employment in various digital industry segments
CREATE TABLE digital_sector_employment (
    id SERIAL PRIMARY KEY,
    year INTEGER NOT NULL,
    quarter VARCHAR(2) NOT NULL,  -- Q1, Q2, Q3, Q4
    sector VARCHAR(100) NOT NULL,
    total_employees INTEGER NOT NULL,
    local_employees INTEGER NOT NULL,
    foreign_employees INTEGER NOT NULL,
    professional_roles INTEGER NOT NULL,
    technical_roles INTEGER NOT NULL,
    average_salary_sgd DECIMAL(10, 2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Sample data for digital sector employment (2022-2024)
INSERT INTO digital_sector_employment
(year, quarter, sector, total_employees, local_employees, foreign_employees, professional_roles, technical_roles, average_salary_sgd)
VALUES
    (2022, 'Q1', 'Software Development', 28500, 19200, 9300, 15200, 13300, 7850.00),
    (2022, 'Q2', 'Software Development', 29100, 19600, 9500, 15600, 13500, 7920.00),
    (2022, 'Q3', 'Software Development', 29800, 20100, 9700, 16100, 13700, 8010.00),
    (2022, 'Q4', 'Software Development', 30200, 20400, 9800, 16300, 13900, 8100.00),
    (2023, 'Q1', 'Software Development', 31200, 21000, 10200, 16900, 14300, 8250.00),
    (2023, 'Q2', 'Software Development', 32100, 21600, 10500, 17400, 14700, 8350.00),
    (2023, 'Q3', 'Software Development', 33200, 22300, 10900, 18000, 15200, 8480.00),
    (2023, 'Q4', 'Software Development', 34100, 23000, 11100, 18600, 15500, 8620.00),
    (2024, 'Q1', 'Software Development', 35400, 23900, 11500, 19300, 16100, 8790.00),
    (2024, 'Q2', 'Software Development', 36200, 24500, 11700, 19800, 16400, 8910.00),

    (2022, 'Q1', 'Cybersecurity', 8200, 6500, 1700, 5200, 3000, 9200.00),
    (2022, 'Q2', 'Cybersecurity', 8500, 6700, 1800, 5400, 3100, 9350.00),
    (2022, 'Q3', 'Cybersecurity', 8900, 7000, 1900, 5700, 3200, 9520.00),
    (2022, 'Q4', 'Cybersecurity', 9200, 7200, 2000, 5900, 3300, 9680.00),
    (2023, 'Q1', 'Cybersecurity', 9700, 7600, 2100, 6200, 3500, 9890.00),
    (2023, 'Q2', 'Cybersecurity', 10100, 7900, 2200, 6500, 3600, 10100.00),
    (2023, 'Q3', 'Cybersecurity', 10600, 8300, 2300, 6800, 3800, 10340.00),
    (2023, 'Q4', 'Cybersecurity', 11100, 8700, 2400, 7100, 4000, 10590.00),
    (2024, 'Q1', 'Cybersecurity', 11700, 9200, 2500, 7500, 4200, 10850.00),
    (2024, 'Q2', 'Cybersecurity', 12200, 9600, 2600, 7800, 4400, 11120.00),

    (2022, 'Q1', 'AI and Data Analytics', 6400, 4800, 1600, 4200, 2200, 8900.00),
    (2022, 'Q2', 'AI and Data Analytics', 6900, 5200, 1700, 4500, 2400, 9050.00),
    (2022, 'Q3', 'AI and Data Analytics', 7500, 5600, 1900, 4900, 2600, 9230.00),
    (2022, 'Q4', 'AI and Data Analytics', 8100, 6000, 2100, 5300, 2800, 9420.00),
    (2023, 'Q1', 'AI and Data Analytics', 8900, 6600, 2300, 5800, 3100, 9650.00),
    (2023, 'Q2', 'AI and Data Analytics', 9600, 7100, 2500, 6300, 3300, 9880.00),
    (2023, 'Q3', 'AI and Data Analytics', 10500, 7800, 2700, 6900, 3600, 10150.00),
    (2023, 'Q4', 'AI and Data Analytics', 11400, 8500, 2900, 7500, 3900, 10440.00),
    (2024, 'Q1', 'AI and Data Analytics', 12500, 9300, 3200, 8200, 4300, 10760.00),
    (2024, 'Q2', 'AI and Data Analytics', 13400, 10000, 3400, 8800, 4600, 11080.00),

    (2022, 'Q1', 'Digital Marketing', 12300, 10800, 1500, 6200, 6100, 6200.00),
    (2022, 'Q2', 'Digital Marketing', 12700, 11100, 1600, 6400, 6300, 6280.00),
    (2022, 'Q3', 'Digital Marketing', 13100, 11500, 1600, 6600, 6500, 6360.00),
    (2022, 'Q4', 'Digital Marketing', 13400, 11700, 1700, 6800, 6600, 6450.00),
    (2023, 'Q1', 'Digital Marketing', 13900, 12200, 1700, 7000, 6900, 6560.00),
    (2023, 'Q2', 'Digital Marketing', 14300, 12500, 1800, 7200, 7100, 6650.00),
    (2023, 'Q3', 'Digital Marketing', 14800, 13000, 1800, 7500, 7300, 6760.00),
    (2023, 'Q4', 'Digital Marketing', 15200, 13300, 1900, 7700, 7500, 6870.00),
    (2024, 'Q1', 'Digital Marketing', 15800, 13800, 2000, 8000, 7800, 7000.00),
    (2024, 'Q2', 'Digital Marketing', 16200, 14200, 2000, 8200, 8000, 7120.00);

-- 2. AI Workforce Programmes
-- Tracks government-funded AI workforce development initiatives
CREATE TABLE ai_workforce_programmes (
    id SERIAL PRIMARY KEY,
    programme_name VARCHAR(200) NOT NULL,
    programme_type VARCHAR(100) NOT NULL,  -- 'Training', 'Certification', 'Internship', 'Attachment'
    start_date DATE NOT NULL,
    end_date DATE,
    target_participants INTEGER NOT NULL,
    actual_participants INTEGER,
    completion_rate DECIMAL(5, 2),  -- Percentage
    employment_rate_6months DECIMAL(5, 2),  -- Percentage employed within 6 months
    funding_sgd DECIMAL(12, 2) NOT NULL,
    partner_organizations TEXT[],
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO ai_workforce_programmes
(programme_name, programme_type, start_date, end_date, target_participants, actual_participants,
 completion_rate, employment_rate_6months, funding_sgd, partner_organizations)
VALUES
    ('AI Apprenticeship Programme 2022', 'Training', '2022-01-15', '2022-12-15', 500, 478, 89.50, 82.30, 2500000.00,
     ARRAY['NUS', 'NTU', 'Google Singapore', 'Microsoft Singapore']),
    ('Data Science Bootcamp Q1 2022', 'Training', '2022-02-01', '2022-04-30', 200, 185, 92.50, 78.50, 850000.00,
     ARRAY['General Assembly', 'DataCamp', 'Amazon Web Services']),
    ('Machine Learning Certification Programme', 'Certification', '2022-03-01', '2022-09-30', 350, 342, 94.00, 85.60, 1200000.00,
     ARRAY['Coursera', 'DeepLearning.AI', 'IMDA']),
    ('AI Ethics and Governance Workshop Series', 'Training', '2022-06-01', '2022-08-31', 150, 162, 96.30, NULL, 350000.00,
     ARRAY['AI Singapore', 'PDPC', 'SMU']),
    ('TechSkills Accelerator (AI Track)', 'Training', '2022-07-01', '2023-06-30', 800, 756, 87.20, 79.40, 4500000.00,
     ARRAY['IMDA', 'SkillsFuture Singapore', 'Industry Partners']),

    ('AI Apprenticeship Programme 2023', 'Training', '2023-01-20', '2023-12-20', 600, 589, 91.20, 84.70, 3000000.00,
     ARRAY['NUS', 'NTU', 'SUTD', 'Google Singapore', 'Microsoft Singapore']),
    ('Advanced NLP Workshop Series', 'Training', '2023-03-15', '2023-06-15', 120, 128, 94.50, 88.20, 680000.00,
     ARRAY['AI Singapore', 'Hugging Face', 'OpenAI']),
    ('Computer Vision Certification', 'Certification', '2023-04-01', '2023-10-31', 280, 271, 93.40, 86.90, 1100000.00,
     ARRAY['Coursera', 'NVIDIA', 'AI Singapore']),
    ('GenAI for Business Leaders', 'Training', '2023-09-01', '2023-11-30', 200, 218, 97.70, NULL, 450000.00,
     ARRAY['INSEAD', 'MIT Sloan', 'IMDA']),
    ('AI Internship Exchange Programme', 'Internship', '2023-06-01', '2024-05-31', 300, 287, 85.70, 91.30, 1800000.00,
     ARRAY['Various Tech Companies', 'IMDA', 'EDB']),

    ('AI Apprenticeship Programme 2024', 'Training', '2024-01-15', '2024-12-15', 700, 650, NULL, NULL, 3500000.00,
     ARRAY['NUS', 'NTU', 'SUTD', 'Google', 'Microsoft', 'Meta']),
    ('Prompt Engineering Masterclass', 'Training', '2024-02-01', '2024-04-30', 250, 268, 95.10, NULL, 920000.00,
     ARRAY['OpenAI', 'Anthropic', 'AI Singapore']),
    ('AI Safety and Alignment Workshop', 'Training', '2024-03-01', '2024-05-31', 100, 94, NULL, NULL, 380000.00,
     ARRAY['Oxford', 'AI Singapore', 'IMDA']);

-- 3. Online Safety Incidents Summary
-- Aggregated statistics on online safety incidents (privacy-preserving)
CREATE TABLE online_safety_incidents_summary (
    id SERIAL PRIMARY KEY,
    reporting_period DATE NOT NULL,  -- First day of the month
    incident_category VARCHAR(100) NOT NULL,
    total_reports INTEGER NOT NULL,
    verified_incidents INTEGER NOT NULL,
    severity_high INTEGER NOT NULL,
    severity_medium INTEGER NOT NULL,
    severity_low INTEGER NOT NULL,
    age_group_child INTEGER,  -- Under 18
    age_group_adult INTEGER,  -- 18 and above
    resolution_rate DECIMAL(5, 2),  -- Percentage resolved
    avg_resolution_days DECIMAL(5, 2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO online_safety_incidents_summary
(reporting_period, incident_category, total_reports, verified_incidents, severity_high, severity_medium,
 severity_low, age_group_child, age_group_adult, resolution_rate, avg_resolution_days)
VALUES
    -- 2022 Data
    ('2022-01-01', 'Cyberbullying', 245, 198, 23, 89, 86, 152, 46, 78.30, 12.50),
    ('2022-01-01', 'Privacy Violation', 189, 156, 45, 78, 33, 34, 122, 82.10, 15.20),
    ('2022-01-01', 'Misinformation', 412, 328, 67, 189, 72, 89, 239, 71.50, 8.30),
    ('2022-01-01', 'Online Harassment', 298, 267, 89, 145, 33, 78, 189, 85.60, 14.70),

    ('2022-06-01', 'Cyberbullying', 267, 219, 28, 95, 96, 165, 54, 79.80, 11.90),
    ('2022-06-01', 'Privacy Violation', 203, 171, 52, 84, 35, 41, 130, 83.50, 14.60),
    ('2022-06-01', 'Misinformation', 456, 365, 78, 201, 86, 98, 267, 73.20, 7.80),
    ('2022-06-01', 'Online Harassment', 321, 289, 95, 158, 36, 87, 202, 86.90, 13.90),

    -- 2023 Data
    ('2023-01-01', 'Cyberbullying', 289, 238, 31, 102, 105, 178, 60, 81.20, 11.30),
    ('2023-01-01', 'Privacy Violation', 221, 189, 58, 92, 39, 47, 142, 84.70, 14.10),
    ('2023-01-01', 'Misinformation', 498, 401, 89, 218, 94, 112, 289, 74.80, 7.50),
    ('2023-01-01', 'Online Harassment', 342, 308, 102, 169, 39, 95, 213, 88.10, 13.20),
    ('2023-01-01', 'Deepfake Content', 78, 62, 34, 22, 6, 18, 44, 76.90, 18.50),

    ('2023-06-01', 'Cyberbullying', 312, 259, 35, 110, 114, 189, 70, 82.40, 10.80),
    ('2023-06-01', 'Privacy Violation', 245, 209, 64, 101, 44, 54, 155, 85.90, 13.50),
    ('2023-06-01', 'Misinformation', 534, 432, 98, 234, 102, 123, 309, 76.10, 7.20),
    ('2023-06-01', 'Online Harassment', 367, 331, 108, 181, 42, 102, 229, 89.30, 12.70),
    ('2023-06-01', 'Deepfake Content', 95, 78, 42, 28, 8, 23, 55, 79.50, 17.30),

    -- 2024 Data
    ('2024-01-01', 'Cyberbullying', 334, 278, 38, 118, 122, 201, 77, 83.50, 10.20),
    ('2024-01-01', 'Privacy Violation', 267, 228, 71, 109, 48, 61, 167, 87.20, 12.90),
    ('2024-01-01', 'Misinformation', 578, 469, 107, 253, 109, 134, 335, 77.50, 6.90),
    ('2024-01-01', 'Online Harassment', 389, 352, 115, 194, 43, 109, 243, 90.10, 12.10),
    ('2024-01-01', 'Deepfake Content', 112, 94, 51, 33, 10, 28, 66, 81.40, 16.80),
    ('2024-01-01', 'AI-Generated Scams', 156, 128, 67, 48, 13, 34, 94, 74.60, 19.20);

-- 4. Emerging Tech Adoption Index
-- Tracks adoption of emerging technologies across sectors
CREATE TABLE emerging_tech_adoption_index (
    id SERIAL PRIMARY KEY,
    assessment_year INTEGER NOT NULL,
    assessment_quarter VARCHAR(2) NOT NULL,
    industry_sector VARCHAR(100) NOT NULL,
    technology_category VARCHAR(100) NOT NULL,
    adoption_score DECIMAL(5, 2) NOT NULL,  -- 0-100 scale
    implementation_maturity VARCHAR(50) NOT NULL,  -- 'Exploring', 'Piloting', 'Scaling', 'Mature'
    investment_level VARCHAR(50) NOT NULL,  -- 'Low', 'Medium', 'High', 'Very High'
    workforce_readiness DECIMAL(5, 2),  -- 0-100 scale
    regulatory_clarity DECIMAL(5, 2),  -- 0-100 scale
    num_companies_surveyed INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO emerging_tech_adoption_index
(assessment_year, assessment_quarter, industry_sector, technology_category, adoption_score,
 implementation_maturity, investment_level, workforce_readiness, regulatory_clarity, num_companies_surveyed)
VALUES
    -- 2022 Data
    (2022, 'Q4', 'Financial Services', 'Generative AI', 45.30, 'Piloting', 'Medium', 52.10, 68.40, 125),
    (2022, 'Q4', 'Financial Services', 'Blockchain', 62.80, 'Scaling', 'High', 71.30, 74.20, 125),
    (2022, 'Q4', 'Healthcare', 'Generative AI', 38.70, 'Exploring', 'Low', 45.20, 62.10, 89),
    (2022, 'Q4', 'Healthcare', 'IoT Medical Devices', 71.50, 'Scaling', 'Very High', 78.90, 81.30, 89),
    (2022, 'Q4', 'Manufacturing', 'Generative AI', 28.40, 'Exploring', 'Low', 38.60, 55.70, 156),
    (2022, 'Q4', 'Manufacturing', 'Industrial IoT', 68.90, 'Scaling', 'High', 73.20, 79.50, 156),
    (2022, 'Q4', 'Retail', 'Generative AI', 41.20, 'Piloting', 'Medium', 48.70, 64.30, 203),
    (2022, 'Q4', 'Retail', 'Computer Vision', 59.60, 'Scaling', 'Medium', 65.40, 72.80, 203),

    -- 2023 Data
    (2023, 'Q2', 'Financial Services', 'Generative AI', 67.50, 'Scaling', 'High', 68.90, 72.60, 132),
    (2023, 'Q2', 'Financial Services', 'Blockchain', 69.20, 'Scaling', 'High', 74.50, 76.80, 132),
    (2023, 'Q2', 'Healthcare', 'Generative AI', 54.30, 'Piloting', 'Medium', 58.40, 66.90, 95),
    (2023, 'Q2', 'Healthcare', 'IoT Medical Devices', 76.80, 'Mature', 'Very High', 82.30, 83.70, 95),
    (2023, 'Q2', 'Manufacturing', 'Generative AI', 42.80, 'Piloting', 'Medium', 51.20, 61.30, 167),
    (2023, 'Q2', 'Manufacturing', 'Industrial IoT', 73.40, 'Scaling', 'Very High', 76.80, 81.20, 167),
    (2023, 'Q2', 'Retail', 'Generative AI', 58.90, 'Scaling', 'High', 62.30, 69.50, 218),
    (2023, 'Q2', 'Retail', 'Computer Vision', 66.70, 'Scaling', 'High', 70.80, 75.60, 218),
    (2023, 'Q2', 'Education', 'Generative AI', 51.20, 'Piloting', 'Medium', 56.70, 58.90, 142),
    (2023, 'Q2', 'Education', 'Adaptive Learning Systems', 63.40, 'Scaling', 'Medium', 68.50, 71.20, 142),

    -- 2024 Data
    (2024, 'Q1', 'Financial Services', 'Generative AI', 81.60, 'Mature', 'Very High', 79.30, 76.50, 145),
    (2024, 'Q1', 'Financial Services', 'Blockchain', 72.90, 'Mature', 'High', 77.20, 78.40, 145),
    (2024, 'Q1', 'Healthcare', 'Generative AI', 68.70, 'Scaling', 'High', 67.80, 71.40, 102),
    (2024, 'Q1', 'Healthcare', 'IoT Medical Devices', 81.30, 'Mature', 'Very High', 85.60, 85.90, 102),
    (2024, 'Q1', 'Manufacturing', 'Generative AI', 59.40, 'Scaling', 'High', 63.50, 67.80, 178),
    (2024, 'Q1', 'Manufacturing', 'Industrial IoT', 78.20, 'Mature', 'Very High', 80.40, 83.60, 178),
    (2024, 'Q1', 'Retail', 'Generative AI', 73.80, 'Scaling', 'Very High', 72.10, 74.20, 234),
    (2024, 'Q1', 'Retail', 'Computer Vision', 72.50, 'Mature', 'High', 75.30, 78.10, 234),
    (2024, 'Q1', 'Education', 'Generative AI', 66.30, 'Scaling', 'High', 65.20, 63.70, 156),
    (2024, 'Q1', 'Education', 'Adaptive Learning Systems', 70.80, 'Scaling', 'High', 73.40, 74.50, 156),
    (2024, 'Q1', 'Public Sector', 'Generative AI', 62.40, 'Scaling', 'High', 61.80, 78.90, 87),
    (2024, 'Q1', 'Public Sector', 'Smart City Infrastructure', 74.20, 'Scaling', 'Very High', 72.50, 82.30, 87);

-- Create indexes for common queries
CREATE INDEX idx_digital_employment_year_quarter ON digital_sector_employment(year, quarter);
CREATE INDEX idx_digital_employment_sector ON digital_sector_employment(sector);
CREATE INDEX idx_ai_programmes_dates ON ai_workforce_programmes(start_date, end_date);
CREATE INDEX idx_safety_incidents_period ON online_safety_incidents_summary(reporting_period);
CREATE INDEX idx_safety_incidents_category ON online_safety_incidents_summary(incident_category);
CREATE INDEX idx_tech_adoption_year_quarter ON emerging_tech_adoption_index(assessment_year, assessment_quarter);
CREATE INDEX idx_tech_adoption_sector ON emerging_tech_adoption_index(industry_sector);
CREATE INDEX idx_tech_adoption_technology ON emerging_tech_adoption_index(technology_category);

-- Grant necessary permissions
GRANT SELECT ON ALL TABLES IN SCHEMA public TO postgres;
