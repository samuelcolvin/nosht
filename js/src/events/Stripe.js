import React from 'react'
import {
  Col,
  FormFeedback,
  FormGroup,
  Label,
  Row,
} from 'reactstrap'
import {StripeProvider, Elements, CardElement, injectStripe} from 'react-stripe-elements'
import {FontAwesomeIcon} from '@fortawesome/react-fontawesome'
import {get_component_name, grecaptcha_execute, load_script, window_property} from '../utils'
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
            <InjectedWrappedComponent {...this.props}/>
          </Elements>
        </StripeProvider>
      )
    }
  }
  StripeContext.displayName = `StripeContext(${get_component_name(WrappedComponent)})`
  return WithContext(StripeContext)
}

export async function stripe_pay (post_url, request_data) {
  if (this.state.submitting || !stripe_form_valid(this.state.payment)) {
    const payment = Object.assign({}, this.state.payment, {
      name_error: this.state.payment.name ? null: 'Required',
      address_error: this.state.payment.address ? null: 'Required',
      city_error: this.state.payment.city ? null: 'Required',
      postcode_error: this.state.payment.postcode ? null: 'Required',
    })
    this.setState({submitting: false, payment})
    return false
  }

  let token = null
  if (this.state.payment.source_hash) {
    request_data.stripe = {source_hash: this.state.payment.source_hash}
  } else {
    const r = await this.props.stripe.createToken({
      name: this.state.payment.name,
      address_line1: this.state.payment.address,
      address_city: this.state.payment.city,
      address_zip: this.state.payment.postcode,
    })
    token = r.token
    request_data.stripe = {
      token: token.id,
      card_ref: `${token.card.last4}-${token.card.exp_year}-${token.card.exp_month}`,
      client_ip: token.client_ip,
    }
  }
  this.setState({submitted: true})

  request_data.grecaptcha_token = await grecaptcha_execute('stripe_pay')

  let response_data
  try {
    response_data = await requests.post(post_url, request_data, {expected_statuses: [200, 402]})
  } catch (error) {
    this.props.ctx.setError(error)
    return false
  }
  console.log(response_data)
  if (response_data._response_status === 200) {
    if (token) {
      record_card(this.props.ctx.user, token, response_data.source_hash)
    }
    return true
  } else {
    const payment = Object.assign({}, this.state.payment, {error: response_data.message})
    this.setState({payment, submitted: false, submitting: false})
    return false
  }
}

export const stripe_form_valid = payment_details => (
  payment_details.source_hash || ['complete', 'name', 'address', 'city', 'postcode'].every(f => payment_details[f])
)

export const record_card = (user, token, source_hash) => {
  window.sessionStorage[`card_details_${user.id}`] = JSON.stringify(Object.assign({}, token.card, {source_hash}))
}

export const get_card = user => {
  const v = window.sessionStorage[`card_details_${user.id}`]
  return v ? JSON.parse(v) : {}
}

const ShowCard = ({card}) => (
  <span>
    {card.brand} expiring: {card.exp_month}/{card.exp_year - 2000}, ending: {card.last4}
  </span>
)

const name_field = {name: 'billing_name', required: true}
const address_field = {name: 'billing_address', required: true}
const city_field = {name: 'billing_city', required: true}
const postcode_field = {name: 'billing_postcode', required: true}

class StripeForm_ extends React.Component {
  constructor (props) {
    super(props)
    this.setPaymentState = this.setPaymentState.bind(this)
    this.radioChange = this.radioChange.bind(this)
    this.stored_card = get_card(props.ctx.user)
  }

  componentDidMount () {
    const u = this.props.ctx.user
    this.props.setPaymentState({
      error: false,
      complete: false,
      name: this.stored_card.name || `${u.first_name || ''} ${u.last_name || ''}`.trim(),
      name_error: null,
      address: this.stored_card.address_line1,
      address_error: null,
      city: this.stored_card.address_city,
      city_error: null,
      postcode: this.stored_card.address_zip,
      postcode_error: null,
      source_hash: this.stored_card.source_hash || null,
    })
  }

  setPaymentState (change) {
    this.props.setPaymentState(Object.assign({}, this.props.payment_state, change))
  }

  update_stripe_status (status) {
    this.setPaymentState({error: status.error && status.error.message, complete: status.complete})
  }

  radioChange (e) {
    this.setPaymentState({source_hash: e.target.value === 'saved' ? this.stored_card.source_hash : null})
  }

  render () {
    let form_height = 300
    const payment_state = this.props.payment_state || {}
    const has_saved_card = Boolean(this.stored_card.source_hash)
    if (has_saved_card) {
      form_height = payment_state.source_hash ? 130 : 340
    }
    if (this.props.submitted) {
      return (
        <div style={{height: form_height}} className="vertical-center">
          <Waiting/>
          <small className="text-muted mt-4">processing payment...</small>
        </div>
      )
    } else {
      return (
        <div style={{height: form_height}} className="hide-help-text">
          {has_saved_card && (
            <Row className="justify-content-center">
              <Col md="10">
                <div className="form-check">
                  <input className="form-check-input" type="radio" id="card-saved" value="saved"
                         checked={!!payment_state.source_hash} onChange={this.radioChange}/>
                  <label className="form-check-label" htmlFor="card-saved">
                    Use <ShowCard card={this.stored_card}/>
                  </label>
                </div>

                <div className="form-check">
                  <input className="form-check-input" type="radio" id="card-new" value="new"
                         checked={!payment_state.source_hash} onChange={this.radioChange}/>
                  <label className="form-check-label" htmlFor="card-new">
                    Use new Card
                  </label>
                </div>
              </Col>
            </Row>
          )}
          <div className={payment_state.source_hash ? 'invisible' : ''}>
            <Input field={name_field} value={payment_state.name} error={payment_state.name_error}
                   set_value={v => this.setPaymentState({name: v, name_error: null})}/>
            <Input field={address_field} value={payment_state.address} error={payment_state.address_error}
                   set_value={v => this.setPaymentState({address: v, address_error: null})}/>
            <Row>
              <Col md="6">
                <Input field={city_field} value={payment_state.city} error={payment_state.city_error}
                       set_value={v => this.setPaymentState({city: v, city_error: null})}/>
              </Col>
              <Col md="6">
                <Input field={postcode_field} value={payment_state.postcode} error={payment_state.postcode_error}
                       set_value={v => this.setPaymentState({postcode: v, postcode_error: null})}/>
              </Col>
            </Row>
            <FormGroup>
              <Label className="required">
                Card Details
              </Label>
              <CardElement className={`py-2 px-1${payment_state.error ? ' stripe-error' : ''}`}
                           hidePostalCode={true}
                           onChange={this.update_stripe_status.bind(this)}/>
              {payment_state.error &&
                <FormFeedback className="d-block">
                  <FontAwesomeIcon icon="times" className="mr-1"/>
                  {payment_state.error}
                </FormFeedback>
              }
            </FormGroup>
          </div>
          {this.props.children}
        </div>
      )
    }
  }
}
export const StripeForm = injectStripe(WithContext(StripeForm_))
