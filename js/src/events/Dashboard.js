import React from 'react'
import {Link} from 'react-router-dom'
import {Alert, Button, Table, Progress as BsProgress} from 'reactstrap'
import {format_event_start, format_event_duration, format_datetime, as_title} from '../utils'
import WithContext from '../utils/context'
import requests from '../utils/requests'
import {
  RenderList, RenderDetails, ImageThumbnail, MiniMap, render,
  MarkdownPreview
} from '../general/Dashboard'
import {Money} from '../general/Money'
import {InfoModal} from '../general/Modal'
import ButtonConfirm from '../general/Confirm'
import {ModalForm} from '../forms/Form'
import SetImage from './SetImage'
import {TicketTypes, TicketTypeTable} from './TicketTypes'
import {Tickets, CancelTicket} from './Tickets'
import {EVENT_FIELDS} from './Create'
import {ModalDropzoneForm} from '../forms/Drop'

export class EventsList extends RenderList {
  constructor (props) {
    super(props)
    this.state.formats = {
      start_ts: {
        title: 'Date',
        render: (v, item) => format_event_start(v, item.duration),
      },
      duration: {
        render: format_event_duration
      },
      status: {render: as_title},
    }
    this.state.buttons = [
      {name: 'Create Event', link: '/create/'},
    ]
  }

  no_items_msg () {
    return (
      <div>
        Thank you for signing up - click "Create Event" to get started.
        You may need to confirm your email address, so please check your emails and spam.
      </div>
    )
  }
}

const EVENT_STATUS_FIELDS = [
  {name: 'status', required: true, type: 'select', choices: [
    {value: 'pending'},
    {value: 'published'},
    {value: 'suspended'},
  ]},
]
const EVENT_EMAIL_UPDATE_FIELDS = [
  {name: 'subject', required: true},
  {name: 'message', required: true, type: 'textarea'},
]

