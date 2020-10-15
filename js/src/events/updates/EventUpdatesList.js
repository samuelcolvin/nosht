import React from 'react'
import {Table} from 'reactstrap'

import {format_datetime, as_title} from '../../utils'
import {InfoModal} from '../../general/Modal'



export class EventUpdatesList extends React.Component {
  constructor (props) {
    super(props)
    this.state = {selected: null}
  }

  render () {
    if (!this.props.event_updates || !this.props.event_updates.length) {
      return (
        <div className="mb-5">
          <h4>Event Updates</h4>
          <small>No Updates sent for this event</small>
        </div>
      )
    }
    return (
      <div className="mb-5">
        <InfoModal isOpen={!!this.state.selected}
                   onClose={() => this.setState({selected: null})}
                   title="Event Update"
                   fields={{subject: {}, message: {}}}
                   object={this.state.selected}/>
        <h4>Event Updates</h4>
        <Table striped>
          <thead>
            <tr>
              <th>Time</th>
              <th>Subject</th>
            </tr>
          </thead>
          <tbody>
            {this.props.event_updates.map((a, i) => (
              <tr key={i} onClick={() => this.setState({selected: a})} className="cursor-pointer">
                <td>{format_datetime(a.ts)}</td>
                <td>{as_title(a.subject)}</td>
              </tr>
            ))}
          </tbody>
        </Table>
      </div>
    )
  }
}
export default EventUpdatesList
