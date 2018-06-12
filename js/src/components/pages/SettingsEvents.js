import {format_event_start, format_event_duration} from '../../utils'
import {RenderList, RenderDetails} from '../utils/Renderers'

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
  }
}

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
