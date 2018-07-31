import React from 'react'
import {Link} from 'react-router-dom'
import {Button, Modal, ModalHeader, ModalBody, ModalFooter, Table} from 'reactstrap'
import {format_event_start, format_event_duration, format_datetime, format_money} from '../utils'
import {Dash, Detail, RenderList, RenderDetails} from '../general/Dashboard'
import {ModalForm} from '../forms/Form'

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
  {name: 'price', type: 'number', step: 0.01, min: 1, max: 1000},
  {name: 'long_description', title: 'Description', type: 'textarea', required: true},
]
const EVENT_STATUS_FIELDS = [
  {name: 'status', required: true, type: 'select', choices: [
    {value: 'pending'},
    {value: 'published'},
    {value: 'suspended'},
  ]},
]

class Tickets extends React.Component {
  constructor (props) {
    super(props)
    this.state = {selected: null}
  }

  render () {
    if (!this.props.tickets || !this.props.tickets.length) {
      return <small>No Tickets bought for this event</small>
    }
    const close = () => this.setState({selected: null})
    const selected = this.state.selected || {}
    return (
      <div>
        <Modal isOpen={!!this.state.selected} toggle={close} size="lg">
          <ModalHeader toggle={close}>{selected.user_name || <Dash/>}</ModalHeader>
          <ModalBody>
            <Detail name="Guest">
              {selected.user_id ?
                <Link to={`/dashboard/users/${selected.user_id}/`}>{selected.user_name }</Link>
                :
                <span className="text-muted">Guest of "{selected.buyer_name}", no name provided</span>
              }
            </Detail>
            <Detail name="Buyer">
              {selected.user_id === selected.buyer_id ?
                <span className="text-muted">this guest</span>
                :
                <Link to={`/dashboard/users/${selected.buyer_id}/`}>{selected.buyer_name}</Link>
              }
            </Detail>
            <Detail name="Bought At">{format_datetime(selected.bought_at)}</Detail>
            <Detail name="Extra Info">{selected.extra && selected.extra.extra_info}</Detail>
          </ModalBody>
          <ModalFooter>
            <Button color="secondary" onClick={close}>Close</Button>
          </ModalFooter>
        </Modal>
        <h4>Tickets</h4>
        <Table striped>
          <thead>
            <tr>
              <th>#</th>
              <th>Guest</th>
              <th>Buyer</th>
              <th>Bought at</th>
              <th>Extra Info</th>
            </tr>
          </thead>
          <tbody>
            {this.props.tickets.map((t, i) => (
              <tr key={i} onClick={() => this.setState({selected: t})} className="cursor-pointer">
                <th scope="row">{i + 1}</th>
                <td>{t.user_name || <Dash/>}</td>
                <td>{t.buyer_name}</td>
                <td>{format_datetime(t.bought_at)}</td>
                <td className="text-right">
                  {t.extra && t.extra.extra_info.length > 30 ?
                    <small>{t.extra.extra_info}</small>
                    :
                    <span>{t.extra.extra_info}</span>
                  }
                </td>
              </tr>
            ))}
          </tbody>
        </Table>
      </div>
    )
  }
}

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
      price: {
        render: (v, item) => v && format_money(item.currency, v)
      },
      currency: null,
      slug: null,
      cat_slug: null,
      location_lat: null,
      location_lng: null,
      long_description: null,
    }
    this.uri = `/dashboard/events/${this.id}/`
  }

  async got_data (data) {
    super.got_data(data)
    let r
    try {
      r = await this.requests.get(`/events/${this.id}/tickets/`)
    } catch (error) {
      this.props.setRootState({error})
      return
    }
    this.setState(
      {
        tickets: r.tickets,
        buttons: [
          {name: 'Edit', link: this.uri + 'edit/'},
          this.props.user.role === 'admin' && {name: 'Set Status', link: this.uri + 'set-status/'},
          {name: 'View Guest Page', link: `/${data.cat_slug}/${data.slug}/`, disabled: data.status !== 'published'}
        ]
      }
    )
  }

  extra () {
    if (!this.state.item) {
      return
    }
    const item = Object.assign({}, this.state.item)
    item.location = {name: item.location_name, lat: item.location_lat, lng: item.location_lng}
    item.date = {dt: item.start_ts, dur: item.duration}
    return [
      <Tickets key="1" tickets={this.state.tickets}/>,
      <ModalForm {...this.props}
                 title="Edit Event"
                 request_method="put"
                 key="2"
                 parent_uri={this.uri}
                 mode="edit"
                 success_msg='Event updated'
                 initial={item}
                 update={this.update}
                 action={`/events/${this.id}/`}
                 fields={EVENT_FIELDS}/>,
      <ModalForm {...this.props}
                 key="3"
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
