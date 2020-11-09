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
  stripe_webhook_secret VARCHAR(63),
  currency CURRENCY NOT NULL DEFAULT 'gbp',
  display_timezone VARCHAR(63) NOT NULL DEFAULT 'Europe/London',
  image VARCHAR(255),
  logo VARCHAR(255),
  email_from VARCHAR(255),
  email_reply_to VARCHAR(255),
  email_template TEXT,
  footer_links JSONB
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
  created_ts TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  active_ts TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
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
  post_booking_message TEXT,
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
  name VARCHAR(150) NOT NULL,
  slug VARCHAR(63),
  highlight BOOLEAN NOT NULL DEFAULT FALSE,
  external_ticket_url VARCHAR(255),
  external_donation_url VARCHAR(255),
  start_ts TIMESTAMPTZ NOT NULL,
  timezone VARCHAR(63) NOT NULL DEFAULT 'Europe/London',
  duration INTERVAL,
  youtube_video_id VARCHAR(140),
  short_description VARCHAR(140),
  description_intro TEXT,
  description_image VARCHAR(255),
  long_description TEXT,
  public BOOLEAN DEFAULT TRUE,
  allow_tickets BOOLEAN NOT NULL DEFAULT TRUE,
  allow_donations BOOLEAN NOT NULL DEFAULT FALSE,

  location_name VARCHAR(140),
  location_lat FLOAT,
  location_lng FLOAT,

  ticket_limit INT CONSTRAINT ticket_limit_gt_0 CHECK (ticket_limit > 0),
  donation_target NUMERIC(10, 2) CONSTRAINT donation_target_gte_1 CHECK (donation_target > 0),
  tickets_taken INT NOT NULL DEFAULT 0,  -- sold and reserved
  image VARCHAR(255),
  secondary_image VARCHAR(255),
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
  'buy-tickets-offline',
  'book-free-tickets',
  'donate-prepare',
  'donate-direct-prepare',
  'donate',
  'cancel-reserved-tickets',
  'cancel-booked-tickets',
  'create-event',
  'event-guest-reminder',
  'event-update',
  'edit-event',
  'edit-profile',
  'edit-other',
  'email-waiting-list',
  'unsubscribe'
);
CREATE TABLE actions (
  id SERIAL PRIMARY KEY,
  company INT NOT NULL REFERENCES companies ON DELETE CASCADE,
  user_id INT REFERENCES users ON DELETE CASCADE,
  event INT REFERENCES events ON DELETE SET NULL,
  ts TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  type ACTION_TYPES NOT NULL,
  extra JSONB
);
CREATE INDEX action_compound ON actions USING btree (company, user_id);
CREATE INDEX action_user ON actions USING btree (user_id);
CREATE INDEX action_event ON actions USING btree (event);
CREATE INDEX action_type ON actions USING btree (type);
CREATE INDEX action_ts ON actions USING btree (ts);

CREATE TYPE TICKET_MODE AS ENUM ('ticket', 'donation');

CREATE TABLE ticket_types (
  id SERIAL PRIMARY KEY,
  event INT NOT NULL REFERENCES events ON DELETE CASCADE,
  name VARCHAR(63) NOT NULL,
  mode TICKET_MODE NOT NULL DEFAULT 'ticket',
  custom_amount BOOL NOT NULL DEFAULT FALSE,
  price NUMERIC(7, 2) CONSTRAINT price_gte_1 CHECK (price >= 1),
  slots_used INT DEFAULT 1 CONSTRAINT slots_used_gt_0 CHECK (slots_used > 0),
  active BOOLEAN DEFAULT TRUE
);
CREATE INDEX ticket_type_mode ON ticket_types USING btree (mode);


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
  cancel_action INT REFERENCES actions ON DELETE SET NULL,
  status TICKET_STATUS NOT NULL DEFAULT 'reserved',
  created_ts TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
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
  'admin-notification', 'event-tickets-available', 'waiting-list-add'
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

