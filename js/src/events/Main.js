import React from 'react'
import {Link} from 'react-router-dom'
import FontAwesomeIcon from '@fortawesome/react-fontawesome'
import {Row, Col, Button} from 'reactstrap'
import requests from '../requests'
import {format_money_free, unique} from '../utils'
import {Loading, NotFound} from '../general/Errors'
import PromptUpdate from '../general/PromptUpdate'
import Markdown from '../general/Markdown'
import Map from '../general/Map'
import When from '../general/When'
import BookEvent from './Book'

class Event extends React.Component {
  constructor (props) {
    super(props)
    this.state = {
      event: null,
    }
    const params = this.props.match.params
    this.uri = `/${params.category}/${params.event}/`
    this.props.register(this.get_data.bind(this))
  }

  async get_data () {
    let event, ticket_types
    const params = this.props.match.params
    this.props.ctx.setRootState({active_page: params.category})
    try {
      const data = await requests.get(`events/${params.category}/${params.event}/`)
      event = data.event
      ticket_types = data.ticket_types
    } catch (error) {
      if (error.status === 404) {
        this.setState({event: 404})
      } else {
        this.props.ctx.setRootState({error})
      }
      return
    }
    this.props.ctx.setRootState({
      page_title: event.name,
      background: event.image,
      extra_menu: [{name: 'Book Now', to: this.uri + 'book/'}],
    })
    this.setState({event, ticket_types})
  }

  render () {
    const event = this.state.event
    if (!event) {
      return <Loading/>
    } else if (event === 404) {
      return <NotFound location={this.props.location}/>
    }
    return (
      <div>
        <Row>
          <Col>
            <h1>{event.name}</h1>
            <p className="lead">
              {event.short_description}
            </p>
          </Col>
          <Col md="3" className="text-right">
            {this.props.ctx.user && (this.props.ctx.user.role === 'admin' || this.props.ctx.user.id === event.host_id) &&
              <Button color="link" tag={Link} to={`/dashboard/events/${event.id}/`}>
                Edit Event
              </Button>
            }
            <Button color={event.tickets_available ? 'danger': 'primary'} size="lg"
                    className="hover-raise" tag={Link} to={this.uri + 'book/'}>
              Book Now
            </Button>
            {event.tickets_available &&
              <div className="font-weight-bold mt-3">Only {event.tickets_available} Tickets Remaining</div>}
          </Col>
        </Row>

        <Row className="text-muted mb-1 h5">
          <Col md="auto">
            <FontAwesomeIcon icon={['far', 'clock']} className="mx-1 text-success" />
            <When event={event} />
          </Col>

          <Col md="auto">
            <FontAwesomeIcon icon="pound-sign" className="mx-1 text-success" />
              {this.state.ticket_types.map(tt => tt.price).filter(unique).map((p, i) => (
                <span key={i}>
                  {i > 0 && <span className="px-1">/</span>}
                  {format_money_free(event.currency, p)}
                </span>
              ))}
          </Col>

          <Col md="auto">
            <FontAwesomeIcon icon={'user'} className="mx-1 text-success" />
            hosted by {event.host_name}
          </Col>

          {event.location.name &&
            <Col md="auto">
              <FontAwesomeIcon icon={['fas', 'map-marker']} className="mx-1 text-success" />
              at {event.location.name}
            </Col>
          }
        </Row>

        <Map geolocation={event.location}/>

        {event.category_content && (
          <div className="pt-3">
            <Markdown content={event.category_content} />
          </div>
        )}
        <div className="pt-3">
          <h2>About {event.name}</h2>
          <Markdown content={event.long_description}/>
        </div>
        <BookEvent {...this.props} parent_uri={this.uri} event={event}/>
      </div>
    )
  }
}

export default PromptUpdate(Event)
