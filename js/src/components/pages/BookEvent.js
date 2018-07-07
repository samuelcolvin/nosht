import React from 'react'
import {
  Button,
  ButtonGroup,
  ModalBody,
  ModalFooter,
  Row,
} from 'reactstrap'
import FontAwesomeIcon from '@fortawesome/react-fontawesome'
import AsModal from '../forms/Modal'
import {BookingLogin} from '../utils/Booking'

const User = ({user}) => (
  <div className="text-right">
    <small className="text-muted">
      Booking as:
    </small>
    &nbsp;
    <small className="text-dark">
      {user.name}
    </small>
  </div>
)

const TicketInfo = ({index, state}) => (
  <div>{index}</div>
)

const BookForm = ({user, state, change_ticket_count}) => (
  <div>
    <User user={user}/>
    <Row className="justify-content-center my-1">
      <Button color="danger" disabled={state.ticket_count === 1} onClick={() => change_ticket_count(-1)}>
        <FontAwesomeIcon icon="minus"/>
      </Button>
      <span className="my-1 mx-3 larger font-weight-bold">{state.ticket_count}</span>
      <Button color="success" disabled={state.ticket_count === 10} onClick={() => change_ticket_count(1)}>
        <FontAwesomeIcon icon="plus"/>
      </Button>
    </Row>
    <div className="text-muted text-center small">
      Select the number of tickets you would like to purchase.
    </div>
    <div>
      {[...Array(state.ticket_count).keys()].map(i => (
        <TicketInfo key={i} index={i} state={state}/>
      ))}
    </div>
  </div>
)

class BookWrapper extends React.Component {
  constructor (props) {
    super(props)
    this.state = {
      ticket_count: 1,
    }
  }

  change_ticket_count (change) {
    this.setState({ticket_count: this.state.ticket_count + change})
  }

  render () {
    const user = this.props.user
    return [
      <ModalBody key="1">
        {user ?
          <BookForm
              user={user}
              state={this.state}
              change_ticket_count={this.change_ticket_count.bind(this)}/>
          :
          <BookingLogin setRootState={this.props.setRootState} requests={this.props.requests}/>
        }
      </ModalBody>,
      <ModalFooter key="2">
        <ButtonGroup>
          <Button type="button" color="secondary" onClick={() => this.props.finished && this.props.finished()}>
            Cancel
          </Button>
          <Button type="submit" color="primary" disabled>
            Book
          </Button>
        </ButtonGroup>
      </ModalFooter>
    ]
  }
}
const ModalBookForm = AsModal(BookWrapper)

const BookEvent = props => (
  <ModalBookForm {...props}
                 title={`Book Tickets for ${props.event.name}`}
                 regex={/book\/$/}/>
)
export default BookEvent
