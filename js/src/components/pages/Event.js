import React, { Component } from 'react'
import FontAwesomeIcon from '@fortawesome/react-fontawesome'
import { Row, Col, Button } from 'reactstrap'
import { load_script } from '../../utils'
import { Loading, OnUpdate, Markdown } from '../Utils'
import { When } from '../Events'

class Map extends Component {
  constructor (props) {
    super(props)
    this.update_map = this.update_map.bind(this)
    this.loaded = false
  }

  async componentDidMount () {
    await load_script('https://maps.googleapis.com/maps/api/js?key=' + process.env.REACT_APP_GOOGLE_MAPS_KEY)
    this.update_map()
  }

  componentDidUpdate () {
    this.update_map()
  }

  update_map () {
    const el = document.getElementById('event-map')
    if (window.google && el && !this.loaded) {
      this.loaded = true
      const map = new window.google.maps.Map(el, {
        center: this.props.location,
        zoom: 14,
        fullscreenControl: false,
      })
      new window.google.maps.Marker({
        position: this.props.location,
        map: map,
        title: this.props.location.name,
      })
    }
  }

  render () {
    return this.props.location.lat && this.props.location.lng && <div id="event-map" className="mt-2"/>
  }
}


export default class Event extends OnUpdate {
  constructor (props) {
    super(props)
    this.state = {
      event: null,
    }
  }

  async setup () {
    let event
    const params = this.props.match.params
    try {
      const data = await this.requests.get(`event/${params.category}/${params.event}/`)
      event = data.event
    } catch (error) {
      this.props.setRootState({ error })
      return
    }
    this.setState({ event })
    this.props.setRootState({
      page_title: event.name,
      background: event.image,
      extra_menu: [{name: 'Book Now', to: '/'}],
      active_page: params.category,
    })
  }

  render () {
    const event = this.state.event
    if (!event) {
      return <Loading/>
    }
    return (
      <div className="card-grid">
        <Row>
          <Col>
            <h1>{event.name}</h1>
            <p className="lead">
              {event.short_description}
            </p>
          </Col>
          <Col md="3" className="text-right">
            <Button color="primary" size="lg" className="hover-raise">Book Now</Button>
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

        <Map location={event.location}/>

        {event.category_content && (
          <div className="pt-3">
            <Markdown content={event.category_content} />
          </div>
        )}
        <div className="pt-3">
          <h2>About {event.name}</h2>
          <Markdown content={event.long_description}/>
        </div>
      </div>
    )
  }
}
