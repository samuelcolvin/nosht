from enum import Enum, unique


@unique
class ActionTypes(str, Enum):
    login = 'login'
    guest_signin = 'guest-signin'
    host_signup = 'host-signup'
    logout = 'logout'
    password_reset = 'password-reset'
    reserve_tickets = 'reserve-tickets'
    buy_tickets = 'buy-tickets'
    buy_tickets_offline = 'buy-tickets-offline'
    book_free_tickets = 'book-free-tickets'
    donate_prepare = 'donate-prepare'
    donate_direct_prepare = 'donate-direct-prepare'
    donate = 'donate'
    cancel_reserved_tickets = 'cancel-reserved-tickets'
    cancel_booked_tickets = 'cancel-booked-tickets'
    create_event = 'create-event'
    event_guest_reminder = 'event-guest-reminder'
    event_update = 'event-update'
    edit_event = 'edit-event'
    edit_profile = 'edit-profile'
    edit_other = 'edit-other'
    email_waiting_list = 'email-waiting-list'
    unsubscribe = 'unsubscribe'
