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


const stripe_styles = {
  invalid: {
    // from bootstrap > _variables.scss > $form-feedback-invalid-color
    color: '#dc3545'
  }
}

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
    this.state = {error: null}
    this.setDetails = this.setDetails.bind(this)
  }

  componentDidMount () {
    this.props.setDetails({
      complete: false,
      name: `${this.props.ctx.user.first_name || ''} ${this.props.ctx.user.last_name || ''}`.trim(),
      name_error: null,
      address: null,
      address_error: null,
      city: null,
      city_error: null,
      postcode: null,
      postcode_error: null,
    })
  }

  setDetails (change) {
    this.props.setDetails(Object.assign({}, this.props.details, change))
  }

  update_stripe_status (status) {
    this.setState({error: status.error && status.error.message})
    this.setDetails({complete: status.complete})
  }

  render () {
    const form_height = 300
    if (this.props.submitted) {
      return (
        <div style={{height: form_height}} className="vertical-center">
          <Waiting/>
          <small className="text-muted mt-4">processing payment...</small>
        </div>
      )
    } else {
      const details = this.props.details || {}
      return (
        <div style={{height: form_height}} className="hide-help-text">
          <Input field={name_field}
                 value={details.name}
                 error={details.name_error}
                 set_value={v => this.setDetails({name: v, name_error: null})}/>
          <Input field={address_field}
                 value={details.address}
                 error={details.address_error}
                 set_value={v => this.setDetails({address: v, address_error: null})}/>
          <Row>
            <Col md="6">
              <Input field={city_field}
                     value={details.city}
                     error={details.city_error}
                     set_value={v => this.setDetails({city: v, city_error: null})}/>
            </Col>
            <Col md="6">
              <Input field={postcode_field}
                     value={details.postcode}
                     error={details.postcode_error}
                     set_value={v => this.setDetails({postcode: v, postcode_error: null})}/>
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
              this.state.error &&
              <FormFeedback className="d-block">
                <FontAwesomeIcon icon="times" className="mr-1"/>
                {this.state.error}
              </FormFeedback>
            }
          </FormGroup>
          {this.props.children}
        </div>
      )
    }
  }
}
export const StripeForm = injectStripe(WithContext(StripeForm_))
