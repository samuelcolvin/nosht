import React from 'react'
import {Link, withRouter} from 'react-router-dom'
import {FontAwesomeIcon} from '@fortawesome/react-fontawesome'
import {Badge, Button, Table} from 'reactstrap'
import {as_title, format_datetime} from '../utils'
import WithContext from '../utils/context'
import {Dash, Detail} from '../general/Dashboard'
import {MoneyFree, Money} from '../general/Money'
import {InfoModal} from '../general/Modal'
import {ModalForm} from '../forms/Form'

class Tickets_ extends React.Component {
  constructor (props) {
    super(props)
    this.state = {selected: null}
  }

  render () {
    if (!this.props.tickets || !this.props.tickets.length) {
      return (
        <div className="mb-5">
          <h4>Tickets</h4>
          <small>No Tickets bought for this event.</small>
        </div>
      )
    }
    const s = this.state.selected || {}
    const is_admin = this.props.ctx.user.role === 'admin'
    return (
      <div className="mb-5">
        <InfoModal isOpen={!!this.state.selected}
                   title={s.guest_name || <Dash/>}
                   onClose={() => this.setState({selected: null})}>
          <Detail name="ID">
            <code className="text-dark font-weight-bold mt-1">
              {s.ticket_id}
            </code>
          </Detail>
          <Detail name="Guest">
            {(s.guest_name || s.guest_email) ?
              is_admin ?
                <Link to={`/dashboard/users/${s.guest_user_id}/`}>{s.guest_name || s.guest_email}</Link>
                :
                <span>{s.guest_name}</span>
              :
              <span className="text-muted">No name provided</span>
            }
          </Detail>
          <Detail name="Buyer">
            {s.guest_user_id === s.buyer_user_id ?
              <span className="text-muted">this guest</span>
              :
              is_admin ?
                <Link to={`/dashboard/users/${s.buyer_user_id}/`}>
                  {s.buyer_name || s.buyer_email || <span className="text-muted">No name provided</span>}
                </Link>
                :
                <span>{s.buyer_name || s.buyer_email || <span className="text-muted">No name provided</span>}</span>
            }
          </Detail>
          <Detail name="Status">{s.ticket_status && as_title(s.ticket_status)}</Detail>
          <Detail name="Bought At">{format_datetime(s.bought_at)}</Detail>
          <Detail name="Price"><MoneyFree>{s.price}</MoneyFree></Detail>
          <Detail name="Extra Donated"><Money>{s.extra_donated}</Money></Detail>
          <Detail name="Ticket Type">{s.ticket_type_name}</Detail>
          <Detail name="Booking Type">{s.booking_type && as_title(s.booking_type)}</Detail>
          <Detail name="Extra Info">{s.extra_info}</Detail>
        </InfoModal>
        <h4>
          Tickets
          <a href={`/api/events/${this.props.id}/tickets/export.csv`}
              download={true} className="btn btn-secondary btn-sm ml-2">
            <FontAwesomeIcon icon="file-export" className="mr-1"/>
            Export
          </a>
        </h4>
        <Table striped>
          <thead>
            <tr>
              <th>ID</th>
              <th>Guest</th>
              <th>Buyer</th>
              <th>Bought At</th>
              <th>Type</th>
              {is_admin && <th>Cancel Ticket</th>}
            </tr>
          </thead>
          <tbody>
            {this.props.tickets.map((t, i) => (
              <tr key={i}>
                <th scope="row" onClick={() => this.setState({selected: t})} className="cursor-pointer">
                  <code className="text-dark">
                    {t.ticket_id}
                  </code>
                </th>
                <td>{t.guest_name || t.guest_email || <Dash/>}</td>
                <td>{t.buyer_name || t.buyer_email || <Dash/>}</td>
                <td>{format_datetime(t.booked_at)}</td>
                <td>{t.ticket_type_name}</td>
                <td className="align-right">
                  {is_admin && t.ticket_status !== 'cancelled' && (
                    <Button tag={Link} to={`${this.props.uri}tickets/${t.id}/cancel/`} size="sm" color="primary">
                      Cancel
                    </Button>
                  )}
                  {t.ticket_status === 'cancelled' && (
                    <Badge color="danger">Cancelled</Badge>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </Table>
      </div>
    )
  }
}
export const Tickets = WithContext(Tickets_)

export const CancelTicket = WithContext(withRouter(({ctx, update, uri, id, location, tickets}) => {
  if (ctx.user.role !== 'admin') {
    return
  }
  const regex = /tickets\/(\d+)\/cancel\/$/
  const m = location.pathname.match(regex)
  let action = '/'
  let fields = []
  let content = null
  if (m && tickets) {
    const ticket_id = parseInt(m[1])
    action = `/events/${id}/tickets/${ticket_id}/cancel/`
    const ticket = tickets.find(t => t.id === ticket_id)
    if (ticket) {
      const buyer = ticket.buyer_name || ticket.buyer_email || <Dash/>
      const guest = ticket.guest_name || ticket.guest_email || <Dash/>
      if (ticket.price) {
        content = (
          <div>
            Cancelling ticket <b>{ticket.ticket_id}</b> bought for <b>{guest}</b> by <b>{buyer}</b>
            , price <b><MoneyFree>{ticket.price}</MoneyFree></b>.
          </div>
        )
        if (ticket.booking_type === 'buy-tickets') {
          fields = [
            {
              name: 'refund_amount',
              title: 'Amount to refund via Stripe',
              default: 0,
              help_text: 'Amount to refund to the ticket buyer via Stripe, ' +
                'maximum is the full amount paid for the ticket. Leave blank to not refund via Stripe.',
              type: 'number', step: 0.01, min: 1, max: ticket.price,
            }
          ]
        }
      } else{
        content = (
          <div>
            Cancelling ticket <b>{ticket.ticket_id}</b> bought for <b>{guest}</b> by <b>{buyer}</b>.
          </div>
        )
      }
    }
  }

  return (
    <ModalForm
      key="cancel"
      title="Cancel Ticket"
      parent_uri={uri}
      mode="edit"
      success_msg="Ticket Cancelled"
      update={update}
      regex={regex}
      action={action}
      content_before={content}
      fields={fields}
      allow_empty_form={true}
      cancel="Close"
      save="Cancel Ticket"
      save_color="danger"
    />
  )
}))

export const WaitingList = ({waiting_list, user}) => {
  if (!waiting_list || !waiting_list.length) {
    return (
      <div className="mb-5">
        <h4>Waiting List</h4>
        <small>No one on the waiting list for this event.</small>
      </div>
    )
  }
  const is_admin = user.role === 'admin'
  return (
    <div className="mb-5">
      <h4>Waiting List ({waiting_list.length} people)</h4>
      <Table striped>
        <thead>
          <tr>
            <th>Name</th>
            {is_admin && <th>Email</th>}
            <th>Time Added</th>
          </tr>
        </thead>
        <tbody>
          {waiting_list.map((w, i) => (
            <tr key={i}>
              <th scope="row">
                {w.name}
              </th>
              {is_admin && <td>{w.email || <Dash/>}</td>}
              <td>{format_datetime(w.added_ts)}</td>
            </tr>
          ))}
        </tbody>
      </Table>
    </div>
  )
}

export const Donations = ({donations, user, id}) => {
  if (!donations || !donations.length) {
    return (
      <div className="mb-5">
        <h4>Donations</h4>
        <small>No Donations made for this event.</small>
      </div>
    )
  }
  const is_admin = user.role === 'admin'
  return (
    <div>
      <h4>
        Donations
        <a href={`/api/events/${id}/donations/export.csv`}
           download={true}
           className="btn btn-secondary btn-sm ml-2">
          <FontAwesomeIcon icon="file-export" className="mr-1"/>
          Export
        </a>
      </h4>
      <Table striped>
        <thead>
          <tr>
            <th>Donor</th>
            <th>Amount</th>
            <th>Donated At</th>
            <th>Via</th>
          </tr>
        </thead>
        <tbody>
          {donations.map((t, i) => (
            <tr key={i}>
              <th scope="row">
                {is_admin ? <Link to={`/dashboard/users/${t.user_id}/`}>{t.name}</Link> : t.name}
              </th>
              <td><Money>{t.amount}</Money></td>
              <td>{format_datetime(t.timestamp)}</td>
              <td>
                <small>{t.ticket_type_id ? 'donate button' : 'donation option on thanks page'}</small>
              </td>
            </tr>
          ))}
        </tbody>
      </Table>
    </div>
  )
}
