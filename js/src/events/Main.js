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
import DonateToEvent from './Donate'
import WaitingList from './WaitingList'
import Thanks from '../donations/Thanks'
import YoutubePlayer from '../general/YoutubePlayer'


const DonateButton = ({event, uri}) => {
  if (event.allow_donations) {
    return event.external_donation_url ? (
      <a href={event.external_donation_url}
         className="hover-raise ml-2 btn btn-lg btn-success"
         target="_blank" rel="noopener noreferrer">
        Donate Now
      </a>
    ) : (
      <Button color="success" size="lg" className="hover-raise ml-2" tag={Link} to={uri + 'donate/'}>
        Donate
      </Button>
    )
  } else {
    return null
  }
}

const BookButton = ({event, existing_tickets, on_waiting_list, uri}) => {
  if (!event.allow_tickets) {
    return null
  } else if (event.external_ticket_url) {
    const link_classes = (
      `hover-raise ml-2 btn btn-lg btn-${event.tickets_available !== null ? 'danger': 'primary'}` +
      (event.tickets_available === 0 ? ' disabled' : '')
    )
    return <a className={link_classes} href={event.external_ticket_url}>Buy Now</a>
  } else if (event.tickets_available === null) {
    return (
      <Button color={existing_tickets ? 'secondary' : 'primary'} size="lg" className="hover-raise ml-2"
              tag={Link} to={uri + 'book/'}>
        {existing_tickets ? 'Book more tickets' : 'Buy Now'}
      </Button>
    )
  } else if (event.tickets_available === 0) {
    if (on_waiting_list || existing_tickets) {
      return null
    }
    return (
      <Button color={existing_tickets ? 'secondary' : 'primary'} size="lg" className="hover-raise ml-2"
              tag={Link} to={uri + 'waiting-list/'}>
        Join Waiting List
      </Button>
    )
  } else {
    return (
      <Button color={existing_tickets ? 'secondary' : 'danger'} size="lg" className="hover-raise ml-2"
              tag={Link} to={uri + 'book/'}>
        {existing_tickets ? 'Book more tickets' : 'Buy Now'}
      </Button>
    )
  }
}

const EventDetails = WithContext(({ctx, event, uri, ticket_types, existing_tickets, on_waiting_list}) => (
  <div>
    <Row>
      <Col>
        <h1>{event.name}</h1>
        <div className="lead pb-2">
          <Markdown content={event.short_description}/>
        </div>
      </Col>
      <Col md="5" className="text-right">
        {ctx.user && (ctx.user.role === 'admin' || ctx.user.id === event.host_id) &&
          <Button color="link" tag={Link} to={`/dashboard/events/${event.id}/`}>
            Edit Event
          </Button>
        }
        <DonateButton event={event} uri={uri}/>
        <BookButton event={event} existing_tickets={existing_tickets} on_waiting_list={on_waiting_list} uri={uri}/>
        {event.allow_tickets && event.tickets_available !== null &&
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

      {event.allow_tickets ? (
        <Col md="auto">
          <FontAwesomeIcon icon="pound-sign" className="mx-1 text-success"/>
            {ticket_types.filter(tt => tt.mode === 'ticket').map(tt => tt.price).filter(unique).map((p, i) => (
              <span key={i}>
                {i > 0 && <span className="px-1">/</span>}
                <MoneyFree NoSymbol={i === 0}>{p}</MoneyFree>
              </span>
            ))}
        </Col>
      ) : null}

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

      {event.youtube_video_id && <YoutubePlayer vid={event.youtube_video_id} className='event-video'/>}

      {event.description_intro && <Markdown content={event.description_intro}/>}

      {event.description_image && (
        <div className="py-2 description-image">
          <img src={event.description_image} alt={event.name} className="img"/>
        </div>
      )}

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
    if (this.state.event && this.props.location.pathname.match(/\/(waiting-list|book|donate)\/$/)) {
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
        {this.props.location.pathname.match(/\/post-donation(\/(\d+))?\/$/) ?
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
        <DonateToEvent
          {...this.props}
          parent_uri={this.uri}
          event={this.state.event}
          params={this.props.match.params}
          set_complete={() => this.setState({booking_complete: true})}
        />
      </div>
    )
  }
}
export default PromptUpdate(Event)
