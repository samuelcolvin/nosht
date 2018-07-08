-- TODO: update user active_ts on actions

CREATE OR REPLACE FUNCTION set_taken_insert() RETURNS trigger AS $$
  DECLARE
  BEGIN
    UPDATE events SET tickets_taken = tickets_taken + 1 WHERE id=NEW.event;
    return NULL;
  END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS set_taken_insert ON tickets;
CREATE TRIGGER set_taken_insert AFTER INSERT ON tickets FOR EACH ROW EXECUTE PROCEDURE set_taken_insert();


CREATE OR REPLACE FUNCTION set_taken_update() RETURNS trigger AS $$
  DECLARE
    tickets_taken INT;
  BEGIN
    SELECT COUNT(*) INTO tickets_taken FROM tickets WHERE event=NEW.event AND status != 'cancelled';
    UPDATE events SET tickets_taken = tickets_taken WHERE id=NEW.event;
    return NULL;
  END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS set_taken_update ON tickets;
CREATE TRIGGER set_taken_update AFTER UPDATE ON tickets FOR EACH ROW EXECUTE PROCEDURE set_taken_update();
