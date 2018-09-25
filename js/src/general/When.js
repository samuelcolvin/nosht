import React from 'react'
import {format_event_start, format_event_duration} from '../utils'

export default ({event}) => (
  <span>
    {format_event_start(event.start_ts, event.duration)}
    {event.tz && <span>&nbsp;{event.tz}</span>}
    &nbsp;&bull; {format_event_duration(event.duration)}
  </span>
)
