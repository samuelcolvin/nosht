import React from 'react'
import AsModal from '../forms/Modal'
import {Loading} from '../utils/Errors'
import {BookingLogin, TicketForm, Stripe} from '../utils/Booking'
import {load_script} from '../../utils'

class BookWrapper extends React.Component {
  constructor (props) {
    super(props)
    this.state = {
      ticket_count: 1,
      got_booking_info: false,
      booking_info: null,
      reservation: null,
      stripe_loaded: false,
      stripe: null
    }
    this.get_user_name = () => (
      this.props.user.name && this.props.user.name !== this.props.user.email ? this.props.user.name : null
    )
  }

  async componentDidMount () {
    await load_script('https://js.stripe.com/v3/')
    this.setState({stripe_loaded: true})
  }

  async componentDidUpdate () {
    if (this.state.got_booking_info || !this.props.user || !this.state.stripe_loaded) {
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
    const stripe = window.Stripe(r.event.stripe_key)
    delete r.event.stripe_key
    this.setState({booking_info: r.event, stripe})
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
    console.log(r)
    this.setState({reservation: r})
  }

  async take_payment (e, stripe) {
    e.preventDefault()
    const payload = await stripe.createToken({name: this.get_user_name()})
    console.log('payload:', payload)
  }

  render () {
    if (!this.props.user) {
      return <BookingLogin
          setRootState={this.props.setRootState}
          requests={this.props.requests}
          finished={this.props.finished}/>
    } else if (!this.state.reservation) {
      return (
        <TicketForm
            user={this.props.user}
            finished={this.props.finished}
            state={this.state}
            logout={this.logout.bind(this)}
            set_ticket_state={this.set_ticket_state.bind(this)}
            reserve={this.reserve.bind(this)}
            change_ticket_count={this.change_ticket_count.bind(this)}/>
      )
    } else if (!this.state.stripe) {
      return <Loading/>
    } else {
      return (
        <Stripe reservation={this.state.reservation}
                stripe={this.state.stripe}
                take_payment={this.take_payment.bind(this)}/>
      )
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
