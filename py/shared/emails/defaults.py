from enum import Enum


class Triggers(str, Enum):
    """
    Must match EMAIL_TRIGGERS in sql/models.py
    """
    confirmation_buyer = 'confirmation-buyer'
    confirmation_other = 'confirmation-other'
    event_update = 'event-update'
    event_reminder = 'event-reminder'

    event_booking = 'event-booking'
    event_host_update = 'event-host-update'

    password_reset = 'password-reset'
    account_created = 'account-created'
    admin_notification = 'admin-notification'


EMAIL_DEFAULTS = {
    Triggers.confirmation_buyer: {
        'subject': '{{{ company_name }}} Ticket Confirmation',
        'title': 'Ticket Purchase Confirmation',
        'body': """
Dear {{ first_name }}

This is a **test** of emails.

# With a title (h1)

and a like [to something](https://www.example.com).

## this is h2

with some body

### this is an h3

hello people
"""
    },
    Triggers.confirmation_other: {
        'subject': 'confirmation_other',
        'title': '',
        'body': """
Email confirmation_other
"""
    },
    Triggers.event_update: {
        'subject': 'event_update',
        'title': '',
        'body': """
Email event_update
"""
    },
    Triggers.event_reminder: {
        'subject': 'event_reminder',
        'title': '',
        'body': """
Email event_reminder
"""
    },
    Triggers.event_booking: {
        'subject': 'event_booking',
        'title': '',
        'body': """
Email event_booking
"""
    },
    Triggers.event_host_update: {
        'subject': 'event_host_update',
        'title': '',
        'body': """
Email event_host_update
"""
    },
    Triggers.password_reset: {
        'subject': '{{{ company_name }}} Password Reset',
        'title': '',
        'body': """
Email password_reset
"""
    },
    Triggers.account_created: {
        'subject': 'account_created',
        'title': '',
        'body': """
Email account_created
"""
    },
    Triggers.admin_notification: {
        'subject': 'admin_notification',
        'title': '',
        'body': """
Email admin_notification
"""
    },
}
