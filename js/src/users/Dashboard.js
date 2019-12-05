import React from 'react'
import {Table} from 'reactstrap'
import requests from '../utils/requests'
import {format_date, format_datetime, as_title} from '../utils'
import {RenderList, RenderDetails} from '../general/Dashboard'
import ButtonConfirm from '../general/Confirm'
import {InfoModal} from '../general/Modal'
import {ModalForm} from '../forms/Form'
import Tickets from './Tickets'

const FIELDS = [
  {name: 'first_name'},
  {name: 'last_name'},
  {name: 'email', type: 'email', required: true},
  {
    name: 'role_type',
    type: 'select',
    required: true,
    choices: [
      {value: 'guest'},
      {value: 'host'},
      {value: 'admin'}
    ]
  },
  {name: 'phone_number'},
  {
    name: 'receive_emails',
    type: 'bool',
    help_text: 'Whether this user should receive emails.',
    default: true,
  },
  {
    name: 'allow_marketing',
    type: 'bool',
    help_text: 'Whether this user has opted in to marketing emails.',
    default: false,
  },
]
const ADD_ROLE_CHOICES = [
  {value: 'host'},
  {value: 'admin'}
]

export class UsersList extends RenderList {
  constructor (props) {
    super(props)
    this.uri = '/dashboard/users/'
    this.state.buttons = [
      {name: 'Create User', link: this.uri + 'add/'},
    ]
    this.state.formats = {
      active_ts: {
        title: 'Last Active',
        render: v => format_date(v, true),
      },
      role_type: {render: as_title},
      status: {render: as_title},
    }
    this.state.search_uri = '/users/search/'
  }

  extra () {
    const fields = (
      FIELDS
      .map(f => f.name === 'role_type' ? Object.assign({}, f, {choices: ADD_ROLE_CHOICES}) : f)
    )
    return <ModalForm title="Create User"
                      parent_uri={this.uri}
                      success_msg="User Created"
                      mode="add"
                      action='/users/add/'
                      fields={fields}/>
  }
}

class Actions extends React.Component {
  constructor (props) {
    super(props)
    this.state = {selected: null}
  }

  render () {
    if (!this.props.actions || !this.props.actions.length) {
      return (
        <div>
          <h4>Actions</h4>
          <small>No Actions for this user</small>
        </div>
      )
    }
    const fields = {
      type: {title: 'Action', render: as_title},
      ts: {title: 'Time', render: format_datetime},
    }
    return (
      <div>
        <InfoModal isOpen={!!this.state.selected}
                   onClose={() => this.setState({selected: null})}
                   title={this.state.selected && as_title(this.state.selected.type)}
                   fields={fields}
                   object={this.state.selected}/>
        <h4>Actions</h4>
        <Table striped>
          <thead>
            <tr>
              <th>Time</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {this.props.actions.map((a, i) => (
              <tr key={i} onClick={() => this.setState({selected: a})} className="cursor-pointer">
                <td>{format_datetime(a.ts)}</td>
                <td>{as_title(a.type)}</td>
              </tr>
            ))}
          </tbody>
        </Table>
      </div>
    )
  }
}

export class UsersDetails extends RenderDetails {
  constructor (props) {
    super(props)
    this.state.buttons = [
      {name: 'Edit', link: this.uri + 'edit/'},
    ]
    this.state.formats = {
      email: {index: -1},
      role_type: {render: as_title},
      status: {
        render: v => {
          const new_status = v === 'active' ? 'suspended' : 'active'
          return (
            <span>
              {as_title(v)}
              <ButtonConfirm action={`/users/${this.id()}/switch-status/`}
                             modal_title="Switch Status"
                             btn_text={`Mark as ${as_title(new_status)}`}
                             done={this.update}
                             btn_size="sm"
                             className="ml-2">
                Are you sure you want to change the user's status from
                &nbsp;<b>{as_title(v)}</b> to <b>{as_title(new_status)}</b>?
              </ButtonConfirm>
            </span>
          )
        }
      },
      created_ts: {
        title: 'Created',
        render: v => format_date(v, true),
        index: 1,
      },
      active_ts: {
        title: 'Last Active',
        render: v => format_date(v, true),
        index: 2,
      },
      first_name: null,
      last_name: null,
    }
  }

  async got_data (data) {
    super.got_data(data)
    let r
    try {
      r = await Promise.all([
        requests.get(`/users/${this.id()}/actions/`),
        requests.get(`/users/${this.id()}/tickets/`),
      ])
    } catch (error) {
      this.props.ctx.setError(error)
      return
    }
    this.setState({actions: r[0].actions, tickets: r[1].tickets})
  }

  extra () {
    return [
      <Tickets key="t" tickets={this.state.tickets}/>,
      <Actions key="a" actions={this.state.actions}/>,
      <ModalForm key="edit"
                 title="Edit User"
                 parent_uri={this.uri}
                 mode="edit"
                 success_msg="User updated"
                 initial={this.state.item}
                 update={this.update}
                 action={`/users/${this.id()}/`}
                 fields={FIELDS}/>,
    ]
  }
}
