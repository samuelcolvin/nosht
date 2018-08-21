import React from 'react'
import PromptUpdate from '../general/PromptUpdate'
import {Row, Col} from 'reactstrap'
import {FontAwesomeIcon} from '@fortawesome/react-fontawesome'
import requests from '../utils/requests'

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
    console.log(this.props.event.category_id, data)
  }

  render () {
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

        {this.state.donation_options.length &&
          <div className="h4">
            While you're here, please consider making a donation to {this.props.ctx.company.company.name}...
          </div>
        }
        {this.state.donation_options.map(don => (
          <div key={don.id}>
            {JSON.stringify(don)}
          </div>
        ))}
      </div>
    )
  }
}
export default PromptUpdate(Thanks)
