import React from 'react'
import {Link} from 'react-router-dom'
import {FontAwesomeIcon} from '@fortawesome/react-fontawesome'
import {Row, Col, Button, Alert} from 'reactstrap'
import requests from '../utils/requests'
import {image_thumb, unique} from '../utils'
import WithContext from '../utils/context'
import {Loading, NotFound} from '../general/Errors'
import PromptUpdate from '../general/PromptUpdate'
import Markdown from '../general/Markdown'
import Map from '../general/Map'
import When from '../general/When'
import {MoneyFree} from '../general/Money'
import BookEvent from './Book'
import WaitingList from './WaitingList'
import Thanks from '../donations/Thanks'


const link_classes = e => (
  `hover-raise btn btn-lg btn-${e.tickets_available !== null ? 'danger': 'primary'}` +
  (e.tickets_available === 0 ? ' disabled' : '')
)


const EventDetails = WithContext(({ctx, event, uri, ticket_types, existing_tickets, on_waiting_list}) => (
  <div>
    <Row>
      <Col>
        <h1>{event.name}</h1>
        <div className="lead pb-2">
          <Markdown content={event.short_description}/>
        </div>
      </Col>
      <Col md="4" className="text-right">
        {ctx.user && (ctx.user.role === 'admin' || ctx.user.id === event.host_id) &&
          <Button color="link" tag={Link} to={`/dashboard/events/${event.id}/`}>
            Edit Event
          </Button>
        }
        {event.external_ticket_url ? (
          <a className={link_classes(event)} href={event.external_ticket_url}>Book Now</a>
        ) : (
          event.tickets_available === null ? (
            <Button color={existing_tickets ? 'secondary' : 'primary'} size="lg" className="hover-raise"
                    tag={Link} to={uri + 'book/'}>
              {existing_tickets ? 'Book more tickets' : 'Book Now'}
            </Button>
          ) : (
            event.tickets_available === 0 ? (
              !on_waiting_list && !existing_tickets && (
                <Button color={existing_tickets ? 'secondary' : 'primary'} size="lg" className="hover-raise"
                        tag={Link} to={uri + 'waiting-list/'}>
                  Join Waiting List
                </Button>
              )
            ) : (
              <Button color={existing_tickets ? 'secondary' : 'danger'} size="lg" className="hover-raise"
                      tag={Link} to={uri + 'book/'}>
                {existing_tickets ? 'Book more tickets' : 'Book Now'}
              </Button>
            )
          )
        )
        }
        {event.tickets_available !== null &&
          <div className="mt-3">
            {event.tickets_available === 0 ?
              !existing_tickets && (
                on_waiting_list ? (
                  <span>Sold out, You're on the waiting list.</span>
                ) : (
                  <span><b>Sold Out!</b>Join the waiting list to get notified when more tickets become available.</span>
                )
              )
              :
              <span className="font-weight-bold">Only {event.tickets_available} Tickets Remaining</span>
            }
          </div>}
      </Col>
    </Row>

    {!!existing_tickets && (
      <Alert color="success" className="mt-1 font-weight-bold">
        You've booked {existing_tickets === 1 ? 'a ticket' : `${existing_tickets} tickets`} for this event.
      </Alert>
    )}
    <Row className="text-muted mb-1 h5">
      <Col md="auto">
        <FontAwesomeIcon icon={['far', 'clock']} className="mx-1 text-success"/>
        <When event={event}/>
      </Col>

      <Col md="auto">
        <FontAwesomeIcon icon="pound-sign" className="mx-1 text-success"/>
          {ticket_types.map(tt => tt.price).filter(unique).map((p, i) => (
            <span key={i}>
              {i > 0 && <span className="px-1">/</span>}
              <MoneyFree NoSymbol={i === 0}>{p}</MoneyFree>
            </span>
          ))}
      </Col>

      <Col md="auto">
        <FontAwesomeIcon icon={'user'} className="mx-1 text-success"/>
        hosted by {event.host_name}
      </Col>

      {event.location.name &&
        <Col md="auto">
          <FontAwesomeIcon icon={['fas', 'map-marker']} className="mx-1 text-success"/>
          at {event.location.name}
        </Col>
      }
    </Row>

    <Map geolocation={event.location}/>

    {event.category_content && (
      <div className="pt-3">
        <Markdown content={event.category_content}/>
      </div>
    )}
    <div className="pt-3 event-about">
      {event.secondary_image && (
        <div className="float-left pr-2">
          <img src={image_thumb(event.secondary_image, 'main')} alt={event.name} className="img-thumbnail"/>
        </div>
      )}
      <h2>About</h2>
      <Markdown content={event.long_description}/>
    </div>
  </div>
))

class Event extends React.Component {
  constructor (props) {
    super(props)
    this.state = {
      event: null,
      booking_complete: false,
    }
    const params = this.props.match.params
    if (params.sig) {
      this.uri = `/pvt/${params.category}/${params.event}/${params.sig}/`
    } else {
      this.uri = `/${params.category}/${params.event}/`
    }
    this.props.register(this.get_data)
  }

  get_data = async () => {
    if (this.state.event && this.props.location.pathname.match(/\/(waiting-list|book)\/$/)) {
      // don't re-get the data when opening the booking or waiting-list forms
      return
    }
    const p = this.props.match.params
    this.props.ctx.setRootState({active_page: p.category})
    let data
    try {
      data = await requests.get(`events/${p.category}/${p.event}/${p.sig ? p.sig + '/': ''}`)
    } catch (error) {
      if (error.status === 404) {
        this.setState({event: 404})
      } else {
        this.props.ctx.setError(error)
      }
      return
    }
    this.props.ctx.setRootState({
      page_title: data.event.name,
      background: data.event.image,
    })
    this.setState(data)
  }

  render () {
    if (!this.state.event) {
      return <Loading/>
    } else if (this.state.event === 404) {
      return <NotFound location={this.props.location}/>
    }
    return (
      <div>
        {this.props.location.pathname.match(/\/donate(\/(\d+))?\/$/) ?
            <Thanks uri={this.uri} {...this.state}/>
            :
            <EventDetails uri={this.uri} {...this.state}/>
        }
        <BookEvent
          {...this.props}
          parent_uri={this.uri}
          event={this.state.event}
          params={this.props.match.params}
          set_complete={() => this.setState({booking_complete: true})}
        />
        <WaitingList
          {...this.props}
          parent_uri={this.uri}
          event={this.state.event}
          params={this.props.match.params}
        />
      </div>
    )
  }
}
export default PromptUpdate(Event)
