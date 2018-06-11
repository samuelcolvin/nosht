import {format_event_start, format_event_duration} from '../../utils'
import {RenderList} from '../utils/Renderers'

export class EventsList extends RenderList {
  constructor (props) {
    super(props)
    this.title = 'Events'
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

export class CategoriesList extends RenderList {
  constructor (props) {
    super(props)
    this.title = 'Categories'
  }
}


export class UsersList extends RenderList {
  constructor (props) {
    super(props)
    this.title = 'Users'
  }
}
