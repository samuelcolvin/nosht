import React from 'react'
import {Button, Row, Col, Card, CardImg, CardBody, CardTitle, CardText} from 'reactstrap'
import {FontAwesomeIcon} from '@fortawesome/react-fontawesome'
import {Link} from 'react-router-dom'
import PromptUpdate from '../general/PromptUpdate'
import requests from '../utils/requests'
import {Money} from '../general/Money'
import DonateModal from './Donate'

class Thanks extends React.Component {
  constructor (props) {
    super(props)
    this.state = {donation_options: []}
    this.props.register(this.get_data.bind(this))
  }

  async get_data () {
    let data
    try {
      data = await requests.get(`/categories/${this.props.event.category_id}/donation-options/`)
    } catch (error) {
      this.props.ctx.setError(error)
      return
    }
    this.setState({donation_options: data.donation_options})
  }

  render () {
    let selected_opt = {}
    const m = this.props.location.pathname.match(/donate\/(\d+)\/$/)
    if (m && this.state.donation_options.length) {
      selected_opt = this.state.donation_options.find(opt => opt.id === parseInt(m[1]))
    }
    return (
      <div>
        <Row>
          <Col>
            <h1>{this.props.event.name}</h1>
            <p className="lead">
              {this.props.event.short_description}
            </p>
          </Col>
        </Row>

        <Row className="text-muted mb-3 h5">
          <Col md="auto">
            <FontAwesomeIcon icon={['fas', 'check-circle']} className="mx-1 text-success"/>
            Booking successful, please check your email for tickets and other details.
          </Col>
        </Row>

        {this.state.donation_options.length && [
          <div key="p" className="h4">
            While you're here, please consider making a donation to {this.props.ctx.company.company.name}...
          </div>,
          <Row key="g" className="pt-2">
            {this.state.donation_options.map(opt => (
              <Col key={opt.id} md="4" className="box-container">
                <Card>
                  {opt.image &&
                    <CardImg top width="100%" src={opt.image + '/thumb.jpg'} alt={opt.name}/>
                  }
                  <CardBody>
                    <CardTitle>{opt.name}</CardTitle>
                    <CardText>
                      {opt.short_description || opt.long_description}
                    </CardText>
                    <Button tag={Link} to={this.props.uri + `donate/${opt.id}/`}>
                      Donate <Money>{opt.amount}</Money>
                    </Button>
                  </CardBody>
                </Card>
              </Col>
            ))}
          </Row>
        ]}

        <DonateModal
            {...this.props}
            parent_uri={this.uri}
            event={this.state.event}
            donation_option={selected_opt}
            title={`Donate ${selected_opt.name}`}
            regex={/donate\/\d+\/$/}
        />
      </div>
    )
  }
}
export default PromptUpdate(Thanks)
