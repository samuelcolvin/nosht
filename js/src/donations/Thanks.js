import React from 'react'
import {Button, Row, Col, Card, CardImg, CardBody, CardTitle, CardText} from 'reactstrap'
import {FontAwesomeIcon} from '@fortawesome/react-fontawesome'
import {Link} from 'react-router-dom'
import PromptUpdate from '../general/PromptUpdate'
import {Loading} from '../general/Errors'
import {image_thumb} from '../utils'
import requests from '../utils/requests'
import {Money} from '../general/Money'
import {PaymentModal} from './PaymentForm'

class Thanks extends React.Component {
  constructor (props) {
    super(props)
    this.state = {donation_options: null, post_booking_message: null}
    this.props.register(this.get_data.bind(this))
  }

  async get_data () {
    if (this.state.donation_options) {
      return
    }
    let data
    try {
      data = await requests.get(`/categories/${this.props.event.category_id}/donation-options/`)
    } catch (error) {
      this.props.ctx.setError(error)
      return
    }
    this.setState({donation_options: data.donation_options, post_booking_message: data.post_booking_message})
  }

  render () {
    if (!this.state.donation_options) {
      return <Loading/>
    }
    let payment_config = {}
    const m = this.props.location.pathname.match(/post-donation\/(\d+)\/$/)
    if (m && this.state.donation_options.length) {
      const donation_option = this.state.donation_options.find(opt => opt.id === parseInt(m[1]))
      if (donation_option) {
        payment_config = {
          donation_option_id: donation_option.id,
          amount: donation_option.amount,
          name: donation_option.name,
          long_description: donation_option.long_description,
          image: donation_option.image,
        }
      }
    }
    return (
      <div>
        <Row>
          <Col>
            <h1>{this.props.event.name}</h1>
            <Link to={this.props.uri}>&lsaquo; Back to event details</Link>
          </Col>
        </Row>

        {this.props.booking_complete && this.state.post_booking_message && (
          <div className="text-muted mt-2 mb-3 h5">
            <FontAwesomeIcon icon={['fas', 'check-circle']} className="mx-1 text-success"/>
            {this.state.post_booking_message}
          </div>
        )}

        {this.state.donation_options.length ? [
          <div key="p" className="lead">
            Make a donation to {this.props.ctx.company.company.name}
          </div>,
          <Row key="g">
            {this.state.donation_options.map(opt => (
              <Col key={opt.id} md="4" className="box-container pb-4">
                <Card>
                  {opt.image &&
                    <CardImg top width="100%" src={image_thumb(opt.image)} alt={opt.name}/>
                  }
                  <CardBody>
                    <CardTitle>{opt.name}</CardTitle>
                    <CardText>
                      {opt.short_description || opt.long_description}
                    </CardText>
                    <Button tag={Link} to={this.props.uri + `post-donation/${opt.id}/`} disabled={!this.props.ctx.user}>
                      Donate <Money>{opt.amount}</Money>
                    </Button>
                    {!this.props.ctx.user && (
                      <small className="text-muted d-block">
                        You must be logged in to donate.
                      </small>
                    )}
                  </CardBody>
                </Card>
              </Col>
            ))}
          </Row>
        ] : <p>No donation options set up for this category.</p>}

        <PaymentModal
            {...this.props}
            parent_uri={this.props.uri + 'post-donation/'}
            config={payment_config}
            regex={/post-donation\/\d+\/$/}
        />
      </div>
    )
  }
}
export default PromptUpdate(Thanks)
