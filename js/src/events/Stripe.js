import React from 'react'
import {
  Col,
  Collapse,
  FormFeedback,
  FormGroup,
  Label,
  Row,
} from 'reactstrap'
import {StripeProvider, Elements, CardElement, injectStripe} from 'react-stripe-elements'
import {FontAwesomeIcon} from '@fortawesome/react-fontawesome'
import {get_component_name, load_script, window_property} from '../utils'
import WithContext from '../utils/context'
import Input from '../forms/Input'
import {Waiting} from '../general/Errors'
import requests from '../utils/requests'


export function StripeContext (WrappedComponent) {
  const InjectedWrappedComponent = injectStripe(WrappedComponent)

  class StripeContext extends React.Component {
    constructor (props) {
      super(props)
      this.state = {stripe: null}
    }

    async componentDidMount () {
      await load_script('https://js.stripe.com/v3/')
      const Stripe = await window_property('Stripe')
      const stripe = Stripe(this.props.ctx.company.company.stripe_public_key)
      this.setState({stripe})
    }

    render () {
      return (
        <StripeProvider stripe={this.state.stripe}>
          <Elements>
            <InjectedWrappedComponent {...this.props} raw_stripe={this.state.stripe}/>
          </Elements>
        </StripeProvider>
      )
    }
  }
  StripeContext.displayName = `StripeContext(${get_component_name(WrappedComponent)})`
  return WithContext(StripeContext)
}

export async function stripe_pay (client_secret) {
  if (!stripe_form_valid(this.state.payment)) {
    const payment = Object.assign({}, this.state.payment, {
      name_error: this.state.payment.name ? null: 'Required',
      address_error: this.state.payment.address ? null: 'Required',
      city_error: this.state.payment.city ? null: 'Required',
      postal_code_error: this.state.payment.postal_code ? null: 'Required',
    })
    this.setState({submitting: false, payment})
    return false
  }

  let r
  const payment_method = this.state.payment.payment_method_id
  if (payment_method) {
    r = await this.props.raw_stripe.handleCardPayment(client_secret, {payment_method})
  } else {
    r = await this.props.stripe.handleCardPayment(client_secret, {
      payment_method_data: {
        billing_details: {
          address: {
            city: this.state.payment.city,
            line1: this.state.payment.address,
            postal_code: this.state.payment.postal_code,
          },
          name: this.state.payment.name,
        }
      },
      save_payment_method: true
    })
  }
  if (r.error) {
    // happens for any stripe or card error
    console.warn('handleCardPayment response:', r)
    const payment = {...this.state.payment, error: r.error.message || 'Invalid Card'}
    this.setState({payment, submitting: false})
    return false
  } else {
    if (!payment_method) {
      record_payment_method(this.props.ctx.user, r.paymentIntent.payment_method)
    }
    return true
  }
}

export const stripe_form_valid = payment_details => (
  payment_details.payment_method_id ||
  ['complete', 'name', 'address', 'city', 'postal_code'].every(f => payment_details[f])
)

export const record_payment_method = (user, payment_method) => {
  window.sessionStorage[`payment_method_${user.id}`] = payment_method
}

export const get_payment_method = async (user) => {
  const storage_key = `payment_method_${user.id}`
  const payment_method_id = window.sessionStorage[storage_key]
  if (payment_method_id) {
    try {
      const data = await requests.get(`/stripe/payment-method-details/${payment_method_id}/`)
      delete data._response_status
      return {payment_method_id, ...data}
    } catch (e) {
      window.sessionStorage.removeItem(storage_key)
      console.info('error getting payment method details', e)
    }
  }
  return {}
}

const ShowCard = ({card}) => (
  <span>
    {card.brand} expiring: {card.exp_month}/{card.exp_year - 2000}, ending: {card.last4}
  </span>
)

export class Overlay extends React.Component {
  state = {style: null}

  componentDidUpdate () {
    this.clear_timer = setTimeout(() => {
      const el = document.getElementById(this.props.element_id)
      if (el) {
        this.setState({style: {height: el.offsetHeight, width: el.offsetWidth}})
      }
    }, 100)
  }

  componentWillUnmount () {
    clearInterval(this.clear_timer)
  }

