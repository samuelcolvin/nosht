import React from 'react'
import {Link} from 'react-router-dom'
import {Alert, Button, Modal, ModalHeader, ModalBody, ModalFooter, Table, Progress as BsProgress} from 'reactstrap'
import {format_event_start, format_event_duration, format_datetime, format_money_free, format_money} from '../utils'
import {Dash, Detail, RenderList, RenderDetails, ImageThumbnail, MiniMap, render_bool} from '../general/Dashboard'
import {ModalForm} from '../forms/Form'
import SetImage from './SetImage'
import TicketTypes from './TicketTypes'
import {EVENT_FIELDS} from './Create'

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

const EVENT_STATUS_FIELDS = [
  {name: 'status', required: true, type: 'select', choices: [
    {value: 'pending'},
    {value: 'published'},
    {value: 'suspended'},
  ]},
]

const Progress = ({event, tickets, ticket_types}) => {
  const tickets_booked = tickets && (
    tickets.reduce((sum, t) => sum + ticket_types.find(tt => tt.id === t.ticket_type_id).slots_used, 0)
  )
  return (
    <div className="mb-5">
      <h4>Progress</h4>
      <div>
        <div className="text-center mb-1">
          <span className="very-large">
            {format_money(event.currency, tickets && tickets.reduce((sum, t) => sum + t.price, 0))}
          </span>
          &nbsp;collected so far
        </div>
        {tickets_booked !== null &&
          event.ticket_limit ?
          <div>
            <div className="text-center mb-1">
              <span className="very-large">{tickets_booked}</span>
              &nbsp;ticket{tickets_booked === 1 ? '' : 's'} booked of {event.ticket_limit}
            </div>
            <BsProgress value={tickets_booked / event.ticket_limit * 100}/>
          </div>
          :
          <div className="text-center mb-1">
            <span className="very-large">{tickets_booked}</span> tickets booked
          </div>
        }
      </div>
    </div>
  )
}

const TicketTypeTable = ({ticket_types, currency}) => (
  <div className="mb-5">
    <h4>Ticket Types</h4>
    <Table striped>
      <thead>
        <tr>
          <th>Name</th>
          <th>Price</th>
          <th>Group Size</th>
          <th>Active</th>
        </tr>
      </thead>
      <tbody>
        {ticket_types.map(tt => (
          <tr key={tt.id}>
            <td>{tt.name}</td>
            <td>{format_money_free(currency, tt.price)}</td>
            <td>{tt.slots_used}</td>
            <td>{render_bool(tt.active)}</td>
          </tr>
        ))}
      </tbody>
    </Table>
  </div>
)

class Tickets extends React.Component {
  constructor (props) {
    super(props)
    this.state = {selected: null}
  }

  render () {
    if (!this.props.tickets || !this.props.tickets.length) {
      return (
        <div>
          <h4>Tickets</h4>
          <small>No Tickets bought for this event</small>
        </div>
      )
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
            <Detail name="Price">{format_money_free(this.props.event.currency, selected.price)}</Detail>
            <Detail name="Ticket Type">{selected.ticket_type_name}</Detail>
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
              <th>Bought At</th>
              <th>Type</th>
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
                <td>{t.ticket_type_name}</td>
                <td className="text-right">
                  {t.extra && t.extra.extra_info.length > 30 ?
                    <small>{t.extra.extra_info}</small>
                    :
                    <span>{t.extra && t.extra.extra_info}</span>
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
      currency: null,
      slug: null,
      cat_id: null,
      cat_slug: null,
      ticket_limit: null,
      long_description: null,
      image: {
        render: (v, item) => <ImageThumbnail image={v} alt={item.name}/>,
        index: 1
      },
      location_lng: null,
      location_name: null,
      location_lat: {
        render: (v, item) => <MiniMap lat={v} lng={item.location_lng}m name={item.location_name}/>,
        title: 'Location',
        index: 2,
      },
    }
    this.uri = `/dashboard/events/${this.id}/`
  }

  async got_data (data) {
    super.got_data(data)
    let r
    try {
      r = await Promise.all([
        this.requests.get(`/events/${this.id}/tickets/`),
        this.requests.get(`/events/${this.id}/ticket-types/`),
      ])
    } catch (error) {
      this.props.setRootState({error})
      return
    }
    this.setState(
      {
        tickets: r[0].tickets,
        ticket_types: r[1].ticket_types,
        buttons: [
          {name: 'Edit', link: this.uri + 'edit/'},
          {name: 'Set Image', link: this.uri + 'set-image/'},
          {name: 'Custom Ticket Types', link: this.uri + 'ticket-types/'},
          this.props.user.status === 'active' && {name: 'Set Status', link: this.uri + 'set-status/'},
          {name: 'View Guest Page', link: `/${data.cat_slug}/${data.slug}/`, disabled: data.status !== 'published'},
        ]
      }
    )
    this.props.setRootState({
      page_title: this.state.item.name,
      background: this.state.item.image,
    })
  }

  pre () {
    const event = this.state.item
    if (!event) {
      return
    }
    const start = new Date(event.start_ts)
    const now = new Date()
    if (event.status === 'published' && start > now) {
      return (
        <Alert color="primary">
          Event upcoming, share the following link for guests to book tickets:
          <code className="d-block text-dark font-weight-bold mt-1">
            {window.location.origin}/{event.cat_slug}/{event.slug}/
          </code>
        </Alert>
      )
    }
    const u = this.props.user
    if (event.status === 'pending' && start > now) {
      if (u.role === 'host' && u.status !== 'active') {
        return (
          <Alert color="danger">
            Event pending until you confirm your email address.
          </Alert>
        )
      } else {
        return (
          <Alert color="primary">
            Event not yet published.
          </Alert>
        )
      }
    }
  }

  extra () {
    if (!this.state.item) {
      return
    }
    const event = Object.assign({}, this.state.item)
    event.location = {name: event.location_name, lat: event.location_lat, lng: event.location_lng}
    event.date = {dt: event.start_ts, dur: event.duration}
    const event_fields = EVENT_FIELDS.filter(f => !['category', 'price'].includes(f.name))
    return [
      <Progress key="progress" event={event} ticket_types={this.state.ticket_types} tickets={this.state.tickets}/>,
      this.state.ticket_types ?
        <TicketTypeTable key="ttt" currency={event.currency} ticket_types={this.state.ticket_types}/>
        : null,
      <Tickets key="tickets" tickets={this.state.tickets} event={event}/>,
      <ModalForm {...this.props}
                 key="edit"
                 title="Edit Event"
                 request_method="put"
                 parent_uri={this.uri}
                 mode="edit"
                 success_msg='Event updated'
                 initial={event}
                 update={this.update}
                 action={`/events/${this.id}/`}
                 fields={event_fields}/>,
      <ModalForm {...this.props}
                 key="set-status"
                 title="Set Event Status"
                 parent_uri={this.uri}
                 regex={/set-status\/$/}
                 mode="edit"
                 success_msg='Event updated'
                 initial={{status: event.status}}
                 update={this.update}
                 action={`/events/${this.id}/set-status/`}
                 fields={EVENT_STATUS_FIELDS}/>,
      <SetImage {...this.props}
                key="set-image"
                event={event}
                parent_uri={this.uri}
                regex={/set-image\/$/}
                update={this.update}
                title="Upload Background Image"/>,
      this.state.ticket_types ?
        <TicketTypes {...this.props}
                     key="edit-ticket-types"
                     event={event}
                     ticket_types={this.state.ticket_types}
                     regex={/ticket-types\/$/}
                     update={this.update}
                     title="Customise Ticket Types"/>
        : null,
    ]
  }
}
