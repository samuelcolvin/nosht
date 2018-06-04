import React from 'react'
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
    <Col md="4" className="box-container">
      <Link to={`/${event.cat_slug}/${event.slug}/`}>
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

const Events = ({events}) => (
  chunk_array(events, 3).map((chunk, i) => (
    <Row key={i}>
      {chunk.map((event, j) => <Event event={event} key={j}/>)}
    </Row>
  ))
)

export default Events
