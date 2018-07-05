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
    this.setState({
      buttons: [
        {name: 'View Public Page', link: `/${data.cat_slug}/${data.slug}/`},
        {name: 'Edit', link: this.uri + 'edit/'},
      ]
    })
  }

  extra () {
    if (!this.state.item) {
      return
    }
    const item = Object.assign({}, this.state.item)
    item.location = {name: item.location, lat: item.location_lat, lng: item.location_lng}
    item.date = {dt: item.start_ts, dur: item.duration}
    return <ModelForm {...this.props}
                      parent_uri={this.uri}
                      mode="edit"
                      success_msg='Event updated'
                      initial={item}
                      update={this.update}
                      action={`/events/${this.id}/`}
                      fields={EVENT_FIELDS}/>
  }
}
