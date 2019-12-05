import React from 'react'
import WithContext from './utils/context'

export const UnsubscribeValid = WithContext(({ctx}) => (
  <div>
    <h1>Thank you for Unsubscribing</h1>
    <p>You will not receive any more emails from {ctx.company.company.name}.</p>
  </div>
))

export const UnsubscribeInvalid = () => (
  <div>
    <h1>Invalid Unsubscribe link</h1>
    <p>The link you followed was invalid.</p>
  </div>
)

export const WaitingListRemoved = () => (
  <div>
    <h1>You've been remove from the waiting</h1>
    <p>You will not receive any more waiting list emails about this event.</p>
    <p>You may re-add yourself to the waiting for this or other events at any time.</p>
  </div>
)
