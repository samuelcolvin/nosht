import React from 'react'
import {
  Col,
  Form as BootstrapForm,
  ModalBody,
  Row,
} from 'reactstrap'
import requests from '../utils/requests'
import {grecaptcha_execute} from '../utils'
import {ModalFooter} from '../general/Modal'
import {Money, MoneyFree} from '../general/Money'
import Markdown from '../general/Markdown'
import Input from '../forms/Input'
import {User} from './BookingTickets'
import ReactGA from 'react-ga'
import {StripeContext, StripeForm} from './Stripe'

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
      submitted: false,
      cancelled: false,
      terms_and_conditions: false,
      payment: {}
    }
    this.update_timer = this.update_timer.bind(this)
    this.render_form = this.render_form.bind(this)
    this.take_payment = this.take_payment.bind(this)
    this.book_free = this.book_free.bind(this)
  }

  update_timer () {
    const t = this.props.reservation.timeout - (new Date()).getTime() / 1000
    this.setState({time_left: Math.floor(t / 60)})
  }

  componentDidMount () {
    this.update_timer()
    this.clear = setInterval(this.update_timer, 500)
  }

  componentWillUnmount () {
    clearInterval(this.clear)
  }

  async componentWillMount () {
    this.props.register_toggle_handler(this.cancel_reservation.bind(this))
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
    if (this.props.reservation.total_price) {
      this.take_payment()
    } else {
      this.book_free()
    }
  }

  async take_payment () {
    const required = ['complete', 'name', 'address', 'city', 'postcode']
    if (this.state.submitting || !required.every(f => this.state.payment[f])) {
      const payment = Object.assign({}, this.state.payment, {
        name_error: this.state.payment.name ? null: 'Required',
        address_error: this.state.payment.address ? null: 'Required',
        city_error: this.state.payment.city ? null: 'Required',
        postcode_error: this.state.payment.postcode ? null: 'Required',
      })
      this.setState({submitting: false, payment})
      return
    }

    try {
      const [{token}, grecaptcha_token] = await Promise.all([
        this.props.stripe.createToken({
          name: this.state.payment.name,
          address_line1: this.state.payment.address,
          address_city: this.state.payment.city,
          address_zip: this.state.payment.postcode,
        }),
        grecaptcha_execute('stripe_pay'),
      ])
      this.setState({submitted: true})

      await requests.post('events/buy/', {
        stripe_token: token.id,
        stripe_client_ip: token.client_ip,
        stripe_card_ref: `${token.card.last4}-${token.card.exp_year}-${token.card.exp_month}`,
        booking_token: this.props.reservation.booking_token,
        grecaptcha_token
      })
    } catch (error) {
      this.props.ctx.setError(error)
      return
    }
    this.props.ctx.setMessage({icon: ['fas', 'check-circle'], message: 'Payment successful, check your email'})
    ReactGA.event({
      category: 'ticket-booking',
      action: 'ticket-booking-confirm',
      label: 'pay',
      value: this.props.reservation.total_price
    })
    this.props.finished(true)
  }

  async book_free () {
    this.setState({submitted: true})
    const grecaptcha_token = await grecaptcha_execute('book_free')

    try {
      await requests.post('events/book-free/',
          {booking_token: this.props.reservation.booking_token, grecaptcha_token})
    } catch (error) {
      this.props.ctx.setError(error)
      return
    }

    this.props.ctx.setMessage({icon: ['fas', 'check-circle'], message: 'Booking successful, check your email'})
    ReactGA.event({
      category: 'ticket-booking',
      action: 'ticket-booking-confirm',
      label: 'free',
    })
    this.props.finished(true)
  }

  render_form (expired) {
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
          set_value={v => this.setState({terms_and_conditions: v})}
        />
      )
    }
    if (expired) {
      return <h4 className="has-error">Rervation expired</h4>
    } else if (!this.props.reservation.total_price) {
      return tncs_field && <div style={{height: 40}}>{this.state.submitted ? null : tncs_field}</div>
    } else {
      return (
          <StripeForm
              submitted={this.state.submitted}
              details={this.state.payment}
              setDetails={payment => this.setState({payment})}>
            {tncs_field}
          </StripeForm>
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
    const confirm_disabled = (
      (!this.state.terms_and_conditions && this.props.event.terms_and_conditions_message) ||
      expired ||
      this.state.submitting ||
      (res.total_price && !this.state.payment.complete)
    )
    return (
      <BootstrapForm className="pad-less" onSubmit={this.submit.bind(this)}>
        <ModalBody>
          <User {...this.props}/>
          <Row className="justify-content-center">
            <Col md="8">
              <PricingList className="mb-2" items={items}/>
              <hr/>

              {this.render_form(expired)}
            </Col>
          </Row>
        </ModalBody>
        <ModalFooter finished={this.props.finished}
                     label={res.total_price ? 'Buy Now' : 'Confirm'}
                     disabled={confirm_disabled}/>
      </BootstrapForm>
    )
  }
}
export default StripeContext(StripeBookingForm)
