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
  email_reply_to VARCHAR(255),
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
  allow_marketing BOOLEAN DEFAULT FALSE,
  created_ts TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  active_ts TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX user_email ON users USING btree (company, email);
CREATE INDEX user_role ON users USING btree (role);
CREATE INDEX user_status ON users USING btree (status);
CREATE INDEX user_company ON users USING btree (company);
CREATE INDEX user_created_ts ON users USING btree (created_ts);
CREATE INDEX user_active_ts ON users USING btree (active_ts);


CREATE TYPE EVENT_TYPES AS ENUM ('ticket_sales', 'donation_requests');
CREATE TABLE categories (
  id SERIAL PRIMARY KEY,
  company INT NOT NULL REFERENCES companies ON DELETE CASCADE,
  name VARCHAR(63) NOT NULL,
  slug VARCHAR(63) NOT NULL,
  live BOOLEAN DEFAULT TRUE,
  sort_index INT,
  event_type EVENT_TYPES NOT NULL DEFAULT 'ticket_sales',
  suggested_price NUMERIC(7, 2) CHECK (suggested_price >= 1),
  image VARCHAR(255),

  description VARCHAR(140),
  event_content TEXT,
  host_advice TEXT,
  booking_trust_message TEXT,
  cover_costs_message TEXT,
  cover_costs_percentage NUMERIC(5, 2) CHECK (cover_costs_percentage > 0 AND cover_costs_percentage <= 100),
  terms_and_conditions_message TEXT,
  allow_marketing_message TEXT,
  ticket_extra_title VARCHAR(200),
  ticket_extra_help_text TEXT
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


CREATE TYPE ACTION_TYPES AS ENUM (
  'login',
  'guest-signin',
  'host-signup',
  'logout',
  'password-reset',
  'reserve-tickets',
  'buy-tickets',
  'donate',
  'book-free-tickets',
  'cancel-reserved-tickets',
  'create-event',
  'event-guest-reminder',
  'event-update',
  'edit-event',
  'edit-profile',
  'edit-other',
  'unsubscribe'
);
CREATE TABLE actions (
  id SERIAL PRIMARY KEY,
  company INT NOT NULL REFERENCES companies ON DELETE CASCADE,
  user_id INT REFERENCES users ON DELETE CASCADE,
  event INT REFERENCES events ON DELETE SET NULL,
  ts TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  type ACTION_TYPES NOT NULL,
  extra JSONB
);
CREATE INDEX action_compound ON actions USING btree (company, user_id);
CREATE INDEX action_user ON actions USING btree (user_id);
CREATE INDEX action_event ON actions USING btree (event);
CREATE INDEX action_type ON actions USING btree (type);
CREATE INDEX action_ts ON actions USING btree (ts);


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
  price NUMERIC(7, 2) CONSTRAINT price_gte_1 CHECK (price >= 1),  -- in case ticket prices change
  extra_donated NUMERIC(7, 2) CONSTRAINT extra_donated_gt_0 CHECK (extra_donated > 0),
  reserve_action INT NOT NULL REFERENCES actions ON DELETE CASCADE,
  booked_action INT REFERENCES actions ON DELETE CASCADE,
  status TICKET_STATUS NOT NULL DEFAULT 'reserved',
  created_ts TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  extra_info TEXT
);
CREATE INDEX ticket_event ON tickets USING btree (event);
CREATE INDEX ticket_user ON tickets USING btree (user_id);
CREATE INDEX ticket_reserve_action ON tickets USING btree (reserve_action);
CREATE INDEX ticket_status ON tickets USING btree (status);
CREATE INDEX ticket_created_ts ON tickets USING btree (created_ts);

-- must match triggers from emails/defaults.py!
CREATE TYPE EMAIL_TRIGGERS AS ENUM (
  'ticket-buyer', 'ticket-other', 'event-update', 'event-reminder', 'donation-thanks', 'event-booking',
  'event-host-created', 'event-host-update', 'event-host-final-update', 'password-reset', 'account-created',
  'admin-notification'
);

CREATE TABLE email_definitions (
  id SERIAL PRIMARY KEY,
  company INT NOT NULL REFERENCES companies ON DELETE CASCADE,
  trigger EMAIL_TRIGGERS NOT NULL,
  active BOOLEAN DEFAULT TRUE,
  subject VARCHAR(255) NOT NULL,
  title VARCHAR(127),
  body TEXT NOT NULL
);
CREATE UNIQUE INDEX email_def_unique ON email_definitions USING btree (company, trigger);

-- TODO email events

CREATE TABLE donation_options (
  id SERIAL PRIMARY KEY,
  category INT NOT NULL REFERENCES categories ON DELETE CASCADE,
  name VARCHAR(255) NOT NULL,
  amount NUMERIC(7, 2) NOT NULL CHECK (amount >= 1),
  sort_index INT,

  live BOOLEAN DEFAULT TRUE,
  image VARCHAR(255),
  short_description VARCHAR(140),
  long_description TEXT
);
CREATE INDEX don_opt_category ON donation_options USING btree (category);
CREATE INDEX don_opt_live ON donation_options USING btree (live);
CREATE INDEX don_opt_sort_index ON donation_options USING btree (sort_index);


CREATE TABLE donations (
  id SERIAL PRIMARY KEY,
  donation_option INT NOT NULL REFERENCES donation_options ON DELETE CASCADE,
  amount NUMERIC(7, 2) NOT NULL CHECK (amount >= 1),
  gift_aid BOOLEAN NOT NULL,
  address VARCHAR(255),
  city VARCHAR(255),
  postcode VARCHAR(31),

  action INT NOT NULL REFERENCES actions ON DELETE CASCADE  -- to get event, user and ts
);
CREATE UNIQUE INDEX con_action ON donations USING btree (action);
CREATE INDEX don_donation_option ON donations USING btree (donation_option);
CREATE INDEX don_gift_aid ON donations USING btree (gift_aid);
CREATE INDEX don_action ON donations USING btree (action);
