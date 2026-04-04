CREATE TABLE IF NOT EXISTS users (
  id SERIAL PRIMARY KEY,
  email VARCHAR(255) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  is_admin BOOLEAN NOT NULL DEFAULT FALSE,
  is_approved BOOLEAN NOT NULL DEFAULT TRUE,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  theme_preference VARCHAR(20),
  created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS app_settings (
  id SERIAL PRIMARY KEY,
  key VARCHAR(100) NOT NULL UNIQUE,
  value VARCHAR(255) NOT NULL,
  created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS default_store_templates (
  id SERIAL PRIMARY KEY,
  template_key VARCHAR(36) NOT NULL UNIQUE,
  name VARCHAR(100) NOT NULL,
  sort_order INTEGER NOT NULL DEFAULT 0,
  created_at TIMESTAMP DEFAULT now(),
  CONSTRAINT uq_default_store_template_name UNIQUE (name)
);

CREATE TABLE IF NOT EXISTS default_item_templates (
  id SERIAL PRIMARY KEY,
  template_key VARCHAR(36) NOT NULL UNIQUE,
  name TEXT NOT NULL,
  quantity FLOAT NOT NULL DEFAULT 1,
  unit VARCHAR(30),
  category VARCHAR(60),
  sort_order INTEGER NOT NULL DEFAULT 0,
  store_template_id INTEGER REFERENCES default_store_templates(id),
  created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS audit_logs (
  id SERIAL PRIMARY KEY,
  actor_user_id INTEGER REFERENCES users(id),
  action VARCHAR(80) NOT NULL,
  target_type VARCHAR(80) NOT NULL,
  target_id INTEGER,
  summary VARCHAR(255) NOT NULL,
  details TEXT,
  created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS stores (
  id SERIAL PRIMARY KEY,
  name VARCHAR(100) NOT NULL,
  sort_order INTEGER NOT NULL DEFAULT 0,
  user_id INTEGER REFERENCES users(id),
  template_store_id INTEGER REFERENCES default_store_templates(id),
  created_at TIMESTAMP DEFAULT now(),
  CONSTRAINT uq_store_user_name UNIQUE (user_id, name)
);

CREATE TABLE IF NOT EXISTS items (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  quantity FLOAT DEFAULT 1,
  unit VARCHAR(30),
  category VARCHAR(60),
  sort_order INTEGER NOT NULL DEFAULT 0,
  price NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
  checked BOOLEAN DEFAULT FALSE,
  store_id INTEGER REFERENCES stores(id),
  user_id INTEGER REFERENCES users(id),
  template_item_id INTEGER REFERENCES default_item_templates(id),
  created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS alembic_version (
  version_num VARCHAR(32) NOT NULL PRIMARY KEY
);

INSERT INTO alembic_version (version_num)
VALUES ('3c6a0bb190a1')
ON CONFLICT (version_num) DO NOTHING;

INSERT INTO app_settings (key, value)
VALUES ('default_theme', 'meadow')
ON CONFLICT (key) DO NOTHING;

INSERT INTO default_item_templates (template_key, name, quantity, unit, category, sort_order) VALUES
  ('dflt-0001-rice',                   'Rice',                   25,   'lb',    'Food',      10),
  ('dflt-0002-dog-food',               'Dog Food',               15,   'lb',    'Food',      20),
  ('dflt-0003-oranges',                'Oranges',                8,    'each',  'Food',      30),
  ('dflt-0004-apples',                 'Apples',                 8,    'each',  'Food',      40),
  ('dflt-0005-beef',                   'Beef',                   2.5,  'lb',    'Food',      50),
  ('dflt-0006-pork',                   'Pork',                   2.5,  'lb',    'Food',      60),
  ('dflt-0007-chicken-whole',          'Chicken whole',          1,    'ea',    'Food',      70),
  ('dflt-0008-breakfast-sausage',      'Breakfast Sausage',      2,    'lb',    'Food',      80),
  ('dflt-0009-leafy-greens',           'Leafy greens',           2,    'lb',    'Food',      90),
  ('dflt-0010-cherry-peppers',         'Cherry Peppers',         1,    'lb',    'Food',     100),
  ('dflt-0011-cherry-tomatoes',        'Cherry tomatoes',        2,    'lb',    'Food',     110),
  ('dflt-0012-half-half',              'Half & Half',            2,    'qt',    'Food',     120),
  ('dflt-0013-heavy-cream',            'Heavy Cream',            2,    'qt',    'Food',     130),
  ('dflt-0014-popcorn',                'Popcorn',                16,   'oz',    'Food',     140),
  ('dflt-0015-corn-starch',            'Corn Starch',            8,    'oz',    'Food',     150),
  ('dflt-0016-bananas',                'Bananas',                8,    'each',  'Food',     160),
  ('dflt-0017-crackers',               'Crackers',               2.5,  'lb',    'Food',     170),
  ('dflt-0018-candy-hard-caramel',     'Candy hard caramel',     1,    'lb',    'Food',     180),
  ('dflt-0019-eggs',                   'Eggs',                   1,    'dz',    'Food',     190),
  ('dflt-0020-tea-english-breakfast',  'Tea English Breakfast',  40,   'bags',  'Food',     200),
  ('dflt-0021-flour',                  'Flour',                  2.5,  'lb',    'Food',     210),
  ('dflt-0022-peanut-butter-creamy',   'Peanut butter creamy',   8,    'oz',    'Food',     220),
  ('dflt-0023-steak-strips',           'Steak strips',           2,    'lb',    'Food',     230),
  ('dflt-0024-nuts-chocolate-covered', 'Nuts Chocolate covered', 2,    'lb',    'Food',     240),
  ('dflt-0025-yogurt-greek',           'Yogurt Greek',           8,    'oz',    'Food',     250),
  ('dflt-0026-egg-whites',             'Egg Whites',             1,    'qt',    'Food',     260),
  ('dflt-0027-bread-whole-wheat',      'Bread whole wheat',      2,    'loaf',  'Food',     270),
  ('dflt-0028-dishwasher-detergent',   'Dishwasher detergent',   2,    'qt',    'Non-Food', 280),
  ('dflt-0029-windex-refill',          'Windex Refill',          2,    'qt',    'Non-Food', 290),
  ('dflt-0030-aa-batteries',           'AA Batteries',           10,   'each',  'Non-Food', 300),
  ('dflt-0031-aaa-batteries',          'AAA Batteries',          10,   'each',  'Non-Food', 310),
  ('dflt-0032-lotion-sunblock',        'Lotion sunblock',        8,    'oz',    'Non-Food', 320)
ON CONFLICT (template_key) DO NOTHING;
