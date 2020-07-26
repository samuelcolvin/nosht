import React from 'react'
import {Form as BootstrapForm, ModalBody} from 'reactstrap'
import WithContext from '../utils/context'
import Input from '../forms/Input'
import {ModalFooter} from '../general/Modal'
import {MoneyFree, format_money} from '../general/Money'
import {User} from './BookingTickets'

const custom_donate_field = {
  name: 'donation_amount',
  placeholder: 'Custom Donation Amount',
  show_label: false,
  type: 'number',
  step: 0.01, min: 1, max: 1000
}


const DonationForm = props => {
  const state = props.state
  const setDonatingState = props.setDonatingState
  const currency = props.ctx.company.company.currency

  const custom_amount_tt = state.ticket_types.find(tt => tt.custom_amount)
  let custom_amount_id = custom_amount_tt && custom_amount_tt.id

  return (
    <BootstrapForm onSubmit={props.submit}>
      <ModalBody>
        <User {...props}/>
        <div className="py-2">
          <h3>
            Donation Amount
          </h3>
          <div className="text-muted small">
            Select how much you would like to donate.
          </div>
          <div className="px-4 pb-2">
            {state.ticket_types.filter(tt => !tt.custom_amount).map(tt => (
              <label key={tt.id} className="d-block">
                <input
                  className="mr-2"
                  type="radio"
                  checked={state.selected_ticket_type === tt.id}
                  onChange={() => setDonatingState({selected_ticket_type: tt.id, donation_amount: tt.amount})}
                />
                <b><MoneyFree>{tt.amount}</MoneyFree></b> &mdash; {tt.name}
              </label>
            ))}
            <label className="d-block">
              <input
                className="mr-2"
                type="radio"
                checked={state.selected_ticket_type === custom_amount_id}
                onChange={() => setDonatingState({selected_ticket_type: custom_amount_id, donation_amount: null})}
              />
              <b>Custom Amount</b>
            </label>
          </div>
          {state.selected_ticket_type === custom_amount_id ? (
            <Input value={state.donation_amount}
                   field={custom_donate_field}
                   onChange={v => setDonatingState({donation_amount: v})}/>
          ) : null}
        </div>

        {props.event.allow_marketing_message &&
          <Input value={state.allow_marketing}
                 field={{name: 'allow_marketing', title: props.event.allow_marketing_message, type: 'bool'}}
                 onChange={v => setDonatingState({allow_marketing: true})}/>
        }
      </ModalBody>

      <ModalFooter
        finished={props.finished}
        cancel_disabled={state.submitting_reservation}
        label={state.donation_amount ? `Donate ${format_money(currency, state.donation_amount)}` : 'Donate'}
        disabled={!state.donation_amount}
      />
    </BootstrapForm>
  )
}
export default WithContext(DonationForm)
