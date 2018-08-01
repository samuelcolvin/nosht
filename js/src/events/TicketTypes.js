import React from 'react'
import {
  Button,
  ButtonGroup,
  ModalBody,
  ModalFooter,
  Row,
  Col,
  Form as BootstrapForm,
} from 'reactstrap'
import FontAwesomeIcon from '@fortawesome/react-fontawesome'
import AsModal from '../general/Modal'
import Input from '../forms/Input'

const TicketType = ({index, ticket_type, update_ticket, type_count}) => {
  const name_field = {
    name: `type_${index}_name`,
    title: 'Name',
    required: true,
    help_text: 'Name of the ticket type shown to users.',
  }
  const price_field = {
    name: `type_${index}_price`,
    title: 'Ticket Price',
    required: true,
    help_text: 'Price guests are charged for tickets of this type.',
    type: 'number', step: 0.01, min: 1, max: 1000,
  }
  const slots_field = {
    name: `type_${index}_slots_used`,
    title: 'Group Size',
    type: 'integer',
    default: 1,
    required: true,
    help_text: 'Number of tickets associated with this type of ticket.',
  }
  return (
    <div className="border-bottom-2 py-1 mb-1">
      <Row>
        <Col md="4">
          <Input field={name_field} value={ticket_type.name} set_value={v => update_ticket(index, 'name', v)}/>
        </Col>
        <Col md="4">
          <Input field={price_field} value={ticket_type.price} set_value={v => update_ticket(index, 'price', v)}/>
        </Col>
        <Col md="4">
          <Input field={slots_field}
                value={ticket_type.slots_used}
                set_value={v => update_ticket(index, 'slots_used', v)}/>
        </Col>
      </Row>
      <div className="text-right mb-1">
        <Button color="danger" size="sm" onClick={() => update_ticket(index)} disabled={type_count <= 1}>
          <FontAwesomeIcon icon="minus" className="mr-2"/>
          Delete Ticket Type
        </Button>
      </div>
    </div>
  )
}

class TicketTypes extends React.Component {
  constructor (props) {
    super(props)
    this.state = {
      types: [
        {
          name: 'Standard',
          price: 123,
          slots_used: 0,
        }
      ]
    }
  }

  add_ticket_type () {
    const types = this.state.types.slice()
    types.push({})
    this.setState({types})
  }

  update_ticket (index, key, value) {
    const types = this.state.types.slice()
    if (!key && !value) {
      // means delete
      types.splice(index, 1)
    } else {
      types[index][key] = value
    }
    this.setState({types})
  }

  async submit (e) {
    e.preventDefault()
  }

  render () {
    return (
      <BootstrapForm onSubmit={(this.submit.bind(this))} className="highlight-required">
        <ModalBody key="1">
          <div>
            {this.state.types.map((t, i) => (
              <TicketType key={i} index={i} ticket_type={t} type_count={this.state.types.length}
                          update_ticket={this.update_ticket.bind(this)}/>
            ))}
          </div>
          <div className="text-right mt-4">
            <Button color="success" size="sm" onClick={this.add_ticket_type.bind(this)}>
              <FontAwesomeIcon icon="plus" className="mr-2"/>
              Add Ticket Type
            </Button>
          </div>
        </ModalBody>
        <ModalFooter key="2">
          <ButtonGroup>
            <Button type="button" color="secondary" onClick={() => this.props.finished()}>
              {this.props.close || 'Close'}
            </Button>
            <Button type="submit" color="primary">
              {this.props.save || 'Save'}
            </Button>
          </ButtonGroup>
        </ModalFooter>
      </BootstrapForm>
    )
  }
}

export default AsModal(TicketTypes)
