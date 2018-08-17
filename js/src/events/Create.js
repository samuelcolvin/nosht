import React from 'react'
import {Row, Col} from 'reactstrap'
import WithContext from '../utils/context'
import requests from '../utils/requests'
import {Form} from '../forms/Form'
import Markdown from '../general/Markdown'

export const EVENT_FIELDS = [
  {
    name: 'name',
    required: true,
    help_text: 'Public name of the event, keep this short and appealing.',
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
    help_text: 'The type of event you want to host.',
  },
  {
    name: 'public',
    title: 'Public Event',
    type: 'bool',
    help_text: 'Whether or not this event will be visible to anyone on the site and in public search results. ' +
                'If not public people will need a link to view this event.',
  },
  {
    name: 'date',
    title: 'Event Start',
    type: 'datetime',
    required: true,
    help_text: 'Let guests know when the event will start and how long it will go on for, you can add more ' +
                'details about exact timings in the description below.',
  },
  {
    name: 'location',
    type: 'geolocation',
    help_text: 'Drag the marker to set the exact event location.',
  },
  {
    name: 'ticket_limit',
    type: 'integer',
    help_text: 'Maximum number of tickets available for the event.',
  },
  {
    name: 'price',
    type: 'number',
    step: 0.01, min: 1, max: 1000,
    help_text: "Price of standard tickets for the event. Leave blank if tickets are free. You can add more " +
                "ticket types onces you've created the event.",
  },
  {
    name: 'long_description',
    title: 'Long Description',
    type: 'md',
    required: true,
    help_text: 'Detailed description of the event.',
    max_length: 5000,
    placeholder: 'Full description of the event with everything your guests might like to know...'
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
    let data
    try {
      data = await requests.get('/events/categories/')
    } catch (error) {
      this.props.ctx.setError(error)
      return
    }
    this.setState({categories: data.categories})
  }

  fields () {
    const c = (this.state.categories || []).map(c => ({value: c.id, display_name: c.name}))
    const m = this.props.location.search.match(/cat=(\d+)/)
    const cat_default = m ? parseInt(m[1]) : null
    return (
      EVENT_FIELDS
      .filter(f => f.name !== 'short_description')
      .map(f => f.name === 'category' ? Object.assign({}, f, {choices: c, default: cat_default}) : f)
    )
  }

  finished (r) {
    this.props.history.push(r ? `/dashboard/events/${r.pk}/` : '/dashboard/events/')
  }

  modify_form_data (d, field_name) {
    if (field_name === 'category' && d.price === undefined) {
      const suggested_price = this.state.categories.find(c => c.id.toString() === d.category).suggested_price
      if (suggested_price) {
        d.price = suggested_price
      }
    }
  }

  render () {
    const cat_id = this.state.form_data && this.state.form_data.category && parseInt(this.state.form_data.category)
    const cat = cat_id && this.state.categories.find(c => c.id === cat_id)
    return (
      <Row>
        <Col md={8}>
          <h1>Create Event</h1>
          <Form fields={this.fields()}
                action="/events/add/"
                onChange={d => this.setState({form_data: d})}
                modify_data={this.modify_form_data.bind(this)}
                finished={this.finished.bind(this)}/>
        </Col>
        <Col md={4}>
          {cat && <Markdown content={cat.host_advice}/>}
        </Col>
      </Row>
    )
  }
}
export default WithContext(CreateEvent)
