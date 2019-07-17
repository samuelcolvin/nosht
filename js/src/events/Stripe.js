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

export async function stripe_pay (post_url, request_data, client_secret) {
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

  this.setState({submitting: true})
  if (this.state.payment.source_hash) {
    // TODO complete payment intent via
    request_data.stripe = {source_hash: this.state.payment.source_hash}
  } else {
    const r = await this.props.stripe.handleCardPayment(client_secret, {
      payment_method_data: {
        billing_details: {
          address: {
            city: this.state.payment.city,
            line1: this.state.payment.address,
            postal_code: this.state.payment.postcode,
          },
          name: this.state.payment.name,
        }
      }
    })
    if (r.error) {
      // happens at least when you use a test card on live stripe
      console.warn('create token response:', r)
      const payment = {...this.state.payment, error: r.error.message || 'Invalid Card'}
      this.setState({payment, submitting: false})
      return false
    }
    record_payment_method(this.props.ctx.user, r.paymentIntent.payment_method)
  }
  return true
}

export const stripe_form_valid = payment_details => (
  payment_details.source_hash || ['complete', 'name', 'address', 'city', 'postcode'].every(f => payment_details[f])
)

export const record_payment_method = (user, payment_method) => {
  window.sessionStorage[`payment_method_${user.id}`] = payment_method
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
    this.state = {overlay_style: null}
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

  componentDidUpdate () {
    this.clear_timer = setTimeout(() => {
      const el = document.getElementById('stripe-form')
      if (el && el.offsetHeight !== this.state.form_height) {
        this.setState({
          overlay_style: {
            height: el.offsetHeight,
            width: el.offsetWidth,
          }
        })
      }
    }, 100)
  }

  componentWillUnmount () {
    clearInterval(this.clear_timer)
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
    const payment_state = this.props.payment_state || {}
    const has_saved_card = Boolean(this.stored_card.source_hash)
    return (
      <div className="hide-help-text" id="stripe-form">
        {this.props.submitting && (
          <div style={this.state.overlay_style} className="stripe-overlay">
            <Waiting/>
            <small className="text-muted mt-4">processing payment...</small>
          </div>
        )}
        {has_saved_card && (
          <div className="pb-2">
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
          </div>
        )}
        <Collapse isOpen={!payment_state.source_hash}>
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
              <Input field={postcode_field} value={payment_state.postcode} error={payment_state.postcode_error}
                     onChange={v => this.setPaymentState({postcode: v, postcode_error: null})}/>
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
        </Collapse>
      </div>
    )
  }
}
export const StripeForm = injectStripe(WithContext(StripeForm_))
