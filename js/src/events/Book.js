import React from 'react'
import ReactGA from 'react-ga'
import {set_tmp_name} from '../utils'
import requests from '../utils/requests'
import AsModal from '../general/Modal'
import BookingLogin from './BookingLogin'
import BookingTickets from './BookingTickets'
import BookingStripe from './BookingStripe'

class BookForm extends React.Component {
  constructor (props) {
    super(props)
    this.state = {
      ticket_count: 1,
      reservation_error: null,
      got_booking_info: false,
      booking_info: null,
      reservation: null,
      ticket_type: null
    }
    this.finished = this.finished.bind(this)
  }

  async componentDidUpdate () {
    if (this.state.got_booking_info || !this.props.ctx.user) {
      return
    }
    this.setState({got_booking_info: true})
    let r
    const p = this.props.params
    try {
      r = await requests.get(`events/${p.category}/${p.event}/${p.sig ? p.sig + '/': ''}booking-info/`)
    } catch (error) {
      this.props.ctx.setError(error)
      return
    }
    delete r._response_status
    this.setState({booking_info: r})
  }

  set_ticket_state (key, t_key, value) {
    const t = Object.assign({}, this.state[key] || {}, {[t_key]: value})
    this.setState({[key]: t})
  }

  set_ticket_type (ticket_type) {
    this.setState({ticket_type})
  }

  change_ticket_count (change) {
    this.setState({ticket_count: this.state.ticket_count + change})
  }

  async reserve (e) {
    e.preventDefault()
    const tickets = [...Array(this.state.ticket_count).keys()]
      .map(index => this.state[`ticket_${index}`] || {})
      .map(t => ({
        t: true,
        first_name: t.first_name || null,
        last_name: t.last_name || null,
        email: t.email || null,
        extra_info: t.extra_info || null,
        cover_costs: t.cover_costs || null,
      }))

    tickets[0].first_name = tickets[0].first_name || this.props.ctx.user.first_name
    tickets[0].last_name = tickets[0].last_name || this.props.ctx.user.last_name
    tickets[0].email = tickets[0].email || this.props.ctx.user.email

    const u = this.props.ctx.user
    if (tickets[0].email === u.email && u.first_name === null  && u.last_name === null) {
      set_tmp_name(tickets[0].first_name, tickets[0].last_name)
      this.props.ctx.setUser(u)
    }
    let ticket_type = this.state.booking_info.ticket_types[0].id
    if (this.state.booking_info.ticket_types.length > 1) {
      if (this.state.ticket_type) {
        ticket_type = this.state.ticket_type
      } else {
        this.setState({reservation_error: 'No ticket type selected'})
        return
      }
    }

    let r
    try {
      r = await requests.post(`events/${this.props.event.id}/reserve/`,
          {tickets, ticket_type}, {expected_statuses: [200, 470]})
    } catch (error) {
      this.props.ctx.setError(error)
      return
    }
    if (r._response_status === 470) {
      this.setState({reservation_error: r.message})
      if (r.tickets_remaining) {
        const booking_info = Object.assign({}, this.state.booking_info, {tickets_remaining: r.tickets_remaining})
        this.setState({booking_info})
      }
    } else {
      delete r._response_status
      this.setState({reservation: r})
      ReactGA.event({category: 'ticket-booking', action: 'ticket-booking-reserve', value: tickets.length})
    }
  }

  finished (complete) {
    if (complete) {
      this.props.set_complete()
      this.props.finished({pk: 'donate'})
    } else {
      this.props.finished()
    }
  }

  render () {
    if (!this.props.ctx.user) {
      return <BookingLogin
          event={this.props.event}
          finished={this.finished}
          clear_reservation={() => this.setState({reservation: null})}/>
    } else if (!this.state.reservation) {
      return <BookingTickets
          event={this.props.event}
          finished={this.finished}
          state={this.state}
          set_ticket_state={this.set_ticket_state.bind(this)}
          set_ticket_type={this.set_ticket_type.bind(this)}
          reserve={this.reserve.bind(this)}
          change_ticket_count={this.change_ticket_count.bind(this)}/>
    } else {
      return <BookingStripe
          event={this.props.event}
          finished={this.finished}
          register_toggle_handler={this.props.register_toggle_handler}
          reservation={this.state.reservation}/>
    }
  }
}
const ModalBookForm = AsModal(BookForm)

const BookEvent = props => (
  <ModalBookForm {...props}
                 title={`Book Tickets for ${props.event.name}`}
                 regex={/book\/$/}/>
)
export default BookEvent
