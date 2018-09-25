CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE OR REPLACE FUNCTION update_user_ts() RETURNS trigger AS $$
  BEGIN
    UPDATE users SET active_ts=now() WHERE id=NEW.user_id;
    return NULL;
  END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS update_user_ts ON actions;
CREATE TRIGGER update_user_ts AFTER INSERT ON actions FOR EACH ROW EXECUTE PROCEDURE update_user_ts();

CREATE OR REPLACE FUNCTION check_tickets_remaining(event_id INT, ttl INT) RETURNS INT AS $$
  DECLARE
    tickets_taken_ INT;
  BEGIN
    DELETE FROM tickets
    WHERE status='reserved' AND event=event_id AND now() - created_ts > (ttl || ' seconds')::interval;

    SELECT coalesce(SUM(tt.slots_used), 0) INTO tickets_taken_
    FROM tickets
    JOIN ticket_types AS tt ON tickets.ticket_type=tt.id
    WHERE tickets.event=event_id AND status != 'cancelled';

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


CREATE OR REPLACE FUNCTION iso_ts(v TIMESTAMP) RETURNS VARCHAR(5) AS $$
  DECLARE
  BEGIN
    return to_char(v, 'YYYY-MM-DD"T"HH24:MI:SS');
  END;
$$ LANGUAGE plpgsql;


CREATE OR REPLACE FUNCTION iso_ts_tz(v TIMESTAMPTZ, tz VARCHAR(63)) RETURNS VARCHAR(5) AS $$
  DECLARE
  BEGIN
    return to_char(v AT TIME ZONE tz, 'YYYY-MM-DD"T"HH24:MI:SS');
  END;
$$ LANGUAGE plpgsql;


CREATE OR REPLACE FUNCTION iso_ts_with_tz(v TIMESTAMPTZ, tz VARCHAR(63)) RETURNS VARCHAR(5) AS $$
  DECLARE
  BEGIN
    PERFORM set_config('timezone', tz, true);
    return to_char(v, 'YYYY-MM-DD"T"HH24:MI:SSOF');
  END;
$$ LANGUAGE plpgsql;

