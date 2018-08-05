import React from 'react'
import {
  Button,
  ButtonGroup,
  FormText,
  ModalBody,
  ModalFooter,
  Row,
  Col,
  Form as BootstrapForm,
} from 'reactstrap'
import FontAwesomeIcon from '@fortawesome/react-fontawesome'
import requests from '../requests'
import AsModal from '../general/Modal'
import Input from '../forms/Input'

const TicketType = ({index, ticket_type, update_ticket, active_count}) => {
  const name_field = {
    name: `type_${index}_name`,
    title: 'Name',
    required: true,
    help_text: 'Name of the ticket type shown to users.',
  }
  const price_field = {
    name: `type_${index}_price`,
    title: 'Ticket Price',
    help_text: 'Leave blank if tickets of this type are free.',
    type: 'number', step: 0.01, min: 1, max: 1000,
  }
  const slots_field = {
    name: `type_${index}_slots_used`,
    title: 'Group Size',
    type: 'integer',
    required: true,
    help_text: 'Number of tickets associated with this type of ticket.',
  }
  const active_field = {
    name: `type_${index}_active`,
    title: 'Active',
    type: 'bool',
    help_text: 'Enable or disable this ticket type',
  }
  const msg = (ticket_type.active && active_count <= 1) ?
    'Cannot be deleted as at least one ticket type must be active'
    :
    ticket_type.has_tickets ? 'Cannot be deleted as tickets of this type exist' : null
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
        <Col md="6">
          <Input field={active_field} value={ticket_type.active}
                 set_value={v => update_ticket(index, 'active', v)}
                 disabled={ticket_type.active && active_count <= 1}/>
        </Col>
        <Col md="6" className="text-right mb-1">
          <Button color="danger"
                  size="sm"
                  onClick={() => update_ticket(index)}
                  disabled={(ticket_type.active && active_count <= 1) || ticket_type.has_tickets}>
            <FontAwesomeIcon icon="minus" className="mr-2"/>
            Delete Ticket Type
          </Button>
          {msg && <FormText>{msg}</FormText>}
        </Col>
      </Row>
    </div>
  )
}

class TicketTypes extends React.Component {
  constructor (props) {
    super(props)
    this.state = {
      ticket_types: this.props.ticket_types,
      savable: false,
    }
  }

  add_ticket_type () {
    const ticket_types = this.state.ticket_types.slice()
    ticket_types.push({slots_used: 1, active: true})
    this.setState({ticket_types, savable: true})
  }

  update_ticket (index, key, value) {
    const ticket_types = this.state.ticket_types.slice()
    if (!key && !value) {
      // means delete
      ticket_types.splice(index, 1)
    } else {
      ticket_types[index][key] = value
    }
    this.setState({ticket_types, savable: true})
  }

  async submit (e) {
    e.preventDefault()
    try {
      await requests.post(`events/${this.props.event.id}/ticket-types/update/`,
                                     {ticket_types: this.state.ticket_types})
    } catch (error) {
      this.props.setRootState({error})
      return
    }
    this.props.update()
    this.props.finished()
  }

  render () {
    const active_count = this.state.ticket_types.filter(t => t.active).length
    return (
      <BootstrapForm onSubmit={(this.submit.bind(this))} className="highlight-required">
        <ModalBody key="1">
          <div>
            {this.state.ticket_types.map((t, i) => (
              <TicketType key={i} index={i} ticket_type={t} active_count={active_count}
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
            <Button type="submit" color="primary" disabled={!this.state.savable}>
              {this.props.save || 'Save'}
            </Button>
          </ButtonGroup>
        </ModalFooter>
      </BootstrapForm>
    )
  }
}

export default AsModal(TicketTypes)
