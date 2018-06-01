import React, { Component } from 'react'
import { Link } from 'react-router-dom'
import { Card, CardImg, CardTitle, CardText, CardSubtitle, CardBody, Row, Col } from 'reactstrap'
import FontAwesomeIcon from '@fortawesome/react-fontawesome'
import {chunk_array, format_date, format_datetime, format_duration} from '../utils'


export const When = ({event}) => {
  if (event.duration) {
    return <span>{format_datetime(event.start_ts)} &bull; {format_duration(event.duration)}</span>
  } else {
    return <span>{format_date(event.start_ts)} &bull; All day</span>
  }
}

const Event = ({event}) => {
  return (
    <Col md="4">
      <Link className="index-card" to={`/${event.slug}/`}>
        <Card>
          <CardImg top width="100%" src={event.image + '/thumb.jpg'} alt={event.name} />
          <CardBody>
            <CardTitle>{event.name}</CardTitle>
            <CardSubtitle className="mb-1 text-muted">
              <FontAwesomeIcon icon={['far', 'clock']} className="mr-1" />
              <When event={event}/>
            </CardSubtitle>
            <CardText>
              {event.short_description}
            </CardText>

            <small className="text-muted">
              <FontAwesomeIcon icon={['fas', 'map-marker']} className="mr-1" />
              {event.location}
            </small>
          </CardBody>
        </Card>
      </Link>
    </Col>
  )
}

const Category = ({cat}) => {
  return (
    <Col md="4">
      <Link className="index-card" to={`/${cat.slug}/`}>
        <Card>
          <CardImg top width="100%" src={cat.image + '/thumb.jpg'} alt={cat.name} />
          <CardBody>
            <CardTitle>{cat.name}</CardTitle>
          </CardBody>
        </Card>
      </Link>
    </Col>
  )
}

export default class Index extends Component {
  render () {
    const categories = this.props.company_data ? this.props.company_data.categories : []
    const events = this.props.company_data ? this.props.company_data.highlight_events : []
    return (
      <div>
        <div>
          <h1>Highlighted Events</h1>
          {chunk_array(events, 3).map((chunk, i) => (
            <Row key={i}>
              {chunk.map((event, j) => <Event event={event} key={j}/>)}
            </Row>
          ))}
        </div>
        <div className="mt-4">
          <h1>Categories</h1>
          {chunk_array(categories, 3).map((chunk, i) => (
            <Row key={i}>
              {chunk.map((cat, j) => <Category cat={cat} key={j}/>)}
            </Row>
          ))}
        </div>
        {/*<pre>*/}
          {/*<code>*/}
            {/*events: {JSON.stringify({events, categories}, null, 2)}*/}
          {/*</code>*/}
        {/*</pre>*/}
      </div>
    )
  }
}
