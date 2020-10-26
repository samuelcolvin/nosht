import React from 'react'
import requests from '../utils/requests'
import {Table} from 'reactstrap'
import {Link} from 'react-router-dom'
import {RenderList, RenderDetails, ImageThumbnail, MarkdownPreview} from '../general/Dashboard'
import {Money} from '../general/Money'
import {ModalForm} from '../forms/Form'
import {ModalDropzoneForm} from '../forms/Drop'
import {format_datetime} from '../utils'
import {InfoModal} from '../general/Modal'

const FIELDS = [
  {name: 'name', required: true},
  {name: 'category', type: 'select', choices: [], required: true},
  {name: 'live', type: 'bool', default: true},
  {name: 'amount', type: 'number', step: 0.01, min: 1, max: 1000, required: true},
  {name: 'sort_index', type: 'integer'},
  {name: 'short_description', type: 'textarea', required: true},
  {name: 'long_description', type: 'md', required: true},
]

const get_fields = categories => {
  const c = (categories || []).map(c => ({value: c.id, display_name: c.name}))
  return FIELDS.map(f => f.name === 'category' ? Object.assign({}, f, {choices: c}) : f)
}

export class DonationOptionsList extends RenderList {
  constructor (props) {
    super(props)
    this.uri = '/dashboard/donation-options/'
    this.state.buttons = [
      {name: 'Add Donation Option', link: this.uri + 'add/'},
    ]
    this.state.formats = {
      amount: {render: v => <Money>{v}</Money>},
      category_name: {title: 'Category'},
    }
  }

  async got_data (data) {
    await super.got_data(data)
    try {
      const r = await requests.get('/events/categories/')
      this.setState({categories: r.categories})
    } catch (error) {
      this.props.ctx.setError(error)
    }
  }

  extra () {
    return <ModalForm {...this.props}
                      title="Add Donation Option"
                      parent_uri={this.uri}
                      success_msg="Donation Option Added"
                      mode="add"
                      action='/donation-options/add/'
                      fields={get_fields(this.state.categories)}/>
  }
}

class Donations extends React.Component {
  constructor (props) {
    super(props)
    this.state = {selected: null}
  }

  render () {
    if (!this.props.donations || !this.props.donations.length) {
      return (
        <div>
          <h4>Donations</h4>
          <small>No Donations for this donation option</small>
        </div>
      )
    }
    const fields = {
      ts: {title: 'Time', render: format_datetime},
      amount: {render: v => <Money>{v}</Money>},
      gift_aid: {},
      first_name: {},
      last_name: {},
      address: {},
      city: {},
      postcode: {},
      user_id: {
        title: 'User',
        render: (v, item) => (
          <Link to={`/dashboard/users/${v}/`}>
            {item.user_first_name} {item.user_last_name} {item.user_email}
          </Link>
        )
      },
      event_id: {
        title: 'Event',
        render: (v, item) => <Link to={`/dashboard/events/${v}/`}>{item.event_name}</Link>
      }
    }
    return (
      <div>
        <InfoModal isOpen={!!this.state.selected}
                   onClose={() => this.setState({selected: null})}
                   title={this.state.selected && `${this.state.selected.first_name} ${this.state.selected.last_name}`}
                   fields={fields}
                   object={this.state.selected}/>
        <h4>Donations</h4>
        <Table striped>
          <thead>
            <tr>
              <th>User</th>
              <th>Time</th>
            </tr>
          </thead>
          <tbody>
            {this.props.donations.map(d => (
              <tr key={d.id} onClick={() => this.setState({selected: d})} className="cursor-pointer">
                <td>{d.first_name} {d.last_name}</td>
                <td>{format_datetime(d.ts)}</td>
              </tr>
            ))}
          </tbody>
        </Table>
      </div>
    )
  }
}

export class DonationOptionDetails extends RenderDetails {
  constructor (props) {
    super(props)
    this.uri = `/dashboard/donation-options/${this.id()}/`
    this.state.formats = {
      amount: {render: v => <Money>{v}</Money>},
      category_name: {title: 'Category'},
      long_description: {wide: true, render: v => <MarkdownPreview v={v}/>},
      image: {
        wide: true,
        edit_link: this.uri + 'set-image/',
        render: (v, item) => <ImageThumbnail image={v} alt={item.name}/>
      },
      category: null,
    }
    this.state.buttons = [
      {name: 'Edit', link: this.uri + 'edit/'},
      {
        name: 'Delete Donation Option',
        action: `/donation-options/${this.id()}/delete/`,
        btn_color: 'danger',
        confirm_msg: 'Are you sure you want to permanently delete this donation option? This cannot be undone.',
        success_msg: 'Category deleted.',
        redirect_to: '/dashboard/donation-options/',
      }
    ]
  }

  async got_data (data) {
    super.got_data(data)
    let r
    try {
      r = await Promise.all([
        requests.get('/events/categories/'),
        requests.get(`/donation-options/${this.id()}/donations/`),
      ])
    } catch (error) {
      this.props.ctx.setError(error)
      return
    }
    this.setState({categories: r[0].categories, donations: r[1].donations})
  }

  extra () {
    return [
      <Donations key="l" donations={this.state.donations} id={this.id()}/>,
      <ModalForm title="Edit Donation Option"
                 key="e"
                 parent_uri={this.uri}
                 mode="edit"
                 success_msg="Donation Option Updated"
                 initial={this.state.item}
                 update={this.update}
                 action={`/donation-options/${this.id()}/`}
                 fields={get_fields(this.state.categories)}/>,
      <ModalDropzoneForm key="d"
                         parent_uri={this.uri}
                         regex={/set-image\/$/}
                         update={this.update}
                         title="Upload Image"
                         action={`donation-options/${this.id()}/upload-image/`}
                         help_text="Images must be at least 640px x 480px."/>,
    ]
  }
}
