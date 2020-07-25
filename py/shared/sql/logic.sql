CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE OR REPLACE FUNCTION update_user_ts() RETURNS trigger AS $$
  BEGIN
    UPDATE users SET active_ts=NEW.ts WHERE id=NEW.user_id;
    return NULL;
  END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS update_user_ts ON actions;
CREATE TRIGGER update_user_ts AFTER INSERT ON actions FOR EACH ROW EXECUTE PROCEDURE update_user_ts();

CREATE OR REPLACE FUNCTION check_tickets_remaining(event_id INT, ttl INT) RETURNS INT AS $$
  DECLARE
    tickets_taken_ INT;
  BEGIN
    -- delete reserved tickets after a week,
    -- this allows time for webhooks to succeed even after the reservation has "expired"
    DELETE FROM tickets
    WHERE status='reserved' AND event=event_id AND now() - created_ts > '604800 seconds'::interval;

    SELECT coalesce(SUM(tt.slots_used), 0) INTO tickets_taken_
    FROM tickets
    JOIN ticket_types AS tt ON tickets.ticket_type=tt.id
    WHERE tickets.event=event_id AND tt.mode='ticket' AND
          (status='booked' or (status='reserved' and now() - created_ts < (ttl || ' seconds')::interval));

    UPDATE events SET tickets_taken=tickets_taken_ WHERE id=event_id;

    return (SELECT ticket_limit - tickets_taken FROM events WHERE id=event_id);
  END;
$$ LANGUAGE plpgsql;


CREATE OR REPLACE FUNCTION full_name(first_name VARCHAR(255), last_name VARCHAR(255),
    email VARCHAR(255) DEFAULT NULL) RETURNS VARCHAR(255) AS $$
  DECLARE
  BEGIN
    return coalesce(first_name || ' ' || last_name, first_name, last_name, email);
  END;
$$ LANGUAGE plpgsql;


CREATE OR REPLACE FUNCTION event_link(cat_slug VARCHAR(255), event_slug VARCHAR(255), public BOOLEAN, key TEXT) RETURNS TEXT AS $$
  DECLARE
    base_uri TEXT;
  BEGIN
    SELECT '/' || cat_slug || '/' || event_slug || '/' INTO base_uri;
    IF public THEN
      RETURN base_uri;
    ELSE
      RETURN '/pvt' || base_uri || encode(hmac(base_uri, key, 'md5'), 'hex') || '/';
    END IF;
  END;
$$ LANGUAGE plpgsql;


CREATE OR REPLACE FUNCTION boolstr(v BOOLEAN) RETURNS VARCHAR(5) AS $$
  DECLARE
  BEGIN
    return CASE WHEN v IS TRUE THEN 'true' ELSE 'false' END;
  END;
$$ LANGUAGE plpgsql;


CREATE OR REPLACE FUNCTION iso_ts(v TIMESTAMPTZ, tz VARCHAR(63)) RETURNS VARCHAR(63) AS $$
  DECLARE
  BEGIN
    PERFORM set_config('timezone', tz, true);
    return to_char(v, 'YYYY-MM-DD"T"HH24:MI:SSOF');
  END;
$$ LANGUAGE plpgsql;


CREATE OR REPLACE FUNCTION tz_abbrev(v TIMESTAMPTZ, tz VARCHAR(63)) RETURNS VARCHAR(8) AS $$
  DECLARE
  BEGIN
    PERFORM set_config('timezone', tz, true);
    return to_char(v, 'TZ');
  END;
$$ LANGUAGE plpgsql;


CREATE OR REPLACE FUNCTION as_time_zone(v TIMESTAMPTZ, tz VARCHAR(63)) RETURNS TIMESTAMP AS $$
  DECLARE
  BEGIN
    return v AT TIME ZONE tz;
  END;
$$ LANGUAGE plpgsql;


CREATE OR REPLACE FUNCTION update_user_search() RETURNS trigger AS $$
  DECLARE
    name TEXT = full_name(NEW.first_name, NEW.last_name, NEW.email);
    label TEXT;
    email TEXT = coalesce(NEW.email, '');
  BEGIN
    IF name IS NOT NULL THEN
      IF (NEW.first_name IS NOT NULL OR NEW.last_name IS NOT NULL) AND NEW.email IS NOT NULL THEN
        SELECT format('%s (%s)', name, NEW.email) INTO label;
      ELSE
        SELECT name INTO label;
      END IF;
      INSERT INTO search (company, user_id, label, active_ts, vector) VALUES (
        NEW.company,
        NEW.id,
        label,
        NEW.active_ts,
        setweight(to_tsvector(name), 'A') ||
        setweight(to_tsvector(email), 'B') ||
        setweight(to_tsvector(NEW.status || ' ' || NEW.role), 'C') ||
        to_tsvector(replace(email, '@', ' '))
      ) ON CONFLICT (user_id) DO UPDATE SET label=EXCLUDED.label, vector=EXCLUDED.vector, active_ts=EXCLUDED.active_ts;
    END IF;
    return NULL;
  END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS user_inserted ON users;
CREATE TRIGGER user_inserted AFTER INSERT ON users FOR EACH ROW EXECUTE PROCEDURE update_user_search();
DROP TRIGGER IF EXISTS user_updated ON users;
CREATE TRIGGER user_updated AFTER UPDATE ON users FOR EACH ROW EXECUTE PROCEDURE update_user_search();


CREATE OR REPLACE FUNCTION update_event_search() RETURNS trigger AS $$
  DECLARE
    company INT;
    category_name TEXT;
  BEGIN
    SELECT c.company, c.name INTO company, category_name FROM categories c WHERE id=NEW.category;
    INSERT INTO search (company, event, label, active_ts, vector) VALUES (
      company,
      NEW.id,
      NEW.name,
      NEW.start_ts,
      setweight(to_tsvector(NEW.name), 'A') ||
      setweight(to_tsvector(coalesce(NEW.short_description, '')), 'B') ||
      setweight(to_tsvector(coalesce(NEW.location_name, '')), 'C') ||
      setweight(to_tsvector(NEW.status || ' ' || category_name), 'C') ||
      to_tsvector(coalesce(NEW.long_description, ''))
    ) ON CONFLICT (event) DO UPDATE SET label=EXCLUDED.label, vector=EXCLUDED.vector, active_ts=EXCLUDED.active_ts;
    return NULL;
  END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS event_inserted ON events;
CREATE TRIGGER event_inserted AFTER INSERT ON events FOR EACH ROW EXECUTE PROCEDURE update_event_search();
DROP TRIGGER IF EXISTS event_updated ON events;
CREATE TRIGGER event_updated AFTER UPDATE ON events FOR EACH ROW EXECUTE PROCEDURE update_event_search();
