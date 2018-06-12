import React from 'react'
import {format_event_start, format_event_duration, format_date} from '../../utils'
import {RenderDetails, ModalForm} from '../utils/Renderers'



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
      }
    }
  }
}

export class CategoriesDetails extends RenderDetails {
  constructor (props) {
    super(props)
    this.uri = `/settings/categories/${this.id}/`
    this.buttons = [
      {name: 'Edit', link: this.uri + 'edit/'}
    ]
  }

  extra () {
    return <ModalForm history={this.props.history} location={this.props.location} parent_uri={this.uri}/>
  }
}


export class UsersDetails extends RenderDetails {
  constructor (props) {
    super(props)
    this.formats = {
      created_ts: {
        title: 'Created',
        render: v => format_date(v, true),
      },
      active_ts: {
        title: 'Last Active',
        render: v => format_date(v, true),
      },
    }
  }
}
