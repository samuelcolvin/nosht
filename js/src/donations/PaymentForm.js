import React from 'react'
import {ModalBody, Form as BootstrapForm, Row, Col, Collapse} from 'reactstrap'
import ReactGA from 'react-ga'
import WithContext from '../utils/context'
import AsModal, {SetModalTitle, ModalFooter} from '../general/Modal'
import Markdown from '../general/Markdown'
import {Money} from '../general/Money'
import {stripe_pay, StripeContext, StripeForm} from '../events/Stripe'
import Input from '../forms/Input'
import requests from '../utils/requests'


const gift_aid_field = {
  type: 'bool',
  name: 'gift_aid',
  title: 'Make my donation worth even more with Gift Aid',
  help_text: (  // TODO this needs to be a cat field so the link isn't too specific
    <b>
      Adding Gift Aid increases your donation by 25%, that’s £2.50 in every £10 – at no cost to you.
      To read more about Gift aid and donations which can’t include gift aid click&nbsp;
      <a href="https://handsupfoundation.org/news/gift-aid-the-low-down-on-increasing-your-donation-by-25"
         target="_blank" rel="noopener noreferrer">here</a>.
    </b>
  )
}

export class PaymentForm_ extends React.Component {
  constructor (props) {
    super(props)
    this.state = {
      gift_aid: false,
      submitting: false,
      payment: {},
    }
    this.stripe_pay = stripe_pay.bind(this)
  }

  async componentDidMount () {
    if (!this.props.ctx.user) {
      this.props.ctx.setError('You must be logged in to make a donation')
      return
    }

    this.setState({
      title: this.props.ctx.user.title,
      title_error: null,
      first_name: this.props.ctx.user.first_name,
      first_name_error: null,
      last_name: this.props.ctx.user.last_name,
      last_name_error: null,
      address_error: null,
      city_error: null,
      postcode_error: null,
    })

    let url
    let data = null
    if (this.props.config.donation_option_id) {
      url = `/donation-options/${this.props.config.donation_option_id}/prepare/${this.props.event.id}/`
    } else {
      url = `/donation-prepare/${this.props.config.ticket_type}/`
      data = {custom_amount: this.props.config.amount}
    }
    let r
    try {
      r = await requests.post(url, data)
    } catch (error) {
      this.props.ctx.setError(error)
      return
    }
    this.setState({
      donation_action_id: r.action_id,
      client_secret: r.client_secret,
    })
  }

  setPaymentState = payment => {
    this.setState({payment})
    if (!this.state.address && !this.state.city && !this.state.postcode) {
      this.setState({
        address: payment.address,
        city: payment.city,
        postcode: payment.postal_code,
      })
    }
  }

  async submit (e) {
    e.preventDefault()
    if (!this.state.client_secret || this.state.submitting) {
      return
    }
    this.setState({submitting: true})
    if (this.state.gift_aid) {
      const data = {
        title: this.state.title,
        first_name: this.state.first_name,
        last_name: this.state.last_name,
        address: this.state.address,
        city: this.state.city,
        postcode: this.state.postcode,
      }
      try {
        await requests.post(`/donation/${this.state.donation_action_id}/gift-aid/`, data)
      } catch (error) {
        this.props.ctx.setError(error)
        return
      }
    }
    const ok = await this.stripe_pay(this.state.client_secret)
    if (ok) {
      this.props.ctx.setMessage({icon: ['fas', 'check-circle'], message: 'Donation successful, check your email'})
      ReactGA.event({
        category: 'donation',
        action: 'donation-complete',
        label: this.props.config.donation_option_id,
        value: Math.round(this.props.config.amount * 100),
      })
      this.props.finished(true)
    }
  }

  render () {
    if (!this.props.ctx.user) {
      return null
    }
    const can_submit = (
      !this.state.submitting &&
      this.state.client_secret &&
      (this.state.payment.complete || this.state.payment.payment_method_id)
    )

    const title_field = {name: 'title', required: this.state.gift_aid, max_length: 10}
    const first_name_field = {name: 'first_name', required: this.state.gift_aid}
    const last_name_field = {name: 'last_name', required: this.state.gift_aid}
    const address_field = {name: 'address', required: this.state.gift_aid}
    const city_field = {name: 'city', required: this.state.gift_aid}
    const postcode_field = {name: 'postcode', required: this.state.gift_aid}

    return (
      <BootstrapForm className="pad-less" onSubmit={this.submit.bind(this)}>
        {this.props.config.name ? (
            <SetModalTitle>
              {this.props.config.name} &bull; <Money>{this.props.config.amount}</Money> donation
            </SetModalTitle>
          )
          : null
        }
        <ModalBody key="mb">
          <div>
            <div className="text-center">
              {this.props.config.image &&
                <img src={this.props.config.image} className="img-fluid" alt={this.props.config.name}/>
              }
            </div>
            <Markdown content={this.props.config.long_description}/>
          </div>
          <Row className="justify-content-center">
            <Col lg="8">
              {this.props.config.long_description ? <hr/> : null}

              <StripeForm submitting={this.state.submitting}
                          payment_state={this.state.payment}
                          setPaymentState={this.setPaymentState}/>

              <hr/>

              <strong>
                <Input field={gift_aid_field}
                       value={this.state.gift_aid}
                       disabled={this.state.submitting}
                       onChange={gift_aid => this.setState({gift_aid})} />
              </strong>

              <Collapse isOpen={this.state.gift_aid} className="pb-2">
                <Row>
                  <Col md="6">
                    <Input field={title_field} value={this.state.title} error={this.state.title_error}
                           disabled={this.state.submitting}
                           onChange={v => this.setState({title: v, title_error: null})}/>
                  </Col>
                </Row>
                <Row>
                  <Col md="6">
                    <Input field={first_name_field} value={this.state.first_name} error={this.state.first_name_error}
                           disabled={this.state.submitting}
                           onChange={v => this.setState({first_name: v, first_name_error: null})}/>
                  </Col>
                  <Col md="6">
                    <Input field={last_name_field} value={this.state.last_name} error={this.state.last_name_error}
                           disabled={this.state.submitting}
                           onChange={v => this.setState({last_name: v, last_name_error: null})}/>
                  </Col>
                </Row>
                <Input field={address_field} value={this.state.address} error={this.state.address_error}
                       disabled={this.state.submitting}
                       onChange={v => this.setState({address: v, address_error: null})}/>
                <Row>
                  <Col md="6">
                    <Input field={city_field} value={this.state.city} error={this.state.city_error}
                           disabled={this.state.submitting}
                           onChange={v => this.setState({city: v, city_error: null})}/>
                  </Col>
                  <Col md="6">
                    <Input field={postcode_field} value={this.state.postcode} error={this.state.postcode_error}
                           disabled={this.state.submitting}
                           onChange={v => this.setState({postcode: v, postcode_error: null})}/>
                  </Col>
                </Row>
              </Collapse>
            </Col>
          </Row>
        </ModalBody>
        <ModalFooter finished={this.props.finished}
                     label={<span>Donate <Money>{this.props.config.amount}</Money></span>}
                     cancel_disabled={this.state.submitting}
                     disabled={!can_submit}/>
      </BootstrapForm>
    )
  }
}
export const PaymentForm = WithContext(StripeContext(PaymentForm_))
export const PaymentModal = AsModal(PaymentForm)
