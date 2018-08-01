from enum import Enum


class Triggers(str, Enum):
    """
    Must match EMAIL_TRIGGERS in sql/models.sql
    """
    ticket_buyer = 'ticket-buyer'
    ticket_other = 'ticket-other'
    event_update = 'event-update'
    event_reminder = 'event-reminder'

    event_booking = 'event-booking'
    event_host_update = 'event-host-update'

    password_reset = 'password-reset'
    account_created = 'account-created'
    admin_notification = 'admin-notification'


EMAIL_DEFAULTS = {
    Triggers.ticket_buyer: {
        'subject': '{{{ event_name }}} Ticket Confirmation',
        'title': '{{ company_name }}',
        'body': """
Hi {{ first_name }},

Thanks for booking your ticket{{#ticket_count_plural}}s{{/ticket_count_plural}} for **{{ event_name }}**.

{{ centered_button(View Event | {{ event_link }}) }}

Event:

* Start Time: **{{ event_start }}**
* Duration: **{{ event_duration }}**
* Location: **{{ event_location }}**

{{#static_map}}
[![{{ event_location }}]({{{ static_map }}})]({{{ google_maps_url }}})
{{/static_map}}

Payment:

* Ticket Price: **{{ ticket_price }}**
* Tickets Purchased: **{{ ticket_count }}**
* Total Amount Charged: **{{ total_price }}**


_(Card Charged: {{ card_details }})_
"""
    },
    Triggers.ticket_other: {
        'subject': '{{{ event_name }}} Ticket',
        'title': '{{ company_name }}',
        'body': """
Hi {{ first_name }},

Great news! {{ buyer_name }} has bought you a ticket for **{{ event_name }}**.

{{ centered_button(View Event | {{ event_link }}) }}

Event:

* Start Time: **{{ event_start }}**
* Duration: **{{ event_duration }}**
* Location: **{{ event_location }}**

{{#static_map}}
[![{{ event_location }}]({{{ static_map }}})]({{{ google_maps_url }}})
{{/static_map}}
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
        'subject': (
            '{{{ company_name }}} Account Created{{#confirm_email_link}} (Action required){{/confirm_email_link}}'
        ),
        'title': '{{ company_name }}',
        'body': """
Hi {{ first_name }},

Thanks for signing up for an account with {{ company_name }}.

{{#confirm_email_link}}
You need to confirm your email address before you can publish events.

{{ centered_button(Confirm Email | {{ confirm_email_link }}) }}
{{/confirm_email_link}}
{{^confirm_email_link}}
You can now create and publish events whenever you wish.

{{ centered_button(Create & Publish Events | {{ my_events_link }}) }}
{{/confirm_email_link}}
"""
    },
    Triggers.admin_notification: {
        'subject': '{{{ company_name }}} notification',
        'title': '',
        'body': """
```
{{{ __print_debug_context__ }}}
```
"""
    },
}
