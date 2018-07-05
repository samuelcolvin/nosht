import React from 'react'
import {format_event_start, format_event_duration} from '../../utils'
import {RenderList, RenderDetails} from '../utils/Settings'
import {ModelForm} from '../forms/Form'

export class EventsList extends RenderList {
  constructor (props) {
    super(props)
    this.formats = {
      start_ts: {
        title: 'Date',
        render: (v, item) => format_event_start(v, item.duration),
      },
      duration: {
        render: format_event_duration
      }
    }
    this.state['buttons'] = [
      {name: 'Create Event', link: '/create/'},
    ]
  }
}

const EVENT_FIELDS = [
  {name: 'name', required: true},
  {name: 'public', title: 'Public Event', type: 'bool'},
  {name: 'date', title: 'Event Start', type: 'datetime', required: true},
  {name: 'location', type: 'geolocation', help_text: 'Drag the marker to set the exact event location.'},
  {name: 'ticket_limit', type: 'integer'},
  {name: 'long_description', title: 'Description', type: 'textarea', required: true},
]
const EVENT_STATUS_FIELDS = [
  {name: 'status', required: true, type: 'select', choices: [
    {value: 'pending'},
    {value: 'published'},
    {value: 'suspended'},
  ]},
]

export class EventsDetails extends RenderDetails {
  constructor (props) {
    super(props)
    this.formats = {
      start_ts: {
        title: 'Date',
        render: (v, item) => format_event_start(v, item.duration),
      },
      duration: {
        render: format_event_duration
      },
      slug: null,
      cat_slug: null,
      location_lat: null,
      location_lng: null,
    }
    this.uri = `/settings/events/${this.id}/`
  }

  async got_data (data) {
    super.got_data(data)
    const buttons = [
        {name: 'Edit', link: this.uri + 'edit/'},
        {name: 'Set Status', link: this.uri + 'set-status/'},
      ]
    if (data.status === 'published') {
      buttons.push({name: 'View Public Page', link: `/${data.cat_slug}/${data.slug}/`})
    }
    this.setState({buttons})
  }

  extra () {
    if (!this.state.item) {
      return
    }
    const item = Object.assign({}, this.state.item)
    item.location = {name: item.location, lat: item.location_lat, lng: item.location_lng}
    item.date = {dt: item.start_ts, dur: item.duration}
    return [
      <ModelForm {...this.props}
                 key="1"
                 parent_uri={this.uri}
                 mode="edit"
                 success_msg='Event updated'
                 initial={item}
                 update={this.update}
                 action={`/events/${this.id}/`}
                 fields={EVENT_FIELDS}/>,
      <ModelForm {...this.props}
                 key="2"
                 title="Set Event Status"
                 parent_uri={this.uri}
                 regex={/set-status\/$/}
                 mode="edit"
                 success_msg='Event updated'
                 initial={{status: item.status}}
                 update={this.update}
                 action={`/events/${this.id}/set-status/`}
                 fields={EVENT_STATUS_FIELDS}/>,

    ]
  }
}
