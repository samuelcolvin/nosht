import React from 'react'
import {format_event_start, format_event_duration, format_date} from '../../utils'
import {RenderDetails} from '../utils/Renderers'
import {ModelForm} from '../forms/Modal'


export class EventsDetails extends RenderDetails {
  constructor (props) {
    super(props)
    this.skip_keys = ['id', 'slug', 'cat_slug']
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

  async got_data (data) {
    super.got_data(data)
    this.setState({
      buttons: [
        {name: 'View Public Page', link: `/${data.cat_slug}/${data.slug}/`}
      ]
    })
  }
}

const CAT_FIELDS = [
  {name: 'name'},
  {name: 'live', type: 'bool'},
  {name: 'description', type: 'textarea'},
]

export class CategoriesDetails extends RenderDetails {
  constructor (props) {
    super(props)
    this.uri = `/settings/categories/${this.id}/`
    this.state = {
      item: null,
      buttons: [
        {name: 'Edit', link: this.uri + 'edit/'}
      ]
    }
  }

  extra () {
    return <ModelForm {...this.props}
                      parent_uri={this.uri}
                      title="Edit Category"
                      method="put"
                      update={this.update}
                      action={`/${this.props.page.name}/${this.id}/`}
                      fields={CAT_FIELDS}/>
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
