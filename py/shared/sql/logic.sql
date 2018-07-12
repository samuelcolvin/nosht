-- TODO: update user active_ts on actions


-- TODo remove ticket_insert and call check_tickets_remaining instead
CREATE OR REPLACE FUNCTION ticket_insert() RETURNS trigger AS $$
  DECLARE
  BEGIN
    UPDATE events SET tickets_taken = tickets_taken + 1 WHERE id=NEW.event;
    return NULL;
  END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS ticket_insert ON tickets;
CREATE TRIGGER ticket_insert AFTER INSERT ON tickets FOR EACH ROW EXECUTE PROCEDURE ticket_insert();


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
