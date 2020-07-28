import React from 'react'
import {
  Button,
  ButtonGroup,
  FormText,
  ModalBody,
  ModalFooter,
  Row,
  Col,
  Table,
  Form as BootstrapForm
} from 'reactstrap'
import {FontAwesomeIcon} from '@fortawesome/react-fontawesome'
import requests from '../utils/requests'
import AsModal from '../general/Modal'
import Input from '../forms/Input'
import WithContext from '../utils/context'
import {Link} from 'react-router-dom'
import {MoneyFree, Money} from '../general/Money'
import {render} from '../general/Dashboard'

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
    help_text: 'Number of people associated with this type of ticket.',
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
          <Input field={name_field} value={ticket_type.name} onChange={v => update_ticket(index, 'name', v)}/>
        </Col>
        <Col md="4">
          <Input field={price_field} value={ticket_type.price} onChange={v => update_ticket(index, 'price', v)}/>
        </Col>
        <Col md="4">
          <Input field={slots_field}
                value={ticket_type.slots_used}
                onChange={v => update_ticket(index, 'slots_used', v)}/>
        </Col>
        <Col md="6">
          <Input field={active_field} value={ticket_type.active}
                 onChange={v => update_ticket(index, 'active', v)}
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

const SuggestedDonation = ({index, ticket_type, update_ticket, active_count}) => {
  const name_field = {
    name: `type_${index}_name`,
    title: 'Name',
    required: true,
    help_text: 'Name of the suggested donation shown to users.',
  }
  const amount_field = {
    name: `type_${index}_price`,
    title: 'Suggested Amount',
    help_text: 'Amount to suggest donating.',
    required: true,
    type: 'number', step: 0.01, min: 1, max: 1000,
  }
  const active_field = {
    name: `type_${index}_active`,
    title: 'Active',
    type: 'bool',
    help_text: 'Enable or disable this ticket type',
  }
  const msg = (ticket_type.active && active_count <= 1) ?
    'Cannot be deleted as at least one suggested donation must be active'
    :
    ticket_type.has_tickets ? 'Cannot be deleted as donations of this type exist' : null
  return (
    <div className="border-bottom-2 py-1 mb-1">
      <Row>
        <Col md="6">
          <Input field={name_field} value={ticket_type.name} onChange={v => update_ticket(index, 'name', v)}/>
        </Col>
        <Col md="6">
          <Input field={amount_field} value={ticket_type.price} onChange={v => update_ticket(index, 'price', v)}/>
        </Col>
        <Col md="6">
          <Input field={active_field} value={ticket_type.active}
                 onChange={v => update_ticket(index, 'active', v)}
                 disabled={ticket_type.active && active_count <= 1}/>
        </Col>
        <Col md="6" className="text-right mb-1">
          <Button color="danger"
                  size="sm"
                  onClick={() => update_ticket(index)}
                  disabled={(ticket_type.active && active_count <= 1) || ticket_type.has_tickets}>
            <FontAwesomeIcon icon="minus" className="mr-2"/>
            Delete Suggested Donation
          </Button>
          {msg && <FormText>{msg}</FormText>}
        </Col>
      </Row>
    </div>
  )
}

class TicketTypes_ extends React.Component {
  constructor (props) {
    super(props)
    this.mode = this.props.ticket_types[0].mode
    this.state = {
      ticket_types: this.props.ticket_types.filter(tt => !tt.custom_amount),
      savable: false,
    }
  }

  add_ticket_type () {
    const ticket_types = this.state.ticket_types.slice()
    ticket_types.push({slots_used: 1, mode: this.mode, active: true})
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
      this.props.ctx.setError(error)
      return
    }
    this.props.update()
    this.props.finished()
  }

  render () {
    const active_count = this.state.ticket_types.filter(t => t.active).length
    const FormComponent = this.mode === 'ticket' ? TicketType : SuggestedDonation
    return (
      <BootstrapForm onSubmit={(this.submit.bind(this))} className="highlight-required">
        <ModalBody key="1">
          <div>
            {this.state.ticket_types.map((t, i) => (
              <FormComponent key={i} index={i} ticket_type={t} active_count={active_count}
                             update_ticket={this.update_ticket.bind(this)}/>
            ))}
          </div>
          <div className="text-right mt-4">
            <Button color="success" size="sm" onClick={this.add_ticket_type.bind(this)}>
              <FontAwesomeIcon icon="plus" className="mr-2"/>
              Add {this.mode === 'ticket' ? 'Ticket Type' : 'Suggested Donation'}
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

export const TicketTypes = AsModal(TicketTypes_)

export const TicketTypeTable = WithContext(({ticket_types, uri, can_edit}) => (
  <div className="mb-5">
    <h4>
      Ticket Types
      {can_edit && (
        <Button tag={Link} to={uri + 'ticket-types/'} size="sm" className="ml-2">
          <FontAwesomeIcon icon="pencil-alt" className="mr-1"/>
          Edit
        </Button>
      )}
    </h4>
    <Table striped>
      <thead>
        <tr>
          <th>Name</th>
          <th>Price</th>
          <th>Group Size</th>
          <th>Active</th>
        </tr>
      </thead>
      <tbody>
        {ticket_types.map(tt => (
          <tr key={tt.id}>
            <td>{tt.name}</td>
            <td><MoneyFree>{tt.price}</MoneyFree></td>
            <td>{tt.slots_used}</td>
            <td>{render(tt.active)}</td>
          </tr>
        ))}
      </tbody>
    </Table>
  </div>
))

export const SuggestedDonationsTable = WithContext(({ticket_types, uri, can_edit}) => (
  <div className="mb-5">
    <h4>
      Suggested Donation Levels
      {can_edit && (
        <Button tag={Link} to={uri + 'suggested-donations/'} size="sm" className="ml-2">
          <FontAwesomeIcon icon="pencil-alt" className="mr-1"/>
          Edit
        </Button>
      )}
    </h4>
    <Table striped>
      <thead>
        <tr>
          <th>Name</th>
          <th>Suggested Donation</th>
          <th>Active</th>
        </tr>
      </thead>
      <tbody>
        {ticket_types.filter(tt => !tt.custom_amount).map(tt => (
          <tr key={tt.id}>
            <td>{tt.name}</td>
            <td><Money>{tt.price}</Money></td>
            <td>{render(tt.active)}</td>
          </tr>
        ))}
      </tbody>
    </Table>
  </div>
))
