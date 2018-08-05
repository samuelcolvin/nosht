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
  password_hash VARCHAR(63),
  stripe_customer_id VARCHAR(31),
  receive_emails BOOLEAN DEFAULT TRUE,
  created_ts TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  active_ts TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX user_email ON users USING btree (company, email);
CREATE INDEX user_role ON users USING btree (role);
CREATE INDEX user_status ON users USING btree (status);
CREATE INDEX user_company ON users USING btree (company);
CREATE INDEX user_created_ts ON users USING btree (created_ts);
CREATE INDEX user_active_ts ON users USING btree (active_ts);


CREATE TYPE ACTION_TYPES AS ENUM (
  'login',
  'guest-signin',
  'host-signup',
  'logout',
  'password-reset',
  'reserve-tickets',
  'buy-tickets',
  'book-free-tickets',
  'cancel-reserved-tickets',
  'create-event',
  'edit-event',
  'edit-profile',
  'edit-other',
  'unsubscribe'
);
CREATE TABLE actions (
  id SERIAL PRIMARY KEY,
  company INT NOT NULL REFERENCES companies ON DELETE CASCADE,
  user_id INT NOT NULL REFERENCES users ON DELETE CASCADE,
  ts TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  type ACTION_TYPES NOT NULL,
  extra JSONB
);
CREATE INDEX action_compound ON actions USING btree (company, user_id);
CREATE INDEX action_type ON actions USING btree (type);
CREATE INDEX action_ts ON actions USING btree (ts);


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
  ticket_extra_title VARCHAR(200),
  ticket_extra_help_text TEXT,
  event_type EVENT_TYPES NOT NULL DEFAULT 'ticket_sales',
  suggested_price NUMERIC(7, 2),
  image VARCHAR(255),
  CHECK (suggested_price > 1)
);
CREATE UNIQUE INDEX category_co_slug ON categories USING btree (company, slug);
CREATE INDEX category_company ON categories USING btree (company);
CREATE INDEX category_slug ON categories USING btree (slug);
CREATE INDEX category_live ON categories USING btree (live);
CREATE INDEX category_sort_index ON categories USING btree (sort_index);


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

  location_name VARCHAR(140),
  location_lat FLOAT,
  location_lng FLOAT,

  ticket_limit INT CONSTRAINT ticket_limit_gt_0 CHECK (ticket_limit > 0),
  tickets_taken INT NOT NULL DEFAULT 0,  -- sold and reserved
  image VARCHAR(255),
  CONSTRAINT ticket_limit_check CHECK (tickets_taken <= ticket_limit)
);
CREATE UNIQUE INDEX event_cat_slug ON events USING btree (category, slug);
CREATE INDEX event_slug ON events USING btree (slug);
CREATE INDEX event_status ON events USING btree (status);
CREATE INDEX event_public ON events USING btree (public);
CREATE INDEX event_highlight ON events USING btree (highlight);
CREATE INDEX event_start_ts ON events USING btree (start_ts);
CREATE INDEX event_category ON events USING btree (category);


CREATE TABLE ticket_types (
  id SERIAL PRIMARY KEY,
  event INT NOT NULL REFERENCES events ON DELETE CASCADE,
  name VARCHAR(63) NOT NULL,
  price NUMERIC(7, 2) CONSTRAINT price_gte_1 CHECK (price >= 1),
  slots_used INT DEFAULT 1 CONSTRAINT slots_used_gt_0 CHECK (slots_used > 0),
  active BOOLEAN DEFAULT TRUE
);


CREATE TYPE TICKET_STATUS AS ENUM ('reserved', 'booked', 'cancelled');
CREATE TABLE tickets (
  id SERIAL PRIMARY KEY,
  event INT NOT NULL REFERENCES events ON DELETE CASCADE,
  ticket_type INT NOT NULL REFERENCES ticket_types ON DELETE RESTRICT,
  user_id INT REFERENCES users ON DELETE CASCADE,
  -- separate from the user's name to avoid confusing updates of the user's name
  first_name VARCHAR(255),
  last_name VARCHAR(255),
  price NUMERIC(7, 2),  -- in case ticket prices change
  reserve_action INT NOT NULL REFERENCES actions ON DELETE CASCADE,
  booked_action INT REFERENCES actions ON DELETE CASCADE,
  status TICKET_STATUS NOT NULL DEFAULT 'reserved',
  created_ts TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  extra JSONB
);
CREATE INDEX ticket_event ON tickets USING btree (event);
CREATE INDEX ticket_user ON tickets USING btree (user_id);
CREATE INDEX ticket_reserve_action ON tickets USING btree (reserve_action);
CREATE INDEX ticket_status ON tickets USING btree (status);
CREATE INDEX ticket_created_ts ON tickets USING btree (created_ts);

-- must match triggers from emails/defaults.py!
CREATE TYPE EMAIL_TRIGGERS AS ENUM (
  'ticket-buyer', 'ticket-other', 'event-update', 'event-reminder', 'event-booking',
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
