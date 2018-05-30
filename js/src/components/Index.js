import React, { Component } from 'react'
import { Link } from 'react-router-dom'
import { Card, CardImg, CardTitle, CardText, CardSubtitle, CardBody, Row, Col } from 'reactstrap'

const Event = ({event}) => {
  return (
    <Col sm="4">
      <Link className="index-card" to={`/${event.slug}/`}>
        <Card>
          <CardImg top width="100%" src={event.image + '/thumb.jpg'} alt={event.name} />
          <CardBody>
            <CardTitle>{event.name}</CardTitle>
            <CardSubtitle>Card subtitle</CardSubtitle>
            <CardText>
              This is a wider card with supporting text below as a natural lead-in to
              additional content. This content is a little bit longer.
            </CardText>

            <small className="text-muted">
              Someone famous in <cite title="Source Title">Source Title</cite>
            </small>
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
        <Row>
          {events.map((event, i) => <Event event={event} key={i}/>)}
          {events.map((event, i) => <Event event={event} key={i}/>)}
          {events.map((event, i) => <Event event={event} key={i}/>)}
          {events.map((event, i) => <Event event={event} key={i}/>)}
          {events.map((event, i) => <Event event={event} key={i}/>)}
        </Row>
        <pre className="mb-0 mt-1">
          <code>
            events: {JSON.stringify({events, categories}, null, 2)}
          </code>
        </pre>
      </div>
    )
  }
}
