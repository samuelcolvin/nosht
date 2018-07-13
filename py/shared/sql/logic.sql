CREATE OR REPLACE FUNCTION update_user_ts() RETURNS trigger AS $$
  DECLARE
  BEGIN
    UPDATE users SET active_ts=now() WHERE id=NEW.user_id;
    return NULL;
  END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS update_user_ts ON actions;
CREATE TRIGGER update_user_ts AFTER INSERT ON actions FOR EACH ROW EXECUTE PROCEDURE update_user_ts();

DROP TRIGGER IF EXISTS ticket_insert ON tickets;

CREATE OR REPLACE FUNCTION check_tickets_remaining(event_id INT) RETURNS INT AS $$
  DECLARE
    tickets_taken_ INT;
    ticket_limit_ INT;
  BEGIN
    DELETE FROM tickets WHERE status='reserved' AND (now() - created_ts) > interval '10 minutes';

    SELECT coalesce(COUNT(*), 0) INTO tickets_taken_
    FROM tickets
    WHERE event=event_id AND status != 'cancelled';

    UPDATE events SET tickets_taken=tickets_taken_ WHERE id=event_id;

    SELECT ticket_limit INTO ticket_limit_ FROM events WHERE id=event_id;

    return ticket_limit_ - tickets_taken_;
  END;
$$ LANGUAGE plpgsql;