const Progress = WithContext(({event, all_tickets, ticket_types, ctx}) => {
  const tickets = all_tickets && all_tickets.filter(t => t.ticket_status === 'booked')
  const tickets_booked = tickets && (
    tickets
    .reduce((sum, t) => sum + ticket_types.find(tt => tt.id === t.ticket_type_id).slots_used, 0)
  )
  return (
    <div className="mb-5">
      <h4>Progress</h4>
      <div>
        <div className="text-center mb-1">
          <span className="very-large">
            <Money>{tickets && tickets.reduce((sum, t) => sum + t.price + t.extra_donated, 0)}</Money>
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
})

class EventUpdates extends React.Component {
  constructor (props) {
    super(props)
    this.state = {selected: null}
  }

  render () {
    if (!this.props.event_updates || !this.props.event_updates.length) {
      return (
        <div className="mb-5">
          <h4>Event Updates</h4>
          <small>No Updates sent for this event</small>
        </div>
      )
    }
    return (
      <div className="mb-5">
        <InfoModal isOpen={!!this.state.selected}
                   onClose={() => this.setState({selected: null})}
                   title="Event Update"
                   fields={{subject: {}, message: {}}}
                   object={this.state.selected}/>
        <h4>Event Updates</h4>
        <Table striped>
          <thead>
            <tr>
              <th>Time</th>
              <th>Subject</th>
            </tr>
          </thead>
          <tbody>
            {this.props.event_updates.map((a, i) => (
              <tr key={i} onClick={() => this.setState({selected: a})} className="cursor-pointer">
                <td>{format_datetime(a.ts)}</td>
                <td>{as_title(a.subject)}</td>
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
    this.uri = `/dashboard/events/${this.id}/`
    this.can_edit_event = this.can_edit_event.bind(this)
  }

  can_edit_event () {
    const user = this.props.ctx.user
    if (user && user.role === 'host') {
      const event_start = this.state.item && new Date(this.state.item.start_ts)
      if (event_start && event_start > (new Date())) {
        return true
      }
    }
    return user && user.role === 'admin'
  }

  async got_data (data) {
    super.got_data(data)
    let r
    try {
      r = await Promise.all([
        requests.get(`/events/${this.id}/tickets/`),
        requests.get(`/events/${this.id}/ticket-types/`),
        requests.get(`/events/${this.id}/updates/list/`),
      ])
    } catch (error) {
      this.props.ctx.setError(error)
      return
    }
    const user = this.props.ctx.user
    const can_edit = this.can_edit_event()
    this.setState(
      {
        tickets: r[0].tickets,
        ticket_types: r[1].ticket_types,
        event_updates: r[2].event_updates,
        buttons: [
          can_edit && {name: 'Edit', link: this.uri + 'edit/'},
          can_edit && data.status === 'published' && {name: 'Send Update', link: this.uri + 'send-update/'},
          {name: 'View Guest Page', link: data.link, disabled: data.status !== 'published'},
          user && user.role === 'admin' && {
            name: 'Delete Event',
            action: `/events/${this.id}/delete/`,
            btn_color: 'danger',
            confirm_msg: (
              <div>
                <p>
                  Are you sure you want to <b>permanently delete</b> this event?
                  All Tickets and Ticket Types will be deleted. (If you just want to hide the event from
                  guests you can simply mark it as suspended.)
                </p>
                <p className="font-weight-bold">
                  This cannot be undone!
                </p>
              </div>
            ),
            success_msg: 'Event deleted.',
            redirect_to: '/dashboard/events/',
          }
        ],
        formats: {
          start_ts: {
            title: 'Date',
            render: (v, item) => format_event_start(v, item.duration),
          },
          duration: {
            render: format_event_duration
          },
          status: {
            index: 1,
            render: v => (
              <span>
                {as_title(v)}
                {user.status === 'active' && can_edit &&
                  <Button tag={Link} to={this.uri + 'set-status/'} size="sm" className="ml-2">Change Status</Button>
                }
              </span>
            )
          },
          highlight: user && user.role === 'admin' ? {
            render: v => {
              return (
                <span>
                  {render(v)}
                  <ButtonConfirm action={`/events/${this.id}/switch-highlight/`}
                                 modal_title="Switch Status"
                                 btn_text={v ? 'Mark as not highlighted' : 'Mark as highlight'}
                                 done={this.update}
                                 btn_size="sm"
                                 className="ml-2">
                    {v ?
                      'Are you sure you want to remove this event from Highlights?'
                      :
                      'Are you sure you want to mark this event as a Highlights?'}
                  </ButtonConfirm>
                </span>
              )
            }
          } : null,
          cat_id: null,
          link: null,
          host: null,
          host_name: user && user.role === 'admin' ? {
            render: (v, item) => <Link to={`/dashboard/users/${item.host}/`}>{v}</Link>,
            title: 'Host',
          } : null,
          short_description: {index: 2},
          image: {
            index: 3,
            wide: true,
            edit_link: can_edit && this.uri + 'set-image/',
            render: (v, item) => <ImageThumbnail image={v} alt={item.name}/>,
          },
          secondary_image: {
            index: 4,
            wide: true,
            edit_link: can_edit && this.uri + 'set-secondary-image/',
            delete_button: this.state.item.secondary_image && {
              action: `/events/${this.id}/remove-image/secondary/`,
              modal_title: 'Remove Secondary Image',
              content: 'Are you sure you want to remove the secondary Image?',
              done: this.update,
            },
            render: (v, item) => <ImageThumbnail image={v} alt={item.name} image_type="main" width={150}/>,
          },
          long_description: {
            index: 5,
            wide: true,
            render: v => <MarkdownPreview v={v}/>,
          },
          location_lng: null,
          location_name: null,
          location_lat: {
            render: (v, item) => <MiniMap lat={v} lng={item.location_lng} name={item.location_name}/>,
            title: 'Location',
            wide: true,
            index: 6,
          },
        }
      }
    )
    this.props.ctx.setRootState({
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
    const response = []
    if (!event.image) {
      response.push(
        <Alert key="image" color="warning">
          To really make your event stand out you should <Link to={this.uri + 'set-image/'}>add an image</Link>.
        </Alert>
      )
    }
    if (event.status === 'published' && start > now) {
      response.push(
        <div key="link" className="mb-4">
          <div className="mb-2">Event upcoming, share the following link for guests to book tickets:</div>
          <div className="text-center">
            <Alert color="primary" className="d-inline-block font-weight-bold font-monospace">
              {window.location.origin}{event.link}
            </Alert>
          </div>
        </div>
      )
    } else {
      const u = this.props.ctx.user
      if (event.status === 'pending' && start > now) {
        if (u.role === 'host' && u.status !== 'active') {
          response.push(
            <Alert key="pending" color="danger">
              Event pending until you confirm your email address.
            </Alert>
          )
        } else {
          response.push(
            <Alert key="published" color="primary">
              Event not yet published.
            </Alert>
          )
        }
      }
    }
    return response
  }

  extra () {
    if (!this.state.item) {
      return
    }
    const event = Object.assign({}, this.state.item)
    event.location = {name: event.location_name, lat: event.location_lat, lng: event.location_lng}
    event.date = {dt: event.start_ts, dur: event.duration}
    const event_fields = (
      EVENT_FIELDS.filter(f => !['category', 'price'].includes(f.name))
      .filter(f => this.props.ctx.user.role === 'admin' || f.name !== 'external_ticket_url')
    )
    const internal = !event.external_ticket_url
    return [
      internal ?
        <Progress key="progress" event={event} ticket_types={this.state.ticket_types} all_tickets={this.state.tickets}/>
        : null,
      this.state.ticket_types ?
        <TicketTypeTable key="ttt" ticket_types={this.state.ticket_types} uri={this.uri}
                         can_edit={this.can_edit_event()}/>
        : null,
      internal ? <Tickets key="tickets" tickets={this.state.tickets} event={event} id={this.id} uri={this.uri}/> : null,
      <EventUpdates key="event-updates" event_updates={this.state.event_updates}/>,
      <ModalForm key="edit"
                 title="Edit Event"
                 parent_uri={this.uri}
                 mode="edit"
                 success_msg="Event updated"
                 initial={event}
                 update={this.update}
                 action={`/events/${this.id}/`}
                 fields={event_fields}/>,
      <ModalForm key="set-status"
                 title="Set Event Status"
                 parent_uri={this.uri}
                 regex={/set-status\/$/}
                 mode="edit"
                 success_msg='Event Updated'
                 initial={{status: event.status}}
                 update={this.update}
                 action={`/events/${this.id}/set-status/`}
                 fields={EVENT_STATUS_FIELDS}/>,
      <ModalForm key="send-update"
                 title="Send Event update to Guests"
                 parent_uri={this.uri}
                 regex={/send-update\/$/}
                 mode="edit"
                 success_msg='Event Update Sent'
                 initial={{status: event.status}}
                 update={this.update}
                 action={`/events/${this.id}/updates/send/`}
                 fields={EVENT_EMAIL_UPDATE_FIELDS}/>,
      <SetImage key="set-image"
                event={event}
                parent_uri={this.uri}
                regex={/set-image\/$/}
                update={this.update}
                title="Upload Background Image"/>,
      <ModalDropzoneForm key="set-secondary-image"
                         multiple={false}
                         parent_uri={this.uri}
                         regex={/set-secondary-image\/$/}
                         update={this.update}
                         title="Upload Secondary Image"
                         help_text="Image should at least 300px x 300px, it will be displayed square."
                         action={`/events/${this.id}/set-image/secondary/`}/>,
      this.props.ctx.user.role === 'admin' ?
        <CancelTicket key="cancel" tickets={this.state.tickets} update={this.update} id={this.id} uri={this.uri}/>
        : null,
      this.state.ticket_types ?
        <TicketTypes key="edit-ticket-types"
                     event={event}
                     ticket_types={this.state.ticket_types}
                     regex={/ticket-types\/$/}
                     update={this.update}
                     title="Customise Ticket Types"/>
        : null,
    ]
  }
}
