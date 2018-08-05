
import React from 'react'
import {Table} from 'reactstrap'
import {format_date} from '../utils'
import {MoneyFree} from '../general/Money'

export default ({tickets}) => {
  if (!tickets || !tickets.length) {
    return (
      <div>
        <h4>Tickets</h4>
        <small>No Tickets bought.</small>
      </div>
    )
  }
  return (
    <div className="mb-3">
      <h4>Tickets</h4>
      <Table striped>
        <thead>
          <tr>
            <th>Event</th>
            <th>Price</th>
            <th>Event Date</th>
            <th>Buyer</th>
            <th>Guest</th>
            <th>Extra</th>
          </tr>
        </thead>
        <tbody>
          {tickets.map((t, i) => (
            <tr key={i}>
              <td>{t.event_name}</td>
              <td><MoneyFree>{t.price}</MoneyFree></td>
              <td>{format_date(t.event_start)}</td>
              <td>{t.buyer_name}</td>
              <td>{t.guest_name}</td>
              <td className="text-right">
                <small>{t.extra && t.extra.extra_info}</small>
              </td>
            </tr>
          ))}
        </tbody>
      </Table>
    </div>
  )
}
