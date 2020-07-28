import React from 'react'
import {
  Col,
  Form as BootstrapForm,
  ModalBody,
  Row,
} from 'reactstrap'
import requests from '../utils/requests'
import {ModalFooter} from '../general/Modal'
import {Money, MoneyFree} from '../general/Money'
import Markdown from '../general/Markdown'
import Input from '../forms/Input'
import {User} from './BookingTickets'
import ReactGA from 'react-ga'
import {StripeContext, StripeForm, stripe_pay} from './Stripe'

export const PricingList = ({items, className}) => (
  <div className={className}>
    {items.filter(item => item).map((item, i) => (
      <div key={i} className={`d-flex justify-content-between ${item.className || ''}`}>
        <div>{item.name}:</div>
        <div className="font-weight-bold">{item.value}</div>
      </div>
    ))}
  </div>
)

class StripeBookingForm extends React.Component {
  constructor (props) {
    super(props)
    this.state = {
      time_left: 0,
      submitting: false,
      cancelled: false,
      terms_and_conditions: false,
      buy_offline: false,
      payment: {}
    }
    this.update_timer = this.update_timer.bind(this)
    this.payment_form = this.payment_form.bind(this)
    this.take_payment = this.take_payment.bind(this)
    this.book_free = this.book_free.bind(this)
    this.stripe_pay = stripe_pay.bind(this)
  }

  update_timer () {
    const t = this.props.reservation.timeout - (new Date()).getTime() / 1000
    this.setState({time_left: Math.floor(t / 60)})
  }

  componentDidMount () {
    this.update_timer()
    this.clear = setInterval(this.update_timer, 500)
    this.props.register_toggle_handler(this.cancel_reservation.bind(this))
  }

  componentWillUnmount () {
    clearInterval(this.clear)
  }

  async cancel_reservation () {
    if (!this.state.submitting && !this.state.cancelled) {
      this.setState({cancelled: true})
      try {
        await requests.post(`events/cancel-reservation/`, {
          booking_token: this.props.reservation.booking_token,
        })
      } catch (error) {
        this.props.ctx.setError(error)
      }
    }
  }

  submit (e) {
    e.preventDefault()
    this.setState({submitting: true})
    if (this.state.buy_offline) {
      this.book_free('buy-tickets-offline')
    } else if (this.props.reservation.total_price) {
      this.take_payment()
    } else {
      this.book_free('book-free-tickets')
    }
  }

  async take_payment () {
    if (this.state.submitting) {
      return
    }
    this.setState({submitting: true})
    const ok = await this.stripe_pay(this.props.reservation.client_secret)
    if (ok) {
      this.props.ctx.setMessage({icon: ['fas', 'check-circle'], message: 'Payment successful, check your email'})
      ReactGA.event({
        category: 'ticket-booking', action: 'ticket-booking-confirm', label: 'pay',
        value: this.props.reservation.total_price
      })
      this.props.finished(true)
    }
  }

  async book_free (book_action) {
    this.setState({submitting: true})

    try {
      await requests.post('events/book-free/',
          {booking_token: this.props.reservation.booking_token, book_action})
    } catch (error) {
      this.props.ctx.setError(error)
      return
    }

    this.props.ctx.setMessage({icon: ['fas', 'check-circle'], message: 'Booking successful, check your email'})
    ReactGA.event({category: 'ticket-booking', action: 'ticket-booking-confirm', label: book_action})
    this.props.finished(true)
  }

  payment_form (expired) {
    let tncs_field = null
    if (this.props.event.terms_and_conditions_message) {
      const f = {
        name: 'tncs',
        title: <Markdown content={this.props.event.terms_and_conditions_message}/>,
        type: 'bool',
        required: true,
      }
      tncs_field = (
        <Input
          field={f}
          value={this.state.terms_and_conditions}
          disabled={this.state.submitting}
          onChange={v => this.setState({terms_and_conditions: v})}
        />
      )
    }
    if (expired) {
      return <h4 className="has-error">Reservation expired</h4>
    } else if (!this.props.reservation.total_price || this.state.buy_offline) {
      return tncs_field && <div style={{height: 40}}>{this.state.submitting ? null : tncs_field}</div>
    } else {
      return (
        <div>
          <StripeForm submitting={this.state.submitting} payment_state={this.state.payment}
                      setPaymentState={payment => this.setState({payment})}/>
          {tncs_field}
        </div>
      )
    }
  }

  render () {
    const res = this.props.reservation
    const items = [
      {
        name: 'Reservation expires in',
        value: `${this.state.time_left} minutes`,
        className: this.state.time_left < 3 ? 'mb-4 has-error h4' : 'mb-4'
      },
      {name: 'Tickets', value: res.ticket_count},
      {name: 'Ticket Price', value: <MoneyFree>{res.item_price}</MoneyFree>},
      res.item_price && {name: 'Extra donated to cover Costs', value: <Money>{res.extra_donated}</Money>},
      {name: 'Total Price', value: <MoneyFree>{res.total_price}</MoneyFree>},
    ]
    const expired = this.state.time_left < 1
    if (expired) {
      items.splice(0, 1)
    }

    let buy_offline_field = null
    if (res.total_price &&
        (this.props.ctx.user.role === 'admin' || this.props.ctx.user.id === this.props.event.host_id)) {
      const f = {
        name: 'buy_offline',
        type: 'bool',
        help_text: "Skip Payment here, useful to reserve tickets or book tickets for guests who've paid another way."
      }
      buy_offline_field = (
        <Input
          field={f}
          value={this.state.buy_offline}
          disabled={this.state.submitting}
          onChange={v => this.setState({buy_offline: v})}
        />
      )
    }
    const confirm_disabled = (
      (!this.state.terms_and_conditions && this.props.event.terms_and_conditions_message) ||
      expired ||
      this.state.submitting ||
      (res.total_price &&
        !this.state.payment.complete &&
        !this.state.payment.payment_method_id &&
        !this.state.buy_offline)
    )
    return (
      <BootstrapForm className="pad-less" onSubmit={this.submit.bind(this)}>
        <ModalBody>
          <User {...this.props}/>
          <Row className="justify-content-center">
            <Col lg="8">
              <PricingList className="mb-2" items={items}/>
              {buy_offline_field}
              <hr/>
              {this.payment_form(expired)}
            </Col>
          </Row>
        </ModalBody>
        <ModalFooter finished={this.props.finished}
                     label={res.total_price ? 'Buy Now' : 'Confirm'}
                     cancel_disabled={this.state.submitting}
                     disabled={Boolean(confirm_disabled)}/>
      </BootstrapForm>
    )
  }
}
export default StripeContext(StripeBookingForm)
