DROP SCHEMA public CASCADE;
CREATE SCHEMA public;

CREATE TYPE CURRENCY AS ENUM ('gbp', 'usd', 'eur');
CREATE TABLE companies (
  id SERIAL PRIMARY KEY,
  name VARCHAR(255) NOT NULL UNIQUE,
  slug VARCHAR(255) NOT NULL UNIQUE,
  domain VARCHAR(255) NOT NULL,
  stripe_public_key VARCHAR(63),
  stripe_secret_key VARCHAR(63),
  currency CURRENCY NOT NULL DEFAULT 'gbp',
  image VARCHAR(255),
  logo VARCHAR(255),
  email_from VARCHAR(255),
  email_template TEXT
);
CREATE UNIQUE INDEX company_domain ON companies USING btree (domain);


CREATE TYPE USER_ROLE AS ENUM ('guest', 'host', 'admin');
CREATE TYPE USER_STATUS AS ENUM ('pending', 'active', 'suspended');
CREATE TABLE users (
  id SERIAL PRIMARY KEY,
  company INT NOT NULL REFERENCES companies ON DELETE CASCADE,
  role USER_ROLE NOT NULL,
  status USER_STATUS NOT NULL DEFAULT 'pending',
  first_name VARCHAR(255),
  last_name VARCHAR(255),
  email VARCHAR(255),
  phone_number VARCHAR(63),
  image VARCHAR(255),
  password_hash VARCHAR(63),
  stripe_customer_id VARCHAR(31),
  receive_emails BOOLEAN DEFAULT TRUE,
  created_ts TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  active_ts TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX user_email ON users USING btree (company, email);


CREATE TYPE ACTION_TYPES AS ENUM (
  'login',
  'guest-signin',
  'logout',
  'reserve-tickets',
  'buy-tickets',
  'edit-event',
  'edit-other',
  'unsubscribed'
);
CREATE TABLE actions (
  id SERIAL PRIMARY KEY,
  company INT NOT NULL REFERENCES companies ON DELETE CASCADE,
  user_id INT NOT NULL REFERENCES users ON DELETE CASCADE,
  ts TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  type ACTION_TYPES NOT NULL,
  extra JSONB
);
CREATE INDEX action_compound ON actions USING btree (company, user_id, type);


CREATE TYPE EVENT_TYPES AS ENUM ('ticket_sales', 'donation_requests');
CREATE TABLE categories (
  id SERIAL PRIMARY KEY,
  company INT NOT NULL REFERENCES companies ON DELETE CASCADE,
  name VARCHAR(63) NOT NULL,
  slug VARCHAR(63) NOT NULL,
  live BOOLEAN DEFAULT TRUE,
  description VARCHAR(140),
  sort_index INT,
  event_content TEXT,
  host_advice TEXT,
  event_type EVENT_TYPES NOT NULL DEFAULT 'ticket_sales',
  suggested_price NUMERIC(7, 2),
  image VARCHAR(255),
  CHECK (suggested_price > 1)
);
CREATE UNIQUE INDEX category_slug ON categories USING btree (company, slug);


CREATE TYPE EVENT_STATUS AS ENUM ('pending', 'published', 'suspended');
CREATE TABLE events (
  id SERIAL PRIMARY KEY,
  category INT NOT NULL REFERENCES categories ON DELETE CASCADE,
  status EVENT_STATUS NOT NULL DEFAULT 'pending',
  host INT NOT NULL REFERENCES users ON DELETE RESTRICT,
  name VARCHAR(63) NOT NULL,
  slug VARCHAR(63),
  highlight BOOLEAN NOT NULL DEFAULT FALSE,
  start_ts TIMESTAMP NOT NULL,
  duration INTERVAL,
  short_description VARCHAR(140),
  long_description TEXT,
  public BOOLEAN DEFAULT TRUE,
  location VARCHAR(140),
  location_lat FLOAT,
  location_lng FLOAT,
  price NUMERIC(7, 2) CONSTRAINT price_gt_1 CHECK (price > 1),
  ticket_limit INT CONSTRAINT ticket_limit_gt_0 CHECK (ticket_limit > 0),
  tickets_taken INT NOT NULL DEFAULT 0,  -- sold and reserved
  image VARCHAR(255),
  CONSTRAINT ticket_limit_check CHECK (tickets_taken <= ticket_limit)
);
CREATE UNIQUE INDEX event_slug ON events USING btree (category, slug);


CREATE TYPE TICKET_STATUS AS ENUM ('reserved', 'paid', 'cancelled');
CREATE TABLE tickets (
  id SERIAL PRIMARY KEY,
  event INT NOT NULL REFERENCES events ON DELETE CASCADE,
  user_id INT REFERENCES users ON DELETE CASCADE,
  reserve_action INT NOT NULL REFERENCES actions ON DELETE CASCADE,
  paid_action INT REFERENCES actions ON DELETE CASCADE,
  status TICKET_STATUS NOT NULL DEFAULT 'reserved',
  created_ts TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  extra JSONB
);
CREATE INDEX ticket_event ON tickets USING btree (event);

-- must match triggers from emails/defaults.py!
CREATE TYPE EMAIL_TRIGGERS AS ENUM (
  'confirmation-buyer', 'confirmation-other', 'event-update', 'event-reminder', 'event-booking',
  'event-host-update', 'password-reset', 'account-created', 'admin-notification'
);

CREATE TABLE email_definitions (
  id SERIAL PRIMARY KEY,
  company INT NOT NULL REFERENCES companies ON DELETE CASCADE,
  trigger EMAIL_TRIGGERS NOT NULL,
  active BOOLEAN DEFAULT TRUE,
  subject VARCHAR(255),
  title VARCHAR(127),
  body TEXT
);
CREATE UNIQUE INDEX email_def_unique ON email_definitions USING btree (company, trigger);

-- TODO email events
