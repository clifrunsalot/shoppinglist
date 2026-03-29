CREATE TABLE IF NOT EXISTS stores (
  id SERIAL PRIMARY KEY,
  name VARCHAR(100) NOT NULL UNIQUE,
  created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS items (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  quantity FLOAT DEFAULT 1,
  unit VARCHAR(30),
  category VARCHAR(60),
  price NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
  checked BOOLEAN DEFAULT FALSE,
  store_id INTEGER REFERENCES stores(id),
  created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS alembic_version (
  version_num VARCHAR(32) NOT NULL PRIMARY KEY
);

INSERT INTO alembic_version (version_num)
VALUES ('f86107bdc417')
ON CONFLICT (version_num) DO NOTHING;

INSERT INTO items (name, quantity, unit, category) VALUES
  ('Rice',                   25,   'lb',    'Food'),
  ('Dog Food',               15,   'lb',    'Food'),
  ('Oranges',                8,    'each',  'Food'),
  ('Apples',                 8,    'each',  'Food'),
  ('Beef',                   2.5,  'lb',    'Food'),
  ('Pork',                   2.5,  'lb',    'Food'),
  ('Chicken whole',          1,    'ea',    'Food'),
  ('Breakfast Sausage',      2,    'lb',    'Food'),
  ('Leafy greens',           2,    'lb',    'Food'),
  ('Cherry Peppers',         1,    'lb',    'Food'),
  ('Cherry tomatoes',        2,    'lb',    'Food'),
  ('Half & Half',            2,    'qt',    'Food'),
  ('Heavy Cream',            2,    'qt',    'Food'),
  ('Popcorn',                16,   'oz',    'Food'),
  ('Corn Starch',            8,    'oz',    'Food'),
  ('Bananas',                8,    'each',  'Food'),
  ('Crackers',               2.5,  'lb',    'Food'),
  ('Candy hard caramel',     1,    'lb',    'Food'),
  ('Eggs',                   1,    'dz',    'Food'),
  ('Tea English Breakfast',  40,   'bags',  'Food'),
  ('Flour',                  2.5,  'lb',    'Food'),
  ('Peanut butter creamy',   8,    'oz',    'Food'),
  ('Steak strips',           2,    'lb',    'Food'),
  ('Nuts Chocolate covered', 2,    'lb',    'Food'),
  ('Yogurt Greek',           8,    'oz',    'Food'),
  ('Egg Whites',             1,    'qt',    'Food'),
  ('Bread whole wheat',      2,    'loaf',  'Food'),
  ('Dishwasher detergent',   2,    'qt',    'Non-Food'),
  ('Windex Refill',          2,    'qt',    'Non-Food'),
  ('AA Batteries',           10,   'each',  'Non-Food'),
  ('AAA Batteries',          10,   'each',  'Non-Food'),
  ('Lotion sunblock',        8,    'oz',    'Non-Food')
ON CONFLICT DO NOTHING;
