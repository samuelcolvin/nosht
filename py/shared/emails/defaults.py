from enum import Enum


class Triggers(str, Enum):
    """
    Must match EMAIL_TRIGGERS in sql/models.sql
    """

    ticket_buyer = 'ticket-buyer'
    ticket_other = 'ticket-other'
    event_update = 'event-update'
    event_reminder = 'event-reminder'

    donation_thanks = 'donation-thanks'

    event_host_created = 'event-host-created'
    event_host_update = 'event-host-update'
    event_host_final_update = 'event-host-final-update'
    event_tickets_available = 'event-tickets-available'
    waiting_list_add = 'waiting-list-add'

    password_reset = 'password-reset'
    account_created = 'account-created'
    admin_notification = 'admin-notification'


EMAIL_DEFAULTS = {
    Triggers.ticket_buyer: {
        'subject': '{{{ event_name }}} Ticket Confirmation',
        'title': '{{ company_name }}',
        'body': """
Hi {{ first_name }},

Thanks for booking your ticket{{#ticket_count_plural}}s{{/ticket_count_plural}} for {{ category_name }}, \
**{{ event_name }}** hosted by {{ host_name }}.

{{#extra_info}}
{{ ticket_extra_title }}: **{{ extra_info }}**
{{/extra_info}}
{{^extra_info}}
{{ ticket_extra_title }} not provided, please let the event host {{ host_name }} know if you have any special \
requirements.
{{/extra_info}}

{{ primary_button(View Event | {{ event_link }}) }}

Event:

* Start Time: **{{ event_start }}**
* Duration: **{{ event_duration }}**{{#ticket_id}}
* Ticket ID: **{{ ticket_id }}**{{/ticket_id}}{{#event_location}}
* Location: **{{ event_location }}**{{/event_location}}

{{#static_map}}
[![{{ event_location }}]({{{ static_map }}})]({{{ google_maps_url }}})
{{/static_map}}

{{#ticket_id}}
**This is your ticket**, please bring the email (and particularly the ticket reference above) \
to the event.
{{/ticket_id}}

Payment:

* Ticket Price: **{{ ticket_price }}**
* Tickets Purchased: **{{ ticket_count }}**{{#extra_donated}}
* Discretionary extra donation: **{{ extra_donated }}**{{/extra_donated}}
* Total Amount Charged: **{{ total_price }}**

{{#card_details}}
_(Card Charged: {{ card_details }})_
{{/card_details}}
""",
    },
    Triggers.ticket_other: {
        'subject': '{{{ event_name }}} Ticket',
        'title': '{{ company_name }}',
        'body': """
Hi {{ first_name }},

Great news! {{ buyer_name }} has bought you a ticket for {{ category_name }}, \
**{{ event_name }}** hosted by {{ host_name }}.

{{#extra_info}}
{{ ticket_extra_title }}: **{{ extra_info }}**
{{/extra_info}}
{{^extra_info}}
{{ ticket_extra_title }} not provided, please let the event host {{ host_name }} know if you have any special \
requirements.
{{/extra_info}}

{{ primary_button(View Event | {{ event_link }}) }}

Event:

* Start Time: **{{ event_start }}**
* Duration: **{{ event_duration }}**
* Ticket ID: **{{ ticket_id }}**
{{#event_location}}* Location: **{{ event_location }}**{{/event_location}}

{{#static_map}}
[![{{ event_location }}]({{{ static_map }}})]({{{ google_maps_url }}})
{{/static_map}}

**This is your ticket**, please bring the email (and particularly the ticket reference above) \
to the event.
""",
    },
    Triggers.event_update: {
        'subject': '{{{ subject }}}',
        'title': '{{ company_name }}',
        'body': """
Hi {{ first_name }},

{{{ message }}}

{{ primary_button(View Event | {{ event_link }}) }}
""",
    },
    Triggers.event_reminder: {
        'subject': '{{{ event_name }}} Upcoming',
        'title': '{{ company_name }}',
        'body': """
Hi {{ first_name }},

You're booked in to attend **{{ event_name }}** hosted by {{ host_name }}, the event will start in a day's time.

{{ primary_button(View Event | {{ event_link }}) }}

Event:

* Start Time: **{{ event_start }}**
* Duration: **{{ event_duration }}**
{{#event_location}}* Location: **{{ event_location }}**{{/event_location}}

{{#static_map}}
[![{{ event_location }}]({{{ static_map }}})]({{{ google_maps_url }}})
{{/static_map}}
""",
    },
    Triggers.donation_thanks: {
        'subject': 'Thanks for your donation',
        'title': '{{ company_name }}',
        'body': """
Hi {{ first_name }},

Thanks for your donation to {{ donation_option_name }} of {{ amount_donated }}.

{{#gift_aid_enabled}}
You have allowed us to collect gift aid meaning we can collect %25 on top of your original donation.
{{/gift_aid_enabled}}
{{^gift_aid_enabled}}
You did not enable gift aid.
{{/gift_aid_enabled}}

_(Card Charged: {{ card_details }})_
""",
    },
    Triggers.event_host_update: {
        'subject': '{{{ event_name }}} Update from {{{ company_name }}}',
        'title': '{{ company_name }}',
        'body': """
Hi {{ first_name }},

Your event {{ event_name }} is coming up in **{{ days_to_go }}** days on **{{ event_date }}**.

<div class="stat-label">Tickets Booked in the last day</div>
<div class="stat-value">
  <span class="large">{{ tickets_booked_24h }}</span>
</div>

<div class="stat-label">Tickets Booked Total</div>
<div class="stat-value">
  <span class="large">{{ tickets_booked }}</span>{{#ticket_limit}} of {{ ticket_limit }}.{{/ticket_limit}}
</div>

{{#total_income}}
<div class="stat-label">Total made from ticket sales</div>
<div class="stat-value">
  <span class="large">{{ total_income }}</span>
</div>
{{/total_income}}

{{#fully_booked}}
**Congratulations, all tickets have been booked - your event is full.**
{{/fully_booked}}
{{^fully_booked}}
Guests can book your event by going to

<div class="text-center highlighted">{{ event_link }}</div>

Share this link via email or social media to garner further bookings.
{{/fully_booked}}

{{ primary_button(Event Dashboard | {{ event_dashboard_link }}) }}
""",
    },
    Triggers.event_host_created: {
        'subject': '{{{ event_name }}} Created for {{{ company_name }}}',
        'title': '{{ company_name }}',
        'body': """
Hi {{ first_name }},

Great news - you've set up your {{ category_name }} in support of {{ company_name }}. \
Thank you, we're thrilled that you're getting involved.

You can access all information, including tickets sold, guest lists etc... \
related to your event at any time by using the following link:

{{ primary_button(Event Dashboard | {{ event_dashboard_link }}) }}
""",
    },
    Triggers.event_host_final_update: {
        'subject': '{{{ event_name }}} Final Update from {{{ company_name }}}',
        'title': '{{ company_name }}',
        'body': """
Hi {{ first_name }},

It's nearly time for your {{ category_name }}, {{ event_name }}, which is very exciting. \
We wanted to make sure you have all the info you need.

You have **{{ tickets_booked }}** bookings confirmed, guests can continue to book tickets until the event ends.

You can download your guest list with booking references, dietary requirements and any special requests \
by visiting the event page:

{{ primary_button(Event Dashboard | {{ event_dashboard_link }}) }}

We hope everything goes well and we look forward to hearing about it afterwards.

Good luck!
""",
    },
    Triggers.password_reset: {
        'subject': '{{{ company_name }}} Password Reset',
        'title': '{{ company_name }}',
        'body': """
Hi {{ first_name }},

Please use the link below to reset your password for {{ company_name }}.

{{ primary_button(Reset Your Password | {{ reset_link }}) }}
""",
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

{{ primary_button(Confirm Email | {{ confirm_email_link }}) }}
{{/confirm_email_link}}
{{^confirm_email_link}}
You can now create and publish events whenever you wish.

{{ primary_button(Create & Publish Events | {{ events_link }}) }}
{{/confirm_email_link}}
""",
    },
    Triggers.admin_notification: {
        'subject': 'Update: {{{ summary }}}',
        'title': '',
        'body': """\
{{ company_name }} update:

{{{ details }}}

{{#action_link}}
{{ primary_button({{ action_label }} | {{ action_link }}) }}
{{/action_link}}
""",
    },
    Triggers.event_tickets_available: {
        'subject': '{{{ event_name }}} - New Tickets Available',
        'title': '{{ company_name }}',
        'body': """
Hi {{ first_name }},

Great news! New tickets have become available for **{{ event_name }}**.

{{ primary_button(View Event | {{ event_link }}) }}

If you no-longer wish to see emails about the waiting list for this event,
you may [remove yourself from the waiting list]({{ remove_link }}) at any time.
""",
    },
    Triggers.waiting_list_add: {
        'subject': '{{{ event_name }}} - Added to Waiting List',
        'title': '{{ company_name }}',
        'body': """
Hi {{ first_name }},

You've been added to the waiting list for [{{ event_name }}]({{ event_link }}).

You'll receive an email as soon as more tickets become available.

If you no-longer wish to see emails about the waiting list for this event,
you may [remove yourself from the waiting list]({{ remove_link }}) at any time.
""",
    },
}
