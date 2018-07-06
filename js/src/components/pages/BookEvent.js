import React from 'react'
import {
  Button,
  ButtonGroup,
  ModalBody,
  ModalFooter,
} from 'reactstrap'
import AsModal from '../forms/Modal'
import {BookingLogin} from '../utils/Booking'

class BookForm extends React.Component {
  constructor (props) {
    super(props)
    this.state = {
      disabled: false,
      form_data: {},
      errors: {},
      form_error: null,
    }
    // this.submit = this.submit.bind(this)
    // this.set_form_data = this.set_form_data.bind(this)
  }

  render () {
    return [
      <ModalBody key="1">
        <BookingLogin/>
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
const ModalBookForm = AsModal(BookForm)

const BookEvent = props => (
  <ModalBookForm {...props}
                 title={`Book Tickets for ${props.event.name}`}
                 regex={/book\/$/}/>
)
export default BookEvent
