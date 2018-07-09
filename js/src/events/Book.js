import React from 'react'
import AsModal from '../general/Modal'
import {load_script} from '../utils'
import BookingLogin from './BookingLogin'
import BookingTickets from './BookingTickets'
import BookingStripe from './BookingStripe'

class BookWrapper extends React.Component {
  constructor (props) {
    super(props)
    this.state = {
      ticket_count: 1,
      got_booking_info: false,
      booking_info: null,
      reservation: null,
      stripe: null
    }
    this.get_user_name = () => (
      this.props.user.name && this.props.user.name !== this.props.user.email ? this.props.user.name : null
    )
  }

  async componentDidMount () {
    await load_script('https://js.stripe.com/v3/')
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
    this.setState({booking_info: r.event})
  }

  async logout () {
    try {
      await this.props.requests.post('logout/')
    } catch (error) {
      this.props.setRootState({error})
      return
    }
    this.props.setRootState({user: null})
  }

  set_ticket_state (key, t_key, value) {
    const t = Object.assign({}, this.state[key] || {})
    t[t_key] = value
    this.setState({[key]: t})
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
        name: t.name || null,
        email: t.email || null,
        dietary_req: t.dietary_req || null,
        extra_info: t.extra_info || null,
      }))

    tickets[0].name = tickets[0].name || this.get_user_name()
    tickets[0].email = tickets[0].email || this.props.user.email
    let r
    try {
      r = await this.props.requests.post(`events/${this.props.event.id}/reserve/`, {tickets})
    } catch (error) {
      this.props.setRootState({error})
      return
    }
    delete r._response_status
    this.setState({reservation: r})
  }

  render () {
    if (!this.props.user) {
      return <BookingLogin
          setRootState={this.props.setRootState}
          requests={this.props.requests}
          finished={this.props.finished}/>

    } else if (!this.state.reservation) {
      return <BookingTickets
          user={this.props.user}
          finished={this.props.finished}
          state={this.state}
          logout={this.logout.bind(this)}
          set_ticket_state={this.set_ticket_state.bind(this)}
          reserve={this.reserve.bind(this)}
          change_ticket_count={this.change_ticket_count.bind(this)}/>

    } else {
      return <BookingStripe
          reservation={this.state.reservation}
          event={this.props.event}
          user_name={this.get_user_name()}/>

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
