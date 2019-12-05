import React from 'react'
import {as_title, format_date} from '../utils'
import requests from '../utils/requests'
import {RenderDetails} from '../general/Dashboard'
import {ModalForm} from '../forms/Form'
import Tickets from './Tickets'

const FIELDS = [
  {name: 'first_name'},
  {name: 'last_name'},
  {name: 'email', type: 'email', required: true},
  {name: 'phone_number'},
  {
    name: 'receive_emails',
    type: 'bool',
    help_text: 'Whether you wish to receive emails, this will be set to "false" if you click unsubscribe in an email.',
    default: true,
  },
  {
    name: 'allow_marketing',
    type: 'bool',
    help_text: 'Whether you would like to receive marketing emails.',
    default: false,
  },
]

export default class Account extends RenderDetails {
  constructor (props) {
    super(props)
    this.uri = '/dashboard/account/'
    this.state.buttons = [
      {name: 'Edit', link: this.uri + 'edit/'},
    ]
    this.state.formats = {
      role_type: {render: as_title},
      status: {render: as_title},
      created_ts: {
        title: 'Created',
        render: v => format_date(v, true),
        index: 1,
      },
      first_name: null,
      last_name: null,
    }
  }
  id = () => this.props.ctx.user.id
  get_uri = () => `/account/${this.id()}/`

  async got_data (data) {
    super.got_data(data)
    let r
    try {
      r = await requests.get(`/users/${this.id()}/tickets/`)
    } catch (error) {
      this.props.ctx.setError(error)
      return
    }
    this.setState({tickets: r.tickets})
  }

  extra () {
    return [
      <Tickets key="t" tickets={this.state.tickets}/>,
      <ModalForm title="Edit Profile"
                 key="1"
                 parent_uri={this.uri}
                 mode="edit"
                 success_msg="Profile Updated"
                 initial={this.state.item}
                 update={this.update}
                 action={`/account/${this.id()}/`}
                 fields={FIELDS}/>,
    ]
  }
}
