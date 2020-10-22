import React from 'react'
import ReactGA from 'react-ga'
import requests from '../utils/requests'
import AsModal from '../general/Modal'
import {PaymentForm} from '../donations/PaymentForm'
import BookingLogin from './BookingLogin'
import DonationForm from './DonateSelect'

class DonateForm extends React.Component {
  constructor (props) {
    super(props)
    this.state = {
      got_info: false,
      ticket_types: [],
      selected_ticket_type: null,
      allow_marketing: false,
      donation_amount: null,
      payment_config: null,
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

  async proceed (e) {
    e.preventDefault()
    if (!this.state.selected_ticket_type) {
      return
    }

    this.setState({payment_config: {
      amount: this.state.donation_amount,
      ticket_type: this.state.selected_ticket_type
    }})

    ReactGA.event({category: 'donation', action: 'ticket-donation-prepare', value: this.state.donation_amount})
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
          message={this.props.event.booking_trust_message}
          finished={this.finished}
          success_label="Continue"
          setBookingState={s => this.setState(s)}
        />
      )
    } else if (!this.state.payment_config) {
      return (
        <DonationForm
          event={this.props.event}
          finished={this.finished}
          state={this.state}
          setDonatingState={s => this.setState(s)}
          submit={this.proceed.bind(this)}
        />
      )
    } else {
      return (
        <PaymentForm
          event={this.props.event}
          finished={this.finished}
          register_toggle_handler={this.props.register_toggle_handler}
          config={this.state.payment_config}
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
