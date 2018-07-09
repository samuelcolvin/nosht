import React from 'react'
import {Link} from 'react-router-dom'
import FontAwesomeIcon from '@fortawesome/react-fontawesome'
import {Row, Col, Button} from 'reactstrap'
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
    let event
    const params = this.props.match.params
    this.props.setRootState({active_page: params.category})
    try {
      const data = await this.props.requests.get(`events/${params.category}/${params.event}/`)
      event = data.event
    } catch (error) {
      if (error.status === 404) {
        this.setState({event: 404})
      } else {
        this.props.setRootState({error})
      }
      return
    }
    this.props.setRootState({
      page_title: event.name,
      background: event.image,
      extra_menu: [{name: 'Book Now', to: this.uri + 'book/'}],
    })
    this.setState({event})
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
            <Button color="primary" size="lg" className="hover-raise" tag={Link} to={this.uri + 'book/'}>
              Book Now
            </Button>
          </Col>
        </Row>

        <div className="text-muted mb-1">
          <span>
            <FontAwesomeIcon icon={['far', 'clock']} className="mr-1" />
            <When event={event} />
          </span>
          <span className="ml-4">
            <FontAwesomeIcon icon={'user'} className="mr-1" />
            hosted by {event.host_name}
          </span>

          <span className="ml-4">
            <FontAwesomeIcon icon={['fas', 'map-marker']} className="mr-1" />
            at {event.location.name}
          </span>
        </div>

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