  render () {
    if (!this.props.show) {
      return null
    }
    return (
      <div style={this.state.style} className="processing-overlay">
        <Waiting/>
        <small className="text-muted mt-4">{this.props.text}...</small>
      </div>
    )
  }
}

const name_field = {name: 'billing_name', required: true}
const address_field = {name: 'billing_address', required: true}
const city_field = {name: 'billing_city', required: true}
const postal_code_field = {name: 'billing_postal_code', required: true}

class StripeForm_ extends React.Component {
  constructor (props) {
    super(props)
    this.setPaymentState = this.setPaymentState.bind(this)
    this.radioChange = this.radioChange.bind(this)
    this.stored_payment_method = {}
  }

  async componentDidMount () {
    const u = this.props.ctx.user
    this.stored_payment_method = await get_payment_method(this.props.ctx.user)
    this.props.setPaymentState({
      error: false,
      complete: false,
      name: this.stored_payment_method.name || `${u.first_name || ''} ${u.last_name || ''}`.trim(),
      name_error: null,
      address: this.stored_payment_method.address ? this.stored_payment_method.address.line1 : null,
      address_error: null,
      city: this.stored_payment_method.address ? this.stored_payment_method.address.city : null,
      city_error: null,
      postal_code: this.stored_payment_method.address ? this.stored_payment_method.address.postal_code : null,
      postal_code_error: null,
      payment_method_id: this.stored_payment_method.payment_method_id || null,
    })
  }

  setPaymentState (change) {
    this.props.setPaymentState({...this.props.payment_state, ...change})
  }

  update_stripe_status (status) {
    this.setPaymentState({error: status.error && status.error.message, complete: status.complete})
  }

  radioChange (e) {
    const payment_method_id = e.target.value === 'saved' ? this.stored_payment_method.payment_method_id : null
    this.setPaymentState({payment_method_id})
  }

  render () {
    const payment_state = this.props.payment_state || {}
    const has_saved_card = Boolean(this.stored_payment_method.payment_method_id)
    return (
      <div className="hide-help-text py-2" id="stripe-form">
        <Overlay element_id="stripe-form" show={this.props.submitting} text="processing payment"/>
        {has_saved_card && (
          <div className="pb-2">
            <div className="form-check">
              <input className="form-check-input" type="radio" id="card-saved" value="saved"
                     checked={!!payment_state.payment_method_id} onChange={this.radioChange}/>
              <label className="form-check-label" htmlFor="card-saved">
                Use <ShowCard card={this.stored_payment_method.card}/>
              </label>
            </div>

            <div className="form-check">
              <input className="form-check-input" type="radio" id="card-new" value="new"
                     checked={!payment_state.payment_method_id} onChange={this.radioChange}/>
              <label className="form-check-label" htmlFor="card-new">
                Use new Card
              </label>
            </div>
          </div>
        )}
        <Collapse isOpen={!payment_state.payment_method_id}>
          <Input field={name_field} value={payment_state.name} error={payment_state.name_error}
                 onChange={v => this.setPaymentState({name: v, name_error: null})}/>
          <Input field={address_field} value={payment_state.address} error={payment_state.address_error}
                 onChange={v => this.setPaymentState({address: v, address_error: null})}/>
          <Row>
            <Col md="6">
              <Input field={city_field} value={payment_state.city} error={payment_state.city_error}
                     onChange={v => this.setPaymentState({city: v, city_error: null})}/>
            </Col>
            <Col md="6">
              <Input field={postal_code_field} value={payment_state.postal_code} error={payment_state.postal_code_error}
                     onChange={v => this.setPaymentState({postal_code: v, postal_code_error: null})}/>
            </Col>
          </Row>
          <FormGroup>
            <Label className="required">
              Card Details
            </Label>
            <CardElement className={`py-2 px-1${payment_state.error ? ' stripe-error' : ''}`}
                         hidePostalCode={true}
                         onChange={this.update_stripe_status.bind(this)}/>
          </FormGroup>
        </Collapse>
        <FormFeedback className={payment_state.error ? 'd-block' : 'd-none'}>
          <FontAwesomeIcon icon="times" className="mr-1"/>
          {payment_state.error}
        </FormFeedback>
      </div>
    )
  }
}
export const StripeForm = injectStripe(WithContext(StripeForm_))
