from enum import Enum


class Triggers(str, Enum):
    """
    Must match EMAIL_TRIGGERS in sql/models.sql
    """
    ticket_buyer = 'ticket-buyer'
    ticket_other = 'ticket-other'
    event_update = 'event-update'
    event_reminder = 'event-reminder'

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
{{#event_location}}* Location: **{{ event_location }}**{{/event_location}}

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
        'subject': '{{{ subject }}}',
        'title': '{{ company_name }}',
        'body': """
Hi {{ first_name }},

{{{ message }}}

{{ centered_button(View Event | {{ event_link }}) }}
"""
    },
    Triggers.event_reminder: {
        'subject': '{{{ event_name }}} Upcoming',
        'title': '{{ company_name }}',
        'body': """
Hi {{ first_name }},

You're booked in to attend **{{ event_name }}**, the event will start in a day's time.

{{ centered_button(View Event | {{ event_link }}) }}

Event:

* Start Time: **{{ event_start }}**
* Duration: **{{ event_duration }}**
{{#event_location}}* Location: **{{ event_location }}**{{/event_location}}

{{#static_map}}
[![{{ event_location }}]({{{ static_map }}})]({{{ google_maps_url }}})
{{/static_map}}
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
        'title': '{{ company_name }}',
        'body': """
Hi {{ first_name }},

Please use the link below to reset your password for {{ company_name }}.

{{ centered_button(Reset Your Password | {{ reset_link }}) }}
"""
    },
    Triggers.account_created: {
        'subject': (
            '{{{ company_name }}} Account Created{{#confirm_email_link}} (Action required){{/confirm_email_link}}'
        ),
        'title': '{{ company_name }}',
        'body': """
Hi {{ first_name }},

{{#created_by_admin}}An account has been created for you with {{ company_name }}.{{/created_by_admin}}
{{^created_by_admin}}Thanks for signing up for an account with {{ company_name }}.{{/created_by_admin}}

{{#confirm_email_link}}
{{#is_admin}}
You've been created as an administrator.

You need to confirm your email address before you can administer the system.
{{/is_admin}}
{{^is_admin}}You need to confirm your email address before you can publish events.{{/is_admin}}

{{ centered_button(Confirm Email | {{ confirm_email_link }}) }}
{{/confirm_email_link}}
{{^confirm_email_link}}
You can now create and publish events whenever you wish.

{{ centered_button(Create & Publish Events | {{ events_link }}) }}
{{/confirm_email_link}}
"""
    },
    Triggers.admin_notification: {
        'subject': 'Update: {{{ summary }}}',
        'title': '',
        'body': """\
{{ company_name }} update:

{{{ details }}}

{{#action_link}}
{{ centered_button({{ action_label }} | {{ action_link }}) }}
{{/action_link}}
"""
    },
}