-- { donations change
CREATE TABLE IF NOT EXISTS donation_options (
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
CREATE INDEX IF NOT EXISTS don_opt_category ON donation_options USING btree (category);
CREATE INDEX IF NOT EXISTS don_opt_live ON donation_options USING btree (live);
CREATE INDEX IF NOT EXISTS don_opt_sort_index ON donation_options USING btree (sort_index);


CREATE TABLE IF NOT EXISTS donations (
  id SERIAL PRIMARY KEY,
  donation_option INT REFERENCES donation_options ON DELETE CASCADE,
  ticket_type INT REFERENCES ticket_types ON DELETE CASCADE,
  CONSTRAINT donation_option_or_ticket_type_required CHECK (num_nonnulls(donation_option, ticket_type) = 1),

  amount NUMERIC(7, 2) NOT NULL CHECK (amount >= 1),
  gift_aid BOOLEAN NOT NULL,
  title VARCHAR(31),
  first_name VARCHAR(255),
  last_name VARCHAR(255),
  address VARCHAR(255),
  city VARCHAR(255),
  postcode VARCHAR(31),

  action INT NOT NULL REFERENCES actions ON DELETE CASCADE  -- to get event, user and ts
);
CREATE UNIQUE INDEX IF NOT EXISTS con_action ON donations USING btree (action);
CREATE INDEX IF NOT EXISTS don_donation_option ON donations USING btree (donation_option);
CREATE INDEX IF NOT EXISTS don_gift_aid ON donations USING btree (gift_aid);
CREATE INDEX IF NOT EXISTS don_action ON donations USING btree (action);
-- } donations change


-- { email change
CREATE TABLE IF NOT EXISTS emails (
  id SERIAL PRIMARY KEY,
  company INT NOT NULL REFERENCES companies ON DELETE CASCADE,
  user_id INT REFERENCES users ON DELETE SET NULL,
  ext_id VARCHAR(255) NOT NULL,
  send_ts TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  update_ts TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  status VARCHAR(63) NOT NULL DEFAULT 'pending',
  trigger EMAIL_TRIGGERS NOT NULL,
  subject VARCHAR(255),
  address VARCHAR(255)
);
CREATE INDEX IF NOT EXISTS email_ext_id ON emails USING btree (ext_id);
CREATE INDEX IF NOT EXISTS email_send_ts ON emails USING btree (send_ts);
CREATE INDEX IF NOT EXISTS email_update_ts ON emails USING btree (update_ts);
CREATE INDEX IF NOT EXISTS email_status ON emails USING btree (status);
CREATE INDEX IF NOT EXISTS email_trigger ON emails USING btree (trigger);
CREATE INDEX IF NOT EXISTS email_address ON emails USING btree (address);
CREATE INDEX IF NOT EXISTS email_user ON emails USING btree (user_id);

CREATE TABLE IF NOT EXISTS email_events (
  id SERIAL PRIMARY KEY,
  email INT NOT NULL REFERENCES emails ON DELETE CASCADE,
  ts TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  status VARCHAR(63) NOT NULL,
  extra JSONB
);
CREATE INDEX IF NOT EXISTS email_event_status ON email_events USING btree (status);
CREATE INDEX IF NOT EXISTS email_event_email ON email_events USING btree (email);
CREATE INDEX IF NOT EXISTS email_event_ts ON email_events USING btree (ts);
-- } email change

-- { search
CREATE TABLE IF NOT EXISTS search (
  id SERIAL PRIMARY KEY,
  company INT NOT NULL REFERENCES companies ON DELETE CASCADE,
  user_id INT REFERENCES users ON DELETE CASCADE UNIQUE,
  event INT REFERENCES events ON DELETE CASCADE UNIQUE,
  label VARCHAR(255) NOT NULL,
  active_ts TIMESTAMPTZ NOT NULL,
  vector TSVECTOR NOT NULL
);
CREATE INDEX IF NOT EXISTS search_company ON search USING btree (company);
CREATE INDEX IF NOT EXISTS search_user ON search USING btree (user_id);
CREATE INDEX IF NOT EXISTS search_event ON search USING btree (event);
CREATE INDEX IF NOT EXISTS search_vector ON search USING gin (vector);
CREATE INDEX IF NOT EXISTS search_active_ts ON search USING btree (active_ts);
-- } search

-- { waiting-list
CREATE TABLE IF NOT EXISTS waiting_list (
  id SERIAL PRIMARY KEY,
  event INT REFERENCES events ON DELETE CASCADE,
  user_id INT REFERENCES users ON DELETE CASCADE,
  last_notified TIMESTAMPTZ NOT NULL DEFAULT '2000-01-01',
  added_ts TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX IF NOT EXISTS waiting_list_event_users ON waiting_list USING btree (event, user_id);
-- } waiting-list
