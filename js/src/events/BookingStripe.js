import React from 'react'
import {
  Col,
  Form as BootstrapForm,
  FormFeedback,
  FormGroup,
  Label,
  ModalBody,
  Row,
} from 'reactstrap'
import {StripeProvider, Elements, CardElement, injectStripe} from 'react-stripe-elements'
import FontAwesomeIcon from '@fortawesome/react-fontawesome'
import WithContext from '../utils/context'
import requests from '../utils/requests'
import {load_script, grecaptcha_execute, window_property} from '../utils'
import {ModalFooter} from '../general/Modal'
import {MoneyFree} from '../general/Money'
import Input from '../forms/Input'
import {User} from './BookingTickets'
import {Waiting} from '../general/Errors'

const stripe_styles = {
  invalid: {
    // from bootstrap > _variables.scss > $form-feedback-invalid-color
    color: '#dc3545'
  }
}

export const PricingList = ({items, className}) => (
  <div className={className}>
    {items.map((item, i) => (
      <div key={i} className={`d-flex justify-content-between ${item.className || ''}`}>
        <div>{item.name}:</div>
        <div className="font-weight-bold">{item.value}</div>
      </div>
    ))}
  </div>
)

const name_field = {
  name: 'billing_name',
  required: true,
}
const address_field = {
  name: 'billing_address',
  required: true,
}
const city_field = {
  name: 'billing_city',
  required: true,
}
const postcode_field = {
  name: 'billing_postcode',
  required: true,
}

class StripeForm_ extends React.Component {
  constructor (props) {
    super(props)
    this.state = {
      time_left: 0,
      card_error: null,
      card_complete: false,
      submitting: false,
      submitted: false,
      cancelled: false,
      name: props.billing_name,
      address: null,
      city: null,
      postcode: null,
    }
    this.update_timer = this.update_timer.bind(this)
    this.as_price = p => <MoneyFree>{p && p/100}</MoneyFree>
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
    if (this.props.reservation.item_price_cent) {
      this.take_payment()
    } else {
      this.book_free()
    }
  }

  async take_payment () {
    const required = ['card_complete', 'name', 'address', 'city', 'postcode']
    if (this.state.submitting || !required.every(f => this.state[f])) {
      required.filter(f => !this.state[f]).map(f => this.setState({[`${f}_error`]: 'Required'}))
      this.setState({submitting: false})
      return
    }

    try {
      const [{token}, grecaptcha_token] = await Promise.all([
        this.props.stripe.createToken({
          name: this.state.name,
          address_line1: this.state.address,
          address_city: this.state.city,
          address_zip: this.state.postcode,
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
    this.props.finished()
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
    this.props.finished()
  }

  update_stripe_status (status) {
    this.setState({
      card_error: status.error && status.error.message,
      card_complete: status.complete,
    })
  }

  render_form (expired) {
    const form_height = 300
    if (expired) {
      return <h4 className="has-error">Rervation expired</h4>
    } else if (!this.props.reservation.item_price_cent) {
      return null
    } else if (this.state.submitted) {
      return (
        <div style={{height: form_height}} className="vertical-center">
          <Waiting/>
          <small className="text-muted mt-4">processing payment...</small>
        </div>
      )
    } else {
      return (
        <div style={{height: form_height}} className="hide-help-text">
          <Input field={name_field}
                 value={this.state.name}
                 error={this.state.name_error}
                 set_value={v => this.setState({name: v, name_error: null})}/>
          <Input field={address_field}
                 value={this.state.address}
                 error={this.state.address_error}
                 set_value={v => this.setState({address: v, address_error: null})}/>
          <Row>
            <Col md="6">
              <Input field={city_field}
                     value={this.state.city}
                     error={this.state.city_error}
                     set_value={v => this.setState({city: v, city_error: null})}/>
            </Col>
            <Col md="6">
              <Input field={postcode_field}
                     value={this.state.postcode}
                     error={this.state.postcode_error}
                     set_value={v => this.setState({postcode: v, postcode_error: null})}/>
            </Col>
          </Row>
          <FormGroup>
            <Label className="required">
              Card Details
            </Label>
            <CardElement className="py-2 px-1"
                          hidePostalCode={true}
                          onChange={this.update_stripe_status.bind(this)}
                          style={stripe_styles}/>
            {
              this.state.card_error &&
              <FormFeedback className="d-block">
                <FontAwesomeIcon icon="times" className="mr-1"/>
                {this.state.card_error}
              </FormFeedback>
            }
          </FormGroup>
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
      {name: 'Ticket Price', value: this.as_price(res.item_price_cent)},
      {name: 'Total Price', value: this.as_price(res.total_price_cent)},
    ]
    const expired = this.state.time_left < 1
    if (expired) {
      items.splice(0, 1)
    }
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
                     label={res.item_price_cent ? 'Buy Now' : 'Confirm'}
                     disabled={expired || this.state.submitting || (res.item_price_cent && !this.state.card_complete)}/>
      </BootstrapForm>
    )
  }
}
const StripeForm = injectStripe(WithContext(StripeForm_))

export default class Stripe extends React.Component {
  constructor (props) {
    super(props)
    this.state = {stripe: null}
  }

  async componentDidMount () {
    await load_script('https://js.stripe.com/v3/')
    const stripe = await window_property('Stripe')
    this.setState({stripe: stripe(this.props.event.stripe_key)})
  }

  render () {
    return (
      <StripeProvider stripe={this.state.stripe}>
        <Elements>
          <StripeForm {...this.props} stripe={this.state.stripe}/>
        </Elements>
      </StripeProvider>
    )
  }
}
