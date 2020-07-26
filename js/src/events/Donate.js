import React from 'react'
import ReactGA from 'react-ga'
import requests from '../utils/requests'
import AsModal from '../general/Modal'
import BookingLogin from './BookingLogin'
import DonationForm from './DonateSelect'
import BookingStripe from './BookingStripe'

class DonateForm extends React.Component {
  constructor (props) {
    super(props)
    this.state = {
      got_info: false,
      reservation_error: false,
      ticket_types: [],
      selected_ticket_type: null,
      allow_marketing: false,
      donation_amount: null,
      reservation: null,
    }
    this.finished = this.finished.bind(this)
  }

  async componentDidUpdate () {
    if (this.state.got_info || !this.props.ctx.user) {
      return
    }
    this.setState({got_info: true})
    let r
    const p = this.props.params
    try {
      r = await requests.get(`events/${p.category}/${p.event}/${p.sig ? p.sig + '/': ''}donating-info/`)
    } catch (error) {
      this.props.ctx.setError(error)
      return
    }
    delete r._response_status
    this.setState({ticket_types: r.ticket_types})
  }

  async reserve (e) {
    e.preventDefault()
    if (!this.state.selected_ticket_type) {
      return
    }
    this.setState({submitting_reservation: true})
    const data = {
      tickets: [
        {
          t: true,
          first_name: this.props.ctx.user.first_name,
          last_name: this.props.ctx.user.last_name,
          email: this.props.ctx.user.email,
          extra_info: null,
          cover_costs: null,
          allow_marketing: this.state.allow_marketing,
        }
      ],
      ticket_type: this.state.selected_ticket_type,
      donation_amount: this.state.donation_amount,
    }


    let r
    try {
      r = await requests.post(`events/${this.props.event.id}/reserve/`, data)
    } catch (error) {
      this.props.ctx.setError(error)
      return
    }
    delete r._response_status
    this.setState({reservation: r, submitting_reservation: false})
    ReactGA.event({category: 'donation', action: 'ticket-donation-reserve', value: this.state.donation_amount})
  }

  finished (complete) {
    if (complete) {
      this.props.set_complete()
    }
    this.props.finished()
  }

  render () {
    if (!this.props.ctx.user) {
      return (
        <BookingLogin
          booking_trust_message={this.props.event.booking_trust_message}
          finished={this.finished}
          success_label="Book"
          setBookingState={s => this.setState(s)}
        />
      )
    } else if (!this.state.reservation) {
      return (
        <DonationForm
          event={this.props.event}
          finished={this.finished}
          state={this.state}
          setDonatingState={s => this.setState(s)}
          reserve={this.reserve.bind(this)}
        />
      )
    } else {
      return (
        <BookingStripe
          event={this.props.event}
          finished={this.finished}
          register_toggle_handler={this.props.register_toggle_handler}
          reservation={this.state.reservation}
        />
      )
    }
  }
}
const ModalDonateForm = AsModal(DonateForm)

const DonateToEvent = props => (
  <ModalDonateForm {...props} title={`Donate to ${props.event.name}`} regex={/donate\/$/}/>
)
export default DonateToEvent
