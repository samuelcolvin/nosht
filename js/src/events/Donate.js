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
      ticket_types: [],
      selected_ticket_type: null,
      allow_marketing: false,
      donation_amount: null,
      amount_confirmed: false,
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
    } else if (!this.state.amount_confirmed) {
      return (
        <DonationForm
          event={this.props.event}
          finished={this.finished}
          state={this.state}
          setDonatingState={s => this.setState(s)}
        />
      )
    } else {
      return (
        <BookingStripe
          event={this.props.event}
          finished={this.finished}
          register_toggle_handler={this.props.register_toggle_handler}
          reservation={{total_price: this.state.donation_amount, donation: true}}
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
