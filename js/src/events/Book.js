import React from 'react'
import AsModal from '../general/Modal'
import BookingLogin from './BookingLogin'
import BookingTickets from './BookingTickets'
import BookingStripe from './BookingStripe'

class BookWrapper extends React.Component {
  constructor (props) {
    super(props)
    this.state = {
      ticket_count: 1,
      reservation_error: null,
      got_booking_info: false,
      booking_info: null,
      reservation: null,
      billing_name: null,
      ticket_type: null
    }
  }

  async componentDidUpdate () {
    if (this.state.got_booking_info || !this.props.user) {
      return
    }
    this.setState({got_booking_info: true})
    let r
    try {
      r = await this.props.requests.get(`events/${this.props.event.id}/booking-info/`)
    } catch (error) {
      this.props.setRootState({error})
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
      }))

    tickets[0].first_name = tickets[0].first_name || this.props.user.first_name
    tickets[0].last_name = tickets[0].last_name || this.props.user.last_name
    tickets[0].email = tickets[0].email || this.props.user.email

    this.setState({billing_name:
      tickets[0].email === this.props.user.email ?
      `${tickets[0].first_name || ''} ${tickets[0].last_name || ''}`.trim() : ''
    })
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
      r = await this.props.requests.post(`events/${this.props.event.id}/reserve/`,
          {tickets, ticket_type}, {expected_statuses: [200, 470]})
    } catch (error) {
      this.props.setRootState({error})
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
    }
  }

  render () {
    if (!this.props.user) {
      return <BookingLogin
          {...this.props}
          clear_reservation={() => this.setState({reservation: null})}
          finished={this.props.finished}/>
    } else if (!this.state.reservation) {
      return <BookingTickets
          {...this.props}
          state={this.state}
          set_ticket_state={this.set_ticket_state.bind(this)}
          set_ticket_type={this.set_ticket_type.bind(this)}
          reserve={this.reserve.bind(this)}
          change_ticket_count={this.change_ticket_count.bind(this)}/>
    } else {
      return <BookingStripe {...this.props}
          reservation={this.state.reservation}
          billing_name={this.state.billing_name}/>
    }
  }
}
const ModalBookForm = AsModal(BookWrapper)

const BookEvent = props => (
  <ModalBookForm {...props}
                 title={`Book Tickets for ${props.event.name}`}
                 regex={/book\/$/}/>
)
export default BookEvent
