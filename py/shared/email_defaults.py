from enum import Enum


class Triggers(str, Enum):
    confirmation_buyer = 'confirmation_buyer'
    confirmation_other = 'confirmation_other'
    event_update = 'event_update'
    event_reminder = 'event_reminder'

    event_booking = 'event_booking'
    event_host_update = 'event_host_update'

    password_reset = 'password_reset'
    account_created = 'account_created'
    admin_notification = 'admin_notification'


EMAIL_DEFAULTS = {
    Triggers.confirmation_buyer: {
        'subject': 'confirmation_buyer',
        'title': '',
        'body': """
Email confirmation_buyer
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
        'subject': 'password_reset',
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
