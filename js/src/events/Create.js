import React from 'react'
import {Row, Col} from 'reactstrap'
import WithContext from '../utils/context'
import requests from '../utils/requests'
import {Form} from '../forms/Form'
import timezones from '../forms/timezones'
import Markdown from '../general/Markdown'

export const EVENT_FIELDS = [
  {
    name: 'name',
    required: true,
    title: 'Event name',
    help_text: 'Public name of the event, keep this short and appealing.',
    max_length: 150
  },
  {
    name: 'short_description',
    title: 'Short Description',
    type: 'textarea',
    required: true,
    max_length: 140,
    help_text: 'Short summary of the event, maximum 140 characters.'
  },
  {
    name: 'category',
    type: 'select',
    choices: [],
    required: true,
    help_text: 'The Category of event you want to host.',
  },
  {
    name: 'mode',
    type: 'select',
    choices: [
      {value: 'tickets', display_name: 'Ticketed Only - allow people to book tickets, either paid or for free'},
      {value: 'donations', display_name: 'Donations Only - allow people to make donations'},
      {value: 'both', display_name: 'Tickets and donations - allow people to either book tickets or make donations'},
    ],
    required: true,
    default: 'tickets',
    help_text: 'The type of event you want to host.',
  },
  {
    name: 'public',
    title: 'Public Event',
    type: 'bool',
    default: true,
    help_text: 'Tick to make this event public so it will be visible to anyone on the site and ' +
        'appear in public search results. If your event is not public you will need to share the event link ' +
        'with people for them to view and book tickets or donate (depending on the event type).'
  },
  {
    name: 'date',
    title: 'Event Start or Deadline',
    type: 'datetime',
    required: true,
    help_text: 'Let people know when the event will start and how long it will go on for, you can add more ' +
         'details about exact timings in the description below. If this event is for donations only, ' +
         'this date will be the deadline for donations.',
  },
  {
    name: 'timezone',
    type: 'select',
    choices: timezones,
    required: true,
  },
  {
    name: 'location',
    type: 'geolocation',
    help_text: 'Drag the marker to set the exact event location.',
  },
  {
    name: 'ticket_limit',
    type: 'integer',
    min: 1,
    help_text: 'Maximum number of tickets available for the event.',
  },
  {
    name: 'price',
    type: 'number',
    step: 0.01, min: 1, max: 1000,
    help_text: "Price of standard tickets for your event. Leave blank if tickets are free. " +
               "You can add more ticket types once you've created the event.",
  },
  {
    name: 'suggested_donation',
    type: 'number',
    step: 0.01, min: 1, max: 1000,
    help_text: "Suggested amount for donations. You can add more suggested amounts once you've created the event.",
  },
  {
    name: 'donation_target',
    type: 'number',
    step: 1, min: 1, max: 100000,
    help_text: 'Target for donations, this is only shown to hosts.',
  },
  {
    name: 'external_ticket_url',
    title: 'External Ticketing URL',
    type: 'url',
    help_text: "Set if you're not selling tickets for this event through this platform.",
  },
  {
    name: 'external_donation_url',
    title: 'External Donations URL',
    type: 'url',
    help_text: "Set if you're not accepting donations for this event through this platform.",
  },
  {
    name: 'youtube_video_id',
    title: 'Youtube video ID',
    help_text: `Embed a Youtube video using it's ID e.g: "oD9zn9M9NBg".`,
  },
  {
    name: 'description_intro',
    title: 'Description Intro',
    type: 'md',
    help_text: 'Intro text to appear before image and long description.',
    max_length: 5000,
  },
  {
    name: 'long_description',
    title: 'Long Description',
    type: 'md',
    required: true,
    help_text: 'Detailed description of the event; you can update this later if you have more information.',
    max_length: 5000,
    placeholder: 'Full description of the event with everything your supporters need to know...'
  },
]

class CreateEvent extends React.Component {
  constructor (props) {
    super(props)
    this.state = {
      categories: null,
      form_data: {}
    }
    this.fields = this.fields.bind(this)
  }

  async componentDidMount () {
    const form_data = {timezone: Intl.DateTimeFormat().resolvedOptions().timeZone}
    EVENT_FIELDS.filter(f => f.hasOwnProperty('default')).forEach(f => form_data[f.name] = f.default)
    let data
    try {
      data = await requests.get('/events/categories/')
    } catch (error) {
      this.props.ctx.setError(error)
      return
    }
    this.setState({categories: data.categories})
    const m = this.props.location.search.match(/cat=(\d+)/)
    const cat_initial = m ? parseInt(m[1]) : null
    if (cat_initial) {
      form_data['category'] = cat_initial
    }
    this.setState({form_data})
  }

  fields () {
    const choices = (this.state.categories || []).map(c => ({value: c.id, display_name: c.name}))
    const mode = this.state.form_data.mode || 'tickets'
    return EVENT_FIELDS
      .filter(f => f.name !== 'short_description' && f.name !== 'timezone')
      .filter(f => this.props.ctx.user.role === 'admin'
                || !['external_ticket_url', 'external_donation_url'].includes(f.name))
      .filter(f => mode !== 'donations' || (f.name !== 'price' && f.name !== 'ticket_limit'))
      .filter(f => mode !== 'tickets' || (f.name !== 'suggested_donation' && f.name !== 'donation_target'))
      .map(f => f.name === 'category' ? Object.assign({}, f, {choices}) : f)
  }

  finished (r) {
    this.props.history.push(r ? `/dashboard/events/${r.pk}/` : '/dashboard/events/')
  }

  onChange (form_data) {
    if (form_data.category !== this.state.form_data.category && form_data.price === undefined) {
      const selected_cat = this.state.categories.find(c => c.id.toString() === form_data.category)
      if (selected_cat) {
        form_data.price = selected_cat && selected_cat.suggested_price
      }
    }
    this.setState({form_data})
  }

  render () {
    const cat_id = this.state.form_data && this.state.form_data.category && parseInt(this.state.form_data.category)
    const cat = cat_id && this.state.categories && this.state.categories.find(c => c.id === cat_id)
    return (
      <Row>
        <Col md={8}>
          <h1>Create Event</h1>
          <Form
              fields={this.fields()}
              action="/events/add/"
              form_data={this.state.form_data}
              onChange={this.onChange.bind(this)}
              finished={this.finished.bind(this)}
          />
        </Col>
        <Col md={4}>
          {cat && <Markdown className="sticky-top top-70" content={cat.host_advice}/>}
        </Col>
      </Row>
    )
  }
}
export default WithContext(CreateEvent)
