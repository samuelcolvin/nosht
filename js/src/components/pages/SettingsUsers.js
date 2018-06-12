import {format_date} from '../../utils'
import {RenderList, RenderDetails} from '../utils/Settings'

export class UsersList extends RenderList {}

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
