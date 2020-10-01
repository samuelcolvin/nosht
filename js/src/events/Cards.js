import React from 'react'
import {Link} from 'react-router-dom'
import {Badge, Card, CardImg, CardTitle, CardSubtitle, CardBody, Row, Col} from 'reactstrap'
import {FontAwesomeIcon} from '@fortawesome/react-fontawesome'
import {chunk_array, image_thumb} from '../utils'
import Markdown from '../general/Markdown'
import When from '../general/When'


const Event = ({event}) => (
  <Col md="4" className="box-container">
    <Link to={`/${event.cat_slug}/${event.slug}/`}>
      <Card>
        <CardImg top width="100%" src={image_thumb(event.image)} alt={event.name}/>
        <CardBody>
          {event.secondary_image && (
            <img src={image_thumb(event.secondary_image, 'main')} alt={event.name} className="img-thumbnail"/>
          )}
          <CardTitle tag="h3">
            {event.name}
            {event.sold_out && (<span className="pl-2 h5"><Badge color="danger">Sold Out</Badge></span>)}
          </CardTitle>
          <CardSubtitle className="mb-1 text-muted">
            <FontAwesomeIcon icon={['far', 'clock']} className="mr-1"/>
            <When event={event}/>
          </CardSubtitle>
          <div className="card-text pb-2">
            <Markdown content={event.short_description}/>
          </div>

          <small>
            {event.allow_tickets && !event.allow_donations && 'Event'}
            {!event.allow_tickets && event.allow_donations && 'Fundraiser'}
            {event.allow_tickets && event.allow_donations && 'Event & Fundraiser'}
          </small>

          <small className="text-muted">
            <FontAwesomeIcon icon={['fas', 'map-marker']} className="mr-1"/>
            {event.location_name}
          </small>
        </CardBody>
      </Card>
    </Link>
  </Col>
)

export default ({events}) => (
  chunk_array(events, 3).map((chunk, i) => (
    <Row key={i}>
      {chunk.map((event, j) => <Event event={event} key={j}/>)}
    </Row>
  ))
)
